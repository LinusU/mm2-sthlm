"""Source small-water inventory and native wadeable basins; no engine physics."""

import json
import math
import struct
from pathlib import Path
from statistics import median

from PIL import Image
from shapely.geometry import Point, Polygon, mapping, shape
from shapely.ops import unary_union

import sthlm

OVERRIDES = Path(__file__).resolve().parents[1] / "config/overrides/shallow-water.json"


def classify(tags, area):
    """Retain navigable/coastal water; size alone never converts dock/canal water."""
    if tags.get("leisure") == "marina" or tags.get("disused:dock"):
        return False
    kind = tags.get("water", "")
    if kind in {"canal", "river", "stream", "lock", "reservoir", "sea"}:
        return False
    if tags.get("amenity") == "fountain":
        return area <= 5000
    if kind in {"pond", "basin", "reflecting_pool"}:
        return area <= 5000
    # Several tiny Skansen ponds have OSM water=lake. Authored shallow gameplay
    # depth is deliberately not a claim about their surveyed depth.
    return tags.get("natural") == "water" and area <= 5000


def normalized(source, cfg, boundary, coast=None):
    nodes = {e["id"]: e for e in source["elements"] if e["type"] == "node"}
    ways = {e["id"]: e for e in source["elements"] if e["type"] == "way"}
    overrides = json.loads(OVERRIDES.read_text())
    retained = set(overrides.get("retain_deep_source_ids", []))
    out = []
    claimed = set()
    ordered = sorted(source["elements"], key=lambda e: e["type"] != "relation")
    for e in ordered:
        tags = e.get("tags", {})
        ids = e.get("nodes", [])
        if not (tags.get("natural") == "water" or tags.get("amenity") == "fountain"):
            continue
        if e["type"] == "relation":
            if (
                tags.get("water") not in {"pond", "basin", "reflecting_pool"}
                and tags.get("amenity") != "fountain"
            ):
                continue
            poly = sthlm.assemble_relation(e, ways, nodes, cfg["origin"], boundary)
        elif e["type"] == "way":
            if (
                e["id"] in claimed
                or len(ids) < 4
                or ids[0] != ids[-1]
                or any(n not in nodes for n in ids)
            ):
                continue
            poly = Polygon(
                [
                    sthlm.project(nodes[n]["lon"], nodes[n]["lat"], cfg["origin"])
                    for n in ids
                ]
            )
        else:
            continue
        if (
            not poly.is_valid
            or not boundary.covers(poly)
            or not classify(tags, poly.area)
        ):
            continue
        if f"{e['type']}/{e['id']}" in retained or (
            coast is not None and poly.intersection(coast).area > poly.area * 0.1
        ):
            continue
        out.append(
            {
                "id": f"{e['type']}/{e['id']}",
                "name": tags.get("name", ""),
                "tags": tags,
                "geometry": mapping(poly),
                "depth_m": 0.2,
                "level_rule": "median local bank ground minus 0.04m; gameplay estimate, not surveyed",
            }
        )
        if e["type"] == "relation":
            claimed.update(m["ref"] for m in e["members"] if m["type"] == "way")
    for item in overrides["authored_basins"]:
        poly = Polygon(
            [sthlm.project(*p, cfg["origin"]) for p in item["outline_wgs84"]]
        )
        if boundary.covers(poly):
            out.append(
                {
                    **item,
                    "geometry": mapping(poly),
                    "tags": {"amenity": "fountain"},
                    "level_rule": "median local bank ground minus 0.04m; authored approximate outline/depth, not surveyed",
                }
            )
    return sorted(out, key=lambda item: item["id"])


def footprint(city):
    return unary_union([shape(p["geometry"]) for p in city.get("shallow_water", [])])


def prepare(city, terrain, ground_height=None):
    """Use final local ground field when provided; return native mesh records."""
    sample = ground_height or terrain.height
    # Only ground road collision may claim a surface basin. Upper decks and
    # underground lanes retain their own independent layers.
    roads = shape(city.get("ground_road_surface", city["road_surface"]))
    bounds = shape(city["bounds"])
    records = []
    for item in city.get("shallow_water", []):
        poly = shape(item["geometry"]).difference(roads)
        if poly.is_empty:
            continue
        bank = shape(item["geometry"]).boundary
        levels = [
            sample(
                bank.interpolate(i / 16, normalized=True).x,
                bank.interpolate(i / 16, normalized=True).y,
            )
            for i in range(16)
        ]
        level = median(levels) - 0.04
        depth = item.get("depth_m", 0.2)
        if not 0.1 <= depth <= 0.3 or not math.isfinite(level):
            raise ValueError("invalid authored shallow-water level/depth")
        outer = poly.buffer(4).intersection(bounds).difference(roads)
        record = {
            **item,
            "geometry": mapping(poly),
            "bank_geometry": mapping(outer.difference(poly)),
            "water_level_m": level,
            "floor_level_m": level - depth,
            "depth_m": depth,
        }
        records.append(record)
    all_water = unary_union([shape(r["geometry"]) for r in records])
    for record in records:
        record["bank_geometry"] = mapping(
            shape(record["bank_geometry"]).difference(all_water)
        )
    city["shallow_water"] = records
    return records


def partition_geometry(records):
    return unary_union(
        [shape(r["geometry"]).union(shape(r["bank_geometry"])) for r in records]
    )


def write_mesh(writer, records, ground_height):
    """Partitioned sloped banks and submerged floor. Never mark deadly rooms."""
    for r in records:
        poly = shape(r["geometry"])
        level, depth = r["water_level_m"], r["depth_m"]

        ramp_width = min(
            1.5, max(0.05, poly.representative_point().distance(poly.boundary) / 2)
        )

        def floor(x, n, poly=poly, level=level, depth=depth, ramp_width=ramp_width):
            return level - depth * min(
                1.0, poly.boundary.distance(Point(x, n)) / ramp_width
            )

        inner = poly.buffer(-ramp_width)
        writer.surface(inner, level - depth, "sthlm_pond_floor")
        writer.surface(poly.difference(inner), floor, "sthlm_pond_floor")
    bank_area = unary_union([shape(r["bank_geometry"]) for r in records])
    basins = [(shape(r["geometry"]), r["water_level_m"]) for r in records]

    def bank(x, n):
        point = Point(x, n)
        nearby = [
            (poly.distance(point), level)
            for poly, level in basins
            if poly.distance(point) < 4.000001
        ]
        if not nearby:
            return ground_height(x, n)
        distance, nearest_level = min(nearby)
        if distance < 1e-7:
            return nearest_level
        if distance >= 4:
            return ground_height(x, n)
        # One shared field avoids overlapping collision collars. Inverse-square
        # weights approach each basin's exact rim level continuously, even
        # where neighboring ponds have different terrain-relative water levels.
        weights = [((1 - d / 4) ** 2 / d**2, level) for d, level in nearby if d < 4]
        level = sum(weight * level for weight, level in weights) / sum(
            weight for weight, _ in weights
        )
        t = min(1.0, distance / 4)
        t = t * t * (3 - 2 * t)
        return level * (1 - t) + ground_height(x, n) * t

    writer.surface(bank_area, bank, "paving")


def write(out, city):
    """Append render-only water triangles to the existing native decal pathset."""
    out = Path(out)
    Image.new("RGB", (16, 16), (71, 94, 92)).save(out / "texture/sthlm_pond_floor.png")
    image = Image.new("RGBA", (64, 64))
    for n in range(64):
        for x in range(64):
            ripple = 10 if (n + int(3 * math.sin(x * math.pi / 16))) % 16 < 2 else 0
            image.putpixel((x, n), (72 + ripple, 132 + ripple, 143 + ripple, 175))
    image.save(out / "texture/sthlm_pond_water.png")
    path = out / "city/stockholm/decals.pathset"
    data = path.read_bytes() if path.exists() else b"PTH1" + struct.pack("<II", 0, 0)
    if data[:4] != b"PTH1":
        raise ValueError("cannot append water to invalid PTH1 pathset")
    count = struct.unpack_from("<I", data, 4)[0]
    extra = bytearray()
    triangles = 0
    for r in city.get("shallow_water", []):
        for a, b, c in sthlm.triangulate(shape(r["geometry"])):
            extra.extend(
                b"sthlm_pond_water".ljust(32, b"\0") + struct.pack("<II", 4, 0)
            )
            # Second edge converges: one real triangle plus a degenerate one.
            # Engine's supported PTH strip stays render-only; lift is +0.02m.
            for x, n in (a, b, c, c):
                extra.extend(struct.pack("<I3f", 0, x, r["water_level_m"] - 0.02, -n))
            extra.extend(bytes([2, 20, 0, 0]))
            triangles += 1
    path.write_bytes(data[:4] + struct.pack("<I", count + triangles) + data[8:] + extra)
    mtl = out / "city/materials.mtl"
    csv = out / "city/materials.csv"
    # Preserve other authored tables. These original blocks use native SDL
    # semantics; 0.119 is the shared retail wadeable class, below recovery cutoff.
    text = mtl.read_text() if mtl.exists() else ""
    if "mtl sthlm_shallow_water {" not in text:
        mtl.write_text(
            text
            + "\nmtl sthlm_shallow_water {\n friction: 0.65\n drag: 0.119\n elasticity: 0\n}\n"
        )
    text = csv.read_text() if csv.exists() else "tex,phys\n"
    if "sthlm_pond_floor," not in text:
        csv.write_text(text + "sthlm_pond_floor,sthlm_shallow_water\n")
    sthlm.write_json(
        out / "shallow-water.json",
        {
            "schema": 1,
            "features": city.get("shallow_water", []),
            "water_decal_triangles": triangles,
            "native_floor_drag": 0.119,
            "deadly_water_refs": False,
        },
    )

"""Source-bounded Old Town stone coverage and original seamless granite artwork."""

import json
import math
from functools import lru_cache
from pathlib import Path

from PIL import Image
from shapely import prepare
from shapely.geometry import LineString, Point, Polygon, box, mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
MATERIAL = "sthlm_oldtown_setts"


def project(lon, lat, origin):
    radius = 6378137.0
    return (
        radius * math.radians(lon - origin[0]) * math.cos(math.radians(origin[1])),
        radius * math.radians(lat - origin[1]),
    )


def polygons(geometry):
    if geometry.geom_type == "Polygon":
        return [geometry]
    return [p for g in getattr(geometry, "geoms", []) for p in polygons(g)]


@lru_cache(maxsize=1)
def profile():
    return json.loads((ROOT / "config/overrides/oldtown-surfaces.json").read_text())


def island_mask(land, cfg):
    selected, missing = [], []
    candidates = polygons(land)
    for name, lonlat in profile()["island_references_wgs84"].items():
        point = Point(project(*lonlat, cfg["origin"]))
        match = [p for p in candidates if p.covers(point) and p.area < 1000000]
        if match:
            selected.extend(match)
        else:
            missing.append(name)
    return unary_union(selected), missing


def source_land(source, cfg):
    """Full offline source land before the coordinator applies its playable mask."""
    nodes = {e["id"]: e for e in source["elements"] if e["type"] == "node"}
    ways = {e["id"]: e for e in source["elements"] if e["type"] == "way"}
    from expanded import coast_water
    from sthlm import assemble_relation

    envelope = box(
        *project(*cfg["bounds"][:2], cfg["origin"]),
        *project(*cfg["bounds"][2:], cfg["origin"]),
    )
    water = [coast_water(source, cfg)]
    for element in source["elements"]:
        if element.get("tags", {}).get("natural") != "water":
            continue
        if element["type"] == "relation":
            water.append(
                assemble_relation(element, ways, nodes, cfg["origin"], envelope)
            )
        elif element["type"] == "way":
            ids = element.get("nodes", [])
            if len(ids) >= 4 and ids[0] == ids[-1] and all(i in nodes for i in ids):
                poly = Polygon(
                    [
                        project(nodes[i]["lon"], nodes[i]["lat"], cfg["origin"])
                        for i in ids
                    ]
                )
                if poly.is_valid:
                    water.append(poly)
    return envelope.difference(unary_union(water))


def eligible_pedestrian_ways(source, cfg, *, land=None):
    """Explicit source IDs for driveable historic alleys, never general footpaths.

    The coordinator can pass its already computed land to avoid rebuilding it.
    Default width is 3.5 m; surveyed/estimated widths below 2.5 m are excluded.
    Real steps, area plazas, bridges, tunnels, and incomplete ways stay excluded.
    """
    nodes = {e["id"]: e for e in source["elements"] if e["type"] == "node"}
    ways = {e["id"]: e for e in source["elements"] if e["type"] == "way"}
    if land is None:
        land = source_land(source, cfg)
    coverage = apply(
        source, cfg, {"land": mapping(land), "water": mapping(Polygon()), "roads": []}
    )
    scope = shape(coverage["stone_mask"])
    prepare(scope)
    allowed = {}
    for wid, way in ways.items():
        tags = way.get("tags", {})
        ids = way.get("nodes", [])
        if (
            tags.get("highway") != "pedestrian"
            or tags.get("area") == "yes"
            or tags.get("bridge") not in (None, "no")
            or tags.get("tunnel") not in (None, "no")
            or tags.get("layer", "0") != "0"
            or len(ids) < 2
            or ids[0] == ids[-1]
            or any(i not in nodes for i in ids)
        ):
            continue
        try:
            width = float(tags.get("width", tags.get("est_width", 3.5)))
        except (ValueError, TypeError):
            continue
        if not math.isfinite(width) or width < 2.5:
            continue
        line = LineString(
            [project(nodes[i]["lon"], nodes[i]["lat"], cfg["origin"]) for i in ids]
        )
        if line.length > 0 and scope.covers(line):
            allowed[wid] = min(width, 14.0)
    return allowed


def apply(source, cfg, city):
    """Select real disconnected island land; preserve every sourced green area.

    Missing optional park geometry is reported, never downloaded at build time.
    Roads remain an independent collision partition; no ground is stacked on them.
    """
    art = profile()
    land = shape(city["land"]).difference(shape(city["water"]))
    islands, missing = island_mask(land, cfg)
    nodes = {e["id"]: e for e in source["elements"] if e["type"] == "node"}
    protected, inventory, incomplete = [], [], []
    for element in source["elements"]:
        tags = element.get("tags", {})
        preserve = any(
            tags.get(key) in art["preserve_" + key]
            for key in ("leisure", "landuse", "natural")
        )
        if element["type"] != "way" or not preserve:
            continue
        ids = element.get("nodes", [])
        if len(ids) < 4 or ids[0] != ids[-1]:
            continue
        if any(n not in nodes for n in ids):
            incomplete.append("way/" + str(element["id"]))
            continue
        poly = Polygon(
            [project(nodes[n]["lon"], nodes[n]["lat"], cfg["origin"]) for n in ids]
        )
        if not poly.is_valid or not poly.intersects(islands):
            continue
        protected.append(poly.intersection(islands))
        inventory.append(
            {"id": "way/" + str(element["id"]), "name": tags.get("name"), "tags": tags}
        )
    greens = unary_union(protected)
    stone = islands.difference(greens)
    city["oldtown"] = {
        "profile": art["profile"],
        "stone_mask": mapping(stone),
        "protected_mask": mapping(greens),
        "protected_features": inventory,
        "missing_islands": missing,
        "incomplete_optional_features": incomplete,
        "stone_area_m2": round(stone.area, 2),
        "protected_area_m2": round(greens.area, 2),
    }
    prepare(stone)
    for road in city.get("roads", []):
        if len(road.get("points", [])) < 2:
            continue
        probe = {"tags": {**road.get("tags", {}), "sthlm:surface": "oldtown_setts"}}
        if material_for(probe) and stone.covers(LineString(road["points"])):
            road["tags"]["sthlm:surface"] = "oldtown_setts"
    city["oldtown"]["road_stone_mask"] = mapping(_road_mask(city).intersection(stone))
    return city["oldtown"]


def material_for(road, city=None):
    """Native stone on historic streets; preserve modern ring roads and bridges."""
    tags = road.get("tags", {})
    art = profile()
    if (
        tags.get("highway") in art["asphalt_highways"]
        or tags.get("name") in art["asphalt_streets"]
        or tags.get("bridge") not in (None, "no")
        or tags.get("tunnel") not in (None, "no")
    ):
        return None
    if tags.get("sthlm:surface") == "oldtown_setts":
        return MATERIAL
    if city is None or not city.get("oldtown") or len(road.get("points", [])) < 2:
        return None
    line = LineString(road["points"])
    mask = shape(city["oldtown"]["stone_mask"])
    return MATERIAL if mask.covers(line) else None


def partition(geometry, city):
    """Exactly partition an existing surface, retaining water and park exclusions."""
    mask = shape(city["oldtown"]["stone_mask"]) if city.get("oldtown") else Polygon()
    stone = geometry.intersection(mask)
    return stone, geometry.difference(stone)


def road_partition(geometry, city):
    """Fan remainder uses stone only within historic-road footprints.

    Source-classified asphalt corridors win over overlapping historic streets.
    """
    stored = city.get("oldtown", {}).get("road_stone_mask")
    mask = shape(stored) if stored else _road_mask(city)
    paved = geometry.intersection(mask)
    return paved, geometry.difference(paved)


def _road_mask(city):
    stone, asphalt = [], []
    stone_roads = [road for road in city.get("roads", []) if material_for(road)]
    if not stone_roads:
        return Polygon()
    stone = unary_union(
        [LineString(road["points"]).buffer(road["width"] / 2) for road in stone_roads]
    )
    prepare(stone)
    for road in city.get("roads", []):
        if material_for(road) or len(road.get("points", [])) < 2:
            continue
        line = LineString(road["points"])
        if line.distance(stone) <= road["width"] / 2:
            asphalt.append(line.buffer(road["width"] / 2))
    return stone.difference(unary_union(asphalt))


def texture(size=500):
    """Original integer-period running-bond setts; wrap-safe grit and bevels.

    Fan world UV repeats every ten metres. Fifty courses and fifty blocks per
    tile give about 20 cm granite setts. No photograph or retail pixels used.
    """
    # 500 pixels permits a 10px sett, 50 courses, an even stagger period.
    if size % 20:
        raise ValueError("stone texture size must be a multiple of twenty")
    image = Image.new("RGB", (size, size))
    pixels = image.load()
    for y in range(size):
        row, sy = divmod(y, 10)
        for x in range(size):
            shifted = (x + (5 if row % 2 else 0)) % size
            col, sx = divmod(shifted, 10)
            value = ((col * 17 + row * 31) % 19) - 9
            grain = ((x * 13 + y * 7) % 7) - 3
            if sx == 0 or sy == 0:
                rgb = (75 + grain, 73 + grain, 66 + grain)
            else:
                bevel = 13 if sx == 1 or sy == 1 else -12 if sx == 9 or sy == 9 else 0
                rgb = tuple(base + value + grain + bevel for base in (137, 136, 125))
            pixels[x, y] = rgb
    return image


def write_textures(dest):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    texture().save(dest / (MATERIAL + ".png"))

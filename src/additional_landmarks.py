"""Seventy additional original source-anchored Stockholm landmark silhouettes.

OSM provides the plan geometry. Separate artwork records identify approximate
roof forms, materials and heights; referenced photographs are never texture data.
"""

import json
import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw
from shapely import affinity
from shapely.geometry import Point, shape

from courthouse import frustum, pieces, triangle
from landmarks import PALETTES, block, dome, frame, portal, roof

ART_PATH = (
    Path(__file__).resolve().parents[1] / "assets/landmarks/stockholm-seventy.json"
)
KINDS = {
    "terrace",
    "attic",
    "turrets",
    "pediment",
    "mansard",
    "clock",
    "pavilions",
    "flat",
    "sign",
    "hip",
    "stepped",
    "curved-gable",
    "roundtower",
    "modern",
    "brutalist",
    "rotunda",
    "stave",
    "skylight",
    "windmill",
    "battlements",
    "timber-church",
    "belfry",
    "castle",
    "industrial",
    "slab",
    "corner-tower",
    "roof-house",
    "glass",
    "observatory",
    "gothic",
    "baroque",
    "mosque",
    "round-slab",
    "octagon",
    "pavilion",
}


@lru_cache(maxsize=1)
def _entries():
    return json.loads(ART_PATH.read_text())["entries"]


def inventory():
    # Return fresh dictionaries: callers may annotate their export without
    # changing the inventory used by future builds in the same process.
    return json.loads(json.dumps(_entries()))


def source_ids(entries):
    """Include nested OSM aliases in uniqueness checks and replacement hooks."""
    result = []
    for art in entries:
        result.extend([art["source_id"], *art.get("source_aliases", [])])
    return result


def validate_inventory(first_thirty=None):
    entries = inventory()
    if len(entries) != 70:
        raise ValueError(
            "additional landmark inventory must contain exactly 70 entries"
        )
    all_entries = list(first_thirty or []) + entries
    ids = source_ids(all_entries)
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate landmark source ID or nested source alias")
    names = [a["name"].casefold() for a in all_entries]
    if len(names) != len(set(names)):
        raise ValueError("duplicate landmark name")
    for art in entries:
        if art["kind"] not in KINDS:
            raise ValueError(f"unknown additional landmark kind: {art['kind']}")
        if not 0 < art["body_height_m"] < art["total_height_m"]:
            raise ValueError(f"invalid additional landmark heights: {art['name']}")
    return entries


def replaces(building):
    return building["id"] in source_ids(_entries())


def wall_texture(art):
    return "ms_" + art["source_id"].replace("/", "_")


def _hip(writer, footprint, eave, top, texture):
    """Four plane hip roof clipped to the real plan, including courtyard voids."""
    if footprint.is_empty or footprint.area < 0.01:
        return
    _, world, bounds = frame(footprint)
    lo, bottom, hi, upper = bounds
    w, d = hi - lo, upper - bottom
    cut = min(w * 0.22, d / 2)
    middle = (bottom + upper) / 2
    from shapely.geometry import Polygon

    slopes = [
        (
            [(lo, bottom), (hi, bottom), (hi - cut, middle), (lo + cut, middle)],
            lambda x, y: (y - bottom) / (d / 2),
        ),
        (
            [(lo, upper), (lo + cut, middle), (hi - cut, middle), (hi, upper)],
            lambda x, y: (upper - y) / (d / 2),
        ),
        ([(lo, bottom), (lo + cut, middle), (lo, upper)], lambda x, y: (x - lo) / cut),
        ([(hi, bottom), (hi, upper), (hi - cut, middle)], lambda x, y: (hi - x) / cut),
    ]
    angle = frame_angle(footprint)
    c = footprint.centroid
    ca, sa = math.cos(angle), math.sin(angle)

    def local(x, n):
        return c.x + ca * (x - c.x) + sa * (n - c.y), c.y - sa * (x - c.x) + ca * (
            n - c.y
        )

    for coords, fraction in slopes:

        def height(x, n, fraction=fraction):
            return eave + (top - eave) * max(0, min(1, fraction(*local(x, n))))

        writer.surface(footprint.intersection(world(Polygon(coords))), height, texture)
    # Seal source perimeter cuts below the eave-to-ridge planes. Roof surfaces
    # include the slope intersection vertices, so use those boundaries as walls.
    for coords, fraction in slopes:
        geom = footprint.intersection(world(Polygon(coords)))
        for p in pieces(geom):
            pts = list(p.exterior.coords)
            for a, b in zip(pts, pts[1:]):
                # Internal slope joins do not need vertical walls.
                edge = Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                if footprint.boundary.distance(edge) > 0.01:
                    continue
                ha = eave + (top - eave) * max(0, min(1, fraction(*local(*a))))
                hb = eave + (top - eave) * max(0, min(1, fraction(*local(*b))))
                pa, pb = (a[0], eave, a[1]), (b[0], eave, b[1])
                qa, qb = (a[0], ha, a[1]), (b[0], hb, b[1])
                triangle(writer, [pa, pb, qb], texture, perimeter=p)
                triangle(writer, [pa, qb, qa], texture, perimeter=p)


def frame_angle(footprint):
    """Recover the shared stable frame's angle without a second convention."""
    rect, _, _ = frame(footprint)
    a, b = rect(0.25, 0.5, 1, 1).centroid, rect(0.75, 0.5, 1, 1).centroid
    return math.atan2(b.y - a.y, b.x - a.x)


def render(writer, feature, art):
    footprint = shape(feature["geometry"])
    rect, _, bounds = frame(footprint)
    width, depth = bounds[2] - bounds[0], bounds[3] - bounds[1]
    base = feature.get("base_y", 2.0)
    body, total, kind = art["body_height_m"], art["total_height_m"], art["kind"]
    eave, top = base + body, base + total
    wall, cap = wall_texture(art), "ms_" + art.get("roof_palette", "dark")
    church = kind in {"gothic", "baroque", "timber-church", "mosque", "octagon"}
    if kind == "belfry":
        # The Hällestad belfry stands on four open timber legs, not an opaque
        # thirteen-metre plinth. Keep the upper shuttered bell stage closed.
        for u, v in [(0.12, 0.12), (0.88, 0.12), (0.12, 0.88), (0.88, 0.88)]:
            leg = rect(u, v, 1.1, 1.1).intersection(footprint)
            block(writer, leg, 8, wall, cap, base)
        block(writer, footprint, body - 8, wall, cap, base + 8)
    else:
        block(writer, footprint, body, wall, cap, base, church)

    def patch(u, v, w, d):
        return rect(u, v, w, d).intersection(footprint)

    def tower(u=0.5, v=0.5, diameter=None, rounded=False):
        diameter = diameter or min(depth * 0.6, 12)
        area = patch(u, v, diameter, diameter)
        if rounded and not area.is_empty:
            center = area.centroid
            if not footprint.covers(center):
                center = area.representative_point()
            radius = min(diameter / 2, center.distance(footprint.boundary) * 0.96)
            area = center.buffer(radius, quad_segs=2)
        if area.is_empty:
            p = footprint.representative_point()
            area = p.buffer(min(width, depth) * 0.18, quad_segs=2).intersection(
                footprint
            )
        return area

    if kind == "terrace":
        level = eave
        for fraction, height in [(0.65, 9), (0.43, 7), (0.28, 5)]:
            area = patch(0.5, 0.35, width * fraction, depth * fraction)
            block(writer, area, height, wall, cap, level)
            level += height
        area = tower(0.5, 0.35, 6, rounded=True)
        block(writer, area, 4, "ms_glass", cap, level)
        for poly in pieces(area):
            dome(writer, poly, level + 4, top, cap)
    elif kind in {"hip", "pavilion"}:
        _hip(writer, footprint, eave, top, cap)
        if kind == "pavilion":
            # Four authored flagpoles, positioned on the actual retained pavilion.
            for u, v in [(0.15, 0.2), (0.85, 0.2), (0.15, 0.8), (0.85, 0.8)]:
                pole = patch(u, v, 0.2, 0.2)
                block(writer, pole, total - body + 2, "ms_dark", "ms_dark", eave)
    elif kind == "mansard":
        # A steep lower skirt and flatter upper roof retain courtyard holes.
        _hip(writer, footprint, eave, top - 1.2, cap)
        raised = patch(0.5, 0.5, width * 0.55, depth * 0.45)
        block(writer, raised, 1.2, cap, cap, top - 1.2)
    elif kind in {
        "pediment",
        "attic",
        "pavilions",
        "stepped",
        "curved-gable",
        "industrial",
    }:
        _hip(
            writer,
            footprint,
            eave,
            top - (2 if kind in {"pediment", "attic"} else 0),
            cap,
        )
        if kind == "pavilions":
            for u in [0.12, 0.88]:
                area = patch(u, 0.5, width * 0.16, depth * 0.65)
                block(writer, area, (total - body) * 0.55, wall, cap, eave)
                _hip(writer, area, eave + (total - body) * 0.55, top, cap)
        elif kind == "attic":
            block(
                writer,
                patch(0.5, 0.2, width * 0.28, depth * 0.18),
                total - body,
                wall,
                cap,
                eave,
            )
        elif kind == "pediment":
            area = patch(0.5, 0.15, width * 0.28, depth * 0.2)
            block(writer, area, max(0.5, total - body - 3), wall, cap, eave)
            roof(writer, area, top - 3, top, cap)
        elif kind in {"stepped", "curved-gable"}:
            # Three narrowing rectangular stages suggest a Dutch roof gable.
            for level in range(3):
                area = patch(
                    0.5, 0.08, width * (0.46 - level * 0.11), min(2, depth * 0.12)
                )
                block(
                    writer,
                    area,
                    (total - body) / 3,
                    wall,
                    cap,
                    eave + level * (total - body) / 3,
                )
        elif kind == "industrial":
            chimney = tower(0.2, 0.7, 2.8)
            block(writer, chimney, total - body, wall, cap, eave)
    elif kind in {"turrets", "clock", "corner-tower"}:
        _hip(writer, footprint, eave, eave + min(4, (total - body) * 0.35), cap)
        positions = (
            [(0.1, 0.2), (0.9, 0.2)]
            if kind == "turrets"
            else [(0.5, 0.5)]
            if kind in {"clock", "castle"}
            else [(0.12, 0.15)]
        )
        positions = art.get("tower_positions", positions)
        for u, v in positions:
            area = tower(u, v, rounded=kind in {"turrets", "corner-tower"})
            shafttop = top - min(7, (total - body) * 0.35)
            block(writer, area, max(0.2, shafttop - eave), wall, cap, eave)
            for p in pieces(area):
                if kind == "castle":
                    block(writer, p, top - shafttop, wall, cap, shafttop)
                    for a, b in zip(
                        list(p.exterior.coords), list(p.exterior.coords)[1:]
                    ):
                        c = Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                        merlon = c.buffer(0.7, quad_segs=1).intersection(footprint)
                        block(writer, merlon, 1, wall, cap, top)
                else:
                    upper = affinity.scale(p, 0.5, 0.5, origin="centroid")
                    frustum(writer, p, upper, shafttop, top - 1.5, cap)
                    block(writer, upper, 1.5, cap, cap, top - 1.5)
    elif kind == "castle":
        # Kastellet has flat brick wings and a round central tower with a white
        # continuous parapet. A hipped roof or square medieval keep is wrong.
        area = tower(0.5, 0.5, min(depth * 0.6, 14), rounded=True)
        block(writer, area, total - body - 1.4, wall, cap, eave)
        block(writer, area, 1.4, "ms_white", "ms_white", top - 1.4)
    elif kind == "belfry":
        # Broad shingled skirt, shuttered lantern and a long slender needle.
        area = tower(0.5, 0.5, min(depth * 0.8, width * 0.8))
        for poly in pieces(area):
            upper = affinity.scale(poly, 0.46, 0.46, origin="centroid")
            frustum(writer, poly, upper, eave, eave + 6, wall)
            block(writer, upper, 3, wall, cap, eave + 6, True)
            writer.pyramid(upper, eave + 9, top, wall)
    elif kind in {"gothic", "baroque", "timber-church"}:
        if kind != "belfry":
            roof(writer, footprint, eave, eave + min(5, (total - body) * 0.2), cap)
        area = tower(0.15, 0.5, min(depth * 0.65, 12))
        shafttop = eave + (total - body) * 0.52
        block(writer, area, shafttop - eave, wall, cap, eave, True)
        for p in pieces(area):
            if kind in {"baroque", "timber-church", "belfry"}:
                upper = affinity.scale(p, 0.48, 0.48, origin="centroid")
                frustum(writer, p, upper, shafttop, top - 4, cap)
                block(writer, upper, 2, cap, cap, top - 4)
                writer.pyramid(upper, top - 2, top, cap)
            else:
                writer.pyramid(p, shafttop, top, cap)
    elif kind in {"rotunda", "observatory", "octagon", "mosque"}:
        if kind != "rotunda":
            _hip(writer, footprint, eave, eave + min(3, (total - body) * 0.25), cap)
        area = tower(0.5, 0.5, min(depth * 0.5, width * 0.4), rounded=True)
        drumtop = eave + (total - body) * 0.3
        block(writer, area, drumtop - eave, wall, cap, eave, True)
        for p in pieces(area):
            if kind == "octagon":
                writer.pyramid(p, drumtop, top - 2, cap)
                block(
                    writer,
                    affinity.scale(p, 0.14, 0.14, origin="centroid"),
                    2,
                    cap,
                    cap,
                    top - 2,
                )
            else:
                dome(writer, p, drumtop, top, cap)
    elif kind in {"roundtower", "windmill", "battlements"}:
        # Source plan is already round/octagonal; never add a circular footprint
        # larger than the source tower or mill.
        for p in pieces(footprint):
            if kind == "battlements":
                block(writer, p, total - body, wall, cap, eave)
                pts = list(p.exterior.coords)
                for a, b in zip(pts, pts[1:]):
                    c = Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                    block(
                        writer,
                        c.buffer(0.6, quad_segs=1).intersection(p),
                        0.7,
                        wall,
                        cap,
                        top,
                    )
            else:
                writer.pyramid(p, eave, top, cap)
    elif kind == "stave":
        roof(writer, footprint, eave, eave + 4, cap)
        for fraction, rise in [(0.6, 4), (0.3, 7)]:
            area = patch(0.5, 0.5, width * fraction, depth * fraction)
            block(writer, area, rise - 2, wall, cap, eave + 2)
            roof(writer, area, eave + rise, top, cap)
    elif kind == "roof-house":
        area = patch(0.5, 0.5, width * 0.5, depth * 0.45)
        block(writer, area, 2, "ms_ochre", "ms_red", eave)
        roof(writer, area, eave + 2, top, "ms_red")
    elif kind == "skylight":
        area = patch(0.5, 0.5, width * 0.72, depth * 0.18)
        block(writer, area, total - body, "ms_glass", "ms_glass", eave)
    elif kind == "sign":
        area = tower(0.5, 0.5, 1)
        block(writer, area, total - body - 4, "ms_dark", "ms_dark", eave)
        c = area.centroid
        y = top - 4
        for points in [
            [(c.x - 3, y, c.y), (c.x + 3, y, c.y), (c.x + 3, top, c.y)],
            [(c.x - 3, y, c.y), (c.x + 3, top, c.y), (c.x - 3, top, c.y)],
        ]:
            triangle(writer, points, "ms_nk_sign", perimeter=next(pieces(footprint)))
            triangle(
                writer,
                list(reversed(points)),
                "ms_nk_sign",
                perimeter=next(pieces(footprint)),
            )
    elif kind in {"flat", "modern", "glass", "brutalist", "slab", "round-slab"}:
        area = patch(0.5, 0.5, width * 0.55, depth * 0.6)
        block(writer, area, total - body, cap, cap, eave)
    else:
        raise ValueError(f"unhandled additional landmark kind: {kind}")
    if kind not in {"belfry", "pavilion"}:
        portal(writer, footprint, base, church)
    return {
        key: art[key]
        for key in [
            "name",
            "kind",
            "body_height_m",
            "total_height_m",
            "silhouette",
            "dimensions_note",
            "reference_url",
        ]
    } | {"source_feature": feature["id"], "inventory": "stockholm-seventy"}


def textures(dest):
    """Original landmark palettes and facade motifs, drawn from primitives."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    colors = PALETTES | {
        "mint": (164, 183, 167),
        "dark": (49, 52, 48),
        "timber": (74, 53, 40),
        "gold": (174, 145, 74),
        "copper": (75, 118, 102),
    }
    for key in ["dark", "copper", "red", "ochre", "glass", "white"]:
        Image.new("RGB", (64, 64), colors[key]).save(dest / f"ms_{key}.png")
    sign = Image.new("RGB", (128, 128), colors["dark"])
    d = ImageDraw.Draw(sign)
    d.ellipse((7, 7, 120, 120), fill=(198, 173, 99), outline=(54, 51, 40), width=5)
    d.text((38, 44), "NK", fill=(40, 40, 33), font_size=34)
    sign.save(dest / "ms_nk_sign.png")
    for art in inventory():
        color = colors[art["palette"]]
        im = Image.new("RGB", (128, 128), color)
        d = ImageDraw.Draw(im)
        kind = art["kind"]
        # Materials carry the detail budget; each geometric model stays compact.
        if art["palette"] in {"brick", "red", "timber"}:
            for y in range(0, 128, 8):
                d.line((0, y, 127, y), fill=tuple(max(0, c - 19) for c in color))
                if art["palette"] != "timber":
                    for x in range(-(y % 16), 128, 24):
                        d.line(
                            (x, y, x, y + 8), fill=tuple(max(0, c - 19) for c in color)
                        )
        modern = kind in {"slab", "modern", "glass", "brutalist", "round-slab"}
        trim = (
            (198, 190, 166)
            if art["palette"] in {"brick", "red", "ochre"}
            else (132, 123, 100)
        )
        if modern:
            d.rectangle((0, 32, 127, 89), fill=(44, 62, 65))
            for x in range(0, 128, 24):
                d.line((x, 32, x, 89), fill=trim, width=2)
            d.line((0, 94, 127, 94), fill=trim, width=3)
        else:
            d.rectangle((42, 26, 86, 100), fill=(44, 60, 62), outline=trim, width=4)
            if kind in {
                "gothic",
                "baroque",
                "timber-church",
                "octagon",
                "mosque",
                "battlements",
            }:
                d.ellipse((42, 10, 86, 53), fill=(44, 60, 62), outline=trim, width=4)
                d.rectangle((46, 34, 82, 80), fill=(44, 60, 62))
            d.line((64, 27, 64, 98), fill=trim, width=2)
            d.line((43, 62, 85, 62), fill=trim, width=2)
            d.line((0, 115, 127, 115), fill=trim, width=4)
        if kind == "castle":
            d.line((0, 4, 127, 4), fill=(225, 224, 211), width=8)
            d.ellipse(
                (48, 14, 80, 46), fill=(44, 60, 62), outline=(225, 224, 211), width=4
            )
        if art["name"] == "Axel Oxenstiernas palats":
            for y in [0, 16, 112]:
                d.line((0, y, 127, y), fill=(205, 185, 148), width=5)
        im.save(dest / f"{wall_texture(art)}.png")


def export(writer, city, out):
    import landmarks

    entries = validate_inventory(landmarks.inventory())
    by_id = {b["id"]: b for b in city["buildings"]}
    missing = [a["source_id"] for a in entries if a["source_id"] not in by_id]
    if missing:
        raise ValueError(
            f"additional landmarks absent from normalized source: {missing}"
        )
    result = []
    for art in entries:
        feature = by_id[art["source_id"]]
        metadata = render(writer, feature, art)
        feature["rendering"] = metadata
        result.append(metadata)
    textures(Path(out) / "texture")
    city.setdefault("landmarks", []).extend(result)
    return result

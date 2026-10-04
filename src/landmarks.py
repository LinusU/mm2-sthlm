"""Thirty source-anchored original MM2-scale Stockholm landmark silhouettes.

OSM owns plan position. Approximate authored heights and landmark-specific roof
forms live separately from the source snapshot. No photo pixels are used.
"""

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw
from shapely import affinity
from shapely.geometry import Point, box, shape

from courthouse import frustum, pieces, triangle

ART_PATH = (
    Path(__file__).resolve().parents[1] / "assets/landmarks/stockholm-thirty.json"
)
PALETTES = {
    "brick": (139, 76, 53),
    "sand": (190, 168, 125),
    "ochre": (208, 155, 77),
    "cream": (219, 212, 180),
    "stone": (178, 170, 149),
    "blue": (91, 133, 155),
    "red": (120, 57, 43),
    "glass": (58, 77, 80),
    "white": (217, 219, 207),
    "green": (42, 79, 61),
}


def inventory():
    return json.loads(ART_PATH.read_text())["entries"]


def replaces(building):
    return any(
        (
            a["source_id"] == building["id"]
            or building["id"] in a.get("source_aliases", [])
        )
        and a["kind"] != "existing"
        for a in inventory()
    )


def frame(footprint):
    """Stable longest-axis frame derived from source minimum rotated rectangle."""
    coords = list(footprint.convex_hull.exterior.coords)
    c = footprint.centroid
    candidates = []
    for a, b in zip(coords, coords[1:]):
        angle = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        local = affinity.rotate(footprint, -angle, origin=c)
        lo, bottom, hi, top = local.bounds
        if top - bottom > hi - lo:
            angle += 90
            local = affinity.rotate(footprint, -angle, origin=c)
        area = (hi - lo) * (top - bottom)
        # Round tiny numerical area differences to keep symmetric cases stable.
        candidates.append((round(area, 5), angle % 180))
    _, angle = min(candidates)
    local = affinity.rotate(footprint, -angle, origin=c)
    lo, bottom, hi, top = local.bounds

    def world(poly):
        return affinity.rotate(poly, angle, origin=c)

    def rect(u, v, width, depth):
        x, n = lo + (hi - lo) * u, bottom + (top - bottom) * v
        return world(box(x - width / 2, n - depth / 2, x + width / 2, n + depth / 2))

    return rect, world, (lo, bottom, hi, top)


def block(writer, geom, height, wall, roof, base, church=False):
    for poly in pieces(geom):
        if poly.area > 0.1:
            writer.building(
                poly,
                height,
                wall,
                roof,
                base=base,
                facade_repeat_width_m=7 if church else 5,
                facade_repeat_height_m=height if church else 5,
            )


def dome(writer, footprint, base, top, roof):
    """Eight low-poly rings approximate a rounded dome instead of a pyramid."""
    for h0, s0, h1, s1 in [
        (0, 1, 0.25, 0.97),
        (0.25, 0.97, 0.55, 0.8),
        (0.55, 0.8, 0.8, 0.5),
        (0.8, 0.5, 1, 0.12),
    ]:
        frustum(
            writer,
            affinity.scale(footprint, s0, s0, origin="centroid"),
            affinity.scale(footprint, s1, s1, origin="centroid"),
            base + (top - base) * h0,
            base + (top - base) * h1,
            roof,
        )


def roof(writer, footprint, base, top, texture):
    """Two clipped planar roof slopes keep courtyard voids and source boundaries."""
    _, world, bounds = frame(footprint)
    lo, bottom, hi, upper = bounds
    middle = (bottom + upper) / 2
    # Local cross-axis distance to the long central ridge.
    ridge = world(box(lo, middle, hi, middle + 0.001))
    from shapely.geometry import LineString

    points = list(ridge.exterior.coords)
    line = LineString([points[0], points[3]])
    half = (upper - bottom) / 2

    def height(x, n):
        return base + (top - base) * max(0, 1 - line.distance(Point(x, n)) / half)

    for low, high in [(bottom, middle), (middle, upper)]:
        writer.surface(
            footprint.intersection(world(box(lo, low, hi, high))), height, texture
        )
    # Seal the gable edges, retaining a nondegenerate source perimeter for native winding.
    for poly in pieces(footprint):
        for ring in [poly.exterior, *poly.interiors]:
            pts = list(ring.coords)
            for a, b in zip(pts, pts[1:]):
                cross = LineString([a, b]).intersection(line)
                if (
                    cross.geom_type == "Point"
                    and math.dist(a, cross.coords[0]) > 0.001
                    and math.dist(b, cross.coords[0]) > 0.001
                ):
                    peak = (cross.x, top, cross.y)
                    triangle(
                        writer,
                        [(a[0], base, a[1]), (b[0], base, b[1]), peak],
                        texture,
                        perimeter=poly,
                    )
                pa, pb = (a[0], base, a[1]), (b[0], base, b[1])
                qa, qb = (a[0], height(*a), a[1]), (b[0], height(*b), b[1])
                triangle(writer, [pa, pb, qb], texture, perimeter=poly)
                triangle(writer, [pa, qb, qa], texture, perimeter=poly)


def portal(writer, footprint, base, church=False):
    """Original wood entrance panel, native vertical triangles, metre-scale doors."""
    for poly in pieces(footprint):
        points = list(poly.exterior.coords)
        edges = [(a, b) for a, b in zip(points, points[1:]) if math.dist(a, b) >= 4]
        if not edges:
            continue
        # A restrained entrance on a western perimeter bay, never repeated on each floor.
        side = 1 if poly.exterior.is_ccw else -1
        west = [
            edge
            for edge in edges
            if (edge[1][1] - edge[0][1]) / math.dist(*edge) * side < -0.5
        ]
        a, b = max(west or edges, key=lambda edge: math.dist(*edge))
        length = math.dist(a, b)
        ux, un = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        side = 1 if poly.exterior.is_ccw else -1
        x = (a[0] + b[0]) / 2 + 0.04 * un * side
        n = (a[1] + b[1]) / 2 - 0.04 * ux * side
        half, height = (1.3, 3.8) if church else (1.1, 3.0)
        p = (x - ux * half, base + 0.03, n - un * half)
        q = (x + ux * half, base + 0.03, n + un * half)
        r = (q[0], base + height, q[2])
        t = (p[0], base + height, p[2])
        triangle(writer, [p, q, r], "lm_door", perimeter=poly)
        triangle(writer, [p, r, t], "lm_door", perimeter=poly)


def render(writer, feature, art, body_footprint=None):
    full_footprint = shape(feature["geometry"])
    footprint = body_footprint if body_footprint is not None else full_footprint
    rect, world, bounds = frame(footprint)
    width, depth = bounds[2] - bounds[0], bounds[3] - bounds[1]
    base = feature.get("base_y", 2.0)
    body, total, kind = art["body_height_m"], art["total_height_m"], art["kind"]
    church = kind in {"gothic", "baroque", "lattice", "twin", "dome"}
    wall = "lm_" + art["palette"] + ("_arch" if church else "_bay")
    copper = (
        "lm_dark"
        if kind in {"lattice", "vasa"} or feature["id"] == "way/42038493"
        else "lm_copper"
    )
    copper = "lm_" + art.get("roof_palette", copper.removeprefix("lm_"))
    if feature["id"] == "relation/1257127":
        # Preserve the existing dedicated quiet brick and arched bay art.
        wall = "church_facade"
    if body_footprint is not None:
        block(
            writer,
            full_footprint.difference(footprint),
            4,
            "church_brick",
            "church_copper",
            base,
            True,
        )
    body_geometry = footprint
    if kind == "columns":
        # Carve the actual colonnade void so columns are visible outside the hall.
        lo, bottom, hi, upper = bounds
        porch = world(box(lo, bottom, lo + width * 0.24, upper)).intersection(footprint)
        body_geometry = footprint.difference(porch)
        block(writer, porch, 0.8, "lm_blue", "lm_blue", base)
    block(writer, body_geometry, body, wall, copper, base, church)
    eave = base + body
    if kind in {"gothic", "baroque", "lattice", "twin"}:
        roof(writer, footprint, eave, eave + 5, copper)
        positions = [(0.18, 0.22), (0.18, 0.78)] if kind == "twin" else [(0.18, 0.5)]
        positions = art.get("tower_positions", positions)
        half = min(7, depth * (0.22 if kind == "twin" else 0.28))
        for index, (u, v) in enumerate(positions):
            if "tower_centres_east_north_m" in art:
                shaft = (
                    Point(*art["tower_centres_east_north_m"][index])
                    .buffer(art["tower_radius_m"], quad_segs=2)
                    .intersection(full_footprint)
                )
            else:
                shaft = rect(u, v, half * 2, half * 2).intersection(footprint)
            for poly in pieces(shaft):
                capbase = (
                    base
                    + total
                    - (28 if kind == "lattice" else 24 if kind == "gothic" else 16)
                )
                tower_wall = "church_tower" if kind == "twin" else wall
                block(writer, poly, capbase - eave, tower_wall, copper, eave, True)
                if kind == "lattice":
                    # Open triangular iron ribs have no opaque conical infill.
                    cx, n = poly.centroid.coords[0]
                    for x, z in list(poly.exterior.coords)[:-1]:
                        rib = box(x - 0.22, z - 0.22, x + 0.22, z + 0.22)
                        tip = box(cx - 0.06, n - 0.06, cx + 0.06, n + 0.06)
                        frustum(writer, rib, tip, capbase, base + total, copper)
                    for fraction in [0.25, 0.5, 0.75]:
                        collar = affinity.scale(
                            poly, 1 - fraction, 1 - fraction, origin="centroid"
                        )
                        block(
                            writer,
                            collar,
                            0.3,
                            copper,
                            copper,
                            capbase + fraction * (base + total - capbase),
                        )
                elif kind in {"baroque", "twin"}:
                    upper = affinity.scale(poly, 0.55, 0.55, origin="centroid")
                    frustum(writer, poly, upper, capbase, capbase + 7, copper)
                    block(writer, upper, 4, copper, copper, capbase + 7)
                    writer.pyramid(upper, capbase + 11, base + total, copper)
                else:
                    writer.pyramid(poly, capbase, base + total, copper)
    elif kind == "dome":
        roof(writer, footprint, eave, eave + 4, copper)
        c = footprint.representative_point()
        drum = (
            Point(c.x, c.y)
            .buffer(min(width, depth) * 0.23, quad_segs=2)
            .intersection(footprint)
        )
        for poly in pieces(drum):
            drumtop = base + total - 18
            block(writer, poly, drumtop - eave, wall, copper, eave, True)
            dome(writer, poly, drumtop, base + total - 5, copper)
            lantern = affinity.scale(poly, 0.12, 0.12, origin="centroid")
            block(writer, lantern, 3, "lm_dark", copper, base + total - 5)
            writer.pyramid(lantern, base + total - 2, base + total, copper)
    elif kind == "rotunda":
        c = footprint.centroid
        drum = Point(c.x, c.y).buffer(min(width, depth) * 0.3, quad_segs=8)
        block(writer, drum, total - body, "lm_ochre_clerestory", "lm_dark", eave, True)
    elif kind == "columns":
        block(
            writer,
            rect(0.5, 0.5, width * 0.65, depth * 0.65),
            total - body,
            "lm_blue",
            "lm_dark",
            eave,
        )
        for i in range(10):
            pillar = rect(0.12, 0.09 + i * 0.091, 1.7, 1.7)
            block(writer, pillar, body - 2, "lm_blue", "lm_blue", base + 1)
        block(
            writer, rect(0.12, 0.5, 4, depth * 0.96), 2, "lm_blue", "lm_dark", eave - 1
        )
    elif kind == "nordic":
        roof(writer, footprint, eave, eave + 15, copper)
        for u in [0.08, 0.92]:
            end = rect(u, 0.5, width * 0.15, depth * 0.85).intersection(footprint)
            block(writer, end, 10, wall, copper, eave)
            roof(writer, end, eave + 10, base + total, copper)
        for u in [0.07, 0.93]:
            for v in [0.12, 0.88]:
                turret = rect(u, v, 5, 5).intersection(footprint)
                block(writer, turret, 12, wall, copper, eave)
                for poly in pieces(turret):
                    writer.pyramid(poly, eave + 12, eave + 23, copper)
    elif kind == "vasa":
        roof(writer, footprint, eave, eave + 8, copper)
        for u in [0.25, 0.5, 0.75]:
            mast = rect(u, 0.5, 0.6, 0.6)
            block(writer, mast, total - body, "lm_dark", "lm_dark", eave)
            block(
                writer,
                rect(u, 0.5, 8, 0.35),
                0.35,
                "lm_dark",
                "lm_dark",
                base + total - 5,
            )
    elif kind == "round":
        roof(writer, footprint, eave, eave + 3, copper)
        for u in [0.08, 0.92]:
            c = rect(u, 0.18, 1, 1).centroid
            turret = c.buffer(min(depth, 16) * 0.35, quad_segs=4).intersection(
                footprint
            )
            block(writer, turret, total - body - 4, wall, copper, eave)
            dome(writer, turret, base + total - 4, base + total, copper)
    elif kind in {"palace", "museum", "theatre"}:
        roof(writer, footprint, eave, base + total - 3, copper)
        for u in [0.1, 0.9]:
            pavilion = rect(u, 0.5, width * 0.15, depth * 0.7).intersection(footprint)
            block(writer, pavilion, total - body - 2, wall, copper, eave)
        crown = rect(
            0.5, 0.5, min(12, width * 0.18), min(12, depth * 0.5)
        ).intersection(footprint)
        block(
            writer,
            crown,
            total - body,
            "lm_gold" if kind == "theatre" else wall,
            copper,
            eave,
        )
    elif kind == "glass":
        # Broad horizontal glazing strips distinguish the modern civic slab.
        for level in range(1, 5):
            block(
                writer, footprint, 0.45, "lm_white", "lm_white", base + level * body / 5
            )
        block(
            writer,
            rect(0.5, 0.5, width * 0.55, depth * 0.5),
            total - body,
            "lm_dark",
            "lm_dark",
            eave,
        )
    elif kind == "slab":
        block(
            writer,
            rect(0.5, 0.5, width * 0.3, depth * 0.6),
            total - body,
            "lm_dark",
            "lm_dark",
            eave,
        )
    portal(writer, body_geometry, base, church)
    return {
        "source_feature": feature["id"],
        "kind": kind,
        "body_height_m": body,
        "total_height_m": total,
        "silhouette": art["silhouette"],
        "dimensions_note": art["dimensions_note"],
        "reference_url": art["reference_url"],
    }


def textures(dest):
    dest.mkdir(parents=True, exist_ok=True)
    door = Image.new("RGB", (128, 128), (78, 60, 40))
    draw = ImageDraw.Draw(door)
    draw.rectangle((4, 3, 123, 127), outline=(146, 132, 103), width=7)
    for x in [16, 69]:
        for y in [16, 66]:
            draw.rectangle((x, y, x + 42, y + 44), outline=(43, 35, 26), width=3)
    draw.line((64, 8, 64, 127), fill=(32, 28, 22), width=3)
    draw.rectangle((56, 76, 59, 87), fill=(164, 136, 67))
    draw.rectangle((69, 76, 72, 87), fill=(164, 136, 67))
    door.save(dest / "lm_door.png")
    colors = {
        **PALETTES,
        "copper": (73, 116, 98),
        "dark": (48, 53, 48),
        "gold": (174, 143, 67),
    }
    for palette, color in colors.items():
        for style in ["", "_bay", "_arch", "_clerestory"]:
            im = Image.new("RGB", (128, 128), color)
            d = ImageDraw.Draw(im)
            for y in range(128):
                for x in range(128):
                    grain = (x * 7 + y * 13 + x * y) % 7 - 3
                    d.point((x, y), tuple(max(0, min(255, c + grain)) for c in color))
            if palette == "brick":
                for y in range(0, 128, 5):
                    d.line((0, y, 127, y), fill=(103, 78, 59))
                    for x in range(-(y % 10), 128, 20):
                        d.line((x, y, x, y + 5), fill=(103, 78, 59))
            if style == "_arch":
                d.ellipse((51, 20, 77, 46), fill=(31, 46, 49))
                d.rectangle((51, 33, 77, 108), fill=(31, 46, 49))
                d.line((64, 22, 64, 107), fill=(89, 80, 57), width=2)
                for y in range(48, 108, 18):
                    d.line((52, y, 76, y), fill=(89, 80, 57), width=2)
            elif style == "_bay":
                d.rectangle(
                    (40, 26, 87, 105),
                    fill=(43, 63, 68),
                    outline=(122, 110, 83),
                    width=3,
                )
                d.line((64, 27, 64, 104), fill=(122, 110, 83), width=2)
                d.line((40, 67, 87, 67), fill=(122, 110, 83), width=2)
            elif style == "_clerestory":
                d.rectangle((44, 12, 84, 43), fill=(41, 58, 60))
                d.line((64, 12, 64, 43), fill=(150, 108, 54), width=3)
            im.save(dest / f"lm_{palette}{style}.png")


def export(writer, city, out):
    by_id = {b["id"]: b for b in city["buildings"]}
    result = []
    for art in inventory():
        feature = by_id.get(art["source_id"])
        if feature is None:
            continue
        if art["kind"] == "existing":
            result.append(
                {
                    "source_feature": feature["id"],
                    "kind": "existing",
                    "silhouette": art["silhouette"],
                }
            )
            continue
        body = next(
            (
                shape(by_id[alias]["geometry"])
                for alias in art.get("source_aliases", [])
                if alias in by_id
            ),
            None,
        )
        metadata = render(writer, feature, art, body_footprint=body)
        feature["rendering"] = metadata
        result.append(metadata)
    textures(Path(out) / "texture")
    city["landmarks"] = result
    return result

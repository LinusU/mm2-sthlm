"""Source-anchored original schematic Stockholm Court House landmark.

World geometry is east/north. PsdlWriter alone converts north to engine south.
Photographs guide materials and silhouette; JSON records authored estimates.
"""

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw
from shapely import affinity
from shapely.geometry import Polygon, box, mapping, shape
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

BUILDING_ID = "way/24488933"
ART_PATH = Path(__file__).resolve().parents[1] / "assets/landmarks/courthouse.json"


def pieces(geom):
    if geom.geom_type == "Polygon":
        yield geom
    elif hasattr(geom, "geoms"):
        for part in geom.geoms:
            yield from pieces(part)


def coordinates(art):
    """Local u points across wings; v follows their long northward axis."""
    angle = math.radians(art["rotation_degrees"])
    c, s = math.cos(angle), math.sin(angle)
    x0, n0 = art["origin"]

    def world(u, v):
        return x0 + c * u - s * v, n0 + s * u + c * v

    def local(x, n):
        return c * (x - x0) + s * (n - n0), -s * (x - x0) + c * (n - n0)

    def region(bounds):
        return Polygon([world(u, v) for u, v in box(*bounds).exterior.coords])

    return world, local, region


def model_geometry(feature, art):
    footprint = shape(feature["geometry"])
    _, _, region = coordinates(art)
    courts = unary_union([region(bounds) for bounds in art["courtyards"]])
    body = footprint.difference(courts)
    tower = region(art["tower_bounds"]).intersection(body)
    return footprint, body, tower


def masonry(writer, poly, height, texture, roof, base, floors=2):
    """Use large civic facade bays instead of the generic apartment repeat."""
    part = (
        writer.part(poly.centroid.x, poly.centroid.y)
        if hasattr(writer, "part")
        else writer
    )
    part.building(poly, height, texture, roof, base=base)
    attrs = part.rooms[-1][1]
    edge = 0
    for ring in [poly.exterior, *poly.interiors]:
        pts = list(ring.coords)
        for a, b in zip(pts, pts[1:]):
            attrs[edge + 5] = max(1, round(math.dist(a, b) / 7.0))
            attrs[edge + 6] = floors
            edge += 14


def triangle(writer, points, texture, perimeter=None):
    """Emit one decorative face through either single or chunked PSDL writer."""
    a, b, c = points
    ab, ac = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
    cross = [
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    ]
    if sum(v * v for v in cross) < 1e-12:
        return
    x = sum(p[0] for p in points) / 3
    n = sum(p[2] for p in points) / 3
    part = writer.part(x, n) if hasattr(writer, "part") else writer
    refs = [part.vertex(p) for p in points]
    # The importer uses the room's projected polygon to orient vertical fans.
    # A vertical triangle's own projection is a line, so a roof lantern wall
    # needs its enclosing footprint rather than a degenerate three-point room.
    boundary = (
        refs
        if perimeter is None
        else [
            part.vertex((x, min(p[1] for p in points), n))
            for x, n in perimeter.exterior.coords[:-1]
        ]
    )
    part.rooms.append((boundary, part.texture(texture) + [0xB1, *refs], 0))


def frustum(writer, lower, upper, bottom, top, texture):
    """A stepped copper hip roof, rather than a single conical spire."""
    a = list(orient(lower, sign=1).exterior.coords)[:-1]
    b = list(orient(upper, sign=1).exterior.coords)[:-1]
    for i in range(len(a)):
        j = (i + 1) % len(a)
        p, q = (a[i][0], bottom, a[i][1]), (a[j][0], bottom, a[j][1])
        r, s = (b[j][0], top, b[j][1]), (b[i][0], top, b[i][1])
        # Upward winding in source east/north, as PsdlWriter.pyramid expects.
        triangle(writer, [p, q, r], texture, perimeter=lower)
        triangle(writer, [p, r, s], texture, perimeter=lower)


def gable(writer, geom, bounds, axis, base, rise, art):
    world, local, region = coordinates(art)
    coordinate = 1 if axis == "u" else 0
    lo, hi = (bounds[1], bounds[3]) if coordinate else (bounds[0], bounds[2])
    middle = (lo + hi) / 2
    # Split at ridge before triangulating, so both roof slopes stay planar.
    for left in [True, False]:
        half = list(bounds)
        half[coordinate + (2 if left else 0)] = middle
        area = geom.intersection(region(half))

        def height(x, n):
            value = local(x, n)[coordinate]
            return base + rise * max(0, 1 - abs(value - middle) / ((hi - lo) / 2))

        writer.surface(area, height, "court_tiles")
    # Seal every clipped roof boundary down to the eave. Source walls can be
    # inset from the schematic strip ends; leaving those edges open creates gaps.
    # Courtyard voids remain absent from both roof slopes and sealing faces.
    for poly in pieces(geom):
        pts = list(poly.exterior.coords)
        for a, b in zip(pts, pts[1:]):
            al, bl = local(*a), local(*b)
            ac, bc = al[coordinate], bl[coordinate]
            if min(ac, bc) < middle < max(ac, bc):
                t = (middle - ac) / (bc - ac)
                peak = (a[0] + t * (b[0] - a[0]), base + rise, a[1] + t * (b[1] - a[1]))
                triangle(
                    writer,
                    [(a[0], base, a[1]), (b[0], base, b[1]), peak],
                    "court_plaster",
                    perimeter=poly,
                )
            else:
                ay = base + rise * max(0, 1 - abs(ac - middle) / ((hi - lo) / 2))
                by = base + rise * max(0, 1 - abs(bc - middle) / ((hi - lo) / 2))
                triangle(
                    writer,
                    [(a[0], base, a[1]), (b[0], base, b[1]), (b[0], by, b[1])],
                    "court_plaster",
                    perimeter=poly,
                )
                triangle(
                    writer,
                    [(a[0], base, a[1]), (b[0], by, b[1]), (a[0], ay, a[1])],
                    "court_plaster",
                    perimeter=poly,
                )


def textures(dest):
    """Original repeatable texture art. No photograph pixels are redistributed."""
    dest.mkdir(parents=True, exist_ok=True)
    palette = {
        "court_plaster": (195, 174, 132),
        "court_facade": (195, 174, 132),
        "court_stone": (144, 137, 117),
        "court_tiles": (147, 68, 39),
        "court_copper": (85, 132, 111),
        "court_tower": (195, 174, 132),
        "court_dormer": (74, 68, 55),
        "court_brick": (140, 76, 50),
        "court_metal": (71, 66, 53),
    }
    for name, color in palette.items():
        img = Image.new("RGB", (128, 128), color)
        d = ImageDraw.Draw(img)
        # Deterministic rough stucco grain, never random build outputs.
        for y in range(128):
            for x in range(128):
                grain = ((x * 17 + y * 31 + x * y * 7) % 11) - 5
                d.point((x, y), fill=tuple(max(0, min(255, c + grain)) for c in color))
        if name in {"court_facade", "court_tower", "court_dormer"}:
            rect = (43, 36, 85, 105) if name != "court_tower" else (53, 48, 75, 87)
            if name == "court_facade":
                d.ellipse((39, 15, 89, 65), fill=(161, 137, 99))
                d.rectangle((39, 40, 89, 109), fill=(161, 137, 99))
                d.ellipse(
                    (43, 20, 85, 62), fill=(51, 76, 85), outline=(67, 52, 37), width=4
                )
            d.rectangle(rect, fill=(51, 76, 85), outline=(67, 52, 37), width=4)
            for x in [rect[0] + 14, rect[2] - 14]:
                d.line((x, rect[1], x, rect[3]), fill=(109, 86, 59), width=2)
            for y in range(rect[1] + 14, rect[3], 18):
                d.line((rect[0], y, rect[2], y), fill=(109, 86, 59), width=2)
            d.line((0, 124, 127, 124), fill=(167, 146, 109), width=3)
        elif name in {"court_tiles", "court_stone", "court_brick"}:
            h = 12 if name == "court_tiles" else 20
            for y in range(0, 128, h):
                d.line(
                    (0, y, 127, y), fill=tuple(int(c * 0.72) for c in color), width=2
                )
                for x in range(-16 if (y // h) % 2 else 0, 128, 24):
                    d.line((x, y, x, y + h), fill=tuple(int(c * 0.78) for c in color))
        elif name == "court_copper":
            for x in range(0, 128, 16):
                d.line((x, 0, x, 127), fill=(49, 85, 70), width=2)
            for y in range(0, 128, 32):
                d.line((0, y, 127, y), fill=(67, 106, 88))
        img.save(dest / f"{name}.png")


def export(writer, city, out):
    feature = next((b for b in city["buildings"] if b["id"] == BUILDING_ID), None)
    if feature is None:
        return None
    art = json.loads(ART_PATH.read_text())
    footprint, body, tower = model_geometry(feature, art)
    world, _, region = coordinates(art)
    base = feature.get("base_y", 2.0)
    stone = art["stone_base_height"]
    eave = base + art["body_height"]
    for poly in pieces(body):
        writer.building(poly, stone, "court_stone", "court_stone", base=base)
        masonry(
            writer,
            poly,
            art["body_height"] - stone,
            "court_facade",
            "court_tiles",
            base=base + stone,
        )
    for wing in art["roof_wings"]:
        area = region(wing["bounds"]).intersection(body)
        gable(
            writer,
            area,
            wing["bounds"],
            wing["ridge_axis"],
            eave,
            art["roof_rise"],
            art,
        )
    # Square shaft anchored in the western central wing visible from the park.
    for poly in pieces(tower):
        masonry(
            writer,
            poly,
            art["tower_shaft_height"] - art["body_height"],
            "court_tower",
            "court_copper",
            base=eave,
        )
        writer.building(
            poly,
            0.5,
            "court_metal",
            "court_copper",
            base=base + art["tower_shaft_height"],
        )
        levels = art["tower_cap_levels"]
        for (h0, s0), (h1, s1) in zip(levels, levels[1:]):
            lower = affinity.scale(poly, s0, s0, origin="centroid")
            upper = affinity.scale(poly, s1, s1, origin="centroid")
            frustum(writer, lower, upper, base + h0, base + h1, "court_copper")
        cap = affinity.scale(poly, levels[-1][1], levels[-1][1], origin="centroid")
        writer.pyramid(cap, base + levels[-1][0], base + 50, "court_metal")
        cx, cz = poly.centroid.x, poly.centroid.y
        writer.building(
            box(cx - 0.12, cz - 0.12, cx + 0.12, cz + 0.12),
            art["finial_height"],
            "court_metal",
            "court_metal",
            base=base + 50,
        )
    # Repeated west-facing roof dormers, plus brick chimneys. Every footprint
    # stays within the original source building, including all courtyard voids.
    for v in [15, 29, 65, 78]:
        dormer = region([-22, v - 1.6, -18, v + 1.6]).intersection(body)
        for poly in pieces(dormer):
            writer.building(poly, 2.4, "court_dormer", "court_metal", base=eave + 1.8)
            writer.pyramid(poly, eave + 4.2, eave + 4.7, "court_metal")
        chimney = region([-17, v + 4, -15.5, v + 6.8]).intersection(body)
        for poly in pieces(chimney):
            writer.building(poly, 3.2, "court_brick", "court_brick", base=eave + 4.2)
    textures(Path(out) / "texture")
    metadata = {
        "source_feature": BUILDING_ID,
        "rule": art["description"],
        "body_height_m": art["body_height"],
        "total_height_m": 50 + art["finial_height"],
        "authored_courtyard_voids": mapping(footprint.difference(body)),
        "tower_footprint": mapping(tower),
        "materials": [
            "sand rough plaster",
            "rough stone base",
            "red clay tiles",
            "patinated copper",
            "blue glass with brown frames",
        ],
    }
    feature["rendering"] = metadata
    return metadata

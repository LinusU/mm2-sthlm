"""Original district facade artwork and bounded native street-level entrances."""

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw
from shapely.geometry import LineString, Point, Polygon, shape
from shapely.strtree import STRtree

CONFIG = Path(__file__).resolve().parents[1] / "config/overrides/district-facades.json"


@lru_cache(maxsize=1)
def profiles():
    return json.loads(CONFIG.read_text())


def material_for(building, origin=(18.045, 59.328)):
    """Choose an authored district palette; explicit monuments take precedence."""
    tags = building.get("tags", {})
    if tags.get("building") in {
        "church",
        "cathedral",
        "chapel",
        "religious",
        "shed",
        "garage",
        "garages",
        "service",
    }:
        return None
    if building.get("street_detail") or building.get("height", 15) < 4:
        return None
    point = shape(building["geometry"]).centroid
    radius = 6378137.0
    lon = origin[0] + math.degrees(
        point.x / (radius * math.cos(math.radians(origin[1])))
    )
    lat = origin[1] + math.degrees(point.y / radius)
    art = profiles()
    district = next(
        (
            region["profile"]
            for region in art["regions"]
            if Polygon(region["polygon"]).covers(Point(lon, lat))
        ),
        "norrmalm",
    )
    palette = art["profiles"][district]
    variant = int(hashlib.sha256(building["id"].encode()).hexdigest()[:8], 16) % len(
        palette["colors"]
    )
    prefix = f"district_{district}_{variant}"
    return {
        "district": district,
        "variant": variant,
        "upper": prefix + "_upper",
        "ground": prefix + "_ground",
        "door": prefix + "_door",
        "roof": "district_roof_" + palette["roof"],
        "bay_width_m": palette["bay_width_m"],
        "floor_height_m": palette["floor_height_m"],
    }


class StreetFrontages:
    """Spatially indexed ordinary roads; bridges/tunnels never attract entrances."""

    def __init__(self, city, height):
        self.height = height
        self.lines = [
            LineString(r["points"])
            for r in city["roads"]
            if len(r.get("points", [])) >= 2
            and r.get("tags", {}).get("tunnel") not in {"yes", "building_passage"}
            and r.get("tags", {}).get("bridge") != "yes"
            and str(r.get("tags", {}).get("layer", "0")) == "0"
        ]
        self.tree = STRtree(self.lines)

    def entrance(self, poly, base, top):
        choices = []
        pts = list(poly.exterior.coords)
        for index, (a, b) in enumerate(zip(pts, pts[1:])):
            wall = LineString([a, b])
            if wall.length < 3.4 or not self.lines:
                continue
            middle = wall.interpolate(0.5, normalized=True)
            road = self.lines[int(self.tree.nearest(middle))]
            near = road.interpolate(road.project(middle))
            distance = middle.distance(near)
            # A road across the footprint is a courtyard/back entrance, not a frontage.
            if (
                distance > 35
                or LineString([middle, near]).intersection(poly.buffer(-0.05)).length
                > 0.1
            ):
                continue
            level = (
                self.height(near.x, near.y) if callable(self.height) else self.height
            )
            wall_levels = [
                self.height(point.x, point.y) if callable(self.height) else self.height
                for point in (
                    wall.interpolate(wall.length / 2 - 0.8),
                    middle,
                    wall.interpolate(wall.length / 2 + 0.8),
                )
            ]
            bottom = max(base, level + 0.06, max(wall_levels) + 0.06)
            if bottom + 3.0 <= top:
                choices.append((distance, index, bottom, [near.x, near.y]))
        return min(choices) if choices else None


def export(writer, poly, building, frontages, material=None):
    """Split native Facade surfaces vertically; retain one full wall collider/edge."""
    from sthlm import triangulate

    if hasattr(writer, "part"):
        writer = writer.part(poly.centroid.x, poly.centroid.y)
    art = material or material_for(building)
    if art is None:
        return None
    base = building.get("base_y", 2.0)
    top = base + building["height"]
    entry = frontages.entrance(poly, base, top)
    band_bottom = entry[2] if entry else base
    band_top = min(top, band_bottom + art["floor_height_m"])
    attrs = []

    def face(a, b, bottom, upper, texture, horizontal=1, vertical=1):
        if upper - bottom < 0.001 or math.dist(a, b) < 0.001:
            return
        attrs.extend(writer.texture(texture))
        attrs.extend(
            [
                0x5E,
                writer.height(bottom),
                writer.height(upper),
                horizontal,
                vertical,
                writer.vertex((a[0], bottom, a[1])),
                writer.vertex((b[0], bottom, b[1])),
            ]
        )

    for ring_index, ring in enumerate([poly.exterior, *poly.interiors]):
        pts = list(ring.coords)
        for index, (a, b) in enumerate(zip(pts, pts[1:])):
            repeat = max(1, round(math.dist(a, b) / art["bay_width_m"]))
            face(a, b, base, band_bottom, "district_plinth", repeat)
            if entry and ring_index == 0 and index == entry[1]:
                length = math.dist(a, b)
                # Exactly one 1.6m door module on the selected exterior edge.
                fractions = (0.5 - 0.8 / length, 0.5 + 0.8 / length)
                left, right = [
                    tuple(a[j] + (b[j] - a[j]) * f for j in range(2)) for f in fractions
                ]
                face(
                    a,
                    left,
                    band_bottom,
                    band_top,
                    art["ground"],
                    max(1, round(math.dist(a, left) / art["bay_width_m"])),
                )
                face(left, right, band_bottom, band_top, art["door"])
                face(
                    right,
                    b,
                    band_bottom,
                    band_top,
                    art["ground"],
                    max(1, round(math.dist(right, b) / art["bay_width_m"])),
                )
            else:
                face(a, b, band_bottom, band_top, art["ground"], repeat)
            face(
                a,
                b,
                band_top,
                top,
                art["upper"],
                repeat,
                max(1, round((top - band_top) / art["floor_height_m"])),
            )
            attrs.extend(
                [
                    0x3C,
                    0,
                    writer.height(top),
                    writer.vertex((a[0], base, a[1])),
                    writer.vertex((b[0], base, b[1])),
                ]
            )
    attrs.extend(writer.texture(art["roof"]))
    for tri in triangulate(poly):
        attrs.extend([0xB1, *[writer.vertex((x, top, z)) for x, z in tri]])
    writer.rooms.append(
        ([writer.vertex((x, base, z)) for x, z in poly.exterior.coords[:-1]], attrs, 0)
    )
    return {
        "material_profile": art,
        "entrance": {
            "edge": entry[1],
            "bottom_m": band_bottom,
            "top_m": band_top,
            "road_point": entry[3],
            "repeat_u": 1,
            "repeat_v": 1,
        }
        if entry
        else None,
        "rule": "one exterior street entrance; separate upper-floor repeat; original procedural artwork",
    }


def tile(palette, color, kind):
    """256px original flat-lit MM2-style facade bay; no sampled image pixels."""
    image = Image.new("RGB", (256, 256), tuple(color))
    px = image.load()
    for y in range(256):
        for x in range(256):
            grain = (x * 17 + y * 11) % 5 - 2
            px[x, y] = tuple(max(0, min(255, c + grain)) for c in color)
    d = ImageDraw.Draw(image)
    if palette.get("brick"):
        for y in range(0, 256, 12):
            d.line((0, y, 255, y), fill=tuple(max(0, c - 20) for c in color))
            for x in range(-24 if y // 12 % 2 else 0, 256, 48):
                d.line((x, y, x, y + 12), fill=tuple(max(0, c - 20) for c in color))
    if kind == "door":
        d.rectangle((25, 55, 230, 255), fill=tuple(palette["trim"]))
        d.rectangle((42, 66, 213, 255), fill=tuple(palette["door"]))
        d.rectangle((57, 76, 198, 110), fill=(65, 80, 80))
        d.line((127, 69, 127, 255), fill=(40, 43, 39), width=3)
        for x in (58, 139):
            for y in (127, 184):
                d.rectangle((x, y, x + 58, y + 48), outline=(42, 46, 41), width=3)
        d.rectangle((146, 157, 155, 164), fill=(176, 158, 106))
    else:
        left, right = (63, 192) if palette["window"] == "wide" else (80, 175)
        d.rectangle((left - 7, 41, right + 7, 219), fill=tuple(palette["trim"]))
        d.rectangle((left, 48, right, 209), fill=(48, 66, 72))
        d.rectangle((left + 6, 54, right - 6, 200), fill=(77, 100, 107))
        d.line(
            ((left + right) // 2, 48, (left + right) // 2, 209),
            fill=tuple(palette["trim"]),
            width=5,
        )
        rows = 3 if palette["window"] == "tall" else 2
        for row in range(1, rows):
            y = 48 + row * 161 // rows
            d.line((left, y, right, y), fill=tuple(palette["trim"]), width=5)
        d.line(
            (left - 9, 220, right + 9, 220),
            fill=tuple(max(0, c - 30) for c in palette["trim"]),
            width=4,
        )
        if kind == "ground":
            d.rectangle((0, 241, 255, 255), fill=(104, 103, 94))
    return image


def write(out):
    destination = Path(out) / "texture"
    destination.mkdir(parents=True, exist_ok=True)
    for district, palette in profiles()["profiles"].items():
        for variant, color in enumerate(palette["colors"]):
            for kind in ("upper", "ground", "door"):
                tile(
                    {**palette, "brick": variant in palette.get("brick_variants", [])},
                    color,
                    kind,
                ).save(destination / f"district_{district}_{variant}_{kind}.png")
    Image.new("RGB", (128, 128), (104, 103, 94)).save(
        destination / "district_plinth.png"
    )
    for name, color in profiles()["roofs"].items():
        image = Image.new("RGB", (128, 128), tuple(color))
        d = ImageDraw.Draw(image)
        for x in range(0, 128, 16):
            d.line((x, 0, x, 127), fill=tuple(max(0, c - 22) for c in color), width=2)
        image.save(destination / f"district_roof_{name}.png")

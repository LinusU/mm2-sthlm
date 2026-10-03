"""Original schematic green glass bar anchored to its recorded OSM footprint."""

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw
from shapely.geometry import shape

from courthouse import coordinates, pieces, triangle

BUILDING_ID = "way/1049742528"
ART_PATH = Path(__file__).resolve().parents[1] / "assets/landmarks/waterfront-bar.json"


def model_geometry(feature, art):
    """Partition the source, never replace it with an estimated rectangle."""
    footprint = shape(feature["geometry"])
    _, _, region = coordinates(art)
    centre = footprint.intersection(region(art["central_bounds"]))
    return footprint, centre, footprint.difference(centre)


def facade(writer, poly, height, texture, roof, base):
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
            attrs[edge + 5] = max(1, round(math.dist(a, b) / 3.0))
            attrs[edge + 6] = 1
            edge += 14


def pitched_roof(writer, centre, art, eave):
    _, local, region = coordinates(art)
    bounds = art["central_bounds"]
    middle = (bounds[0] + bounds[2]) / 2
    half_width = (bounds[2] - bounds[0]) / 2

    def height(x, n):
        u, _ = local(x, n)
        return eave + art["roof_rise"] * max(0, 1 - abs(u - middle) / half_width)

    for left in [True, False]:
        half = list(bounds)
        half[2 if left else 0] = middle
        writer.surface(centre.intersection(region(half)), height, "bar_roof")
    # Full polygon room boundaries let native PSDL orient vertical gable fans.
    for poly in pieces(centre):
        pts = list(poly.exterior.coords)
        for a, b in zip(pts, pts[1:]):
            au, _ = local(*a)
            bu, _ = local(*b)
            pa, pb = (a[0], eave, a[1]), (b[0], eave, b[1])
            if min(au, bu) < middle < max(au, bu):
                t = (middle - au) / (bu - au)
                peak = (
                    a[0] + t * (b[0] - a[0]),
                    eave + art["roof_rise"],
                    a[1] + t * (b[1] - a[1]),
                )
                triangle(writer, [pa, pb, peak], "bar_glass", perimeter=poly)
            else:
                qa, qb = (a[0], height(*a), a[1]), (b[0], height(*b), b[1])
                triangle(writer, [pa, pb, qb], "bar_glass", perimeter=poly)
                triangle(writer, [pa, qb, qa], "bar_glass", perimeter=poly)


def textures(dest):
    """Small original opaque textures; no reference photograph pixels."""
    dest.mkdir(parents=True, exist_ok=True)
    green, glass = (29, 69, 51), (35, 61, 60)
    for name in ["bar_glass", "bar_wing", "bar_roof"]:
        img = Image.new("RGB", (128, 128), green)
        draw = ImageDraw.Draw(img)
        if name == "bar_roof":
            for x in range(0, 128, 16):
                draw.line((x, 0, x, 127), fill=(16, 43, 32), width=2)
        else:
            draw.rectangle((9, 8, 118, 116), fill=glass)
            draw.polygon([(14, 12), (66, 12), (14, 75)], fill=(50, 79, 75))
            draw.line((64, 8, 64, 116), fill=green, width=5)
            draw.line((9, 43, 118, 43), fill=green, width=5)
            draw.rectangle((0, 118, 127, 127), fill=green)
            if name == "bar_wing":
                for x in range(0, 128, 16):
                    draw.rectangle(
                        (x, 8, x + 15, 25),
                        fill=(220, 173, 54) if x % 32 == 0 else (235, 225, 191),
                    )
                draw.line((0, 27, 127, 27), fill=green, width=4)
        img.save(dest / f"{name}.png")


def export(writer, city, out):
    feature = next((b for b in city["buildings"] if b["id"] == BUILDING_ID), None)
    if feature is None:
        return None
    art = json.loads(ART_PATH.read_text())
    footprint, centre, wings = model_geometry(feature, art)
    base = feature.get("base_y", 2.0)
    for poly in pieces(wings):
        facade(writer, poly, art["wing_height"], "bar_wing", "bar_roof", base)
    for poly in pieces(centre):
        facade(writer, poly, art["central_height"], "bar_glass", "bar_roof", base)
    pitched_roof(writer, centre, art, base + art["central_height"])
    textures(Path(out) / "texture")
    metadata = {
        "source_feature": BUILDING_ID,
        "rule": art["description"],
        "footprint_area_m2": footprint.area,
        "total_height_m": art["central_height"] + art["roof_rise"],
        "materials": [
            "dark green framing",
            "opaque dark glass",
            "green metal roof",
            "yellow and cream wing awning",
        ],
    }
    feature["rendering"] = metadata
    return metadata

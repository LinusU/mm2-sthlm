"""Authored raised volumes where incomplete building tags block source roads."""

import json
import math
from pathlib import Path
from functools import lru_cache

from shapely.geometry import LineString, Point, shape, mapping
from shapely.ops import unary_union

from elevation import RoadField

RULES = Path(__file__).resolve().parents[1] / "config/overrides/building-passages.json"


@lru_cache(maxsize=1)
def load_rules():
    return json.loads(RULES.read_text())["passages"]


def volume_for(building, roads, rules=None):
    if rules is None:
        rules = load_rules()
    rule = next((r for r in rules if r["building_id"] == building["id"]), None)
    if rule is None:
        return None
    footprint = shape(building["geometry"])
    levels = []
    corridors = []
    for road_id in rule["road_ids"]:
        road = next((r for r in roads if r["id"] == road_id), None)
        if road is None:
            raise ValueError(f"building passage {building['id']} lacks road {road_id}")
        corridor = LineString(road["points"]).buffer(
            road["width"] / 2 + rule.get("margin_m", 0)
        )
        corridors.append(corridor)
        crossing = footprint.intersection(corridor)
        if crossing.is_empty:
            raise ValueError(
                f"building passage {building['id']} no longer overlaps its road"
            )
        field = RoadField([road], None, bridge=True)
        # Include every profile breakpoint and footprint corner, then densely
        # sample the clipped corridor boundary. The sloping deck stays intact.
        polygons = (
            [crossing] if crossing.geom_type == "Polygon" else list(crossing.geoms)
        )
        probes = [p for poly in polygons for p in poly.exterior.coords]
        boundary = crossing.boundary
        for i in range(math.ceil(boundary.length) + 1):
            p = boundary.interpolate(min(i, boundary.length))
            probes.append((p.x, p.y))
        probes.extend(
            p[:2] for p in road["elevated_points"] if crossing.covers(Point(p[:2]))
        )
        levels.extend(field.height_for_road(road_id, x, n) for x, n in probes)
    underside = max(levels) + rule["clearance_m"]
    if rule.get("mode") == "cutout":
        top = building["base_y"] + building["height"]
        if not building["base_y"] < underside < top:
            raise ValueError(
                "building cutout must preserve a lower body and upper storeys"
            )
        opening = footprint.intersection(unary_union(corridors))
        return {
            "mode": "cutout",
            "underside_y_m": underside,
            "top_y_m": top,
            "base_y_m": building["base_y"],
            "opening_geometry": mapping(opening),
            "lower_geometry": mapping(footprint.difference(opening)),
            "facade": rule["facade"],
            "roof": rule.get("roof", "roof"),
            "source_road_ids": rule["road_ids"],
            "clearance_m": rule["clearance_m"],
            "rule": rule["reason"],
            "inferred": True,
        }
    return {
        "underside_y_m": underside,
        "top_y_m": underside + rule["body_height_m"],
        "rule": rule["reason"],
        "source_road_ids": rule["road_ids"],
        "clearance_m": rule["clearance_m"],
        "inferred": True,
    }


def export(writer, poly, volume):
    from sthlm import triangulate, pieces

    if hasattr(writer, "part"):
        writer = writer.part(poly.centroid.x, poly.centroid.y)
    bottom, top = volume["underside_y_m"], volume["top_y_m"]
    if volume.get("mode") == "cutout":
        for lower in pieces(shape(volume["lower_geometry"]).intersection(poly)):
            writer.building(
                lower,
                bottom - volume["base_y_m"],
                volume["facade"],
                volume["roof"],
                base=volume["base_y_m"],
            )
        writer.building(
            poly, top - bottom, volume["facade"], volume["roof"], base=bottom
        )
        underside = poly.intersection(shape(volume["opening_geometry"]))
    else:
        writer.building(poly, top - bottom, "bridge_concrete", "roof", base=bottom)
        underside = poly
    attrs = writer.texture("bridge_concrete")
    for tri in triangulate(underside):
        attrs.extend([0xB1, *[writer.vertex((x, bottom, n)) for x, n in reversed(tri)]])
    perimeter = [writer.vertex((x, bottom, n)) for x, n in poly.exterior.coords[:-1]]
    writer.rooms.append((perimeter, attrs, 0))

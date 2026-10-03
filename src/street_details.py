"""Source-anchored Kronoberg details; authored dimensions remain explicit."""

import json
import math
import struct
from pathlib import Path

from shapely.geometry import LineString, Point, mapping, shape

from props import banger_record, chunk, geometry, lp

CONFIG = Path(__file__).resolve().parents[1] / "config/overrides/kronoberg-details.json"


def rules():
    return json.loads(CONFIG.read_text())


def apply(city):
    """Annotate the exact sourced features before elevation, preserving geometry."""
    config = rules()
    details = []
    for b in list(city["buildings"]):
        for kind in ("guard_hut", "urinal"):
            rule = config[kind]
            if b["id"] != rule["source"]:
                continue
            detail = dict(b, kind=kind, override=rule)
            details.append(detail)
            if kind == "urinal":
                city["buildings"].remove(b)
            else:
                b["height"] = rule["height_m"]
                b["height_rule"] = rule["provenance"]
                b["street_detail"] = kind
    ramp_rule = config["ramp"]
    for road in city["roads"]:
        if f"way/{road['id']}" == ramp_rule["source"]:
            if road["nodes"] != [ramp_rule["entrance_node"], ramp_rule["end_node"]]:
                raise ValueError("Kronoberg driveway source topology changed")
            road["width"] = ramp_rule["width_m"]
            road["street_detail"] = "descending_dead_end"
            road["height_override"] = ramp_rule
    city["street_details"] = details
    # The narrower driveway affects its surface footprint as well as its profile.
    from shapely.ops import unary_union

    surface = unary_union(
        [
            LineString(r["points"]).buffer(r["width"] / 2, cap_style=1, join_style=2)
            for r in city["roads"]
        ]
    )
    if "bounds" in city:
        surface = surface.intersection(shape(city["bounds"]))
    city["road_surface"] = mapping(surface)
    return city


class RampField:
    def __init__(self, base, ramps):
        self.base = base
        self.terrain = base.terrain
        self.ramps = ramps

    def __getattr__(self, name):
        return getattr(self.base, name)

    def nearest(self, x, n):
        p = Point(x, n)
        for line, start, drop, width, shoulder in self.ramps:
            distance = line.distance(p)
            if distance <= width / 2:
                return start - drop * line.project(p, normalized=True), distance
        return self.base.nearest(x, n)

    def __call__(self, x, n):
        return self.nearest(x, n)[0]

    def ground(self, x, n):
        p = Point(x, n)
        raw = self.base.ground(x, n)
        for line, start, drop, width, shoulder in self.ramps:
            # Flat end caps preserve the source dead end; no imaginary tunnel.
            corridor = line.buffer(width / 2 + shoulder, cap_style=2)
            if corridor.covers(p):
                distance = line.distance(p)
                h = start - drop * line.project(p, normalized=True)
                weight = max(0, min(1, (width / 2 + shoulder - distance) / shoulder))
                return h * weight + raw * (1 - weight)
        return raw


def wrap_field(road_field, city):
    """Apply estimated local ramp after elevation; entrance height stays shared."""
    ramps = []
    for road in city["roads"]:
        rule = road.get("height_override")
        if not rule:
            continue
        line = LineString(road["points"])
        start = road["elevated_points"][0][2]
        points = []
        count = max(1, math.ceil(line.length / 4))
        for i in range(count + 1):
            t = i / count
            p = line.interpolate(t, normalized=True)
            points.append([p.x, p.y, start - rule["drop_m"] * t])
        road["elevated_points"] = points
        road["height_rule"] = rule["provenance"]
        ramps.append((line, start, rule["drop_m"], road["width"], rule["shoulder_m"]))
    # Keep the prepared field's bridge separation and shared-junction state.
    # Only this local profile is overlaid; unrelated cached roads stay intact.
    return RampField(road_field, ramps)


def render(writer, city, height):
    """Render the hut as compact glazed architecture, plus driveway termination."""
    for detail in city.get("street_details", []):
        if detail["kind"] != "guard_hut":
            continue
        poly = shape(detail["geometry"])
        b = next(b for b in city["buildings"] if b["id"] == detail["id"])
        base = b.get("base_y", height(poly.centroid.x, poly.centroid.y))
        writer.building(poly, 0.85, "sthlm_hut_panel", "sthlm_hut_panel", base=base)
        writer.building(
            poly.buffer(-0.08),
            1.65,
            "sthlm_hut_glass",
            "sthlm_hut_glass",
            base=base + 0.85,
        )
        writer.building(
            poly.buffer(0.12),
            0.5,
            "sthlm_hut_metal",
            "sthlm_hut_metal",
            base=base + 2.5,
        )
    for road in city["roads"]:
        rule = road.get("height_override")
        if not rule:
            continue
        a, b = road["points"][-2:]
        length = math.dist(a, b)
        dx, dn = -(b[1] - a[1]) / length, (b[0] - a[0]) / length
        half = road["width"] / 2
        cap = LineString(
            [(b[0] + dx * half, b[1] + dn * half), (b[0] - dx * half, b[1] - dn * half)]
        ).buffer(0.25, cap_style=2)
        writer.building(
            cap,
            1.1,
            "sthlm_hut_panel",
            "sthlm_hut_panel",
            base=road["elevated_points"][-1][2],
        )


def two_sided(triangles):
    """Thin booth panels remain visible inside and outside after native culling."""
    return [face for a, b, c in triangles for face in ((a, b, c), (c, b, a))]


def urinal_mesh(radius=0.85, height=2.3):
    panels, posts, roof = [], [], []
    for i in range(8):
        a, b = 2 * math.pi * i / 8, 2 * math.pi * (i + 1) / 8
        p, q = (
            (radius * math.cos(a), radius * math.sin(a)),
            (radius * math.cos(b), radius * math.sin(b)),
        )
        # Omit one panel to leave the reference's visible open entrance.
        if i != 6:
            panels.extend(
                [
                    (
                        (p[0], -height / 2, p[1]),
                        (q[0], -height / 2, q[1]),
                        (q[0], height / 2 - 0.2, q[1]),
                    ),
                    (
                        (p[0], -height / 2, p[1]),
                        (q[0], height / 2 - 0.2, q[1]),
                        (p[0], height / 2 - 0.2, p[1]),
                    ),
                ]
            )
        roof.append(
            (
                (
                    radius * 1.12 * math.cos(a),
                    height / 2 - 0.1,
                    radius * 1.12 * math.sin(a),
                ),
                (
                    radius * 1.12 * math.cos(b),
                    height / 2 - 0.1,
                    radius * 1.12 * math.sin(b),
                ),
                (0, height / 2 + 0.08, 0),
            )
        )
        # Small dark upright at each panel seam.
        r = 0.045
        for j in range(4):
            c, d = j * math.pi / 2, (j + 1) * math.pi / 2
            u, v = (
                (p[0] + r * math.cos(c), p[1] + r * math.sin(c)),
                (p[0] + r * math.cos(d), p[1] + r * math.sin(d)),
            )
            posts.extend(
                [
                    (
                        (u[0], -height / 2, u[1]),
                        (v[0], -height / 2, v[1]),
                        (v[0], height / 2, v[1]),
                    ),
                    (
                        (u[0], -height / 2, u[1]),
                        (v[0], height / 2, v[1]),
                        (u[0], height / 2, u[1]),
                    ),
                ]
            )
        # Narrow roof vent.
        roof.append(
            (
                (0.10 * math.cos(a), height / 2 + 0.08, 0.10 * math.sin(a)),
                (0.10 * math.cos(b), height / 2 + 0.08, 0.10 * math.sin(b)),
                (0, height / 2 + 0.35, 0),
            )
        )
    shaders = struct.pack("<2I", 1, 2)
    for texture in ("sthlm_urinal_panel", "sthlm_hut_metal"):
        shaders += lp(texture) + struct.pack(
            "<17f", *([1, 1, 1, 1] * 2 + [0, 0, 0, 0] * 2 + [0])
        )
    return (
        b"PKG3"
        + chunk("shaders", shaders)
        + chunk("BODY_H", geometry(two_sided(panels), 0))
        + chunk("FRAME_H", geometry(two_sided(posts + roof), 1))
    )


def write(out, city, height):
    """Write original art/tuning, return placements for the shared native pathset."""
    from PIL import Image, ImageDraw

    (out / "geometry").mkdir(parents=True, exist_ok=True)
    (out / "tune/banger").mkdir(parents=True, exist_ok=True)
    (out / "texture").mkdir(parents=True, exist_ok=True)
    for name, colour in (
        ("panel", (175, 178, 172)),
        ("glass", (66, 85, 84)),
        ("metal", (47, 51, 48)),
    ):
        image = Image.new("RGB", (64, 64), colour)
        draw = ImageDraw.Draw(image)
        for i in range(0, 64, 8):
            draw.line((i, 0, i, 63), fill=tuple(max(0, v - 14) for v in colour))
        image.save(out / f"texture/sthlm_hut_{name}.png")
    # Original deterministic grey aggregate speckle, resembling the photo's
    # coarse concrete panels without using any photographic/retail texture.
    panel = Image.new("RGB", (64, 64))
    pixels = panel.load()
    for y in range(64):
        for x in range(64):
            value = 174 + ((x * 73 + y * 151 + x * y * 17) % 19) - 9
            pixels[x, y] = (value, value + 2, value)
    panel.save(out / "texture/sthlm_urinal_panel.png")
    instances = []
    for detail in city.get("street_details", []):
        if detail["kind"] != "urinal":
            continue
        rule = detail["override"]
        poly = shape(detail["geometry"])
        p = poly.centroid
        asset = "sthlm_kronoberg_urinal"
        (out / f"geometry/{asset}.pkg").write_bytes(
            urinal_mesh(rule["radius_m"], rule["height_m"])
        )
        record = (
            banger_record(rule["mass_kg"], 0)
            .replace(
                "Size 0.7 8 0.7",
                f"Size {rule['radius_m'] * 2} {rule['height_m']} {rule['radius_m'] * 2}",
            )
            .replace("CG 0 4 0", f"CG 0 {rule['height_m'] / 2} 0")
            .replace("ImpulseLimit2 450", "ImpulseLimit2 0")
            .replace("YRadius 0.35", f"YRadius {rule['radius_m']}")
        )
        (out / f"tune/banger/{asset}.dgbangerdata").write_text(record)
        instances.append(
            {
                "source": detail["id"],
                "asset": asset,
                "kind": "urinal",
                "position": [p.x, height(p.x, p.y), -p.y],
                "breakable": False,
                "movable": True,
                "source_geometry": detail["geometry"],
                "source_tags": detail["tags"],
                "dimensions_rule": rule["provenance"],
            }
        )
    return instances

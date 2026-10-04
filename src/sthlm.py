"""Independent OSM → local city → PSDL mod. No engine imports."""

from __future__ import annotations
import argparse
import gzip
import hashlib
import heapq
import json
import math
import os
import re
import shutil
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from functools import lru_cache
from shapely import constrained_delaunay_triangles, prepare
from shapely.geometry import LineString, Point, Polygon, box, mapping, shape
from shapely.ops import polygonize_full, unary_union
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project(lon, lat, origin):
    if not all(math.isfinite(v) for v in [lon, lat, *origin]) or not (
        -180 <= lon <= 180 and -90 <= lat <= 90
    ):
        raise ValueError("invalid WGS84 coordinates")
    # Local WGS84 tangent approximation; normalized east/north, export east/south.
    radius = 6378137.0
    return (
        radius * math.radians(lon - origin[0]) * math.cos(math.radians(origin[1])),
        radius * math.radians(lat - origin[1]),
    )


def pieces(geom):
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    return [p for child in getattr(geom, "geoms", []) for p in pieces(child)]


def triangulate(geom):
    for poly in pieces(geom):
        if not poly.is_valid:
            raise ValueError("invalid polygon")
        for tri in constrained_delaunay_triangles(poly).geoms:
            if tri.area > 1e-8:
                pts = list(tri.exterior.coords)[:3]
                a, b, c = pts
                if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) < 0:
                    pts.reverse()
                yield pts


def height_triangles(geom, level, *, interior=True):
    """Refine curved height fields without opening shared material edges.

    An edge's refinement depends only on its endpoints and height sampler, so
    adjacent patches make identical splits. Interior centroid splits retain
    those edges. In particular, a long triangle must not interpolate a nearby
    upper street's height across the centre of a lower hillside street.
    """
    triangles = list(triangulate(geom))
    edge_counts = {}
    for tri in triangles:
        for a, b in zip(tri, tri[1:] + tri[:1]):
            key = tuple(sorted((a, b)))
            edge_counts[key] = edge_counts.get(key, 0) + 1
    boundary_edges = {edge for edge, count in edge_counts.items() if count == 1}
    for _ in range(6):
        refined = []
        changed = False
        for tri in triangles:
            cuts = []
            for a, b in zip(tri, tri[1:] + tri[:1]):
                edge = tuple(sorted((a, b)))
                if not interior and edge not in boundary_edges:
                    continue
                midpoint = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                if (
                    math.dist(a, b) > 0.25
                    and abs(level(*midpoint) - (level(*a) + level(*b)) / 2) > 0.04
                ):
                    cuts.append((a, b, midpoint))
                    if edge in boundary_edges:
                        boundary_edges.update(
                            [tuple(sorted((a, midpoint))), tuple(sorted((midpoint, b)))]
                        )
            children = [tri]
            for a, b, midpoint in cuts:
                split = []
                for child in children:
                    if a in child and b in child:
                        c = next(p for p in child if p != a and p != b)
                        split.extend([[a, midpoint, c], [midpoint, b, c]])
                    else:
                        split.append(child)
                children = split
            if interior and not cuts:
                centre = tuple(sum(p[i] for p in tri) / 3 for i in (0, 1))
                if (
                    max(math.dist(a, b) for a, b in zip(tri, tri[1:] + tri[:1])) > 0.25
                    and abs(level(*centre) - sum(level(*p) for p in tri) / 3) > 0.04
                ):
                    children = [
                        [tri[0], tri[1], centre],
                        [tri[1], tri[2], centre],
                        [tri[2], tri[0], centre],
                    ]
            changed |= len(children) > 1
            refined.extend(children)
        triangles = refined
        if not changed:
            break
    for pts in triangles:
        a, b, c = pts
        if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) < 0:
            pts = list(reversed(pts))
        yield pts


def estimated_height(tags, feature_id, area=None):
    for tag, scale in [("height", 1), ("building:levels", 3.2)]:
        if tag in tags:
            try:
                h = float(tags[tag].replace(" m", "")) * scale
                if math.isfinite(h) and 0.5 <= h <= 150:
                    return h, tag
            except ValueError:
                pass
    if tags.get("building") in ["shed", "garage", "garages", "service"] or (
        area is not None and area < 40
    ):
        return 3.2, "estimated-small-footprint"
    if area is not None and area < 150:
        return 6.4, "estimated-small-footprint"
    return 15.0 + (
        int(hashlib.sha256(feature_id.encode()).hexdigest()[:8], 16) % 4
    ) * 3.2, "estimated"


def assemble_relation(rel, ways, nodes, origin, local_bounds=None):
    rings = {}
    for role in ["outer", "inner"]:
        segments = []
        for m in rel["members"]:
            if m["type"] != "way" or m.get("role", "") not in (
                [role, ""] if role == "outer" else [role]
            ):
                continue
            w = ways.get(m["ref"])
            if not w or any(n not in nodes for n in w["nodes"]):
                raise ValueError(f"relation {rel['id']} missing member {m['ref']}")
            segments.append(
                LineString(
                    [
                        project(nodes[n]["lon"], nodes[n]["lat"], origin)
                        for n in w["nodes"]
                    ]
                )
            )
        if not segments:
            rings[role] = Polygon()
            continue
        polygons, cuts, dangles, invalid = polygonize_full(segments)
        # Mälaren contains two distant non-ring inner members; reject if
        # any malformed fragment can affect this slice, retain them in source.
        local = (
            local_bounds
            if local_bounds is not None
            else box(
                *project(18.0295, 59.3235, origin), *project(18.0605, 59.3345, origin)
            )
        )
        for bad in [cuts, dangles, invalid]:
            if bad.intersects(local):
                raise ValueError(f"relation {rel['id']} contains local open rings")
        polygons = list(polygons.geoms)
        if not polygons:
            raise ValueError(f"relation {rel['id']} has no complete rings")
        rings[role] = unary_union(polygons)
    return rings["outer"].difference(rings["inner"])


def shortest(graph, start, end):
    queue = [(0, start)]
    costs, prev = {start: 0}, {}
    while queue:
        cost, node = heapq.heappop(queue)
        if node == end:
            path = [end]
            while path[-1] != start:
                path.append(prev[path[-1]])
            return path[::-1]
        if cost != costs[node]:
            continue
        for nxt, length in graph.get(node, {}).items():
            c = cost + length
            if c < costs.get(nxt, float("inf")):
                costs[nxt], prev[nxt] = c, node
                heapq.heappush(queue, (c, nxt))
    raise ValueError(f"route disconnected: {start} → {end}")


def normalize(source, cfg, boundary=None, water_override=None):
    nodes = {e["id"]: e for e in source["elements"] if e["type"] == "node"}
    ways = {e["id"]: e for e in source["elements"] if e["type"] == "way"}
    origin = cfg["origin"]
    w, s, e, n = cfg["bounds"]
    bounds = (
        boundary
        if boundary is not None
        else box(*project(w, s, origin), *project(e, n, origin))
    )
    prepare(bounds)
    roads, buildings, waters, omitted = [], [], [], []
    relations = [e for e in source["elements"] if e["type"] == "relation"]
    consumed = {
        m["ref"]
        for r in relations
        if r.get("tags", {}).get("building")
        for m in r["members"]
        if m["type"] == "way"
    }
    for rel in relations:
        tags = rel.get("tags", {})
        if not (tags.get("building") or tags.get("natural") == "water"):
            continue
        if tags.get("natural") == "water" and water_override is not None:
            continue
        try:
            poly = assemble_relation(rel, ways, nodes, origin, bounds).intersection(
                bounds
            )
        except ValueError as exc:
            if tags.get("building") and cfg.get("report_bad_buildings"):
                omitted.append({"id": rel["id"], "reason": str(exc), "tags": tags})
                continue
            raise
        if tags.get("building") and not poly.is_empty:
            h, rule = estimated_height(tags, f"relation/{rel['id']}", poly.area)
            buildings.append(
                {
                    "id": f"relation/{rel['id']}",
                    "tags": tags,
                    "height": h,
                    "height_rule": rule,
                    "geometry": mapping(poly),
                }
            )
        if tags.get("natural") == "water":
            waters.append(poly)
    for wid, way in sorted(ways.items()):
        tags = way.get("tags", {})
        if any(n not in nodes for n in way["nodes"]):
            raise ValueError(f"way {wid}: incomplete referenced geometry")
        pts = [project(nodes[n]["lon"], nodes[n]["lat"], origin) for n in way["nodes"]]
        pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
        if len(pts) < 2:
            continue
        line = LineString(pts)
        if not line.intersects(bounds):
            continue
        if tags.get("highway") in cfg.get(
            "road_classes",
            [
                "residential",
                "tertiary",
                "unclassified",
                "secondary",
                "service",
                "living_street",
            ],
        ) or wid in cfg.get("allowed_surface_ways", {}):
            if (
                (
                    tags.get("bridge") not in (None, "no")
                    or tags.get("tunnel") not in (None, "no")
                    or tags.get("layer", "0") != "0"
                )
                and wid not in cfg.get("allowed_bridge_ways", [])
                and wid not in cfg.get("allowed_tunnel_ways", [])
                and not (
                    cfg.get("allow_internal_open_cuts")
                    and tags.get("tunnel") in (None, "no")
                    and tags.get("bridge") in (None, "no")
                )
            ):
                omitted.append(
                    {"id": wid, "reason": "grade-separated road excluded", "tags": tags}
                )
                continue
            width = cfg["road_width_default"]
            try:
                width = float(tags.get("width", width))
            except ValueError:
                pass
            if not math.isfinite(width) or width <= 0:
                raise ValueError(f"road {wid}: invalid width")
            width = (
                cfg["allowed_surface_ways"][wid]
                if wid in cfg.get("allowed_surface_ways", {})
                else max(5, min(width, 14))
            )
            roads.append(
                {
                    "id": wid,
                    "tags": tags,
                    "nodes": way["nodes"],
                    "points": pts,
                    "width": width,
                }
            )
        if tags.get("building") and wid not in consumed:
            if way["nodes"][0] != way["nodes"][-1]:
                raise ValueError(f"building {wid} is open")
            poly = Polygon(pts)
            if not poly.is_valid:
                omitted.append({"id": wid, "reason": "invalid building polygon"})
                continue
            poly = poly if bounds.covers(poly) else poly.intersection(bounds)
            h, rule = estimated_height(tags, f"way/{wid}", poly.area)
            buildings.append(
                {
                    "id": f"way/{wid}",
                    "tags": tags,
                    "height": h,
                    "height_rule": rule,
                    "geometry": mapping(poly),
                }
            )
        if tags.get("natural") == "water" and way["nodes"][0] == way["nodes"][-1]:
            waters.append(Polygon(pts).intersection(bounds))
    water = (
        water_override
        if water_override is not None
        else unary_union(waters).intersection(bounds)
    )
    if water.area < 10000:
        raise ValueError("waterfront missing: no complete usable water polygon")
    road_surface = unary_union(
        [
            LineString(r["points"]).buffer(r["width"] / 2, cap_style=1, join_style=2)
            for r in roads
        ]
    ).intersection(bounds)
    # Shared-node graph only. Crossing line segments do not imply junctions.
    graph, positions = {}, {}
    for r in roads:
        if r["tags"].get("name") not in cfg["route_streets"]:
            continue
        for nid, p in zip(r["nodes"], r["points"]):
            positions[nid] = p
        for a, b in zip(r["nodes"], r["nodes"][1:]):
            length = math.dist(positions[a], positions[b])
            graph.setdefault(a, {})[b] = length
            graph.setdefault(b, {})[a] = length
    anchors = [
        min(positions, key=lambda nid: math.dist(positions[nid], project(*p, origin)))
        for p in cfg["route_anchors"]
    ]
    ids = []
    for a, b in zip(anchors, anchors[1:]):
        ids.extend(shortest(graph, a, b)[:-1])
    ids.append(anchors[-1])
    route = [positions[n] for n in ids]
    # Densify driving gates to stay on the genuine centreline through bends.
    route_line = LineString(route)
    gates = [
        route_line.interpolate(d).coords[0]
        for d in range(0, int(route_line.length), 15)
    ] + [route[-1]]
    dense = []
    for a, b in zip(route, route[1:]):
        steps = max(1, math.ceil(math.dist(a, b) / 15))
        dense.extend(
            [
                (a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps)
                for i in range(steps)
            ]
        )
    route = dense + [route[-1]]
    spawn = [route[0][0], cfg["road_y"] + 1.5, -route[0][1]]
    dx, dz = route[1][0] - route[0][0], -(route[1][1] - route[0][1])
    yaw = math.degrees(math.atan2(-dx, -dz))
    return {
        "schema": 1,
        "identity": "stockholm",
        "origin": origin,
        "bounds": mapping(bounds),
        "roads": roads,
        "buildings": sorted(buildings, key=lambda b: b["id"]),
        "water": mapping(water),
        "road_surface": mapping(road_surface),
        "route": route,
        "drive_gates": gates,
        "route_nodes": ids,
        "route_length": route_line.length,
        "spawn": spawn + [yaw],
        "omitted": omitted,
    }


class PsdlWriter:
    def __init__(self, *, vertex_limit=65535):
        self.vertices, self.lookup, self.rooms, self.heights = [], {}, [], [0.0]
        self.textures = []
        self.water_rooms = []
        self.vertex_limit = vertex_limit

    def vertex(self, p):
        key = (round(p[0], 5), round(p[1], 5), round(-p[2], 5))
        if key not in self.lookup:
            if (
                self.vertex_limit is not None
                and len(self.vertices) >= self.vertex_limit
            ):
                raise ValueError("PSDL vertex-index limit reached; reduce slice")
            self.lookup[key] = len(self.vertices)
            self.vertices.append(key)
        return self.lookup[key]

    def height(self, h):
        if h not in self.heights:
            self.heights.append(h)
        return self.heights.index(h)

    def texture(self, name):
        if name not in self.textures:
            self.textures.append(name)
        idx = self.textures.index(name) + 1
        return [0x50 | ((idx // 256) & 7), idx % 256]

    def surface(self, geom, y, texture, road=False, water=False):
        # Tile meshes spatially; one shared vertex pool means identical seams.
        if geom.is_empty:
            return
        varying = callable(y)
        level = lru_cache(maxsize=None)(y) if varying else lambda x, n: y
        step = 100
        if varying:
            from elevation import conforming_boundary

            geom = conforming_boundary(geom)
        xmin, zmin, xmax, zmax = geom.bounds
        for x in range(
            math.floor(xmin / step) * step, math.ceil(xmax / step) * step, step
        ):
            for z in range(
                math.floor(zmin / step) * step, math.ceil(zmax / step) * step, step
            ):
                tile = geom.intersection(box(x, z, x + step, z + step))
                for poly in pieces(tile):
                    attrs = self.texture(texture)
                    patches = [poly]
                    if varying:
                        patches = [
                            patch
                            for sx in range(x, x + step, 25)
                            for sn in range(z, z + step, 25)
                            for patch in pieces(
                                poly.intersection(box(sx, sn, sx + 25, sn + 25))
                            )
                        ]
                    emitted_area = 0.0
                    for tri in (
                        tri
                        for patch in patches
                        for tri in (
                            height_triangles(
                                patch,
                                level,
                                interior=road
                                or texture in ("paving", "sthlm_oldtown_setts"),
                            )
                            if varying
                            else triangulate(patch)
                        )
                    ):
                        a, b, c = tri
                        emitted_area += (
                            abs(
                                (b[0] - a[0]) * (c[1] - a[1])
                                - (b[1] - a[1]) * (c[0] - a[0])
                            )
                            / 2
                        )
                        refs = [self.vertex((a, level(a, b), b)) for a, b in tri]
                        attrs.extend([0x80 | (0x28 if road else 0x30) | 1, *refs])
                    if abs(emitted_area - poly.area) > max(1e-4, poly.area * 1e-8):
                        raise ValueError("surface triangulation area mismatch")
                    perimeter = [
                        self.vertex((a, level(a, b), b))
                        for a, b in poly.exterior.coords[:-1]
                    ]
                    if len(attrs) > 2:
                        self.rooms.append(
                            (perimeter, attrs, 4 if water else 8 if road else 0)
                        )
                        if water:
                            self.water_rooms.append(len(self.rooms))

    def building(
        self,
        poly,
        height,
        texture,
        roof="roof",
        base=2.0,
        *,
        facade_repeat_width_m=4.0,
        facade_repeat_height_m=None,
    ):
        repeat_height = facade_repeat_height_m or (
            12 if texture == "tower_brick" else 5 if texture == "brick" else 3.2
        )
        attrs = []
        hb, ht = self.height(base), self.height(base + height)
        for ring in [poly.exterior, *poly.interiors]:
            pts = list(ring.coords)
            for a, b in zip(pts, pts[1:]):
                left, right = (
                    self.vertex((a[0], base, a[1])),
                    self.vertex((b[0], base, b[1])),
                )
                attrs += self.texture(texture)
                attrs += [
                    0x5E,
                    hb,
                    ht,
                    max(1, round(math.dist(a, b) / facade_repeat_width_m)),
                    max(1, round(height / repeat_height)),
                    left,
                    right,
                ]
                attrs += [0x3C, 0, ht, left, right]
        attrs += self.texture(roof)
        for tri in triangulate(poly):
            attrs += [0xB1, *[self.vertex((x, base + height, z)) for x, z in tri]]
        per = [self.vertex((x, base, z)) for x, z in poly.exterior.coords[:-1]]
        self.rooms.append((per, attrs, 0))

    def pyramid(self, poly, base, top, texture):
        coords = list(poly.exterior.coords)
        centre = poly.centroid
        attrs = self.texture(texture)
        for a, b in zip(coords, coords[1:]):
            pts = [(a[0], base, a[1]), (b[0], base, b[1]), (centre.x, top, centre.y)]
            # Upward winding after north→south conversion.
            if (b[0] - a[0]) * (centre.y - a[1]) - (b[1] - a[1]) * (
                centre.x - a[0]
            ) < 0:
                pts.reverse()
            attrs += [0xB1, *[self.vertex(p) for p in pts]]
        self.rooms.append(
            ([self.vertex((x, base, z)) for x, z in coords[:-1]], attrs, 0)
        )

    def vertex_pools(self, limit=65535):
        """Partition complete rooms into stable native vertex pools."""
        if not isinstance(limit, int) or not 1 <= limit <= 65535:
            raise ValueError("Invalid native vertex pool limit")
        water = set(self.water_rooms)
        if any(not 1 <= room <= len(self.rooms) for room in water):
            raise ValueError("Invalid water room reference")
        pools = []
        pool = None
        mapping = {}
        for room_id, (perimeter, attrs, flags) in enumerate(self.rooms, 1):
            refs = list(perimeter)
            slots = []
            cursor = 0
            while cursor < len(attrs):
                code = attrs[cursor]
                kind, subtype = (code >> 3) & 15, code & 7
                if kind == 10:
                    words, offsets = 1, ()
                elif kind == 2 and subtype == 2:
                    words, offsets = 4, (1, 2, 3, 4)
                elif kind in (5, 6) and subtype == 1:
                    words, offsets = 3, (1, 2, 3)
                elif kind == 11 and subtype == 6:
                    words, offsets = 6, (5, 6)
                elif kind == 7 and subtype == 4:
                    words, offsets = 4, (3, 4)
                else:
                    raise ValueError(f"Unsupported exported attribute {code}")
                if cursor + words >= len(attrs):
                    raise ValueError("Truncated exported attribute")
                slots.extend(cursor + offset for offset in offsets)
                refs.extend(attrs[cursor + offset] for offset in offsets)
                cursor += words + 1
            if any(
                not isinstance(v, int) or not 0 <= v < len(self.vertices) for v in refs
            ):
                raise ValueError("Invalid source vertex reference")
            unique = set(refs)
            if len(unique) > limit:
                raise ValueError("Single room exceeds native vertex pool limit")
            if (
                pool is None
                or len(mapping) + sum(v not in mapping for v in unique) > limit
                or len(pool.rooms) >= 65534
            ):
                pool = PsdlWriter()
                pool.textures = list(self.textures)
                pool.heights = list(self.heights)
                pools.append(pool)
                mapping = {}
            for original in refs:
                if original not in mapping:
                    mapping[original] = len(pool.vertices)
                    point = self.vertices[original]
                    pool.vertices.append(point)
                    pool.lookup[point] = mapping[original]
            remapped = list(attrs)
            for slot in slots:
                remapped[slot] = mapping[attrs[slot]]
            pool.rooms.append(([mapping[v] for v in perimeter], remapped, flags))
            if room_id in water:
                pool.water_rooms.append(len(pool.rooms))
        # Small existing parts preserve their native indexing and bytes.
        if len(pools) <= 1 and len(self.vertices) <= limit and len(self.rooms) <= 65534:
            return [self]
        return pools

    def write(self, path, center):
        if len(self.vertices) > 65535 or len(self.rooms) >= 65535:
            raise ValueError(
                "PSDL pool exceeds native index limits; split before writing"
            )
        out = bytearray(b"PSD0")

        def pack(fmt, *values):
            out.extend(struct.pack("<" + fmt, *values))

        pack("II", 2, len(self.vertices))
        for p in self.vertices:
            pack("3f", *p)
        pack("I", len(self.heights))
        for h in self.heights:
            pack("f", h)
        pack("I", len(self.textures) + 1)
        for t in self.textures:
            b = t.encode() + b"\0"
            pack("B", len(b))
            out.extend(b)
        pack("II", len(self.rooms) + 1, 0)
        for perimeter, attrs, _ in self.rooms:
            pack("II", len(perimeter), len(attrs))
            for v in perimeter:
                pack("HH", v, 0)
            pack("H" * len(attrs), *attrs)
        out.extend(bytes([0] + [r[2] for r in self.rooms]))
        out.extend(bytes(len(self.rooms) + 1))
        mins = [min(v[i] for v in self.vertices) for i in range(3)]
        maxs = [max(v[i] for v in self.vertices) for i in range(3)]
        mins[1] = -20.0
        for p in [mins, maxs, center]:
            pack("3f", *p)
        pack("fI", math.dist(mins, maxs) / 2, 0)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(out)


def textures(dest):
    palette = {
        "road": (62, 67, 70),
        "paving": (139, 137, 127),
        "grass": (94, 119, 77),
        "water": (50, 107, 135),
        "roof": (66, 76, 73),
        "copper": (72, 112, 98),
        "brick": (153, 80, 58),
        "tower_brick": (140, 72, 51),
        "ochre": (200, 171, 119),
        "cream": (216, 209, 181),
        "pink": (184, 143, 128),
        "gold": (212, 178, 64),
        "wood": (88, 69, 47),
        "foliage": (70, 104, 65),
    }
    dest.mkdir(parents=True, exist_ok=True)
    for name, color in palette.items():
        img = Image.new("RGB", (64, 64), color)
        draw = ImageDraw.Draw(img)
        if name in ["brick", "ochre", "cream", "pink"]:
            # Repeating facade module; one batched wall per footprint edge.
            draw.rectangle(
                (19, 12, 43, 48), fill=(60, 74, 77), outline=(230, 222, 196), width=3
            )
            draw.line((31, 12, 31, 48), fill=(205, 201, 184), width=2)
            draw.line((19, 30, 43, 30), fill=(205, 201, 184), width=2)
            draw.line((0, 62, 64, 62), fill=tuple(int(c * 0.8) for c in color), width=2)
        elif name == "tower_brick":
            for y in range(0, 64, 8):
                draw.line((0, y, 64, y), fill=(132, 68, 49))
            draw.rectangle((28, 17, 35, 40), fill=(47, 47, 39))
        elif name == "road":
            for x in range(0, 64, 7):
                for y in range(0, 64, 11):
                    draw.point((x, y), fill=(72, 77, 79))
        elif name == "water":
            for y in range(0, 64, 16):
                draw.line((0, y, 64, y + 3), fill=(62, 119, 145), width=1)
        elif name == "paving":
            for y in range(0, 64, 16):
                draw.line((0, y, 64, y), fill=(115, 116, 110))
            for x in range(0, 64, 16):
                draw.line((x, 0, x, 64), fill=(115, 116, 110))
        img.save(dest / (name + ".png"))


def build(output, minimal=False, profile="expanded"):
    expanded = profile == "expanded"
    cfg = json.loads(
        (
            ROOT / ("config/expanded.json" if expanded else "config/slice.json")
        ).read_text()
    )
    source_dir = ROOT / ("sources/expanded" if expanded else "sources")
    with gzip.open(source_dir / "osm.json.gz", "rt") as f:
        source = json.load(f)
    manifest = json.loads((source_dir / "manifest.json").read_text())
    if sha(source_dir / "osm.json.gz") != manifest["snapshot_sha256"]:
        raise ValueError("source snapshot checksum mismatch")
    if expanded:
        from expanded import normalized

        city = normalized(source, cfg)
        if not minimal:
            from street_details import apply as apply_street_details
            from road_details import normalized as normalize_road_details

            apply_street_details(city)
            city["road_details"] = normalize_road_details(source, cfg, city)
    else:
        city = normalize(source, cfg)
    if expanded and not minimal:
        from oldtown import apply as apply_oldtown

        apply_oldtown(source, cfg, city)
    out = output / "stockholm"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    if expanded:
        from expanded import ChunkedWriter

        writer = ChunkedWriter(city["spawn"])
    else:
        writer = PsdlWriter()
    road = shape(city["road_surface"])
    water = shape(city["water"])
    bounds = shape(city["bounds"])
    if minimal:
        road = unary_union(
            [
                LineString(r["points"]).buffer(r["width"] / 2)
                for r in city["roads"]
                if r["tags"].get("name") == "Norr Mälarstrand"
            ]
        ).intersection(bounds)
    if minimal:
        city["road_surface"] = mapping(road)
    write_json(out / "normalized.json", city)

    def ground_height(x, n):
        return 2.0

    def road_height(x, n):
        return cfg["road_y"]

    bridge_native_triangles = []
    if expanded:
        from terrain import TerrainGrid
        from elevation import apply

        terrain = TerrainGrid.from_project(ROOT, cfg["origin"])
        road_field, deck_field, base_roads, bridge_roads = apply(city, terrain)
        import tunnels

        tunnels.prepare(city, terrain)
        tunnels.write_roads(writer, city, terrain)
        if not minimal:
            from street_details import wrap_field

            road_field = wrap_field(road_field, city)
        ground_height = road_height = road_field.ground
        if not minimal:
            from road_details import surface_height

            detail_height = surface_height(city, ground_height, deck_field)
        if minimal:
            base_roads = road
            bridge_roads = Polygon()
        base_roads = tunnels.clip_surface(base_roads, city)
        city["ground_road_surface"] = mapping(base_roads)
        print("Meshing terrain-conforming roads", file=sys.stderr, flush=True)
        if minimal:
            writer.surface(base_roads, road_height, "road", road=True)
            writer.surface(bridge_roads, deck_field, "road", road=True)
        else:
            from road_surfaces import render as render_road_surfaces
            from road_surfaces import render_bridge_layers

            city["road_materials"] = {
                "base": render_road_surfaces(
                    writer,
                    city,
                    base_roads,
                    road_height,
                    road_height=lambda r, x, n: road_field.height_for_road(r, x, n),
                    station_height=road_field.height_at_station,
                ),
                "bridge": render_bridge_layers(
                    writer,
                    city,
                    terrain,
                    triangle_sink=bridge_native_triangles,
                ),
            }
        road = base_roads
    else:
        writer.surface(road, cfg["road_y"], "road", road=True)
    pond_records = []
    pond_area = Polygon()
    if expanded and not minimal:
        from ponds import prepare as prepare_ponds, partition_geometry

        pond_records = prepare_ponds(city, terrain, ground_height)
        pond_area = partition_geometry(pond_records)
    if not minimal:
        # Partition collision surfaces instead of stacking a ground plane beneath roads.
        quay = water.buffer(2).difference(water).intersection(bounds)
        paving = (
            road.buffer(2)
            .union(quay)
            .difference(road)
            .difference(water)
            .intersection(bounds)
        )
        if expanded:
            paving = tunnels.clip_surface(paving, city)
        print("Meshing shoulders", file=sys.stderr, flush=True)
        from oldtown import MATERIAL as oldtown_material
        from oldtown import partition as partition_oldtown

        paving = paving.difference(pond_area)
        stone_paving, paving = partition_oldtown(paving, city)
        writer.surface(stone_paving, ground_height if expanded else 2, oldtown_material)
        writer.surface(paving, ground_height if expanded else 2, "paving")
        land = (
            shape(city["land"]).difference(
                road.union(paving)
                .union(stone_paving)
                .union(shape(city["bridge_approach_surface"]))
            )
            if expanded
            else bounds.difference(water).difference(
                road.union(paving).union(stone_paving)
            )
        )
        if expanded:
            land = land.difference(shape(city["tunnel_terrain_cutout"]))
        print("Meshing land", file=sys.stderr, flush=True)
        land = land.difference(pond_area)
        stone_land, land = partition_oldtown(land, city)
        writer.surface(stone_land, ground_height if expanded else 2, oldtown_material)
        writer.surface(land, ground_height if expanded else 2, "grass")
        if pond_records:
            from ponds import write_mesh as write_pond_mesh

            write_pond_mesh(writer, pond_records, ground_height)
        remaining_water = water
        for region in city.get("water_regions", []):
            area = shape(region["geometry"]).intersection(remaining_water)
            writer.surface(area, region["height_m"], "water", water=True)
            remaining_water = remaining_water.difference(area)
        writer.surface(remaining_water, 0, "water", water=True)
        print("Meshing buildings and props", file=sys.stderr, flush=True)
        from church_materials import material_for as church_material_for

        from manor_materials import material_for as manor_material_for
        from district_facades import (
            StreetFrontages,
            export as export_district,
            material_for as district_material_for,
        )

        district_frontages = StreetFrontages(city, road_height)

        from landmarks import replaces as landmark_replaces, export as export_landmarks

        import additional_landmarks

        for b in city["buildings"]:
            if expanded and (landmark_replaces(b) or additional_landmarks.replaces(b)):
                continue
            if expanded and b["id"] in {"way/24488933", "way/1049742528"}:
                continue
            if b.get("street_detail"):
                continue
            index = int(hashlib.sha256(b["id"].encode()).hexdigest()[:8], 16) % 3
            manor_material = manor_material_for(b)
            manor_repeat = (
                {
                    "facade_repeat_width_m": manor_material["width_repeat_m"],
                    "facade_repeat_height_m": manor_material["height_repeat_m"],
                }
                if manor_material
                else {}
            )
            if manor_material:
                b["rendering"] = {"material_profile": manor_material}
            church_material = church_material_for(b)
            facade_repeat = (
                {
                    "facade_repeat_width_m": church_material["facade_repeat_width_m"],
                    "facade_repeat_height_m": church_material["facade_repeat_height_m"],
                }
                if church_material
                else {}
            )
            for p in pieces(shape(b["geometry"])):
                landmark = b["id"] == "relation/29368"
                church = (
                    b["tags"].get("building")
                    in {"church", "cathedral", "chapel", "religious"}
                    and b["height"] > 35
                )
                body_height = min(18.0, b["height"] - 20) if church else b["height"]
                if church:
                    b["rendering"] = {
                        "rule": "schematic nave and narrow spire; source height is total height, not full-height office facade",
                        "nave_height_m": body_height,
                        **(
                            {"material_profile": church_material}
                            if church_material
                            else {}
                        ),
                        "tower_position": "footprint representative point; not surveyed",
                    }
                district_material = (
                    district_material_for(b, city["origin"])
                    if not (landmark or church or church_material or manor_material)
                    else None
                )
                if district_material:
                    b["rendering"] = export_district(
                        writer, p, b, district_frontages, district_material
                    )
                    continue
                writer.building(
                    p,
                    24 if landmark else body_height,
                    church_material["textures"]["facade"]
                    if church_material
                    else manor_material["facade"]
                    if manor_material
                    else "brick"
                    if landmark
                    else ["ochre", "cream", "pink"][index],
                    church_material["textures"]["roof"]
                    if church_material
                    else manor_material["roof"]
                    if manor_material
                    else "copper"
                    if landmark
                    else "roof",
                    base=b.get("base_y", 2.0),
                    **manor_repeat,
                    **facade_repeat,
                )
                if church:
                    base = b.get("base_y", 2.0)
                    point = p.representative_point()
                    half = min(4, math.sqrt(p.area) / 8)
                    tower = box(
                        point.x - half, point.y - half, point.x + half, point.y + half
                    ).intersection(p)
                    for shaft in pieces(tower):
                        writer.building(
                            shaft,
                            b["height"] - body_height - 16,
                            church_material["textures"]["tower"]
                            if church_material
                            else "ochre",
                            church_material["textures"]["roof"]
                            if church_material
                            else "copper",
                            base=base + body_height,
                            **facade_repeat,
                        )
                        writer.pyramid(
                            shaft,
                            base + b["height"] - 16,
                            base + b["height"],
                            church_material["textures"]["roof"]
                            if church_material
                            else "copper",
                        )
        outer = max(pieces(bounds), key=lambda p: p.area)
        for a, b in zip(list(outer.exterior.coords), list(outer.exterior.coords)[1:]):
            wall = (
                LineString([a, b])
                .buffer(0.4, cap_style=2)
                .intersection(bounds)
                .difference(water)
            )
            for p in pieces(wall):
                writer.building(
                    p,
                    1.2,
                    "paving",
                    "paving",
                    base=ground_height(p.centroid.x, p.centroid.y),
                )
        if expanded:
            from props import placements, write as write_props
            from fences import write as write_fences
            from courthouse import export as export_courthouse

            export_landmarks(writer, city, out)
            additional_landmarks.export(writer, city, out)
            city["courthouse"] = export_courthouse(writer, city, out)
            from pavilion import export as export_pavilion

            city["waterfront_pavilion"] = export_pavilion(writer, city, out)
            from street_details import render, write as write_street_details
            from bridges import write as write_bridges
            from road_details import write as write_road_details

            render(writer, city, ground_height)

            city["props"] = placements(
                city, land, shape(city["road_surface"]), ground_height
            )
            city["props"].extend(write_fences(out, city, ground_height, source))
            city["props"].extend(write_street_details(out, city, ground_height))
            city["props"].extend(
                write_bridges(
                    out, city, deck_field, road_triangles=bridge_native_triangles
                )
            )
            city["props"].extend(tunnels.write(out, city))
            city["props"].extend(
                write_road_details(
                    out, city, height=ground_height, road_height=detail_height
                )
            )
            from ponds import write as write_ponds

            write_ponds(out, city)
            write_props(out, city["props"])
            write_json(out / "normalized.json", city)
        # Original primitive tower at source footprint's southeastern corner.
        landmark = next(b for b in city["buildings"] if b["id"] == "relation/29368")
        poly = shape(landmark["geometry"])
        landmark_base = landmark.get("base_y", 2.0)
        landmark_delta = landmark_base - 2.0
        x0, z0, x1, z1 = poly.bounds
        art = json.loads((ROOT / "assets/landmarks/stadshuset.json").read_text())
        tx, tz = (
            x1 + art["tower_offset_from_southeast"][0],
            z0 + art["tower_offset_from_southeast"][1],
        )
        half = art["tower_width"] / 2
        writer.building(
            box(tx - half, tz - half, tx + half, tz + half),
            art["tower_shaft_height"],
            "tower_brick",
            "copper",
            base=landmark_base,
        )
        # Open belfry on the shaft: four corner pillars, no giant apartment stack.
        for dx in [-8, 6]:
            for dz in [-8, 6]:
                writer.building(
                    box(tx + dx, tz + dz, tx + dx + 2, tz + dz + 2),
                    art["belfry_height"],
                    "tower_brick",
                    "copper",
                    base=78 + landmark_delta,
                )
        cap = box(tx - 9, tz - 9, tx + 9, tz + 9)
        writer.pyramid(cap, 90 + landmark_delta, 104 + landmark_delta, "copper")
        writer.building(
            box(tx - 0.4, tz - 0.4, tx + 0.4, tz + 0.4),
            3,
            "gold",
            "gold",
            base=104 + landmark_delta,
        )
        for dx, dz in [(-2, 0), (2, 0), (0, 2)]:
            writer.building(
                box(tx + dx - 0.7, tz + dz - 0.3, tx + dx + 0.7, tz + dz + 0.3),
                0.6,
                "gold",
                "gold",
                base=107 + landmark_delta,
            )
        # A modest original copper pitched roof silhouette on each large wing.
        wing = box(x0 + 2, z0 + 5, x0 + 19, z1 - 6).intersection(poly)
        for p in pieces(wing):
            writer.pyramid(p, 26 + landmark_delta, 31 + landmark_delta, "copper")
    # Bounds center also directs the existing engine's default RoadFan spawn.
    center = [city["spawn"][0], city["spawn"][1] - 1.5, city["spawn"][2]]
    print("Writing independent PSDL parts", file=sys.stderr, flush=True)
    writer.write(out / "city/stockholm.psdl", center)
    (out / "city/stockholm.water").write_text(
        "0.2\n" + "".join(f"{i}\n" for i in writer.water_rooms)
    )
    textures(out / "texture")
    if expanded and not minimal:
        from road_surfaces import write_textures as write_road_textures

        from oldtown import write_textures as write_oldtown_textures

        write_oldtown_textures(out / "texture")
        write_road_textures(out / "texture", city)
    from manor_materials import write as write_manor_materials

    write_manor_materials(out)
    from district_facades import write as write_district_materials

    write_district_materials(out)
    from church_materials import write as write_church_materials

    write_church_materials(out)
    from minimap import write as write_minimap

    write_json(out / "minimap.json", write_minimap(out, city, source))
    for index, tod in [(0, "morning"), (4, "noon"), (5, "cloudy-noon"), (8, "evening")]:
        key_pitch = -0.2 if index == 8 else -0.9
        key_color = (
            "0.85 0.50 0.30"
            if index == 8
            else ("0.55 0.58 0.62" if index == 5 else "0.85 0.82 0.75")
        )
        (out / f"city/stockholm.lt{index:02}").write_text(
            f"type: a\n{tod} {{\n"
            f"KeyHeading 2.2\nKeyPitch {key_pitch}\nKeyColor {key_color}\n"
            "Fill1Heading 0.0\nFill1Pitch -0.2\nFill1Color 0.16 0.18 0.22\n"
            "Fill2Heading 3.14\nFill2Pitch -0.3\nFill2Color 0.1 0.1 0.1\n"
            "Ambient -3355444\n}\n"
        )

    (out / "mod.toml").write_text(
        '[mod]\nid = "stockholm"\nname = "Stockholm — Stadshuset"\nversion = "0.1.0"\nauthor = "mm2-sthlm contributors"\n'
    )
    route = city["drive_gates"]
    race = out / "qa/waterfront"
    race.mkdir(parents=True, exist_ok=True)
    (race / "circuit0.aimap").write_text("[Density]\n0\n[Police]\n0\n[Opponent]\n0\n")
    params = [
        "CarType",
        "TimeofDay",
        "Weather",
        "Opponents",
        "Cops",
        "Ambient",
        "Peds",
        "NumLaps",
        "TimeLimit",
        "Difficulty",
    ]
    (race / "mmcircuitdata.csv").write_text(
        ",".join(["Description"] + params * 2)
        + "\n"
        + ",".join(
            ["Stockholm waterfront"]
            + ["0", "1", "0", "0", "0", "0", "0", "1", "300", "0"] * 2
        )
        + "\n"
    )
    (race / "circuit0waypoints.csv").write_text(
        "x,y,z,a,poly count,frame rate,state changes,texture changes,msg\n"
        + "".join(
            f"{x:.5f},{road_height(x, z):.5f},{-z:.5f},"
            f"{math.degrees(math.atan2(-(route[i + 1][0] - x), -(route[i + 1][1] - z))):.5f},"
            "5,0,0,0,\n"
            for i, (x, z) in enumerate(route[:-1])
        )
    )
    # Keep the dense waterfront circuit as a copied integration fixture.
    # Authored player events own all ten Circuit slots.
    if expanded and not minimal and (ROOT / "config/races/circuit.json").exists():
        from races import write as write_races
        from race_vehicle import write as write_race_vehicle
        from race_hud import write_race_hud

        write_race_vehicle(out)
        write_race_hud(out)
        write_races(out, city)
    else:
        shutil.copytree(race, out / "race/stockholm", dirs_exist_ok=True)
    # Data-provided spawn resets through the existing generic CLI.
    write_json(
        out / "map.json",
        {
            "schema": 1,
            "id": "stockholm",
            "units": "metres",
            "axes": "X east, Y up, Z south (current PSDL loader preserves axes)",
            "spawn": city["spawn"],
            "engine_base": "1a568de7996be6813d32ab4f50d2f3dc150f258c",
            "compatible_revisions": json.loads(
                (ROOT / "integration/rust-mm2/compatibility.json").read_text()
            )["expanded_revisions" if expanded else "compatible_revisions"],
            "time_of_day": 1,
            "weather": 0,
            "route_length_m": city["route_length"],
            "minimal": minimal,
            "profile": profile,
        },
    )
    write_json(out / "normalized.json", city)
    terrain_attribution = (
        "Terrain: Lantmäteriet Markhöjdmodell (1 m source grid), ©Lantmäteriet, CC BY 4.0.\n"
        "Modified: bilinear resampling to 10 m local grid, interpolation, road/shoulder profiles and terrain mesh simplification.\n"
        "https://creativecommons.org/licenses/by/4.0/\n"
        "https://www.lantmateriet.se/globalassets/geodata/geodataprodukter/anvandningsvillkor_for_vardefulla_datamangder.pdf\n"
        if expanded
        else ""
    )
    (out / "ATTRIBUTION.txt").write_text(
        "Geodata © OpenStreetMap contributors, ODbL 1.0.\nhttps://www.openstreetmap.org/copyright\nhttps://opendatacommons.org/licenses/odbl/1-0/\nOSM-derived database: normalized.json; source and generator: https://github.com/LinusU/mm2-sthlm\nOriginal procedural artwork and code: MIT. No retail assets.\n"
        + terrain_attribution
    )
    write_json(
        out / "checksums.json",
        {
            str(p.relative_to(out)): sha(p)
            for p in sorted(out.rglob("*"))
            if p.is_file() and p.name != "checksums.json"
        },
    )
    print(
        json.dumps(
            {
                "package": str(out),
                "roads": len(city["roads"]),
                "buildings": len(city["buildings"]),
                "route_m": round(city["route_length"]),
                "vertices": len(writer.vertices),
                "rooms": len(writer.rooms),
            },
            sort_keys=True,
        )
    )
    return out


def inspect_psdl(path, package):
    """Validate only our emitted PSDL subset, with bounded reads/references."""
    data = path.read_bytes()
    offset = 0

    def read(fmt):
        nonlocal offset
        size = struct.calcsize("<" + fmt)
        if offset + size > len(data):
            raise ValueError("truncated PSDL")
        result = struct.unpack_from("<" + fmt, data, offset)
        offset += size
        return result

    if read("4s")[0] != b"PSD0":
        raise ValueError("invalid PSDL magic")
    if read("I")[0] != 2:
        raise ValueError("unsupported PSDL header")
    count = read("I")[0]
    if count > 65535:
        raise ValueError("PSDL vertex count exceeds export contract")
    vertices = [read("3f") for _ in range(count)]
    if any(not all(math.isfinite(v) for v in p) for p in vertices):
        raise ValueError("nonfinite PSDL vertex")
    heights = [read("f")[0] for _ in range(read("I")[0])]
    names = []
    for _ in range(read("I")[0] - 1):
        length = read("B")[0]
        raw = read(f"{length}s")[0]
        if not raw.endswith(b"\0"):
            raise ValueError("unterminated PSDL texture")
        name = raw[:-1].decode("ascii")
        if not name or "/" in name or "\\" in name or ".." in name:
            raise ValueError("escaping PSDL texture reference")
        if not (package / "texture" / (name + ".png")).is_file():
            raise ValueError(f"missing PSDL texture {name}")
        names.append(name)
    rooms = read("I")[0]
    read("I")
    if not 1 < rooms < 65536:
        raise ValueError("invalid room count")
    triangles = 0
    for _ in range(rooms - 1):
        perimeter, words = read("II")
        for _ in range(perimeter):
            vertex, neighbor = read("HH")
            if vertex >= len(vertices) or neighbor >= rooms:
                raise ValueError("invalid PSDL perimeter index")
        end = offset + words * 2
        while offset < end:
            code = read("H")[0]
            kind, subtype = (code >> 3) & 15, code & 7
            if kind == 10:
                index = read("H")[0] + 256 * subtype - 1
                if not 0 <= index < len(names):
                    raise ValueError("invalid PSDL texture index")
            elif kind == 2 and subtype == 2:
                refs = read("4H")
                if any(v >= len(vertices) for v in refs):
                    raise ValueError("invalid PSDL road strip index")
                triangles += 2
            elif kind in [5, 6] and subtype == 1:
                refs = read("3H")
                if any(v >= len(vertices) for v in refs):
                    raise ValueError("invalid PSDL triangle index")
                triangles += 1
            elif kind == 11 and subtype == 6:
                bottom, top, _, _, left, right = read("6H")
                if max(bottom, top) >= len(heights) or max(left, right) >= len(
                    vertices
                ):
                    raise ValueError("invalid PSDL facade reference")
            elif kind == 7 and subtype == 4:
                _, top, left, right = read("4H")
                if top >= len(heights) or max(left, right) >= len(vertices):
                    raise ValueError("invalid PSDL collision reference")
            else:
                raise ValueError(f"unsupported exported attribute {code}")
        if offset != end:
            raise ValueError("PSDL attribute length mismatch")
    read(f"{rooms * 2}B")
    if (
        not all(math.isfinite(v) for v in read("10f"))
        or read("I")[0] != 0
        or offset != len(data)
    ):
        raise ValueError("invalid PSDL bounds or trailing content")
    return {
        "vertices": len(vertices),
        "rooms": rooms - 1,
        "triangles": triangles,
        "textures": len(names),
    }


CITY_PART_LIMIT = 129


def validated_city_parts(package, checks):
    """Reject manifests outside the pinned native engine's import envelope."""
    parts = ["city/stockholm.psdl"]
    manifest = package / "city/stockholm.chunks"
    if not manifest.exists():
        return parts
    lines = [
        line.strip()
        for line in manifest.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not lines or lines[0] != "MM2_CHUNKS 1":
        raise ValueError("unsupported city chunk manifest")
    if len(lines) == 1:
        raise ValueError("city chunk manifest lists no additional parts")
    if len(lines) > CITY_PART_LIMIT:
        raise ValueError("city chunk count exceeds native 129-part limit")
    for relative in lines[1:]:
        if (
            relative not in checks
            or not relative.startswith("city/")
            or not relative.endswith(".psdl")
            or "\\" in relative
            or ":" in relative
            or any(p in {"", ".", ".."} for p in relative.split("/"))
            or relative in parts
        ):
            raise ValueError("invalid or unverified city part")
        parts.append(relative)
    return parts


def validate(package):
    checks = json.loads((package / "checksums.json").read_text())
    for relative, digest in checks.items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("escaping package path")
        if not (package / path).resolve().is_relative_to(package.resolve()):
            raise ValueError("escaping package symlink")
        if sha(package / path) != digest:
            raise ValueError(f"corrupt package asset: {relative}")
    meta = json.loads((package / "map.json").read_text())
    if meta.get("schema") != 1 or meta.get("id") != "stockholm":
        raise ValueError("unsupported map package schema or identity")
    for required in [
        "city/stockholm.psdl",
        "mod.toml",
        "map.json",
        "ATTRIBUTION.txt",
        "normalized.json",
        "minimap.json",
        "tune/stockholm.mmhudmap",
        "geometry/hudmap_stockholm.pkg",
        "geometry/hudmap_tri.pkg",
        "geometry/hudmap_square.pkg",
    ]:
        if required not in checks:
            raise ValueError(f"package manifest missing {required}")
    from minimap import validate as validate_minimap

    minimap_meta = json.loads((package / "minimap.json").read_text())
    if any(resource not in checks for resource in minimap_meta["resources"]):
        raise ValueError("package manifest missing minimap asset")
    validate_minimap(package)
    part_paths = validated_city_parts(package, checks)
    reports = [inspect_psdl(package / p, package) for p in part_paths]
    binary = {key: sum(r[key] for r in reports) for key in reports[0]}
    binary["parts"] = len(reports)
    city = json.loads((package / "normalized.json").read_text())
    road = shape(city["road_surface"])
    if city.get("expanded") and not meta.get("minimal"):
        from expanded import EXCLUDED, INCLUDED, BLOCKED

        land = shape(city["land"])
        building_land = land.buffer(1)
        prepare(building_land)
        if any(
            not building_land.intersects(shape(b["geometry"]))
            or b["tags"].get("building") == "ship"
            for b in city["buildings"]
        ):
            raise ValueError(
                "building has no included-land contact or is an unmodeled ship"
            )
        if set(INCLUDED) != set(city["coverage"]):
            raise ValueError("missing included-island coverage")
        for name, ll in EXCLUDED.items():
            if land.distance(Point(project(*ll, city["origin"]))) < 20:
                raise ValueError(f"excluded island contains generated land: {name}")
        if any(r["tags"].get("name") in BLOCKED for r in city["roads"]):
            raise ValueError("external bridge was made driveable")
        for name, coverage in city["connected_routes"].items():
            if coverage["endpoint_distance_m"] > 200 or not road.buffer(0.01).covers(
                LineString(coverage["points"])
            ):
                raise ValueError(f"coverage route disconnected: {name}")
        shared = {}
        for r in city["roads"]:
            elevated = r["elevated_points"]
            source_nodes = {tuple(p): nid for nid, p in zip(r["nodes"], r["points"])}
            for point in elevated:
                nid = source_nodes.get(tuple(point[:2]))
                if nid is None:
                    continue
                if nid in shared and abs(shared[nid] - point[2]) > 1e-5:
                    raise ValueError("road junction elevation mismatch")
                shared[nid] = point[2]
        if city["terrain"]["coverage_nodata_cells"] != 0:
            raise ValueError("terrain coverage gaps")
        if not all(
            (p.get("breakable") or p.get("movable") or p.get("static"))
            and all(math.isfinite(v) for v in p["position"])
            for p in city["props"]
        ):
            raise ValueError("invalid native prop placement")
        for path in [
            "geometry/sthlm_tree.pkg",
            "tune/banger/sthlm_tree.dgbangerdata",
            "city/stockholm/props.pathset",
        ]:
            if path not in checks:
                raise ValueError("missing native breakable tree asset")
        if city.get("road_details"):
            for path in ("city/stockholm/decals.pathset", "texture/sthlm_paint.png"):
                if path not in checks:
                    raise ValueError(f"missing native road paint resource: {path}")
        for prop in city["props"]:
            paths = [f"geometry/{prop['asset']}.pkg"]
            if not prop.get("static"):
                paths.append(f"tune/banger/{prop['asset']}.dgbangerdata")
            for path in paths:
                if path not in checks:
                    raise ValueError(f"missing native prop asset: {path}")
    route = LineString(city["route"])
    if not meta.get("minimal") and not road.buffer(0.01).covers(route):
        raise ValueError("route leaves road surface")
    spawn = Point(city["spawn"][0], -city["spawn"][2])
    if not road.covers(spawn.buffer(1.5)):
        raise ValueError("spawn lacks chassis clearance")
    overlaps = []
    for b in city["buildings"]:
        if shape(b["geometry"]).intersects(route.buffer(1.5)):
            overlaps.append(b["id"])
    if overlaps:
        raise ValueError(f"buildings obstruct benchmark route: {overlaps}")
    # Expanded export checks every bounded patch during emission. Avoid a
    # second global triangulation of the complete connected city road polygon.
    area = None
    if not city.get("expanded"):
        triangles = list(triangulate(road))
        area = sum(Polygon(t).area for t in triangles)
        if abs(area - road.area) > 0.01:
            raise ValueError("road triangulation area mismatch")
    print(
        json.dumps(
            {
                "status": "pass",
                "route_m": city["route_length"],
                "building_route_overlaps": overlaps,
                "road_area": road.area,
                "triangulated_area": area,
                "spawn_clearance_m": 1.5,
                "binary": binary,
                "minimal": meta.get("minimal", False),
            },
            sort_keys=True,
        )
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["fetch", "build", "validate", "play", "smoke"]
    )
    parser.add_argument(
        "--profile", choices=["expanded", "stadshuset"], default="expanded"
    )
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--minimal", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--engine", type=Path, default=os.environ.get("MM2_ENGINE"))
    args, forward = parser.parse_known_args()
    package = args.output.resolve() / "stockholm"
    if args.command == "build":
        build(args.output.resolve(), args.minimal, args.profile)
    elif args.command == "validate":
        validate(package)
    elif args.command == "fetch":
        fetch()
    else:
        validate(package)
        if not args.engine or not args.engine.is_file():
            parser.error("supply --engine /absolute/path/to/mm2 or MM2_ENGINE")
        meta = json.loads((package / "map.json").read_text())
        forward = forward[1:] if forward[:1] == ["--"] else forward
        if any(
            flag.split("=")[0] in ["--city", "--dev-world", "--mods"]
            for flag in forward
        ):
            parser.error(
                "world selection is owned by the validated package; use a direct engine command for other worlds"
            )
        probe = subprocess.run(
            [
                str(args.engine.resolve()),
                "--dev-world",
                "--headless",
                "--frames",
                "1",
                "--no-profile",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        match = re.search(r"mm2-smoke commit=([^\s]+)", probe.stdout + probe.stderr)
        revision = match.group(1) if match else "unknown"
        if revision not in meta["compatible_revisions"]:
            parser.error(
                f"incompatible engine revision {revision}; tested revisions: {meta['compatible_revisions']}. See docs/INTEGRATION.md"
            )
        print(
            f"engine_revision={revision} © OpenStreetMap contributors (ODbL 1.0)",
            flush=True,
        )
        cmd = [
            str(args.engine.resolve()),
            "--mods",
            str(package.parent),
            "--city",
            "stockholm",
            "--no-profile",
            "--spawn=" + ",".join(str(v) for v in meta["spawn"]),
        ]
        if any(f.startswith("--spawn") for f in forward):
            cmd = [f for f in cmd if not f.startswith("--spawn=")]
        if args.command == "play" and "--time-of-day" not in forward:
            cmd += ["--time-of-day", str(meta["time_of_day"])]
        if args.command == "smoke":
            cmd += ["--headless", "--event", "circuit:0", "--bot"]
            if revision != meta["engine_base"] and "--bot-speed" not in forward:
                cmd += ["--bot-speed", "8"]
            if "--frames" not in forward:
                cmd += [
                    "--frames",
                    "15000" if revision != meta["engine_base"] else "7000",
                ]
        cmd += forward
        print(
            "engine=" + str(args.engine.resolve()) + " package=" + str(package),
            flush=True,
        )
        if args.command == "smoke":
            if revision == meta["engine_base"]:
                parser.error(
                    "full smoke needs the locked engine probe patch/PR; base engine supports interactive play only"
                )
            if any(
                f.split("=")[0]
                in ["--finish", "--reset-at", "--restart", "--restart-at", "--spawn"]
                for f in forward
            ):
                parser.error(
                    "continuous-drive smoke forbids teleport/reset overrides; use play -- --headless for separate probes"
                )
            with tempfile.TemporaryDirectory(prefix="sthlm-smoke-") as tmp:
                relocated = Path(tmp) / "stockholm"
                shutil.copytree(package, relocated)
                fixture = relocated / "qa/waterfront"
                if fixture.exists():
                    shutil.copytree(
                        fixture, relocated / "race/stockholm", dirs_exist_ok=True
                    )
                cmd[cmd.index("--mods") + 1] = tmp
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
                )
            print(result.stdout, end="", flush=True)
            if result.returncode:
                sys.exit(result.returncode)
            records = [
                line
                for line in result.stdout.splitlines()
                if line.startswith("smoke=headless-physics ")
            ]
            if not records:
                raise ValueError("engine produced no driving evidence record")
            validate_drive_record(records[-1])
            print(
                "stockholm-smoke acceptance=pass (complete continuous loop, no teleports)"
            )
        else:
            sys.exit(subprocess.call(cmd))


def validate_drive_record(record):
    fields = dict(item.split("=", 1) for item in record.split() if "=" in item)
    try:
        controls = fields["controls"].split("/")
        passed = (
            fields.get("status") == "pass"
            and fields.get("world") == "city/stockholm.psdl"
            and float(fields["travel"].removesuffix("m")) >= 500
            and float(fields["sim"].removesuffix("s")) >= 60
            and fields["resets"] == "0"
            and fields["finite"] == "true"
            and fields["race"] == "Complete"
            and fields["outcome"] == "finished"
            and all(int(v[:-1]) > 0 for v in controls)
            and all(
                int(v) == 0
                for v in fields.get("p_rec", "0r/0e")
                .replace("r", "")
                .replace("e", "")
                .split("/")
            )
        )
    except (KeyError, ValueError):
        passed = False
    if not passed:
        raise ValueError(
            "continuous driving acceptance failed; inspect engine record (distance/time/controls, resets, full course)"
        )


def fetch():
    # Explicit acquisition only; normal build/play never connects to the network.
    q = (ROOT / "sources/query.overpass").read_text()
    url = "https://overpass.kumi.systems/api/interpreter?" + urllib.parse.urlencode(
        {"data": q}
    )
    with urllib.request.urlopen(url, timeout=120) as r:
        data = r.read()
    parsed = json.loads(data)
    if "elements" not in parsed or "remark" in parsed:
        raise ValueError("Overpass returned incomplete/error response")
    target = ROOT / "sources/osm.json.gz"
    target.write_bytes(gzip.compress(data, mtime=0))
    write_json(
        ROOT / "sources/manifest.json",
        {
            "url": url.split("?")[0],
            "retrieved_utc": datetime.now(timezone.utc).isoformat(),
            "source_timestamp": parsed.get("osm3s", {}).get("timestamp_osm_base"),
            "snapshot_sha256": sha(target),
            "query_sha256": sha(ROOT / "sources/query.overpass"),
            "license": "ODbL-1.0",
            "attribution": "© OpenStreetMap contributors",
            "bounds_buffer": [18.0295, 59.3235, 18.0605, 59.3345],
        },
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as exc:
        sys.exit(f"sthlm: {exc}")

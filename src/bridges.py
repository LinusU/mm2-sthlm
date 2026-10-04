"""Original native static bridge structures; existing driveable deck unchanged."""

import json
import heapq
import math
import struct
from pathlib import Path

from PIL import Image
from shapely import line_merge
from shapely.geometry import LineString, Point, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

import props
from sthlm import triangulate

ROOT = Path(__file__).resolve().parents[1]
OVERRIDE = ROOT / "config/overrides/vasterbron-structure.json"
COLORS = {
    "bridge_concrete": (145, 146, 139),
    "bridge_steel": (109, 124, 121),
    "bridge_stone": (161, 156, 144),
    "bridge_dark": (61, 73, 66),
    "bridge_gold": (167, 145, 77),
    "bridge_timber": (106, 91, 71),
}


def beam(a, b, width, depth=None):
    """Closed rectangular member with outward native XYZ winding."""
    depth = width if depth is None else depth
    axis = [b[k] - a[k] for k in range(3)]
    length = math.sqrt(sum(v * v for v in axis))
    if length < 1e-6:
        return []
    axis = [v / length for v in axis]
    h = math.hypot(axis[0], axis[2])
    side = [axis[2] / h, 0, -axis[0] / h] if h > 1e-6 else [1, 0, 0]
    up = [
        side[1] * axis[2] - side[2] * axis[1],
        side[2] * axis[0] - side[0] * axis[2],
        side[0] * axis[1] - side[1] * axis[0],
    ]
    vertices = [
        tuple(p[k] + s * side[k] * width / 2 + t * up[k] * depth / 2 for k in range(3))
        for p in (a, b)
        for s, t in ((-1, -1), (-1, 1), (1, 1), (1, -1))
    ]
    faces = [
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ]
    centre = [(a[k] + b[k]) / 2 for k in range(3)]
    result = []
    for ids in faces:
        q = [vertices[i] for i in ids]
        u, v = [[q[j][k] - q[0][k] for k in range(3)] for j in (1, 2)]
        normal = [
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        ]
        if (
            sum(normal[k] * (sum(p[k] for p in q) / 4 - centre[k]) for k in range(3))
            < 0
        ):
            q.reverse()
        result += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
    return result


def deck_mesh(poly, height, thickness=0.7):
    """Slab below road; explicitly downward facing bottom triangles."""
    mesh = []
    for tri in triangulate(poly):
        top = tuple((x, height(x, n) - 0.04, -n) for x, n in tri)
        a, b, c = top
        if (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]) < 0:
            top = tuple(reversed(top))
        mesh.append(top)
        mesh.append(tuple((x, y - thickness, z) for x, y, z in reversed(top)))
    for ring in [poly.exterior, *poly.interiors]:
        coords = list(ring.coords)
        for (x, n), (xx, nn) in zip(coords, coords[1:]):
            a, b = (x, height(x, n) - 0.04, -n), (xx, height(xx, nn) - 0.04, -nn)
            c, d = (b[0], b[1] - thickness, b[2]), (a[0], a[1] - thickness, a[2])
            # Ring orientation varies; the narrow edge has both face directions.
            mesh.extend([(a, b, c), (a, c, d), (c, b, a), (d, c, a)])
    return mesh


def native_slab_mesh(road_triangles, thickness=0.7):
    """Offset exact native driveable triangles, retaining their tessellation.

    Sampling another triangulation can interpolate above a concave roadway
    profile between shared vertices. Reusing the road triangles guarantees a
    constant vertical gap everywhere, including profile bends and tile seams.
    """
    mesh = []
    edges = {}
    for triangle in road_triangles:
        top = tuple((x, y - 0.04, z) for x, y, z in triangle)
        a, b, c = top
        if (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]) < 0:
            top = tuple(reversed(top))
        mesh.append(top)
        mesh.append(tuple((x, y - thickness, z) for x, y, z in reversed(top)))
        for a, b in zip(top, top[1:] + top[:1]):
            key = tuple(sorted((a, b)))
            count, _ = edges.get(key, (0, (a, b)))
            edges[key] = (count + 1, (a, b))
    dangling = [edge for count, edge in edges.values() if count == 1]
    for a, b in slab_boundary_segments(dangling):
        c, d = (b[0], b[1] - thickness, b[2]), (a[0], a[1] - thickness, a[2])
        mesh.extend([(a, c, b), (a, d, c)])
    return mesh


def slab_boundary_segments(edges, tolerance=0.0001):
    """Remove internal T-junction edges without merging stacked deck levels.

    A strip can share one long edge with several shorter fan edges. Exact
    endpoint counting leaves all of them exposed. Opposite directed edges on
    the same 3D line cancel their overlapping intervals; any uncovered ends
    remain real slab boundaries. Identically directed exterior edges and
    vertically separate roads retain their collision faces.
    """
    lines = [LineString([(a[0], a[2]), (b[0], b[2])]) for a, b in edges]
    tree = STRtree(lines)
    for index, (a, b) in enumerate(edges):
        dx, dz = b[0] - a[0], b[2] - a[2]
        squared = dx * dx + dz * dz
        if squared <= tolerance * tolerance:
            continue
        length = math.sqrt(squared)
        covered = []
        for other in tree.query(lines[index].buffer(tolerance)):
            if other == index:
                continue
            c, d = edges[other]
            if dx * (d[0] - c[0]) + dz * (d[2] - c[2]) >= 0:
                continue
            projected = []
            for point in (c, d):
                px, pz = point[0] - a[0], point[2] - a[2]
                t = (px * dx + pz * dz) / squared
                if (
                    abs(px * dz - pz * dx) / length > tolerance
                    or abs(point[1] - (a[1] + t * (b[1] - a[1]))) > tolerance
                ):
                    break
                projected.append(t)
            if len(projected) != 2:
                continue
            lo, hi = max(0, min(projected)), min(1, max(projected))
            if (hi - lo) * length > tolerance:
                covered.append((lo, hi))
        cursor = 0.0
        for lo, hi in sorted(covered) + [(1.0, 1.0)]:
            if lo > cursor and (lo - cursor) * length > tolerance:
                yield (
                    tuple(a[k] + cursor * (b[k] - a[k]) for k in range(3)),
                    tuple(a[k] + lo * (b[k] - a[k]) for k in range(3)),
                )
            cursor = max(cursor, hi)


def captured_decks(surface, height, spawn, thickness=0.7):
    """Use the same source writer as the actual bridge roadway export."""
    from expanded import ChunkedWriter

    writer = ChunkedWriter(spawn)
    writer.surface(surface, height, "road", road=True)
    for part in writer.parts.values():
        for _, attrs, flags in part.rooms:
            if flags != 8:
                continue
            # Capture emits one texture prefix followed by native RoadFans.
            triangles = []
            for index in range(2, len(attrs), 4):
                if attrs[index] != 0xA9:
                    raise ValueError("unexpected native bridge RoadFan record")
                triangles.append(
                    tuple(part.vertices[v] for v in attrs[index + 1 : index + 4])
                )
            if triangles:
                yield native_slab_mesh(triangles, thickness)


def alignment(roads):
    lines = [LineString(r["points"]) for r in roads]
    main = max(lines, key=lambda line: line.length)
    if main.coords[0][1] < main.coords[-1][1]:
        main = LineString(list(main.coords)[::-1])
    lines = [
        line
        if math.dist(line.coords[0], main.coords[0])
        < math.dist(line.coords[-1], main.coords[0])
        else LineString(list(line.coords)[::-1])
        for line in lines
    ]
    count = max(2, math.ceil(main.length / 5))
    coords = []
    for i in range(count + 1):
        points = [
            line.interpolate(i / count, normalized=True).coords[0] for line in lines
        ]
        coords.append(tuple(sum(p[k] for p in points) / len(points) for k in range(2)))
    return LineString(coords)


def landmark_mesh(roads, height, cfg):
    line = alignment(roads)
    half = max(
        LineString(r["points"]).distance(line.interpolate(0.5, normalized=True))
        + r["width"] / 2
        for r in roads
    )
    concrete, steel = [], []

    def point(t, lateral=0, y=None):
        d = min(line.length, max(0, t * line.length))
        p = line.interpolate(d)
        a, b = (
            line.interpolate(max(0, d - 1)),
            line.interpolate(min(line.length, d + 1)),
        )
        dx, dn = b.x - a.x, b.y - a.y
        length = math.hypot(dx, dn)
        x, n = p.x - dn / length * lateral, p.y + dx / length * lateral
        return (x, height(x, n) if y is None else y, -n)

    stations = cfg["arch_stations"]
    rib_offsets = (-half + 1.2, half - 1.2)
    for start, end in zip(stations, stations[1:]):
        crown = point((start + end) / 2)[1] - cfg["arch_crown_below_deck"]
        foot = min(cfg["arch_foot_y"], crown - 1)

        def arch_y(t):
            u = (t - start) / (end - start)
            return foot + (crown - foot) * 4 * u * (1 - u)

        for side in rib_offsets:
            count = cfg["arch_segments"]
            for i in range(count):
                t, tt = (
                    start + (end - start) * i / count,
                    start + (end - start) * (i + 1) / count,
                )
                steel += beam(
                    point(t, side, arch_y(t)),
                    point(tt, side, arch_y(tt)),
                    cfg["arch_rib_width"],
                    cfg["arch_rib_depth"],
                )
            count = max(
                2, math.ceil((end - start) * line.length / cfg["spandrel_spacing_m"])
            )
            for i in range(count + 1):
                t = start + (end - start) * i / count
                top = point(t, side)[1] - cfg["deck_thickness_m"] - 0.1
                steel += beam(
                    point(t, side, min(arch_y(t), top - 0.1)), point(t, side, top), 0.38
                )
        for i in range(1, 7):
            t = start + (end - start) * i / 7
            steel += beam(
                point(t, rib_offsets[0], arch_y(t)),
                point(t, rib_offsets[1], arch_y(t)),
                0.25,
            )
    for t in stations:
        for side in rib_offsets:
            concrete += beam(point(t, side, -0.6), point(t, side, 2.1), 3.2, 4.0)
    count = math.ceil(line.length / 3)
    for side in (-half - 0.35, half + 0.35):
        for i in range(count):
            a, b = point(i / count, side), point((i + 1) / count, side)
            concrete += beam(
                (a[0], a[1] + 0.12, a[2]), (b[0], b[1] + 0.12, b[2]), 0.3, 0.24
            )
            for rise in (
                0.55,
                cfg["rail_height_m"],
                1.65,
                2.05,
                cfg["safety_wire_height_m"],
            ):
                steel += beam(
                    (a[0], a[1] + rise, a[2]),
                    (b[0], b[1] + rise, b[2]),
                    0.055 if rise <= cfg["rail_height_m"] else 0.022,
                )
            steel += beam(
                (a[0], a[1] + 0.24, a[2]),
                (a[0], a[1] + cfg["safety_wire_height_m"], a[2]),
                0.07,
            )
            for j in range(1, 6):
                p = point((i + j / 6) / count, side)
                steel += beam(
                    (p[0], p[1] + 0.24, p[2]),
                    (p[0], p[1] + cfg["rail_height_m"], p[2]),
                    0.025,
                )
    return [("bridge_concrete", concrete), ("bridge_steel", steel)]


def crossing_constraints(roads, bridge_ids, minimum_clearance=5.5):
    """Source crossing probes, excluding actual shared-node junctions.

    Clearance is an authored gameplay envelope including the 0.7m slab,
    not a survey. Source layers determine which deck is uppermost.
    """
    lines = [LineString(r["points"]) for r in roads]
    tree = STRtree(lines)
    bridges = set(bridge_ids)
    result = []
    for i, upper in enumerate(roads):
        if upper["id"] not in bridges:
            continue
        layer = int(upper["tags"].get("layer", 1))
        for j in tree.query(lines[i], predicate="intersects"):
            lower = roads[int(j)]
            if i == j or set(upper["nodes"]) & set(lower["nodes"]):
                continue
            lower_layer = int(lower["tags"].get("layer", 0))
            if lower_layer >= layer:
                continue
            crossing = lines[i].intersection(lines[int(j)])
            points = (
                [crossing]
                if crossing.geom_type == "Point"
                else (
                    list(crossing.geoms) if crossing.geom_type == "MultiPoint" else []
                )
            )
            for point in points:
                result.append(
                    {
                        "upper": upper["id"],
                        "lower": lower["id"],
                        "position": [point.x, point.y],
                        "minimum_vertical_separation_m": minimum_clearance,
                    }
                )
    return result


def enforce_crossing_clearance(roads, bridge_ids, clearance=5.5):
    """Lift decks with source-graph-distance envelopes, preserving junctions.

    A per-way envelope restarted at every connecting node spreads a lift across
    the whole city and leaves shared endpoints at different heights. Here each
    genuine source node is one height variable. A lift fades with cumulative
    road distance from its crossing, never reconnecting separate XY crossings.
    """
    probes = crossing_constraints(roads, bridge_ids, clearance)
    keys, xy, levels, graph, chains, stations = {}, [], [], [], {}, {}
    lookup = {r["id"]: r for r in roads}
    lines = {r["id"]: LineString(r["points"]) for r in roads}
    for road in roads:
        source = {tuple(p): n for n, p in zip(road["nodes"], road["points"])}
        chain = []
        ds = []
        for i, point in enumerate(road["elevated_points"]):
            node = source.get(tuple(point[:2]))
            key = ("node", node) if node is not None else (road["id"], i)
            if key not in keys:
                keys[key] = len(levels)
                levels.append(point[2])
                xy.append(point[:2])
                graph.append({})
            index = keys[key]
            levels[index] = max(levels[index], point[2])
            chain.append(index)
            ds.append(lines[road["id"]].project(Point(point[:2])))
        chains[road["id"]], stations[road["id"]] = chain, ds
        for left, right in zip(chain, chain[1:]):
            distance = math.dist(xy[left], xy[right])
            if distance > 1e-6:
                graph[left][right] = graph[right][left] = distance

    def bracket(road_id, position):
        ds, chain = stations[road_id], chains[road_id]
        station = lines[road_id].project(Point(position))
        for i in range(len(ds) - 1):
            if ds[i] <= station <= ds[i + 1] and ds[i + 1] > ds[i]:
                return (
                    chain[i],
                    chain[i + 1],
                    (station - ds[i]) / (ds[i + 1] - ds[i]),
                    station,
                )
        return chain[-1], chain[-1], 0.0, station

    def sample(road_id, position):
        left, right, t, _ = bracket(road_id, position)
        return levels[left] * (1 - t) + levels[right] * t

    adjustments = []
    for _ in range(8):
        changed = False
        for probe in sorted(
            probes, key=lambda p: int(lookup[p["upper"]]["tags"].get("layer", 1))
        ):
            upper, lower, position = probe["upper"], probe["lower"], probe["position"]
            deficit = sample(lower, position) + clearance - sample(upper, position)
            if deficit <= 0.02:
                continue
            left, right, t, _ = bracket(upper, position)
            segment_length = math.dist(xy[left], xy[right])
            radius = max(120, deficit * math.pi / 0.12)
            distances = {left: t * segment_length, right: (1 - t) * segment_length}
            pending = [(distance, node) for node, distance in distances.items()]
            heapq.heapify(pending)
            while pending:
                distance, node = heapq.heappop(pending)
                if distance != distances[node]:
                    continue
                for neighbour, length in graph[node].items():
                    candidate = distance + length
                    if candidate < radius and candidate < distances.get(
                        neighbour, math.inf
                    ):
                        distances[neighbour] = candidate
                        heapq.heappush(pending, (candidate, neighbour))
            weights = {
                node: (1 + math.cos(math.pi * distance / radius)) / 2
                for node, distance in distances.items()
                if distance < radius
            }
            low_a, low_b, low_t, _ = bracket(lower, position)
            response = (
                weights.get(left, 0) * (1 - t)
                + weights.get(right, 0) * t
                - weights.get(low_a, 0) * (1 - low_t)
                - weights.get(low_b, 0) * low_t
            )
            if response <= 0.05:
                # An extremely short connecting loop cannot support this
                # estimated clearance without an implausibly large city lift.
                continue
            lift = deficit / response
            for node, weight in weights.items():
                levels[node] += lift * weight
            changed = True
            adjustments.append(
                {**probe, "lift_m": round(lift, 3), "blend_radius_m": round(radius, 3)}
            )
        if not changed:
            break
    for road in roads:
        road["elevated_points"] = [
            [*point[:2], levels[node]]
            for point, node in zip(road["elevated_points"], chains[road["id"]])
        ]
    for probe in probes:
        probe["actual_vertical_separation_m"] = round(
            sample(probe["upper"], probe["position"])
            - sample(probe["lower"], probe["position"]),
            3,
        )
    return {
        "minimum_vertical_separation_m": clearance,
        "provenance": "Original estimated gameplay clearance, not surveyed bridge elevations",
        "adjustments": adjustments,
        "probes": probes,
        "unresolved": [
            p for p in probes if p["actual_vertical_separation_m"] < clearance - 0.03
        ],
    }


def crossing_report(city, road_height, deck_height):
    """Record reproducible lower-road/deck samples with native XYZ positions."""
    bridges = set(city["bridge_ways"])
    probes = crossing_constraints(city["roads"], bridges)
    for probe in probes:
        x, n = probe["position"]
        upper = (
            deck_height.height_for_road(probe["upper"], x, n)
            if hasattr(deck_height, "height_for_road")
            else deck_height(x, n)
        )
        field = deck_height if probe["lower"] in bridges else road_height
        lower = (
            field.height_for_road(probe["lower"], x, n)
            if hasattr(field, "height_for_road")
            else field(x, n)
        )
        probe.update(
            {
                "deck_y": round(upper, 3),
                "lower_road_y": round(lower, 3),
                "underside_clearance_m": round(upper - 0.74 - lower, 3),
                "native_position": [round(x, 3), round(lower, 3), round(-n, 3)],
            }
        )
    return probes


def source_height(roads, field):
    """Keep structure levels attached to their source roads at deck crossings."""
    if not hasattr(field, "height_for_road"):
        return field
    lines = [LineString(r["points"]) for r in roads]
    tree = STRtree(lines)

    def height(x, n):
        road = roads[int(tree.nearest(Point(x, n)))]
        return field.height_for_road(road, x, n)

    return height


def corridor_mesh(roads, city, height, cfg):
    """Railings on sourced deck edges with openings at real connection nodes.

    Each road follows its own alignment. Averaging unrelated parallel ramps
    creates invented structure between them, so these meshes use the union
    of source corridors and explicitly keep approach portals open.
    """
    lanes = unary_union(
        [
            LineString(r["points"]).buffer(r["width"] / 2, cap_style=1, join_style=2)
            for r in roads
        ]
    )
    bridge_ids = {r["id"] for r in roads}
    nodes = {n for r in roads for n in r["nodes"]}
    connections = {
        n
        for r in city["roads"]
        if r["id"] not in bridge_ids
        for n in r["nodes"]
        if n in nodes
    }
    degree = {}
    positions = {}
    for r in roads:
        positions.update(zip(r["nodes"], r["points"]))
        for a, b in zip(r["nodes"], r["nodes"][1:]):
            degree[a] = degree.get(a, 0) + 1
            degree[b] = degree.get(b, 0) + 1
    portals = [
        Point(positions[n]).buffer(roads[0]["width"] + 2)
        for n in nodes
        if n in connections or degree.get(n) == 1
    ]
    openings = unary_union(portals)
    rail = []
    material = cfg.get("material", "bridge_steel")
    polygons = [lanes] if lanes.geom_type == "Polygon" else list(lanes.geoms)
    for poly in polygons:
        for ring in [poly.exterior, *poly.interiors]:
            edge = LineString(ring.coords).difference(openings)
            parts = [edge] if edge.geom_type == "LineString" else list(edge.geoms)
            for part in parts:
                if part.is_empty:
                    continue
                count = max(1, math.ceil(part.length / 3))
                for i in range(count):
                    a, b = [
                        part.interpolate(t / count, normalized=True) for t in (i, i + 1)
                    ]
                    aa, bb = (
                        (a.x, height(a.x, a.y), -a.y),
                        (b.x, height(b.x, b.y), -b.y),
                    )
                    for rise in (0.45, 1.12):
                        rail += beam(
                            (aa[0], aa[1] + rise, aa[2]),
                            (bb[0], bb[1] + rise, bb[2]),
                            0.065,
                        )
                    rail += beam(
                        (aa[0], aa[1] + 0.05, aa[2]),
                        (aa[0], aa[1] + 1.16, aa[2]),
                        0.085,
                    )
    groups = [(material, rail)] if rail else []
    lower_corridors = unary_union(
        [
            LineString(r["points"]).buffer(r["width"] / 2 + 3)
            for r in city["roads"]
            if r["id"] not in bridge_ids
        ]
    )
    support = []
    steel = []
    axes = line_merge(unary_union([LineString(r["points"]) for r in roads]))
    axes = [axes] if axes.geom_type == "LineString" else list(axes.geoms)
    half = min(r["width"] for r in roads) / 2 - 0.8
    for axis in axes:
        if axis.length < 12:
            continue

        def point(t, side=0, y=None):
            d = max(0, min(axis.length, t * axis.length))
            p = axis.interpolate(d)
            a, b = (
                axis.interpolate(max(0, d - 0.5)),
                axis.interpolate(min(axis.length, d + 0.5)),
            )
            dx, dn = b.x - a.x, b.y - a.y
            length = math.hypot(dx, dn)
            x, n = p.x - dn / length * side, p.y + dx / length * side
            return (x, height(x, n) - 0.85 if y is None else y, -n)

        def member(a, b, width, depth=None):
            # Authored members must never fill a real lower roadway corridor.
            if (
                LineString([(a[0], -a[2]), (b[0], -b[2])])
                .buffer(width / 2)
                .intersects(lower_corridors)
            ):
                return []
            return beam(a, b, width, depth)

        count = max(1, math.ceil(axis.length / 4))
        for side in (-half, half):
            for i in range(count):
                a, b = point(i / count, side), point((i + 1) / count, side)
                steel += beam(a, b, 0.25, 0.38)
        if cfg["style"] in {"stone_arch", "steel_arch"}:
            spans = max(1, round(axis.length / cfg.get("span_length_estimate_m", 35)))
            for span in range(spans):
                start, end = span / spans, (span + 1) / spans
                crown = point((start + end) / 2)[1] - 0.5
                foot = min(crown - 0.5, 0.5)

                def arch_y(t):
                    u = (t - start) / (end - start)
                    return foot + (crown - foot) * 4 * u * (1 - u)

                for side in (-half, half):
                    for i in range(20):
                        t, tt = (
                            start + (end - start) * i / 20,
                            start + (end - start) * (i + 1) / 20,
                        )
                        a, b = point(t, side), point(tt, side)
                        a = (a[0], min(a[1] - 0.3, arch_y(t)), a[2])
                        b = (b[0], min(b[1] - 0.3, arch_y(tt)), b[2])
                        support += member(
                            a, b, 0.7 if cfg["style"] == "stone_arch" else 0.3, 0.7
                        )
    if steel:
        groups.append(("bridge_steel", steel))
    if support:
        groups.append((cfg.get("support_material", "bridge_concrete"), support))
    return groups


def write_asset(out, name, groups, source):
    vertices = [v for _, triangles in groups for tri in triangles for v in tri]
    origin = [min(v[k] for v in vertices) for k in range(3)]
    shaders = struct.pack("<2I", 1, len(groups))
    for texture, _ in groups:
        shaders += props.lp(texture) + struct.pack(
            "<17f", *([1, 1, 1, 1] * 2 + [0, 0, 0, 0] * 2 + [0])
        )
    data = b"PKG3" + props.chunk("shaders", shaders)
    for index, (_, triangles) in enumerate(groups):
        # Each PKG geometry chunk has a u16 vertex index limit.
        for offset in range(0, len(triangles), 20000):
            local = [
                tuple(tuple(v[k] - origin[k] for k in range(3)) for v in tri)
                for tri in triangles[offset : offset + 20000]
            ]
            data += props.chunk(f"PART{index}_{offset}_H", props.geometry(local, index))
    (out / f"geometry/{name}.pkg").write_bytes(data)
    return {
        "source": source,
        "kind": "bridge_structure",
        "asset": name,
        "position": origin,
        "breakable": False,
        "static": True,
        "movable": False,
        "triangle_count": len(vertices) // 3,
    }


def source_bridge_groups(roads):
    """Same-named bridge components joined only by exact source nodes.

    A local layer change does not open a road approach in the middle of one
    sourced span. Unconnected equal-named stacked or parallel spans retain
    their own railing boundaries and physical height ownership.
    """
    named = {}
    for road in roads:
        name = road["tags"].get("name", "Unnamed viaduct")
        named.setdefault(name, []).append(road)
    groups = []
    for name, members in sorted(named.items()):
        by_id = {road["id"]: road for road in members}
        owners = {}
        for road in members:
            for node in road["nodes"]:
                owners.setdefault(node, set()).add(road["id"])
        remaining = set(by_id)
        while remaining:
            todo = [min(remaining)]
            component = set()
            while todo:
                owner = todo.pop()
                if owner in component:
                    continue
                component.add(owner)
                for node in by_id[owner]["nodes"]:
                    todo.extend(owners[node] - component)
            remaining.difference_update(component)
            groups.append((name, [by_id[owner] for owner in sorted(component)]))
    return groups


def physical_bridge_groups(roads):
    """Perimeters for compatible parallel source components of one deck.

    Exact source nodes still define each component. Nearby disconnected
    carriageways can share one physical bridge edge, while their internal
    buffer boundaries are not rail locations. Stacked layers, incompatible
    profiles, branching components and distant equal names stay separate.
    """
    components = source_bridge_groups(roads)
    axes = []
    for _, members in components:
        neighbours, positions = {}, {}
        for road in members:
            positions.update(zip(road["nodes"], road["points"]))
            for a, b in zip(road["nodes"], road["nodes"][1:]):
                neighbours.setdefault(a, set()).add(b)
                neighbours.setdefault(b, set()).add(a)
        ends = sorted(n for n, adjacent in neighbours.items() if len(adjacent) == 1)
        if len(ends) != 2 or any(len(adjacent) > 2 for adjacent in neighbours.values()):
            axes.append(None)
            continue
        path, previous, node = [], None, ends[0]
        while True:
            path.append(positions[node])
            onward = neighbours[node] - {previous}
            if not onward:
                break
            previous, node = node, next(iter(onward))
        axes.append(LineString(path))

    lines = [[LineString(r["points"]) for r in members] for _, members in components]
    from elevation import RoadField

    fields = [RoadField(members, None, bridge=True) for _, members in components]
    layers = [
        {int(r["tags"].get("layer", 1)) for r in members} for _, members in components
    ]
    links = {i: set() for i in range(len(components))}

    def profile(index, point):
        owner = min(
            range(len(lines[index])), key=lambda k: lines[index][k].distance(point)
        )
        return fields[index].height_for_road(
            components[index][1][owner], point.x, point.y
        )

    for i, (name, members) in enumerate(components):
        axis = axes[i]
        if axis is None or axis.length < 20:
            continue
        for j in range(i):
            other_axis = axes[j]
            if name != components[j][0] or layers[i] != layers[j] or other_axis is None:
                continue
            corridor = (
                max(r["width"] for r in members)
                + max(r["width"] for r in components[j][1])
            ) / 2 + 2
            if (
                min(axis.length, other_axis.length)
                / max(axis.length, other_axis.length)
                < 0.8
                or axis.hausdorff_distance(other_axis) > corridor + 20
                or axis.intersection(other_axis.buffer(corridor)).length / axis.length
                < 0.9
                or other_axis.intersection(axis.buffer(corridor)).length
                / other_axis.length
                < 0.9
            ):
                continue
            a, b = (
                axis.interpolate(0.25, normalized=True),
                axis.interpolate(0.75, normalized=True),
            )
            c, d = (
                other_axis.interpolate(0.25, normalized=True),
                other_axis.interpolate(0.75, normalized=True),
            )
            dx, dn, ox, on = b.x - a.x, b.y - a.y, d.x - c.x, d.y - c.y
            cosine = abs(dx * ox + dn * on) / max(
                math.hypot(dx, dn) * math.hypot(ox, on), 1e-9
            )
            if cosine < 0.95:
                continue
            probes = [
                Point(p[:2])
                for k in (i, j)
                for r in components[k][1]
                for p in r["elevated_points"]
            ]
            if max(abs(profile(i, p) - profile(j, p)) for p in probes) > 2.5:
                continue
            links[i].add(j)
            links[j].add(i)
    remaining, grouped = set(links), []
    while remaining:
        todo, component = [min(remaining)], set()
        while todo:
            i = todo.pop()
            if i in component:
                continue
            component.add(i)
            todo.extend(links[i] - component)
        remaining.difference_update(component)
        members = [r for i in sorted(component) for r in components[i][1]]
        grouped.append(
            (components[min(component)][0], sorted(members, key=lambda r: r["id"]))
        )
    return grouped


def write(out, city, deck_field, road_triangles=None):
    """Return static placement records for merging into props.write pathset."""
    cfg = json.loads(OVERRIDE.read_text())
    (out / "geometry").mkdir(parents=True, exist_ok=True)
    (out / "texture").mkdir(parents=True, exist_ok=True)
    for texture, color in COLORS.items():
        Image.new("RGB", (16, 16), color).save(out / f"texture/{texture}.png")
    instances = []
    surface = shape(city["bridge_road_surface"])
    # The road writer may use textured quads plus fans. Its emitted facets,
    # including rounded native vertices and exact strip diagonals, are the
    # authority for slabs. Retain the legacy capture only for older callers.
    slabs = (
        [native_slab_mesh(road_triangles, cfg["deck_thickness_m"])]
        if road_triangles is not None and road_triangles
        else []
        if road_triangles is not None
        else captured_decks(surface, deck_field, city["spawn"], cfg["deck_thickness_m"])
    )
    for index, triangles in enumerate(slabs):
        instances.append(
            write_asset(
                out,
                f"sthlm_deck_{index}",
                [("bridge_concrete", triangles)],
                "bridge deck underside",
            )
        )
    inventory = json.loads(
        (ROOT / "config/overrides/bridge-structures.json").read_text()
    )
    grouped = physical_bridge_groups(
        [road for road in city["roads"] if road["id"] in city["bridge_ways"]]
    )
    structures = []
    for index, (name, source_roads) in enumerate(grouped):
        if name == cfg["name"]:
            continue
        rule = inventory["bridges"].get(name, inventory["default"])
        local_height = source_height(source_roads, deck_field)
        groups = corridor_mesh(source_roads, city, local_height, rule)
        if groups:
            asset = write_asset(out, f"sthlm_bridge_{index}", groups, name)
            instances.append(asset)
            structures.append(
                {
                    "name": name,
                    "source_ways": [r["id"] for r in source_roads],
                    "style": rule["style"],
                    "asset": asset["asset"],
                }
            )
    landmark_components = [roads for name, roads in grouped if name == cfg["name"]]
    for index, roads in enumerate(landmark_components):
        asset_name = "sthlm_vasterbron" if index == 0 else f"sthlm_vasterbron_{index}"
        instances.append(
            write_asset(
                out,
                asset_name,
                landmark_mesh(roads, source_height(roads, deck_field), cfg),
                cfg["id"],
            )
        )
    city["bridge_structure_rules"] = {
        "provenance": cfg["provenance"],
        "deck_thickness_m": cfg["deck_thickness_m"],
        "driveable_deck_modified": False,
        "native_facets_captured": road_triangles is not None,
        "placement": "unbound native PKG static triangle meshes; local minimum Y zero",
        "arch_stations": cfg["arch_stations"],
        "inventory_provenance": inventory["provenance"],
        "structures": structures,
    }
    return instances

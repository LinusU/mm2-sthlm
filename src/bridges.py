"""Original native static bridge structures; existing driveable deck unchanged."""

import json
import math
import struct
from pathlib import Path

from PIL import Image
from shapely.geometry import LineString, shape

import props
from sthlm import triangulate

ROOT = Path(__file__).resolve().parents[1]
OVERRIDE = ROOT / "config/overrides/vasterbron-structure.json"
COLORS = {"bridge_concrete": (145, 146, 139), "bridge_steel": (109, 124, 121)}


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
    for count, (a, b) in edges.values():
        if count != 1:
            continue
        c, d = (b[0], b[1] - thickness, b[2]), (a[0], a[1] - thickness, a[2])
        mesh.extend([(a, c, b), (a, d, c)])
    return mesh


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


def write(out, city, deck_field):
    """Return static placement records for merging into props.write pathset."""
    cfg = json.loads(OVERRIDE.read_text())
    (out / "geometry").mkdir(parents=True, exist_ok=True)
    (out / "texture").mkdir(parents=True, exist_ok=True)
    for texture, color in COLORS.items():
        Image.new("RGB", (16, 16), color).save(out / f"texture/{texture}.png")
    instances = []
    surface = shape(city["bridge_road_surface"])
    for index, triangles in enumerate(
        captured_decks(surface, deck_field, city["spawn"], cfg["deck_thickness_m"])
    ):
        instances.append(
            write_asset(
                out,
                f"sthlm_deck_{index}",
                [("bridge_concrete", triangles)],
                "bridge deck underside",
            )
        )
    roads = [
        r
        for r in city["roads"]
        if r["id"] in city["bridge_ways"] and r["tags"].get("name") == cfg["name"]
    ]
    if roads:
        instances.append(
            write_asset(
                out,
                "sthlm_vasterbron",
                landmark_mesh(roads, deck_field, cfg),
                cfg["id"],
            )
        )
    city["bridge_structure_rules"] = {
        "provenance": cfg["provenance"],
        "deck_thickness_m": cfg["deck_thickness_m"],
        "driveable_deck_modified": False,
        "placement": "unbound native PKG static triangle meshes; local minimum Y zero",
        "arch_stations": cfg["arch_stations"],
    }
    return instances

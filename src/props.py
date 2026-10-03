"""Original primitive PKG art + native breakable prop placement records."""

import math
import struct
from shapely import prepare
from shapely.geometry import LineString, Point, shape
from shapely.strtree import STRtree


def lp(text):
    b = text.encode() + b"\0"
    return bytes([len(b)]) + b


def chunk(name, data):
    return b"FILE" + lp(name) + struct.pack("<I", len(data)) + data


def geometry(triangles, shader):
    vertices = [p for t in triangles for p in t]
    data = struct.pack("<5I", 1, len(vertices), len(vertices), 1, 0x102)
    data += struct.pack("<HHi", 1, 0, shader) + struct.pack("<iI", 3, len(vertices))
    for x, y, z in vertices:
        data += struct.pack("<5f", x, y, z, x / 4, z / 4)
    data += struct.pack("<I", len(vertices)) + struct.pack(
        "<" + "H" * len(vertices), *range(len(vertices))
    )
    return data


def tree_mesh():
    trunk = []
    leaves = []
    # Content centred at CG=(0,4,0); pathset loader offsets it back to ground.
    for i in range(8):
        a = 2 * math.pi * i / 8
        b = 2 * math.pi * (i + 1) / 8
        p = (0.3 * math.cos(a), -4, 0.3 * math.sin(a))
        q = (0.3 * math.cos(b), -4, 0.3 * math.sin(b))
        r = (q[0], 0, q[2])
        s = (p[0], 0, p[2])
        trunk.extend([(p, q, r), (p, r, s)])
        for bottom, top, radius in [(-1, 3, 2.5), (1, 4, 2)]:
            # Clockwise projected winding matches the PKG emitter's reversal.
            leaves.append(
                (
                    (radius * math.cos(a), bottom, radius * math.sin(a)),
                    (radius * math.cos(b), bottom, radius * math.sin(b)),
                    (0, top, 0),
                )
            )
    shaders = struct.pack("<2I", 1, 2)
    for texture in ["wood", "foliage"]:
        shaders += lp(texture) + struct.pack(
            "<17f", *([1, 1, 1, 1] * 2 + [0, 0, 0, 0] * 2 + [0])
        )
    pkg = b"PKG3" + chunk("shaders", shaders)
    pkg += chunk("TRUNK_H", geometry(trunk, 0)) + chunk("CANOPY_H", geometry(leaves, 1))
    # Separate native BREAK parts replace the dormant tree on impact.
    pkg += chunk("BREAK01_H", geometry(trunk, 0)) + chunk(
        "BREAK02_H", geometry(leaves, 1)
    )
    return pkg


def banger_record(mass, parts):
    return f"""type: a
dgBangerData {{
AudioId 0
Size 0.7 8 0.7
CG 0 4 0
NumGlows 0
Mass {mass}
Elasticity 0.1
Friction 0.8
ImpulseLimit2 450
SpinAxis 0
Flash 0
NumParts {parts}
BirthRule {{
Position 0 0 0
PositionVar 0 0 0
Velocity 0 0 0
VelocityVar 0 0 0
Life 0
Mass 1
MassVar 0
Radius 0
RadiusVar 0
Drag 0
DragVar 0
DRadius 0
DRadiusVar 0
DAlpha 0
DAlphaVar 0
DRotation 0
DRotationVar 0
InitialBlast 0
SpewRate 0
SpewTimeLimit 0
Gravity -9.8
TexFrameStart 0
TexFrameEnd 0
BirthFlags 0
}}
TexNumber 0
BillFlags 0
YRadius 0.35
ColliderId 0
CollisionPrim 1
CollisionType 16
}}
"""


def placements(city, land, road, height=lambda x, n: 2.0):
    occupied = [
        shape(b["geometry"])
        for b in city["buildings"]
        if not shape(b["geometry"]).is_empty
    ]
    tree = STRtree(occupied)
    prepare(land)
    centrelines = [LineString(r["points"]) for r in city.get("roads", [])]
    roads = STRtree(centrelines)
    out = []
    seen = set()
    for item in city.get("trees", []):
        x, n = item["position"]
        p = Point(x, n)
        key = (round(x, 1), round(n, 1))
        clearance = (
            centrelines[int(roads.nearest(p))].distance(p) - 7
            if centrelines
            else road.distance(p)
        )
        if key in seen or not land.covers(p.buffer(2.5)) or clearance < 2.5:
            continue
        if occupied and tree.query(p.buffer(2.5), predicate="intersects").size:
            continue
        seen.add(key)
        out.append(
            {
                "source": f"node/{item['id']}",
                "asset": "sthlm_tree",
                "position": [x, height(x, n), -n],
                "breakable": True,
            }
        )
    return out


def write(out, instances):
    (out / "geometry").mkdir(exist_ok=True)
    (out / "tune/banger").mkdir(parents=True, exist_ok=True)
    (out / "geometry/sthlm_tree.pkg").write_bytes(tree_mesh())
    for name, mass, parts in [
        ("sthlm_tree", 120, 2),
        ("sthlm_tree_break01", 40, 0),
        ("sthlm_tree_break02", 80, 0),
    ]:
        (out / f"tune/banger/{name}.dgbangerdata").write_text(
            banger_record(mass, parts)
        )
    # A single Points path stamps every real sourced tree; binding happens via
    # props.pathset, not INST's static placement path in the tested engine.
    data = (
        b"PTH1"
        + struct.pack("<II", 1, 0)
        + b"sthlm_tree".ljust(32, b"\0")
        + struct.pack("<II", len(instances), 0)
    )
    for item in instances:
        data += struct.pack("<I3f", 0, *item["position"])
    data += bytes(4)
    target = out / "city/stockholm/props.pathset"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)

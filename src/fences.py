"""Source-aligned native breakable iron park fence panels."""

import gzip
import hashlib
import json
import math
import struct
from pathlib import Path

from PIL import Image
from shapely.geometry import LineString, Point, shape
from shapely.ops import substring

import props

ROOT = Path(__file__).resolve().parents[1]
OVERRIDE = ROOT / "config/overrides/landstingshuset-fence.json"


def project(lon, lat, origin):
    radius = 6378137.0
    return (
        radius * math.radians(lon - origin[0]) * math.cos(math.radians(origin[1])),
        radius * math.radians(lat - origin[1]),
    )


def fence_lines(city, source=None, override=None):
    """Apply explicit gaps to OSM fence ways, preserving their open ends."""
    cfg = override or json.loads(OVERRIDE.read_text())
    if source is None:
        with gzip.open(ROOT / "sources/expanded/osm.json.gz", "rt") as stream:
            source = json.load(stream)
    nodes = {e["id"]: e for e in source["elements"] if e["type"] == "node"}
    ways = {e["id"]: e for e in source["elements"] if e["type"] == "way"}
    bounds = shape(city["bounds"])
    result = []
    for wid in cfg["ways"]:
        if wid not in ways:
            raise ValueError(f"Fence override requires source way/{wid}")
        way = ways[wid]
        if way.get("tags", {}).get("barrier") != "fence":
            raise ValueError(f"Fence override way/{wid} is not a sourced fence")
        line = LineString(
            [
                project(nodes[n]["lon"], nodes[n]["lat"], city["origin"])
                for n in cfg.get("way_nodes", {}).get(str(wid), way["nodes"])
            ]
        )
        intervals = [(0.0, line.length)]
        for gap in cfg["openings"]:
            if gap["node"] not in way["nodes"]:
                continue
            node = nodes[gap["node"]]
            centre = line.project(
                Point(project(node["lon"], node["lat"], city["origin"]))
            )
            lo, hi = centre - gap["width"] / 2, centre + gap["width"] / 2
            kept = []
            for start, end in intervals:
                if hi <= start or lo >= end:
                    kept.append((start, end))
                else:
                    if start < lo:
                        kept.append((start, lo))
                    if hi < end:
                        kept.append((hi, end))
            intervals = kept
        for start, end in intervals:
            clipped = substring(line, start, end).intersection(bounds)
            pieces = list(clipped.geoms) if hasattr(clipped, "geoms") else [clipped]
            for piece in pieces:
                if piece.geom_type == "LineString" and piece.length > 0.05:
                    result.append({"source": f"way/{wid}", "line": piece})
    return cfg, result


def placements(city, height=lambda x, n: 2.0, source=None, override=None):
    """Directed path records: local +X points from each panel start to end."""
    cfg, lines = fence_lines(city, source, override)
    result = []
    for record in lines:
        coords = list(record["line"].coords)
        for a, b in zip(coords, coords[1:]):
            count = max(1, math.ceil(math.dist(a, b) / cfg["max_panel_length"]))
            for i in range(count):
                p = [a[j] + (b[j] - a[j]) * i / count for j in range(2)]
                q = [a[j] + (b[j] - a[j]) * (i + 1) / count for j in range(2)]
                x, n = [(p[j] + q[j]) / 2 for j in range(2)]
                y = height(x, n)
                descriptor = {
                    "fence_type": cfg.get("fence_type", "iron"),
                    "length": round(math.dist(p, q), 5),
                    "left_y": round(height(*p) - y, 5),
                    "right_y": round(height(*q) - y, 5),
                    "height": cfg["height"],
                    "plinth_height": cfg["plinth_height"],
                    "thickness": cfg["thickness"],
                }
                digest = hashlib.sha256(
                    json.dumps(descriptor, sort_keys=True).encode()
                ).hexdigest()[:16]
                result.append(
                    {
                        "source": record["source"],
                        "override": cfg["id"],
                        "kind": "fence",
                        "asset": f"sthlm_fence_{digest}",
                        "position": [x, y, -n],
                        "direction": [q[0], y, -q[1]],
                        "breakable": True,
                        "endpoints": [p, q],
                        "mesh": descriptor,
                    }
                )
    return result


def box_mesh(x0, x1, y0, y1, z0, z1):
    vertices = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    faces = [
        (0, 1, 3, 2),
        (4, 6, 7, 5),
        (0, 4, 5, 1),
        (2, 3, 7, 6),
        (0, 2, 6, 4),
        (1, 5, 7, 3),
    ]
    return [
        tuple(vertices[i] for i in ids)
        for a, b, c, d in faces
        for ids in [(a, b, c), (a, c, d)]
    ]


def iron_mesh(cfg):
    """Original bars, rails, posts, gold collars, spear tips and stone plinth."""
    length, top = cfg["length"], cfg["height"]
    plinth = cfg["plinth_height"]
    iron, gold, stone = [], [], []
    half = length / 2
    stone += box_mesh(-half, half, -0.06, plinth, -0.11, 0.11)
    for y in (plinth + 0.12, top - 0.43):
        iron += box_mesh(-half, half, y, y + 0.065, -0.045, 0.045)
    for x in (-half + 0.095, half - 0.095):
        iron += box_mesh(x - 0.065, x + 0.065, plinth, top - 0.05, -0.065, 0.065)
        iron += box_mesh(x - 0.095, x + 0.095, top - 0.12, top - 0.02, -0.095, 0.095)
    bars = max(1, math.floor(length / 0.17))
    for i in range(1, bars):
        x = -half + length * i / bars
        iron += box_mesh(x - 0.0175, x + 0.0175, plinth, top - 0.18, -0.0175, 0.0175)
        gold += box_mesh(x - 0.034, x + 0.034, top - 0.42, top - 0.27, -0.034, 0.034)
        base = [
            (x - 0.045, top - 0.18, -0.045),
            (x + 0.045, top - 0.18, -0.045),
            (x + 0.045, top - 0.18, 0.045),
            (x - 0.045, top - 0.18, 0.045),
        ]
        iron += [(base[j], base[(j + 1) % 4], (x, top, 0)) for j in range(4)]

    # Build along local +X, with heights interpolated from terrain samples.
    # Vertices relative to CG match the existing native prop convention.
    def transform(triangles):
        return [
            tuple(
                (
                    x,
                    y
                    + cfg["left_y"]
                    + (x / length + 0.5) * (cfg["right_y"] - cfg["left_y"])
                    - top / 2,
                    z,
                )
                for x, y, z in triangle
            )
            for triangle in triangles
        ]

    pieces = [transform(iron), transform(gold), transform(stone)]
    shaders = struct.pack("<2I", 1, 3)
    for texture in ("fence_iron", "fence_gold", "fence_stone"):
        shaders += props.lp(texture) + struct.pack(
            "<17f", *([1, 1, 1, 1] * 2 + [0, 0, 0, 0] * 2 + [0])
        )
    data = b"PKG3" + props.chunk("shaders", shaders)
    for name, triangles, shader in zip(
        ("IRON_H", "COLLARS_H", "PLINTH_H"), pieces, range(3)
    ):
        data += props.chunk(name, props.geometry(triangles, shader))
    for index, (triangles, shader) in enumerate(zip(pieces, range(3)), 1):
        data += props.chunk(f"BREAK{index:02}_H", props.geometry(triangles, shader))
    return data, pieces


def wooden_placements(city, height, source=None):
    cfg = json.loads(OVERRIDE.read_text())["wood"]
    if source is None:
        with gzip.open(ROOT / "sources/expanded/osm.json.gz", "rt") as stream:
            source = json.load(stream)
    result = placements(city, height, source, cfg)
    nodes = {e["id"]: e for e in source["elements"] if e["type"] == "node"}
    gap = cfg["openings"][0]
    node = nodes[gap["node"]]
    x, n = project(node["lon"], node["lat"], city["origin"])
    if not shape(city["bounds"]).covers(Point(x, n)):
        return result
    end = nodes[4325198572]
    ex, en = project(end["lon"], end["lat"], city["origin"])
    dx, dn = ex - x, en - n
    norm = math.hypot(dx, dn)
    dx, dn = dx / norm, dn / norm
    half = gap["width"] / 2
    a, b = [x - dx * half, n - dn * half], [x + dx * half, n + dn * half]
    y = height(x, n)
    descriptor = {
        "fence_type": "gate",
        "length": gap["width"],
        "height": cfg["height"],
        "plinth_height": 0,
        "thickness": 0.16,
        "left_y": height(*a) - y,
        "right_y": height(*b) - y,
    }
    digest = hashlib.sha256(
        json.dumps(descriptor, sort_keys=True).encode()
    ).hexdigest()[:16]
    result.append(
        {
            "source": "way/28975067",
            "override": cfg["id"],
            "kind": "fence",
            "asset": f"sthlm_gate_{digest}",
            "position": [x, y, -n],
            "direction": [b[0], y, -b[1]],
            "breakable": True,
            "endpoints": [a, b],
            "mesh": descriptor,
            "gate_node": gap["node"],
            "gate_width": gap["width"],
        }
    )
    return result


def wooden_mesh(cfg):
    length, top = cfg["length"], cfg["height"]
    gate = cfg["fence_type"] == "gate"
    pieces = []
    count = 2 if gate else 1
    for leaf in range(count):
        lo = -length / 2 + length * leaf / count
        hi = lo + length / count
        triangles = []
        bars = max(1, math.ceil((hi - lo) / (0.19 if gate else 0.14)))
        for i in range(bars):
            z0 = lo + (hi - lo) * i / bars
            z1 = lo + (hi - lo) * (i + 1) / bars - (0.07 if gate else 0.008)
            triangles += box_mesh(-0.035, 0.035, 0.05, top, z0, z1)
        for y in (0.24, top - 0.28):
            triangles += box_mesh(-0.075, -0.035, y, y + 0.12, lo, hi)
        if gate:
            dz, dy = hi - lo - 0.1, top - 0.5
            brace_length = math.hypot(dz, dy)
            sign = 1 if leaf == 0 else -1
            c, sn = dz / brace_length, sign * dy / brace_length
            brace = box_mesh(
                -0.04, 0.04, -0.06, 0.06, -brace_length / 2, brace_length / 2
            )
            triangles += [
                tuple(
                    (x - 0.06, y * c + z * sn + top / 2, z * c - y * sn + (lo + hi) / 2)
                    for x, y, z in tri
                )
                for tri in brace
            ]
        else:
            for z in (lo + 0.055, hi - 0.055):
                triangles += box_mesh(-0.08, 0.08, 0, top + 0.02, z - 0.055, z + 0.055)
        pieces.append(
            [
                tuple(
                    (
                        z,
                        y
                        + cfg["left_y"]
                        + (z / length + 0.5) * (cfg["right_y"] - cfg["left_y"])
                        - top / 2,
                        -x,
                    )
                    for x, y, z in tri
                )
                for tri in triangles
            ]
        )
    shaders = struct.pack("<2I", 1, 1) + props.lp("fence_wood")
    shaders += struct.pack("<17f", *([1, 1, 1, 1] * 2 + [0, 0, 0, 0] * 2 + [0]))
    data = b"PKG3" + props.chunk("shaders", shaders)
    data += props.chunk("WOOD_H", props.geometry([t for p in pieces for t in p], 0))
    for index, triangles in enumerate(pieces, 1):
        data += props.chunk(f"BREAK{index:02}_H", props.geometry(triangles, 0))
    return data, pieces


def panel_mesh(cfg):
    return (
        iron_mesh(cfg) if cfg.get("fence_type", "iron") == "iron" else wooden_mesh(cfg)
    )


def write(out, city, height=lambda x, n: 2.0, source=None):
    """Emit PKG/banger assets; caller merges returned pathset placements."""
    instances = placements(city, height, source) + wooden_placements(
        city, height, source
    )
    (out / "geometry").mkdir(parents=True, exist_ok=True)
    (out / "tune/banger").mkdir(parents=True, exist_ok=True)
    (out / "texture").mkdir(parents=True, exist_ok=True)
    for name, color in [
        ("fence_iron", (48, 52, 48)),
        ("fence_gold", (189, 171, 106)),
        ("fence_stone", (132, 129, 113)),
        ("fence_wood", (69, 82, 74)),
    ]:
        Image.new("RGB", (16, 16), color).save(out / f"texture/{name}.png")
    written = set()
    for item in instances:
        asset = item["asset"]
        if asset in written:
            continue
        written.add(asset)
        pkg, pieces = panel_mesh(item["mesh"])
        (out / f"geometry/{asset}.pkg").write_bytes(pkg)
        vertices = [v for group in pieces for tri in group for v in tri]
        count = len(pieces)
        bangers = [(asset, 40 if item["mesh"]["fence_type"] == "gate" else 65, count)]
        bangers += [(asset + f"_break{i + 1:02}", 20, 0) for i in range(count)]
        for index, (name, mass, parts) in enumerate(bangers):
            part_vertices = (
                vertices
                if index == 0
                else [v for tri in pieces[index - 1] for v in tri]
            )
            collider_size = [
                max(v[k] for v in part_vertices) - min(v[k] for v in part_vertices)
                for k in range(3)
            ]
            # Record format follows the tested native prop convention.
            record = props.banger_record(mass, parts)
            record = record.replace(
                "Size 0.7 8 0.7", "Size " + " ".join(f"{v:.6f}" for v in collider_size)
            )
            record = record.replace(
                "CG 0 4 0", f"CG 0 {item['mesh']['height'] / 2:.6f} 0"
            )
            record = record.replace("YRadius 0.35", "YRadius 0.11")
            record = record.replace("ImpulseLimit2 450", "ImpulseLimit2 150")
            (out / f"tune/banger/{name}.dgbangerdata").write_text(record)
    return instances

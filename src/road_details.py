"""Source-tagged static signals and native render-only road paint ribbons."""

import math
import struct
from PIL import Image
from shapely.geometry import LineString, Point, Polygon, shape
from shapely.strtree import STRtree
import props
import sthlm


def normalized(source, cfg, city):
    """Retain road-member traffic nodes; standalone crossing nodes use nearest road."""
    roads = city.get("roads", [])
    out = []
    boundary = shape(city["bounds"]) if city.get("bounds") else None
    membership = {}
    lines = [LineString(road["points"]) for road in roads]
    tree = STRtree(lines)
    for index, road in enumerate(roads):
        for node_id in road["nodes"]:
            membership.setdefault(node_id, []).append(index)
    for node in source["elements"]:
        tags = node.get("tags", {})
        if node["type"] != "node" or tags.get("highway") not in {
            "traffic_signals",
            "crossing",
        }:
            continue
        p = sthlm.project(node["lon"], node["lat"], cfg["origin"])
        point = Point(p)
        if boundary is not None and not boundary.covers(point):
            continue
        bounds = cfg.get("bounds")
        if bounds and not (
            bounds[0] <= node["lon"] <= bounds[2]
            and bounds[1] <= node["lat"] <= bounds[3]
        ):
            continue
        candidates = [
            i for i in membership.get(node["id"], []) if lines[i].distance(point) < 3
        ]
        if not candidates and lines:
            candidates = list(tree.query(point.buffer(3)))
            candidates = [i for i in candidates if lines[i].distance(point) < 3]
        if not candidates:
            continue
        road = roads[
            min(candidates, key=lambda i: (lines[i].distance(point), roads[i]["id"]))
        ]
        out.append(
            {"id": node["id"], "position": list(p), "tags": tags, "road_id": road["id"]}
        )
    return out


def surface_height(city, ground, deck):
    """Sample the exported level belonging to each source road, including ramps."""
    bridges = set(city.get("bridge_ways", []))
    widths = {r["id"]: r["width"] for r in city["roads"]}
    approaches = {}
    for approach in city.get("bridge_approaches", []):
        way = approach["source_way"]
        polygon = LineString([p[:2] for p in approach["points"]]).buffer(
            widths[way] / 2 + 0.5, cap_style=1, join_style=2
        )
        approaches.setdefault(way, []).append(polygon)

    def sample(road, x, n):
        if road["id"] in bridges or any(
            p.covers(Point(x, n)) for p in approaches.get(road["id"], [])
        ):
            return deck(x, n)
        return ground(x, n)

    return sample


def tangent(line, distance):
    a = line.interpolate(max(0, distance - 0.5))
    b = line.interpolate(min(line.length, distance + 0.5))
    length = a.distance(b)
    return ((b.x - a.x) / length, (b.y - a.y) / length) if length else (1, 0)


def placements(city, height=lambda x, n: 2.0, *, road_height=None):
    """Signals exist only on explicit source tags; directional placement is inferred."""
    roads = {r["id"]: r for r in city.get("roads", [])}
    out = []
    boundary = shape(city["bounds"]) if city.get("bounds") else None
    for item in city.get("road_details", []):
        tags = item["tags"]
        if (
            tags.get("highway") != "traffic_signals"
            and tags.get("crossing") != "traffic_signals"
        ):
            continue
        road = roads[item["road_id"]]
        line = LineString(road["points"])
        distance = line.project(Point(item["position"]))
        tx, tn = tangent(line, distance)
        # OSM marks stop line/centreline, not pole coordinates. Set on the right
        # verge of the mapped direction; backward tags reverse that direction.
        reverse = (
            tags.get("traffic_signals:direction") == "backward"
            or road["tags"].get("oneway") == "-1"
        )
        if reverse:
            tx, tn = -tx, -tn
        x, n = item["position"]
        offset = road["width"] / 2 + 0.4
        x, n = x + tn * offset, n - tx * offset
        if boundary is not None and not boundary.covers(Point(x, n)):
            continue
        y = road_height(road, x, n) if road_height else height(x, n)
        out.append(
            {
                "source": f"node/{item['id']}",
                "asset": "sthlm_signal",
                "position": [x, y, -n],
                "direction": [x - tx, y, -n + tn],
                "breakable": False,
                "movable": True,
                "placement": "inferred right verge from tagged node",
                "timing": "static visual only",
            }
        )
    return out


def ribbons(city, height=lambda x, n: 2.0, *, road_height=None):
    """White paint rectangles: lane tags set divisions, width only sets spacing."""
    out = []
    boundary = shape(city["bounds"]) if city.get("bounds") else None

    def stripe(a, b, width, source, kind, road):
        length = math.dist(a, b)
        if length < 0.01:
            return
        nx, nn = -(b[1] - a[1]) / length, (b[0] - a[0]) / length
        points = []
        for x, n in (a, b):
            for sign in (-1, 1):
                px, pn = x + sign * nx * width / 2, n + sign * nn * width / 2
                y = road_height(road, px, pn) if road_height else height(px, pn)
                points.append([px, y, -pn])
        if boundary is not None:
            footprint = Polygon([(points[i][0], -points[i][2]) for i in (0, 1, 3, 2)])
            if not boundary.covers(footprint):
                return
        out.append(
            {"asset": "sthlm_paint", "points": points, "source": source, "kind": kind}
        )

    for road in city.get("roads", []):
        tags = road["tags"]
        if tags.get("lane_markings") == "no":
            continue
        try:
            lanes = int(tags.get("lanes", "0"))
        except ValueError:
            continue
        if not 2 <= lanes <= 8:
            continue
        line = LineString(road["points"])
        # Leave ends clear for junctions; no guessed junction boxes or stop lines.
        for division in range(1, lanes):
            offset = road["width"] * (division / lanes - 0.5)
            for start in range(8, max(8, math.floor(line.length - 8)), 6):
                end = min(start + 3, line.length - 8)
                a, b = line.interpolate(start), line.interpolate(end)
                tx, tn = tangent(line, (start + end) / 2)
                stripe(
                    (a.x - tn * offset, a.y + tx * offset),
                    (b.x - tn * offset, b.y + tx * offset),
                    0.12,
                    f"way/{road['id']}",
                    "lane divider",
                    road,
                )
    roads = {r["id"]: r for r in city.get("roads", [])}
    for item in city.get("road_details", []):
        tags = item["tags"]
        # Unmarked/signal-only crossings do not imply zebra paint.
        if (
            tags.get("crossing") not in {"marked", "zebra"}
            and tags.get("crossing:markings") != "zebra"
        ):
            continue
        if tags.get("crossing:markings") == "no":
            continue
        road = roads[item["road_id"]]
        line = LineString(road["points"])
        distance = line.project(Point(item["position"]))
        tx, tn = tangent(line, distance)
        x, n = item["position"]
        half = max(0, road["width"] / 2 - 0.3)
        count = math.floor(2 * half)
        for index in range(count):
            offset = index - (count - 1) / 2
            cx, cn = x - tn * offset, n + tx * offset
            stripe(
                (cx - tx * 1.5, cn - tn * 1.5),
                (cx + tx * 1.5, cn + tn * 1.5),
                0.5,
                f"node/{item['id']}",
                "crossing",
                road,
            )
    return out


def signal_mesh():
    """Original simple signal asset; no retail art dependency."""

    def cuboid(x0, y0, z0, x1, y1, z1):
        p = [
            (x0, y0, z0),
            (x1, y0, z0),
            (x1, y1, z0),
            (x0, y1, z0),
            (x0, y0, z1),
            (x1, y0, z1),
            (x1, y1, z1),
            (x0, y1, z1),
        ]
        p = [(-z, y - 1.9, x) for x, y, z in p]
        faces = [
            (0, 3, 2, 1),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (3, 7, 6, 2),
            (0, 4, 7, 3),
            (1, 2, 6, 5),
        ]
        return [(p[a], p[b], p[c]) for a, b, c, d in faces] + [
            (p[a], p[c], p[d]) for a, b, c, d in faces
        ]

    shaders = struct.pack("<2I", 1, 5)
    for name in (
        "sthlm_signal_dark",
        "sthlm_signal_red",
        "sthlm_signal_amber",
        "sthlm_signal_green",
        "sthlm_signal_yellow",
    ):
        shaders += props.lp(name) + struct.pack(
            "<17f", *([1, 1, 1, 1] * 2 + [0, 0, 0, 0] * 2 + [0])
        )
    pkg = b"PKG3" + props.chunk("shaders", shaders)
    body = cuboid(-0.06, 0, -0.06, 0.06, 3.8, 0.06) + cuboid(
        -0.22, 2.7, -0.15, 0.22, 3.8, 0.15
    )
    pkg += props.chunk("BODY_H", props.geometry(body, 0))
    for index, y in enumerate((3.55, 3.25, 2.95), 1):
        pkg += props.chunk(
            f"LENS{index}_H",
            props.geometry(
                cuboid(-0.13, y - 0.10, -0.17, 0.13, y + 0.10, -0.15), index
            ),
        )
    collars = cuboid(-0.065, 0.55, -0.065, 0.065, 0.70, 0.065) + cuboid(
        -0.065, 1.25, -0.065, 0.065, 1.40, 0.065
    )
    pkg += props.chunk("COLLARS_H", props.geometry(collars, 4))
    return pkg


def grouped_ribbons(paint, max_points=65536):
    """Pack native strips; collapsed edge pairs join disjoint paint invisibly.

    [a,b] -> [b,b] -> [c,c] -> [c,d] has three zero-area quads.
    Thus the renderer keeps each original rectangle with no bridging paint.
    """
    if max_points < 4 or max_points > 65536:
        raise ValueError("native ribbon point limit must be 4..65536")
    out = []
    current = None
    for ribbon in paint:
        points = ribbon["points"]
        extra = len(points) + (4 if current else 0)
        if (
            current is None
            or current["asset"] != ribbon["asset"]
            or len(current["points"]) + extra > max_points
        ):
            current = {"asset": ribbon["asset"], "points": list(points)}
            out.append(current)
        else:
            last, first = current["points"][-1], points[0]
            current["points"].extend([last, last, first, first, *points])
    if len(out) > 4096:
        raise ValueError("native decal path count exceeds 4096")
    return out


def write(out, city, instances=None, height=lambda x, n: 2.0, *, road_height=None):
    """Write art/decal file; return instances for the caller's shared props.pathset."""
    instances = (
        placements(city, height, road_height=road_height)
        if instances is None
        else instances
    )
    for directory in ("geometry", "texture", "tune/banger", "city/stockholm"):
        (out / directory).mkdir(parents=True, exist_ok=True)
    (out / "geometry/sthlm_signal.pkg").write_bytes(signal_mesh())
    # Mesh is centered at CG; native placement offsets it back to ground.
    record = (
        props.banger_record(60, 0)
        .replace("Size 0.7 8 0.7", "Size 0.34 3.8 0.44")
        .replace("CG 0 4 0", "CG 0 1.9 0")
    )
    (out / "tune/banger/sthlm_signal.dgbangerdata").write_text(record)
    colors = {
        "sthlm_paint": (235, 235, 219, 255),
        "sthlm_signal_dark": (35, 38, 34, 255),
        "sthlm_signal_red": (185, 28, 25, 255),
        "sthlm_signal_amber": (60, 43, 18, 255),
        "sthlm_signal_green": (16, 48, 30, 255),
        "sthlm_signal_yellow": (220, 185, 35, 255),
    }
    for name, color in colors.items():
        Image.new("RGBA", (4, 4), color).save(out / f"texture/{name}.png")
    paint = grouped_ribbons(ribbons(city, height, road_height=road_height))
    data = b"PTH1" + struct.pack("<II", len(paint), 0)
    for item in paint:
        data += item["asset"].encode().ljust(32, b"\0") + struct.pack(
            "<II", len(item["points"]), 0
        )
        for point in item["points"]:
            data += struct.pack("<I3f", 0, *point)
        data += bytes([2, 20, 0, 0])
    (out / "city/stockholm/decals.pathset").write_bytes(data)
    return instances

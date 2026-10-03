"""Terrain-conforming surfaces and explicit, estimated bridge deck profiles.

DTM measures ground, not bridge decks. Decks use sourced connectivity plus
an authored clearance ramp; their heights must not be called surveyed data.
"""

import heapq
import math
import numpy as np
from shapely.geometry import LineString, Point, mapping
from shapely.ops import unary_union
from shapely.strtree import STRtree


class RoadField:
    def __init__(self, roads, terrain, bridge=False):
        self.terrain = terrain
        self.segments = []
        self.values = []
        for r in roads:
            points = r["elevated_points"]
            for a, b in zip(points, points[1:]):
                if math.dist(a[:2], b[:2]) > 0:
                    self.segments.append(LineString([a[:2], b[:2]]))
                    self.values.append((a[2], b[2]))
        self.tree = STRtree(self.segments)
        self.bridge = bridge

    def nearest(self, x, n):
        p = Point(x, n)
        if not self.segments:
            return self.terrain.height(x, n), math.inf
        i = int(self.tree.nearest(p))
        segment = self.segments[i]
        t = segment.project(p, normalized=True)
        a, b = self.values[i]
        return a + (b - a) * t, segment.distance(p)

    def __call__(self, x, n):
        return self.nearest(x, n)[0]

    def ground(self, x, n):
        raw = self.terrain.height(x, n)
        road, distance = self.nearest(x, n)
        # Match the roadway at its edge, then blend the shoulder into real land.
        weight = max(0, min(1, (14 - distance) / 7))
        return raw * (1 - weight) + road * weight


def distances(graph, ends):
    result = {n: 0.0 for n in ends}
    pending = [(0.0, n) for n in ends]
    heapq.heapify(pending)
    while pending:
        d, n = heapq.heappop(pending)
        if d != result[n]:
            continue
        for m, length in graph[n].items():
            nd = d + length
            if nd < result.get(m, math.inf):
                result[m] = nd
                heapq.heappush(pending, (nd, m))
    return result


def apply(city, terrain):
    bridges = set(city["bridge_ways"])
    ordinary = [r for r in city["roads"] if r["id"] not in bridges]
    elevated = [r for r in city["roads"] if r["id"] in bridges]
    positions = {
        nid: p for r in city["roads"] for nid, p in zip(r["nodes"], r["points"])
    }
    heights = {nid: max(0.9, terrain.height(*p)) for nid, p in positions.items()}
    groups = {}
    for r in elevated:
        groups.setdefault(r["tags"]["name"], []).append(r)
    profiles = []
    for name, roads in groups.items():
        graph = {}
        for r in roads:
            for a, b in zip(r["nodes"], r["nodes"][1:]):
                length = math.dist(positions[a], positions[b])
                graph.setdefault(a, {})[b] = length
                graph.setdefault(b, {})[a] = length
        ordinary_nodes = {n for r in ordinary for n in r["nodes"]}
        ends = {n for n in graph if n in ordinary_nodes or len(graph[n]) == 1}
        if len(ends) < 2:
            raise ValueError(f"bridge {name}: missing connected deck ends")
        distance = distances(graph, ends)
        # A terrain model often samples water beneath a bridge. Estimate the
        # deck from the two nearest shoreline ends rather than those samples.
        endpoints = list(sorted(ends))
        endpoint_distances = {n: distances(graph, [n]) for n in endpoints}
        clearance = 20.0 if name in {"Västerbron", "Lilla Västerbron"} else 6.0
        for n in graph:
            if n in ends:
                continue
            close = sorted(
                endpoints, key=lambda e: endpoint_distances[e].get(n, math.inf)
            )[:2]
            a, b = close
            da, db = (
                endpoint_distances[a].get(n, math.inf),
                endpoint_distances[b].get(n, math.inf),
            )
            if not math.isfinite(da + db):
                raise ValueError(f"bridge {name}: disconnected source group")
            baseline = (heights[a] * db + heights[b] * da) / (da + db)
            heights[n] = max(heights[n], baseline + min(clearance, distance[n] * 0.08))
        profiles.append(
            {
                "name": name,
                "height_rule": "estimated deck from DTM at ends; ramp <=8 percent above baseline",
                "additional_clearance_m": clearance,
                "source_ways": [r["id"] for r in roads],
            }
        )
    for r in city["roads"]:
        points = []
        for (nid_a, a), (nid_b, b) in zip(
            zip(r["nodes"], r["points"]), zip(r["nodes"][1:], r["points"][1:])
        ):
            count = max(1, math.ceil(math.dist(a, b) / 10))
            for i in range(count):
                t = i / count
                x, n = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                # Endpoints are shared across ways, including bridge approaches.
                if r["id"] in bridges:
                    h = heights[nid_a] * (1 - t) + heights[nid_b] * t
                elif i == 0:
                    h = heights[nid_a]
                else:
                    samples = [
                        terrain.height(
                            x + (b[0] - a[0]) / max(math.dist(a, b), 1) * d,
                            n + (b[1] - a[1]) / max(math.dist(a, b), 1) * d,
                        )
                        for d in [-10, 0, 10]
                    ]
                    h = max(0.9, float(np.median(samples)))
                points.append([x, n, h])
        points.append([*r["points"][-1], heights[r["nodes"][-1]]])
        r["elevated_points"] = points
    road = RoadField(ordinary, terrain)
    deck = RoadField(elevated, terrain, bridge=True)
    city["terrain"] = terrain.metadata
    city["elevation_rules"] = {
        "road_height_floor_m": 0.9,
        "rule": "terrain-derived road beds, shared source junction heights, 10 m centreline intervals with 3-sample median; minimum road height clears nominal water reference",
        "ground_source_modified": False,
        "bridge_decks": "estimated separately; not DTM measurements",
    }
    city["bridge_profiles"] = profiles
    city["spawn"][1] = road(*city["route"][0]) + 1.5
    for b in city["buildings"]:
        from shapely.geometry import shape

        p = shape(b["geometry"])
        # Level roofs; foundation extends to the lowest sampled footprint edge.
        samples = [
            road.ground(x, n)
            for part in (p.geoms if p.geom_type == "MultiPolygon" else [p])
            for x, n in part.exterior.coords
        ]
        b["base_y"] = min(samples)

    def surface(rs):
        return unary_union(
            [
                LineString(r["points"]).buffer(
                    r["width"] / 2, cap_style=1, join_style=2
                )
                for r in rs
            ]
        )

    from shapely.geometry import shape

    bounds = shape(city["bounds"])
    ground_roads = surface(ordinary).intersection(bounds)
    bridge_roads = surface(elevated).intersection(bounds)
    city["ground_road_surface"] = mapping(ground_roads)
    city["bridge_road_surface"] = mapping(bridge_roads)
    return road, deck, ground_roads, bridge_roads

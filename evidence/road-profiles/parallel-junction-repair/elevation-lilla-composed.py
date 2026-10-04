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


def conforming_boundary(geom):
    """Node shared material edges identically before clipping or tessellation.

    Roads, paving and land must retain the same five-metre subdivisions. A
    coarse shoulder edge otherwise bridges road vertices at a different
    linear height, opening a crack despite identical XY coverage.
    """
    return geom.segmentize(5)


def junction_planes(roads):
    """Fit one source-connected plane at a junction, preserving hillside grade.

    No geometric proximity creates connectivity. A neighbouring underpass is
    excluded unless it shares the exact OSM node with the upper carriageway.
    """
    owners = {}
    for road in roads:
        if "nodes" not in road:
            continue
        line = LineString([p[:2] for p in road["elevated_points"]])
        for node, position in zip(road["nodes"], road["points"]):
            if line.distance(Point(*position)) < 1e-6:
                owners.setdefault(node, []).append((road, position))
    planes = []
    for records in owners.values():
        if len({r["id"] for r, _ in records}) < 2:
            continue
        x, n = records[0][1]
        centre = Point(x, n)
        samples, joint_heights = [], []
        for road, _ in records:
            points = road["elevated_points"]
            line = LineString([p[:2] for p in points])
            station = line.project(centre)
            stations = [0.0]
            for a, b in zip(points, points[1:]):
                stations.append(stations[-1] + math.dist(a[:2], b[:2]))
            joint_heights.append(
                float(np.interp(station, stations, [p[2] for p in points]))
            )
            for side in (-1, 1):
                nearby = [
                    (abs(d - station), p)
                    for d, p in zip(stations, points)
                    if 1e-5 < side * (d - station) <= 10
                ]
                if nearby:
                    samples.append(min(nearby, key=lambda v: v[0])[1])
        h = float(np.mean(joint_heights))
        if len(samples) < 2:
            continue
        matrix = np.array([[p[0] - x, p[1] - n] for p in samples])
        # Nearly parallel approaches do not constrain transverse gradient.
        # Ridge regularization suppresses an invented steep bank in that axis.
        ridge = max(1e-8, float(np.sum(matrix * matrix)) * 0.02)
        gradient = np.linalg.solve(
            matrix.T @ matrix + np.eye(2) * ridge,
            matrix.T @ np.array([p[2] - h for p in samples]),
        )
        radius = max(r["width"] / 2 + 1 for r, _ in records)
        planes.append(
            (x, n, h, *map(float, gradient), radius, {r["id"] for r, _ in records})
        )
    return planes


class RoadField:
    def __init__(self, roads, terrain, bridge=False, junctions=(), shared_planes=()):
        self.terrain = terrain
        self.segments = []
        self.values = []
        self.widths = []
        self.ends = []
        self.by_road = {}
        self._source_cache = {}
        self.road_ids = []
        for r in roads:
            points = r["elevated_points"]
            for a, b in zip(points, points[1:]):
                if math.dist(a[:2], b[:2]) > 0:
                    self.by_road.setdefault(r.get("id"), []).append(len(self.segments))
                    self.segments.append(LineString([a[:2], b[:2]]))
                    self.values.append((a[2], b[2]))
                    self.road_ids.append(r.get("id"))
                    self.widths.append(r["width"] / 2)
                    self.ends.append((a[:2], b[:2]))
        self.tree = STRtree(self.segments)
        self.max_half_width = max(self.widths, default=0)
        # A source-connected join can cross independently rendered layer groups.
        # Its complete tangent fit must win an equal-distance local fit.
        self.planes = [*shared_planes, *junction_planes(roads)]
        for seam in junctions:
            if len(seam) == 7:
                x, n, h, radius, owner, gx, gn = seam
                self.planes.append((x, n, h, gx, gn, radius, {owner}))
        self.planes_by_road = {}
        for i, plane in enumerate(self.planes):
            for owner in plane[-1]:
                self.planes_by_road.setdefault(owner, []).append(i)
        self.bridge = bridge
        self.junctions = list(junctions)

    def _sample(self, x, n):
        p = Point(x, n)
        if not self.segments:
            return self.terrain.height(x, n), math.inf, 0
        i = int(self.tree.nearest(p))
        segment = self.segments[i]
        t = segment.project(p, normalized=True)
        a, b = self.values[i]
        height = a + (b - a) * t
        height = self.planar_height(height, x, n, self.road_ids[i])
        return height, segment.distance(p), self.widths[i]

    def planar_height(self, height, x, n, road_id):
        candidates = self.planes_by_road.get(road_id, [])
        if not candidates:
            return height
        # Tangent fits from nearby source joins can have overlapping fades.
        # Choosing just the closest fit makes a vertical step at their Voronoi
        # boundary. Blend the active fits over a three-metre distance band.
        # A supplied complete shared-layer fit precedes a local partial fit
        # at the same origin and must retain that established precedence.
        unique = {}
        for j in candidates:
            unique.setdefault(self.planes[j][:2], j)
        distances = {
            j: math.hypot(x - self.planes[j][0], n - self.planes[j][1])
            for j in unique.values()
        }
        nearest = min(distances.values())
        total = weighted = 0.0
        for j, distance in distances.items():
            influence = max(0.0, 1 - (distance - nearest) / 3) ** 2
            if not influence:
                continue
            xj, nj, h, gx, gn, radius, _ = self.planes[j]
            t = max(0.0, min(1.0, (distance - radius) / 7))
            fade = 1 - t * t * (3 - 2 * t)
            plane = h + gx * (x - xj) + gn * (n - nj)
            weighted += (plane * fade + height * (1 - fade)) * influence
            total += influence
        return weighted / total

    def _profile(self, road):
        points = road["elevated_points"]
        key = road.get("id", id(road))
        cached = self._source_cache.get(key)
        if cached is None or cached[0] is not points:
            line = LineString([p[:2] for p in points])
            stations = [0.0]
            for a, b in zip(points, points[1:]):
                stations.append(stations[-1] + math.dist(a[:2], b[:2]))
            cached = (
                points,
                line,
                np.array(stations),
                np.array([p[2] for p in points]),
            )
            self._source_cache[key] = cached
        return cached

    def height_at_station(self, road, station):
        """Height for both corners of a flat native road cross section."""
        _, _, stations, heights = self._profile(road)
        return float(np.interp(station, stations, heights))

    def height_for_road(self, road_id, x, n):
        """Flat cross section projected onto one source profile.

        Passing the road record also preserves post-elevation authored ramps.
        """
        if isinstance(road_id, dict):
            _, line, stations, heights = self._profile(road_id)
            station = line.project(Point(x, n))
            h = float(np.interp(station, stations, heights))
            if road_id.get("height_override"):
                return h
            return h
        indices = self.by_road.get(road_id, [])
        if not indices:
            raise KeyError(f"road {road_id} is absent from this height layer")
        p = Point(x, n)
        i = min(indices, key=lambda i: self.segments[i].distance(p))
        t = self.segments[i].project(p, normalized=True)
        a, b = self.values[i]
        return a + (b - a) * t

    def nearest(self, x, n):
        height, distance, _ = self._sample(x, n)
        return height, distance

    def __call__(self, x, n):
        return self.nearest(x, n)[0]

    def ground(self, x, n):
        return self.blended(x, n, ground=True)

    def blended(self, x, n, *, ground=False):
        """Continuous profiles within one pre-separated physical height layer."""
        if not self.segments:
            return self.terrain.height(x, n)
        point = Point(x, n)
        nearest = int(self.tree.nearest(point))
        distance = self.segments[nearest].distance(point)
        if ground and distance >= self.max_half_width + 9:
            return self.terrain.height(x, n)
        # A single nearest street changes discontinuously at its Voronoi edge.
        # Blend the closest profile of each nearby source way across a 3 m
        # band. Centreline samples remain exact whenever other streets are
        # farther than the band. Raised decks stay in their separate field.
        candidates = self.tree.query(point, predicate="dwithin", distance=distance + 3)
        owners = {}
        for i in map(int, candidates):
            d = self.segments[i].distance(point)
            owner = self.road_ids[i]
            if owner not in owners or d < owners[owner][0]:
                owners[owner] = (d, i)
        total = weighted = 0.0
        raw = None
        for d, i in owners.values():
            influence = max(0.0, 1 - (d - distance) / 3) ** 2
            if not influence:
                continue
            a, b = self.ends[i]
            dx, dn = b[0] - a[0], b[1] - a[1]
            t = max(
                0.0, min(1.0, ((x - a[0]) * dx + (n - a[1]) * dn) / (dx * dx + dn * dn))
            )
            h0, h1 = self.values[i]
            height = self.planar_height(h0 + (h1 - h0) * t, x, n, self.road_ids[i])
            shoulder = max(0.0, min(1.0, (self.widths[i] + 9 - d) / 7))
            if ground and shoulder < 1:
                if raw is None:
                    raw = self.terrain.height(x, n)
                height = height * shoulder + raw * (1 - shoulder)
            weighted += height * influence
            total += influence
        return weighted / total


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


def bridge_approaches(ordinary, elevated, length=20):
    """Separate short raised approaches from the lower road height field.

    OSM bridge tags often stop just beside an underpass. Keeping that last
    approach in the ground field lets its high profile attract neighbouring
    lower street vertices. Split only source-connected approach ends; an
    unrelated crossing road retains its complete geometry and height profile.
    """
    bridge_nodes = {n for road in elevated for n in road["nodes"]}
    ground, decks, junctions, metadata = [], list(elevated), [], []
    for road in ordinary:
        points = road["elevated_points"]
        first, last = 0, len(points) - 1
        portions = []
        if road["nodes"][0] in bridge_nodes:
            distance = 0.0
            while first < last and distance < length:
                distance += math.dist(points[first][:2], points[first + 1][:2])
                first += 1
            portions.append(points[: first + 1])
        if road["nodes"][-1] in bridge_nodes:
            distance = 0.0
            while last > first and distance < length:
                distance += math.dist(points[last][:2], points[last - 1][:2])
                last -= 1
            portions.append(points[last:])
        if first < last:
            ground.append({**road, "elevated_points": points[first : last + 1]})
        for portion in portions:
            if len(portion) < 2:
                continue
            decks.append({**road, "elevated_points": portion})
            metadata.append({"source_way": road["id"], "points": portion})
        # Both layer fields use a short common plane around their new seam.
        # It covers the overlapping round caps and the complete road width.
        if portions and first < last:
            radius = road["width"] / 2 + 2
            for index in ([first] if first else []) + (
                [last] if last < len(points) - 1 else []
            ):
                a, b = (
                    points[max(0, index - 1)],
                    points[min(len(points) - 1, index + 1)],
                )
                dx, dn = b[0] - a[0], b[1] - a[1]
                square = dx * dx + dn * dn
                gx, gn = (
                    ((b[2] - a[2]) * dx / square, (b[2] - a[2]) * dn / square)
                    if square
                    else (0, 0)
                )
                junctions.append((*points[index], radius, road.get("id"), gx, gn))
    return ground, decks, junctions, metadata


def align_segmented_bridge_profiles(roads, *, anchor_nodes=()):
    """One upper longitudinal datum for compatible segmented carriageways.

    Match complete true-source spans with the physical perimeter guards.
    Original resampled heights define the datum; internal way endpoints are
    not shore anchors and must not restart a taper.
    """
    from bridges import physical_bridge_groups, source_bridge_groups

    reports = []
    anchor_nodes = set(anchor_nodes)
    for name, members in physical_bridge_groups(roads):
        components = source_bridge_groups(members)
        if len(components) < 2 or max(map(lambda c: len(c[1]), components)) < 2:
            continue
        axes = []
        for _, component in components:
            neighbours = {}
            positions = {}
            for road in component:
                positions.update(zip(road["nodes"], road["points"]))
                for a, b in zip(road["nodes"], road["nodes"][1:]):
                    neighbours.setdefault(a, set()).add(b)
                    neighbours.setdefault(b, set()).add(a)
            ends = sorted(n for n, v in neighbours.items() if len(v) == 1)
            if (
                len(ends) != 2
                or any(len(v) > 2 for v in neighbours.values())
                or (set(neighbours) - set(ends)) & anchor_nodes
            ):
                break
            nodes = []
            previous = None
            node = ends[0]
            while True:
                nodes.append(node)
                following = neighbours[node] - {previous}
                if not following:
                    break
                previous, node = node, next(iter(following))
            points = [positions[n] for n in nodes]
            line = LineString(points)
            samples = sorted(
                (line.project(Point(p[:2])), p[2])
                for r in component
                for p in r["elevated_points"]
            )
            axes.append(
                (component, line, [s for s, h in samples], [h for s, h in samples])
            )
        if len(axes) != len(components):
            continue
        reference = max(axes, key=lambda a: a[1].length)[1]
        changed = 0
        for component, line, stations, heights in axes:
            for road in component:
                for point in road["elevated_points"]:
                    p = Point(point[:2])
                    axis = reference.interpolate(reference.project(p))
                    datum = max(
                        float(np.interp(a.project(axis), s, h)) for _, a, s, h in axes
                    )
                    station = line.project(p)
                    distance = min(station, line.length - station)
                    t = min(1, max(0, distance / 20))
                    w = t * t * (3 - 2 * t)
                    original = point[2]
                    point[2] = original + max(0, datum - original) * w
                    changed = max(changed, point[2] - original)
        reports.append(
            {
                "name": name,
                "source_ways": [r["id"] for r in members],
                "rule": "shared component upper longitudinal datum; true span anchors retained",
                "max_raise_m": round(changed, 6),
            }
        )
    return reports


def align_parallel_bridge_profiles(roads, *, anchor_nodes=()):
    """Share an estimated longitudinal datum across opposite carriageways.

    OSM often represents one physical bridge with independently connected
    carriageways. Their separately estimated arches can disagree despite the
    shared deck. Match only named, same-layer, nearly coincident parallel spans
    with compatible heights; genuinely stacked or distant decks stay separate.
    The common upper envelope preserves authored clearance. A twenty-metre
    endpoint taper retains exact source-connected approach anchors.
    """
    original = {r["id"]: [list(p) for p in r["elevated_points"]] for r in roads}
    records = []
    anchor_nodes = set(anchor_nodes)
    for road in sorted(roads, key=lambda r: r["id"]):
        points = [list(p) for p in road["elevated_points"]]
        line = LineString([p[:2] for p in points])
        if (
            not road["tags"].get("name")
            or line.length < 40
            or set(road["nodes"][1:-1]) & anchor_nodes
        ):
            continue
        stations = [0.0]
        for a, b in zip(points, points[1:]):
            stations.append(stations[-1] + math.dist(a[:2], b[:2]))
        records.append((road, line, stations, [p[2] for p in points]))

    def sample(record, point):
        _, line, stations, heights = record
        return float(np.interp(line.project(point), stations, heights))

    links = {i: set() for i in range(len(records))}
    for i, (road, line, _, _) in enumerate(records):
        for j in range(i):
            other, other_line, _, _ = records[j]
            if road["tags"].get("name") != other["tags"].get("name") or int(
                road["tags"].get("layer", 1)
            ) != int(other["tags"].get("layer", 1)):
                continue
            corridor = (road["width"] + other["width"]) / 2 + 2
            if line.hausdorff_distance(other_line) > corridor:
                continue
            a, b = (
                line.interpolate(0.25, normalized=True),
                line.interpolate(0.75, normalized=True),
            )
            c, d = (
                other_line.interpolate(0.25, normalized=True),
                other_line.interpolate(0.75, normalized=True),
            )
            dx, dn, ox, on = b.x - a.x, b.y - a.y, d.x - c.x, d.y - c.y
            cosine = (dx * ox + dn * on) / max(
                math.hypot(dx, dn) * math.hypot(ox, on), 1e-9
            )
            # Preserve crossing roads and independent same-direction ramps.
            if cosine > -0.95:
                continue
            probes = [line.interpolate(t / 10, normalized=True) for t in range(11)]
            if (
                max(abs(sample(records[i], p) - sample(records[j], p)) for p in probes)
                > 2.5
            ):
                continue
            links[i].add(j)
            links[j].add(i)
    remaining = set(links)
    reports = []
    while remaining:
        todo = [min(remaining)]
        component = set()
        while todo:
            i = todo.pop()
            if i in component:
                continue
            component.add(i)
            todo.extend(links[i] - component)
        remaining.difference_update(component)
        if len(component) < 2:
            continue
        members = [records[i] for i in sorted(component)]
        reference = max(members, key=lambda r: (r[1].length, -r[0]["id"]))[1]
        changed = 0.0
        for road, line, stations, heights in members:
            for index, point in enumerate(road["elevated_points"]):
                axis = reference.interpolate(reference.project(Point(point[:2])))
                datum = max(sample(record, axis) for record in members)
                distance = min(stations[index], line.length - stations[index])
                t = min(1.0, max(0.0, distance / 20))
                weight = t * t * (3 - 2 * t)
                y = heights[index] + max(0.0, datum - heights[index]) * weight
                changed = max(changed, y - heights[index])
                point[2] = y
        reports.append(
            {
                "name": members[0][0]["tags"]["name"],
                "source_ways": [record[0]["id"] for record in members],
                "rule": "shared upper longitudinal datum; exact approach anchors retained",
                "max_raise_m": round(changed, 6),
            }
        )
    reports.extend(align_segmented_bridge_profiles(roads, anchor_nodes=anchor_nodes))
    if reports:
        junctions = _reconcile_bridge_profile_junctions(roads, original, anchor_nodes)
        for report in reports:
            report["source_junction_lifts"] = junctions
    return reports


def _reconcile_bridge_profile_junctions(roads, original, anchor_nodes):
    """Fade shared-node lifts along genuine bridge edges, keeping land anchors.

    Parallel spans may have interior source joins to another bridge. Raising
    only the selected carriageway leaves its connector below the deck. One
    variable per exact source node shares the upper height; graph-distance
    cosine envelopes carry that lift through connected profiles without an
    isolated vertex spike or a connection to an unrelated XY crossing.
    """
    keys, positions, baseline, levels, graph, chains, owners = (
        {},
        [],
        [],
        [],
        [],
        {},
        {},
    )
    aligned_minimum = []
    for road in roads:
        source = {tuple(p): n for n, p in zip(road["nodes"], road["points"])}
        chain = []
        for index, (point, old) in enumerate(
            zip(road["elevated_points"], original[road["id"]])
        ):
            node = source.get(tuple(point[:2]))
            key = ("node", node) if node is not None else ("point", road["id"], index)
            if key not in keys:
                keys[key] = len(levels)
                positions.append(point[:2])
                baseline.append(old[2])
                levels.append(point[2])
                aligned_minimum.append(point[2])
                graph.append({})
            vertex = keys[key]
            baseline[vertex] = max(baseline[vertex], old[2])
            levels[vertex] = max(levels[vertex], point[2])
            aligned_minimum[vertex] = min(aligned_minimum[vertex], point[2])
            owners.setdefault(vertex, set()).add(road["id"])
            chain.append(vertex)
        chains[road["id"]] = chain
        for left, right in zip(chain, chain[1:]):
            distance = math.dist(positions[left], positions[right])
            if distance > 1e-6:
                graph[left][right] = graph[right][left] = distance
    anchors = {keys[("node", n)] for n in anchor_nodes if ("node", n) in keys}
    seeds = [
        (key[1], vertex, levels[vertex] - baseline[vertex])
        for key, vertex in keys.items()
        if key[0] == "node"
        and len(owners[vertex]) > 1
        and levels[vertex] - aligned_minimum[vertex] > 1e-8
        and vertex not in anchors
        and levels[vertex] > baseline[vertex] + 1e-8
    ]
    adjustments = []
    for node_id, seed, lift in sorted(seeds):
        radius = max(20.0, lift * math.pi / 0.12)
        distances, pending = {seed: 0.0}, [(0.0, seed)]
        while pending:
            distance, vertex = heapq.heappop(pending)
            if distance != distances[vertex] or vertex in anchors:
                continue
            for neighbour, length in graph[vertex].items():
                candidate = distance + length
                if candidate <= radius and candidate < distances.get(
                    neighbour, math.inf
                ):
                    distances[neighbour] = candidate
                    heapq.heappush(pending, (candidate, neighbour))
        # A fixed ordinary-road approach inside the envelope is its boundary,
        # never a raised height or a path to further ordinary streets.
        radius = min([radius, *(distances[v] for v in anchors if v in distances)])
        if radius <= 1e-6:
            continue
        for vertex, distance in distances.items():
            if distance < radius and vertex not in anchors:
                weight = (1 + math.cos(math.pi * distance / radius)) / 2
                levels[vertex] = max(levels[vertex], baseline[vertex] + lift * weight)
        adjustments.append(
            {
                "source_node": node_id,
                "lift_m": round(lift, 6),
                "blend_radius_m": round(radius, 6),
            }
        )
    for road in roads:
        for point, vertex in zip(road["elevated_points"], chains[road["id"]]):
            point[2] = levels[vertex]
    return adjustments


def apply(city, terrain):
    bridges = set(city["bridge_ways"])
    ordinary = [
        r
        for r in city["roads"]
        if r["id"] not in bridges and r["id"] not in set(city.get("tunnel_ways", []))
    ]
    elevated = [r for r in city["roads"] if r["id"] in bridges]
    positions = {
        nid: p for r in city["roads"] for nid, p in zip(r["nodes"], r["points"])
    }
    heights = {nid: max(0.9, terrain.height(*p)) for nid, p in positions.items()}
    # Bridge-end DTM can already fall down the bank beneath the deck. Anchor
    # the estimated end to the attached roadway uphill instead of forcing the
    # car down to that ground measurement then back onto the bridge.
    bridge_nodes = {n for r in elevated for n in r["nodes"]}
    for r in ordinary:
        line = LineString(r["points"])
        for index, node in [(0, r["nodes"][0]), (-1, r["nodes"][-1])]:
            if node not in bridge_nodes:
                continue
            samples = []
            for distance in [15, 20, 25]:
                station = min(distance, line.length)
                if index == -1:
                    station = line.length - station
                point = line.interpolate(station)
                samples.append(terrain.height(point.x, point.y))
            heights[node] = max(heights[node], float(np.median(samples)))
    # Source-connected components, never street-name buckets: parallel
    # decks and unnamed internal viaducts have independent endpoint anchors.
    by_node = {}
    for i, r in enumerate(elevated):
        for node in r["nodes"]:
            by_node.setdefault(node, []).append(i)
    remaining = set(range(len(elevated)))
    groups = []
    while remaining:
        pending, component = [min(remaining)], []
        while pending:
            i = pending.pop()
            if i not in remaining:
                continue
            remaining.remove(i)
            component.append(elevated[i])
            pending.extend(
                j
                for node in elevated[i]["nodes"]
                for j in by_node[node]
                if j in remaining
            )
        groups.append(component)
    profiles = []
    for roads in groups:
        names = sorted({r["tags"].get("name", "") for r in roads} - {""})
        name = " / ".join(names) or f"bridge way/{min(r['id'] for r in roads)}"
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
        clearance = 20.0 if set(names) & {"Västerbron", "Lilla Västerbron"} else 6.0
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
                "height_rule": "estimated deck from connected approach DTM; ramp <=8 percent above baseline",
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
        if r["id"] not in bridges:
            # Do not retain the shoreline DTM dip between the uphill anchor
            # and its estimated bridge deck end. Keep the source endpoints
            # shared, with a linear approach over the last thirty metres.
            for reverse, node in [(False, r["nodes"][0]), (True, r["nodes"][-1])]:
                if node not in bridge_nodes:
                    continue
                ordered = list(reversed(points)) if reverse else points
                stations = [0.0]
                for a, b in zip(ordered, ordered[1:]):
                    stations.append(stations[-1] + math.dist(a[:2], b[:2]))
                end = next(
                    (i for i, distance in enumerate(stations) if distance >= 30),
                    len(ordered) - 1,
                )
                distance = stations[end]
                if not distance:
                    continue
                start_y, end_y = ordered[0][2], ordered[end][2]
                for i in range(1, end):
                    t = stations[i] / distance
                    ordered[i][2] = start_y * (1 - t) + end_y * t
        r["elevated_points"] = points
    from road_profiles import smooth

    city["road_profile_diagnostics"] = smooth(
        ordinary, terrain, {n: heights[n] for n in bridge_nodes}
    )
    from bridges import enforce_crossing_clearance
    from road_profiles import diagnostics

    city["bridge_clearance"] = enforce_crossing_clearance(ordinary + elevated, bridges)
    city["bridge_profile_alignment"] = align_parallel_bridge_profiles(
        elevated, anchor_nodes={n for r in ordinary for n in r["nodes"]}
    )
    city["road_profile_diagnostics_after_clearance"] = diagnostics(ordinary)
    ground_segments, deck_segments, junctions, approaches = bridge_approaches(
        ordinary, elevated
    )
    road = RoadField(ground_segments, terrain, junctions=junctions)
    deck = RoadField(deck_segments, terrain, bridge=True, junctions=junctions)
    city["bridge_approaches"] = approaches
    city["terrain"] = terrain.metadata
    city["elevation_rules"] = {
        "road_height_floor_m": 0.9,
        "rule": "source-connected 5 m road profiles; longitudinal median and 25 m fairing footprint; 16 percent grade and 0.003 per metre vertical curvature targets; bridge anchors fixed",
        "max_grade_target": 0.16,
        "max_vertical_curvature_target_per_m": 0.003,
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
                LineString([p[:2] for p in r["elevated_points"]]).buffer(
                    r["width"] / 2, cap_style=1, join_style=2
                )
                for r in rs
            ]
        )

    from shapely.geometry import shape

    bounds = shape(city["bounds"])
    ground_roads = surface(ground_segments).intersection(bounds)
    bridge_roads = surface(deck_segments).intersection(bounds)
    # Remove only approach/bridge cap overlap. Other lower streets must still
    # pass under the deck with their original footprint intact.
    approach_ids = {a["source_way"] for a in approaches}
    unconnected_ground = surface(
        [r for r in ground_segments if r["id"] not in approach_ids]
    ).intersection(bounds)
    connector_caps = unary_union(
        [Point(seam[0], seam[1]).buffer(seam[3]) for seam in junctions]
    )
    ground_roads = ground_roads.difference(
        bridge_roads.intersection(connector_caps)
    ).union(unconnected_ground)
    by_id = {r["id"]: r for r in ordinary}
    approach_surface = surface(
        [{**by_id[a["source_way"]], "elevated_points": a["points"]} for a in approaches]
    ).intersection(bounds)
    city["bridge_approach_surface"] = mapping(approach_surface)
    city["ground_road_surface"] = mapping(ground_roads)
    city["bridge_road_surface"] = mapping(bridge_roads)
    return road, deck, ground_roads, bridge_roads

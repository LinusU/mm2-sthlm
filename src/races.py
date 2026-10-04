"""Native MM2 race export from retained source roads, independent of rust-mm2.

Topology is OSM node identity; geometric crossings never create graph joins.
Source points use east/north. Returned route positions use engine east/up/south.
Sparse gameplay gates remain independent of dense source-owned driving lines.
"""

import bisect
import heapq
import json
import math
from pathlib import Path

from shapely.geometry import LineString, Point, shape
from shapely.prepared import prep

ROOT = Path(__file__).resolve().parents[1]
PARAMETERS = (
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
)
TABLES = {
    "race": "mmracedata.csv",
    "blitz": "mmblitzdata.csv",
    "circuit": "mmcircuitdata.csv",
}
WAYPOINT_HEADER = "x,y,z,a,poly count,frame rate,state changes,texture changes,msg\n"
OPP_HEADER = (
    "x,y,z,brake,forward offset,side offset,target speed,speed start,side start\n"
)


def _stations(points):
    result = [0.0]
    for a, b in zip(points, points[1:]):
        result.append(result[-1] + math.dist(a[:2], b[:2]))
    return result


class SourceGraph:
    """Retained edges and owning road profiles, clipped by the playable mask."""

    def __init__(self, city):
        self.roads = {r["id"]: r for r in city["roads"]}
        self.positions = {}
        self.adjacency = {}
        self.edges = {}
        self.profiles = {}
        self.edge_stations = {}
        mask = city.get("bounds")
        boundary = prep(shape(mask).buffer(0.01)) if isinstance(mask, dict) else None
        self.boundary = boundary
        for road in city["roads"]:
            if len(road["nodes"]) != len(road["points"]):
                raise ValueError(f"Road {road['id']} has inconsistent source nodes")
            elevated = road.get("elevated_points")
            if not elevated:
                elevated = [[*p, city.get("road_y", 2.0)] for p in road["points"]]
            self.profiles[road["id"]] = (
                _stations(elevated),
                elevated,
                LineString([p[:2] for p in elevated]),
            )
            for node, position in zip(road["nodes"], road["points"]):
                if (
                    node in self.positions
                    and math.dist(position, self.positions[node]) > 0.01
                ):
                    raise ValueError(f"Source node {node} has inconsistent positions")
                self.positions[node] = position
            source_stations = _stations(road["points"])
            for edge_index, (a, b, pa, pb) in enumerate(
                zip(
                    road["nodes"], road["nodes"][1:], road["points"], road["points"][1:]
                )
            ):
                distance = math.dist(pa, pb)
                if distance < 1e-6 or (
                    boundary and not boundary.covers(LineString([pa, pb]))
                ):
                    continue
                self.adjacency.setdefault(a, {})[b] = distance
                self.adjacency.setdefault(b, {})[a] = distance
                begin, end = source_stations[edge_index : edge_index + 2]
                self.edge_stations[(a, b, road["id"])] = (begin, end)
                self.edge_stations[(b, a, road["id"])] = (end, begin)
                for u, v in ((a, b), (b, a)):
                    self.edges.setdefault((u, v), []).append(road["id"])
        for owners in self.edges.values():
            owners.sort()

    def samples(self, a, b, owner):
        stations, points, line = self.profiles[owner]
        begin, end = self.edge_stations[(a, b, owner)]
        low, high = sorted((begin, end))
        positions = [low, *(s for s in stations if low + 1e-6 < s < high - 1e-6), high]
        positions = sorted(set(positions))
        # Preserve profile vertices while subdividing any remaining long flat leg.
        dense = [positions[0]]
        for left, right in zip(positions, positions[1:]):
            count = max(1, math.ceil((right - left) / 5.0))
            dense.extend(left + (right - left) * i / count for i in range(1, count + 1))
        result = []
        for station in dense:
            index = min(
                max(0, bisect.bisect_right(stations, station) - 1), len(points) - 2
            )
            span = stations[index + 1] - stations[index]
            t = (station - stations[index]) / span if span > 1e-9 else 0.0
            first, second = points[index : index + 2]
            p = [first[k] + (second[k] - first[k]) * t for k in range(3)]
            result.append([p[0], p[2], -p[1]])
        return result if begin <= end else list(reversed(result))

    def node_point(self, node, owner):
        stations, points, line = self.profiles[owner]
        station = line.project(Point(self.positions[node]))
        index = min(max(0, bisect.bisect_right(stations, station) - 1), len(points) - 2)
        span = stations[index + 1] - stations[index]
        t = (station - stations[index]) / span if span > 1e-9 else 0.0
        y = points[index][2] + (points[index + 1][2] - points[index][2]) * t
        x, north = self.positions[node]
        return [x, y, -north]


def source_graph(city):
    return SourceGraph(city)


def resolve_anchor(city, anchor, graph=None):
    graph = graph or source_graph(city)
    road = graph.roads.get(anchor["way_id"])
    node = anchor["node_id"]
    if road is None or node not in road["nodes"] or node not in graph.positions:
        raise ValueError(f"Anchor lacks retained source ownership: {anchor}")
    if node not in graph.adjacency:
        raise ValueError(f"Anchor is outside the boundary-safe source graph: {anchor}")
    return {
        **anchor,
        "position": graph.node_point(node, road["id"]),
        "width_m": road["width"],
        "tags": road.get("tags", {}),
    }


def _shortest(graph, start, end):
    queue = [(0.0, start)]
    distances = {start: 0.0}
    previous = {}
    while queue:
        distance, node = heapq.heappop(queue)
        if distance != distances[node]:
            continue
        if node == end:
            path = [end]
            while path[-1] != start:
                path.append(previous[path[-1]])
            return list(reversed(path))
        for neighbor, length in graph.adjacency.get(node, {}).items():
            candidate = distance + length
            if candidate < distances.get(neighbor, math.inf):
                distances[neighbor] = candidate
                previous[neighbor] = node
                heapq.heappush(queue, (candidate, neighbor))
    raise ValueError(f"Disconnected source route: {start} -> {end}")


def route(city, anchors, closed=False, graph=None):
    graph = graph or source_graph(city)
    resolved = [resolve_anchor(city, a, graph) for a in anchors]
    if len(resolved) < 2:
        raise ValueError("A source route needs at least two anchors")
    itinerary = resolved + (
        [resolved[0]]
        if closed and resolved[-1]["node_id"] != resolved[0]["node_id"]
        else []
    )
    nodes, edges, points, owners, length = [], [], [], [], 0.0
    for start, end in zip(itinerary, itinerary[1:]):
        path = _shortest(graph, start["node_id"], end["node_id"])
        if not nodes:
            nodes.append(path[0])
        for a, b in zip(path, path[1:]):
            candidates = graph.edges[(a, b)]
            # Prefer the anchor's exact owner where it owns the adjoining edge;
            # otherwise deterministic retained source ownership supplies height.
            preferred = (
                start["way_id"]
                if a == start["node_id"]
                else end["way_id"]
                if b == end["node_id"]
                else None
            )
            owner = preferred if preferred in candidates else candidates[0]
            samples = graph.samples(a, b, owner)
            if points and math.dist(points[-1], samples[0]) > 1.0:
                raise ValueError(f"Source join has incompatible heights at {a}")
            points.extend(samples if not points else samples[1:])
            nodes.append(b)
            owners.append(owner)
            edges.append({"from": a, "to": b, "way_id": owner})
            length += graph.adjacency[a][b]
    if not points:
        raise ValueError("Source route has zero length")
    return {
        "nodes": nodes,
        "points": points,
        "edges": edges,
        "way_ids": sorted(set(owners)),
        "length_m": length,
        "minimum_width_m": min(graph.roads[w]["width"] for w in owners),
        "closed": closed,
    }


def _heading(first, second):
    return math.degrees(math.atan2(-(second[0] - first[0]), -(second[2] - first[2])))


def _grid(graph, start, forward_points, count):
    """Single-file source-safe grid behind the line, no lateral invented points."""
    start_node = start["node_id"]
    first = forward_points[0]
    next_point = next(p for p in forward_points[1:] if math.dist(p, first) > 1)
    if count == 0:
        return [{"position": first, "yaw_deg": _heading(first, next_point)}]
    desired = [first[0] - next_point[0], -(first[2] - next_point[2])]
    node, visited, backwards = start_node, {start_node}, [first]
    distance = 0.0
    required = count * 8.0
    while distance < required:
        options = []
        for neighbor in graph.adjacency.get(node, {}):
            if neighbor in visited:
                continue
            dx = graph.positions[neighbor][0] - graph.positions[node][0]
            dn = graph.positions[neighbor][1] - graph.positions[node][1]
            norm = math.hypot(dx, dn) * math.hypot(*desired)
            score = (dx * desired[0] + dn * desired[1]) / norm if norm else -1
            owners = [
                w for w in graph.edges[(node, neighbor)] if graph.roads[w]["width"] >= 5
            ]
            if score > 0.15 and owners:
                options.append((score, -neighbor, neighbor, owners[0]))
        if not options:
            raise ValueError(
                f"Start {start_node} has no source-safe grid approach for {count} opponents"
            )
        _, _, neighbor, owner = max(options)
        samples = graph.samples(node, neighbor, owner)
        backwards.extend(samples[1:])
        distance += graph.adjacency[node][neighbor]
        desired = [
            graph.positions[neighbor][0] - graph.positions[node][0],
            graph.positions[neighbor][1] - graph.positions[node][1],
        ]
        node = neighbor
        visited.add(node)
    stations = _stations([[p[0], p[2]] for p in backwards])
    slots = []
    yaw = _heading(first, next_point)
    for index in range(count + 1):
        station = index * 8.0
        j = min(max(0, bisect.bisect_right(stations, station) - 1), len(backwards) - 2)
        span = stations[j + 1] - stations[j]
        t = (station - stations[j]) / span if span else 0.0
        pos = [
            backwards[j][k] + (backwards[j + 1][k] - backwards[j][k]) * t
            for k in range(3)
        ]
        facing = yaw if index == 0 else _heading(backwards[j + 1], backwards[j])
        slots.append({"position": pos, "yaw_deg": facing})
    return slots


def _family(catalog):
    mode = catalog.get("family", catalog.get("mode"))
    return "race" if mode == "checkpoint" else mode


def _anchors(event, family, order=None):
    gates = event["checkpoints"]
    if family == "circuit":
        return [event["start"], *gates]
    order = (
        order
        if order is not None
        else event.get("suggested_order", list(range(len(gates))))
    )
    if sorted(order) != list(range(len(gates))):
        raise ValueError("AnyOrder itinerary must cover every checkpoint exactly once")
    return [event["start"], *(gates[i] for i in order), event["finish"]]


def through_margins(graph, driving, gates, reach_m=14.0):
    """Audit source gate traversal beyond the native AI point-reach distance."""
    points = driving["points"]
    stations = _stations([[p[0], p[2]] for p in points])
    result = []
    for anchor in gates:
        center = graph.node_point(anchor["node_id"], anchor["way_id"])
        angle = math.radians(gate_heading(graph, anchor))
        normal = [-math.sin(angle), math.cos(angle)]
        margin = None
        for index, point in enumerate(points):
            if (
                math.hypot(point[0] - center[0], point[2] - center[2]) > 0.05
                or abs(point[1] - center[1]) > 1
            ):
                continue
            before = max(0, bisect.bisect_left(stations, stations[index] - 40) - 1)
            after = min(
                len(points) - 1, bisect.bisect_left(stations, stations[index] + 40)
            )
            signed = [
                (p[0] - center[0]) * normal[0] + (p[2] - center[2]) * normal[1]
                for p in (points[before], points[after])
            ]
            if signed[0] * signed[1] < 0 and min(abs(v) for v in signed) > reach_m:
                margin = {
                    "label": anchor["label"],
                    "node_id": anchor["node_id"],
                    "way_id": anchor["way_id"],
                    "before_m": abs(signed[0]),
                    "after_m": abs(signed[1]),
                    "minimum_plane_margin_m": min(abs(v) for v in signed),
                }
                break
        if margin is None:
            raise ValueError(
                f"No through crossing beyond {reach_m:g} m reach: {anchor['label']}"
            )
        result.append(margin)
    return result


def finish_runout(graph, driving, distance_m=60.0):
    """Continue beyond the finish using retained source edges and owned heights."""
    points = list(driving["points"])
    node = driving["nodes"][-1]
    visited = set(driving["nodes"][-2:])
    desired = [points[-1][0] - points[-2][0], points[-1][2] - points[-2][2]]
    edges = []
    walked = 0.0
    while walked < distance_m:
        choices = []
        for neighbor in graph.adjacency.get(node, {}):
            if neighbor in visited:
                continue
            dx = graph.positions[neighbor][0] - graph.positions[node][0]
            dz = -(graph.positions[neighbor][1] - graph.positions[node][1])
            norm = math.hypot(dx, dz) * math.hypot(*desired)
            score = (dx * desired[0] + dz * desired[1]) / norm if norm else -1
            if score < -0.01:
                continue
            for owner in graph.edges[(node, neighbor)]:
                if graph.roads[owner]["width"] < 5:
                    continue
                samples = graph.samples(node, neighbor, owner)
                if abs(samples[0][1] - points[-1][1]) <= 1:
                    choices.append((score, -neighbor, -owner, neighbor, owner, samples))
        if not choices:
            raise ValueError("Finish has no forward source-connected driving runout")
        _, _, _, neighbor, owner, samples = max(choices)
        edges.append({"from": node, "to": neighbor, "way_id": owner})
        for point in samples[1:]:
            previous = points[-1]
            span = math.hypot(point[0] - previous[0], point[2] - previous[2])
            remaining = distance_m - walked
            if span >= remaining:
                t = remaining / span
                points.append(
                    [previous[k] + (point[k] - previous[k]) * t for k in range(3)]
                )
                walked = distance_m
                break
            points.append(point)
            walked += span
        desired = [
            graph.positions[neighbor][0] - graph.positions[node][0],
            -(graph.positions[neighbor][1] - graph.positions[node][1]),
        ]
        node = neighbor
        visited.add(node)
    return {
        **driving,
        "points": points,
        "length_m": driving["length_m"] + walked,
        "finish_runout": {
            "length_m": walked,
            "edges": edges,
            "end_position": points[-1],
        },
    }


def gate_heading(graph, anchor):
    """Gate plane normal follows its owning source road, in waypoint convention."""
    road = graph.roads[anchor["way_id"]]
    index = road["nodes"].index(anchor["node_id"])
    points = road["points"]
    previous = max(0, index - 1)
    following = min(len(points) - 1, index + 1)
    if index == 0 and road["nodes"][0] == road["nodes"][-1]:
        previous = len(points) - 2
    before, after = points[previous], points[following]
    dx, dz = after[0] - before[0], -(after[1] - before[1])
    if math.hypot(dx, dz) < 0.01:
        point = points[index]
        dx, dz = after[0] - point[0], -(after[1] - point[1])
    if math.hypot(dx, dz) < 0.01:
        raise ValueError("Gate owning road has no finite local tangent")
    return math.degrees(math.atan2(-dx, dz)) % 360


def gate_radius(width_m):
    """Whole road corridor plus four metres of normal passing clearance."""
    return max(6.0, min(15.0, width_m / 2 + 4.0))


def _csv_row(point, heading, radius):
    return ",".join(f"{v:.5f}" for v in [*point, heading, radius]) + ",0,0,0,\n"


def write(out, city, catalog_paths=None, opponent_vehicle_geo="sthlm_racer"):
    """Export requested native families; absent catalogs remain absent.

    Requires a legitimately authored mod vehicle matching opponent_vehicle_geo
    or explicit engine procedural-opponent support for physical AI spawning.
    No engine tuning, vehicle physics or retail records are copied here.
    """
    out = Path(out)
    race_dir = out / "race/stockholm"
    race_dir.mkdir(parents=True, exist_ok=True)
    paths = (
        catalog_paths
        if catalog_paths is not None
        else [
            ROOT / "config/races" / f"{name}.json"
            for name in ("checkpoint", "blitz", "circuit")
        ]
    )
    graph = source_graph(city)
    report = {
        "schema": 1,
        "city": "stockholm",
        "axes": "X east, Y up, Z south",
        "opponent_vehicle_geo": opponent_vehicle_geo,
        "events": [],
    }
    families = set()
    for path in paths:
        path = Path(path)
        if not path.exists():
            continue
        catalog = json.loads(path.read_text())
        family = _family(catalog)
        if catalog.get("schema") != 1 or family not in TABLES or family in families:
            raise ValueError(f"Invalid or duplicate native family in {path}")
        families.add(family)
        expected_rule = "Ordered" if family == "circuit" else "AnyOrder"
        if catalog["native_rule"] != expected_rule:
            raise ValueError("Native family and checkpoint rule disagree")
        table = [",".join(["Description", *PARAMETERS, *PARAMETERS])]
        for index, event in enumerate(catalog["events"]):
            if event["index"] != index:
                raise ValueError("Native event row indexes must be contiguous")
            stem = f"{family}{index}"
            if any(c in event["name"] for c in ",\n\r"):
                raise ValueError("Native descriptions cannot contain CSV delimiters")
            table.append(
                ",".join(
                    [
                        event["name"],
                        *[
                            str(event[rank][field])
                            for rank in ("amateur", "professional")
                            for field in PARAMETERS
                        ],
                    ]
                )
            )
            visible = [event["start"], *event["checkpoints"]] + (
                [] if family == "circuit" else [event["finish"]]
            )
            resolved = [resolve_anchor(city, anchor, graph) for anchor in visible]
            if len(resolved) < (4 if family == "circuit" else 3):
                raise ValueError("Insufficient native waypoint rows")
            for i, first in enumerate(resolved):
                for second in resolved[i + 1 :]:
                    horizontal = math.dist(
                        [first["position"][0], first["position"][2]],
                        [second["position"][0], second["position"][2]],
                    )
                    if (
                        horizontal
                        <= gate_radius(first["width_m"])
                        + gate_radius(second["width_m"])
                        and abs(first["position"][1] - second["position"][1]) <= 16
                    ):
                        raise ValueError(
                            "Native gate cylinders overlap; move source anchors"
                        )
            itinerary = event.get("route_via") or _anchors(event, family)
            dense = route(city, itinerary, closed=family == "circuit", graph=graph)
            # Validate dense guide against every visible gate in engine XZ space.
            line = LineString([[p[0], p[2]] for p in dense["points"]])
            for anchor in resolved:
                if (
                    line.distance(Point(anchor["position"][0], anchor["position"][2]))
                    > 0.05
                ):
                    raise ValueError(
                        f"Driving guide misses gameplay gate: {anchor['label']}"
                    )
            guide = dense if family == "circuit" else finish_runout(graph, dense)
            if event.get("opponent_route_via"):
                through_margins(graph, guide, visible[1:])
            maximum = max(
                event[rank]["Opponents"] for rank in ("amateur", "professional")
            )
            grid = _grid(graph, event["start"], dense["points"], maximum)
            (race_dir / f"{stem}_strtpnts").write_text(
                "".join(
                    ",".join(f"{v:.5f}" for v in [*slot["position"], slot["yaw_deg"]])
                    + ",0,0,0,0,0,\n"
                    for slot in grid
                )
            )
            heading = grid[0]["yaw_deg"]
            (race_dir / f"{stem}waypoints.csv").write_text(
                WAYPOINT_HEADER
                + "".join(
                    _csv_row(
                        anchor["position"],
                        gate_heading(graph, anchor),
                        gate_radius(anchor["width_m"]),
                    )
                    for anchor in resolved
                )
            )
            variant_reports = {}
            for rank, tag in (("amateur", "a"), ("professional", "p")):
                params = event[rank]
                guide_dir = out / "qa/races"
                guide_dir.mkdir(parents=True, exist_ok=True)
                guide_path = guide_dir / f"{stem}-{tag}-guide.opp"
                speed_goal = event.get("target_speed_mps", {}).get(rank, 18.0)
                guide_path.write_text(
                    OPP_HEADER
                    + "".join(
                        ",".join(
                            f"{v:.5f}"
                            for v in [
                                *point,
                                heading if j == 0 else 0,
                                0,
                                0,
                                speed_goal,
                                0,
                                0,
                            ]
                        )
                        + "\n"
                        for j, point in enumerate(guide["points"])
                    )
                )
                count = params["Opponents"]
                orders = event.get("opponent_orders", [event.get("suggested_order")])
                roster = []
                lengths = []
                margins = []
                for opponent in range(count):
                    plan_index = opponent % len(orders)
                    order = orders[plan_index]
                    authored_plans = event.get("opponent_route_via")
                    driving = (
                        route(city, authored_plans[plan_index], graph=graph)
                        if authored_plans
                        else (
                            dense
                            if family == "circuit"
                            or event.get("route_via")
                            or order is None
                            or order == event.get("suggested_order")
                            else route(
                                city, _anchors(event, family, order), graph=graph
                            )
                        )
                    )
                    if family != "circuit":
                        driving = finish_runout(graph, driving)
                    if authored_plans:
                        margins.append(through_margins(graph, driving, visible[1:]))
                    name = f"{stem}-{tag}-{opponent}.opp"
                    speed = event.get("target_speed_mps", {}).get(rank, 18.0)
                    (race_dir / name).write_text(
                        OPP_HEADER
                        + "".join(
                            ",".join(
                                f"{v:.5f}"
                                for v in [
                                    *point,
                                    heading if j == 0 else 0,
                                    0,
                                    0,
                                    speed,
                                    0,
                                    0,
                                ]
                            )
                            + "\n"
                            for j, point in enumerate(driving["points"])
                        )
                    )
                    throttle = 0.65 if rank == "amateur" else 0.85
                    corner = 0.9 if rank == "amateur" else 1.05
                    # RACE-14: throttle, unused, look-ahead, brake floor,
                    # avoid traffic/props/player/AI, unusual pathfinding, corner speed.
                    tail = f"{throttle:.2f} 0 75 0.7 1 1 1 1 0 {corner:.2f}"
                    roster.append(
                        f"{event.get('opponent_vehicle_geo', opponent_vehicle_geo)} {name} {tail}"
                    )
                    lengths.append(driving["length_m"])
                suffix = ".aimap" if tag == "a" else ".aimap_p"
                (race_dir / (stem + suffix)).write_text(
                    f"[Density]\n{params['Ambient']}\n[Police]\n0\n[Opponent]\n{count}\n"
                    + "\n".join(roster)
                    + "\n"
                )
                variant_reports[rank] = {
                    "qa_guide": str(guide_path.relative_to(out)),
                    "opponents": count,
                    "opponent_route_lengths_m": lengths,
                    "source_through_margins": margins,
                    "time_limit_s": params["TimeLimit"] if family == "blitz" else None,
                    "target_speed_goal_mps": event.get("target_speed_mps", {}).get(
                        rank
                    ),
                }
            report["events"].append(
                {
                    "id": event["id"],
                    "family": family,
                    "index": index,
                    "name": event["name"],
                    "rule": expected_rule,
                    "visible_waypoint_rows": len(visible),
                    "anchors": [
                        {
                            k: a[k]
                            for k in (
                                "node_id",
                                "way_id",
                                "label",
                                "position",
                                "width_m",
                            )
                        }
                        | {
                            "radius_m": gate_radius(a["width_m"]),
                            "heading_deg": gate_heading(graph, a),
                        }
                        for a in resolved
                    ],
                    "route": dense,
                    "finish_runout": guide.get("finish_runout"),
                    "grid": grid,
                    "variants": variant_reports,
                }
            )
        (race_dir / TABLES[family]).write_text("\n".join(table) + "\n")
    # The native catalog inspects all four tables. An explicitly empty school
    # is complete data; it creates no placeholder lessons or unsupported modes.
    crash_table = race_dir / "mmcrashdata.csv"
    if not crash_table.exists():
        crash_table.write_text(
            ",".join(["Description", *PARAMETERS, *PARAMETERS]) + "\n"
        )
    (out / "races.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return report

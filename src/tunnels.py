"""Sourced underground corridors with independent authored roadway heights.

The terrain is surface ground. Tunnel levels are estimates, never DTM samples.
Shared source nodes connect corridors; coincident XY coordinates do not.
"""

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from shapely.geometry import LineString, mapping, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "config/overrides/tunnel-profiles.json"
MOTOR_CLASSES = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
    "unclassified",
    "residential",
    "living_street",
}


def internal_tunnel_ways(ways, nodes, cfg, playable_mask, blocked=()):
    """Select source-connected public motor tunnel networks with real portals.

    Building passages need facade openings and stay omitted. A retained network
    needs two genuine surface connections; source continuations outside the
    mask become explicitly closed underground ends, not fabricated portals.
    """
    from sthlm import project

    mask = playable_mask.buffer(1)
    bounded, outside, surface_nodes = [], set(), set()
    blocked = set(blocked) | {"Fredhällstunneln"}
    for wid, way in sorted(ways.items()):
        tags = way.get("tags", {})
        if (
            tags.get("highway") not in MOTOR_CLASSES
            or tags.get("name") in blocked
            or tags.get("access") in {"private", "no"}
            or tags.get("motor_vehicle") in {"private", "no"}
            or any(n not in nodes for n in way["nodes"])
            or len(way["nodes"]) < 2
        ):
            continue
        line = LineString(
            [
                project(nodes[n]["lon"], nodes[n]["lat"], cfg["origin"])
                for n in way["nodes"]
            ]
        )
        if line.length <= 0:
            continue
        if tags.get("tunnel") == "yes":
            if mask.covers(line):
                bounded.append(way)
            else:
                outside.update(way["nodes"])
        elif tags.get("tunnel") in (None, "no") and mask.covers(line):
            surface_nodes.update(way["nodes"])
    allowed = []
    for group in components(bounded):
        graph = {}
        for way in group:
            for a, b in zip(way["nodes"], way["nodes"][1:]):
                graph.setdefault(a, set()).add(b)
                graph.setdefault(b, set()).add(a)
        portals = set(graph) & surface_nodes
        ends = {n for n, ns in graph.items() if len(ns) == 1}
        if len(portals) >= 2 and ends <= surface_nodes | outside:
            allowed.extend(way["id"] for way in group)
    return sorted(allowed)


def components(roads):
    """Group by source node identity, including source-connected branches."""
    adjacent = {}
    for i, road in enumerate(roads):
        for node in road["nodes"]:
            adjacent.setdefault(node, set()).add(i)
    unseen = set(range(len(roads)))
    groups = []
    while unseen:
        seed = min(unseen)
        unseen.remove(seed)
        pending, group = [seed], []
        while pending:
            i = pending.pop()
            group.append(roads[i])
            for node in roads[i]["nodes"]:
                for j in sorted(adjacent[node] & unseen):
                    unseen.remove(j)
                    pending.append(j)
        groups.append(sorted(group, key=lambda r: r["id"]))
    return groups


def _samples(roads, spacing):
    keys, xy, chains, edges = {}, [], [], []
    for road in roads:
        chain = []
        for j, (a, b) in enumerate(zip(road["points"], road["points"][1:])):
            count = max(1, math.ceil(math.dist(a, b) / spacing))
            for k in range(count):
                key = ("node", road["nodes"][j]) if k == 0 else (road["id"], j, k)
                if key not in keys:
                    keys[key] = len(xy)
                    t = k / count
                    xy.append(tuple(a[d] + (b[d] - a[d]) * t for d in range(2)))
                chain.append(keys[key])
        key = ("node", road["nodes"][-1])
        if key not in keys:
            keys[key] = len(xy)
            xy.append(tuple(road["points"][-1]))
        chain.append(keys[key])
        chains.append(chain)
        edges.extend(
            (a, b, math.dist(xy[a], xy[b])) for a, b in zip(chain, chain[1:]) if a != b
        )
    return (
        keys,
        xy,
        chains,
        list({tuple(sorted((a, b))): (a, b, d) for a, b, d in edges}.values()),
    )


def prepare(city, terrain):
    """Author floor profiles after surface/bridge profiles exist.

    Returns only underground roads. Surface fields must be built without these
    roads. Only exposed portal ramps cut the terrain, not covered tunnel buffers.
    """
    from elevation import distances

    cfg = json.loads(RULES.read_text())
    ids = set(city.get("tunnel_ways", []))
    tunnels = [r for r in city["roads"] if r["id"] in ids]
    for road in tunnels:
        tags = road["tags"]
        override = cfg.get("road_overrides", {}).get(str(road["id"]))
        if override:
            width = override["width_m"]
            if not math.isfinite(width) or not 3 <= width <= 14:
                raise ValueError("invalid authored tunnel width")
            road["width"] = width
            road["tunnel_width_rule"] = override["reason"]
            continue
        # The ordinary-city nine-metre default can make the walls of paired
        # one-lane bores intersect the opposite lane at close OSM alignments.
        # Respect explicit source widths; otherwise infer bounded lane width.
        if "width" not in tags and "lanes" in tags:
            try:
                lanes = int(tags["lanes"])
            except (ValueError, TypeError):
                continue
            if 1 <= lanes <= 4:
                road["width"] = min(14, 3.4 * lanes + 1.6)
                road["tunnel_width_rule"] = "3.4 m per sourced lane + 1.6 m total verge"
    surface = [r for r in city["roads"] if r["id"] not in ids]
    levels = {}
    for road in surface:
        # Resampled surface profiles retain both source endpoint positions.
        points = road.get("elevated_points", [])
        if points:
            levels[road["nodes"][0]] = points[0][2]
            levels[road["nodes"][-1]] = points[-1][2]
    records, cuts, closures = [], [], []
    for group in components(tunnels):
        keys, xy, chains, edges = _samples(group, cfg["sample_spacing_m"])
        graph = {i: {} for i in range(len(xy))}
        for a, b, length in edges:
            graph[a][b] = graph[b][a] = length
        anchors = {
            keys[("node", n)]: y for n, y in levels.items() if ("node", n) in keys
        }
        # A boundary endpoint without a retained surface connection is not a
        # portal. Keep it underground; never invent an XY surface connection.
        if not anchors:
            baseline = float(np.median([terrain.height(*p) for p in xy]))
            anchors = {min(graph): baseline - cfg["burial_depth_m"]}
            portals = {}
        else:
            portals = dict(anchors)
        heights = np.full(len(xy), sum(anchors.values()) / len(anchors))
        left, right = np.array([(a, b) for a, b, _ in edges], dtype=int).T
        degree = np.maximum(np.bincount(np.r_[left, right], minlength=len(xy)), 1)
        for _ in range(cfg["fairing_iterations"]):
            total = np.bincount(
                np.r_[left, right],
                weights=np.r_[heights[right], heights[left]],
                minlength=len(xy),
            )
            heights += 0.5 * (total / degree - heights)
            for i, y in anchors.items():
                heights[i] = y
        for node, key in keys.items():
            if node[0] == "node" and len(graph[key]) == 1 and key not in portals:
                closures.append(node[1])
        distance = distances(graph, portals) if portals else {}
        depth = np.array(
            [
                cfg["burial_depth_m"]
                * (
                    1
                    - math.cos(
                        math.pi
                        * min(
                            1, distance.get(i, math.inf) / cfg["portal_ramp_length_m"]
                        )
                    )
                )
                / 2
                if portals
                else 0
                for i in range(len(xy))
            ]
        )
        heights -= depth
        for road, chain in zip(group, chains):
            road["elevated_points"] = [[*xy[i], float(heights[i])] for i in chain]
            # Building passages follow the street level, with an opening cut
            # into the building facade by the exporter rather than a deep bore.
            if road["tags"].get("tunnel") == "building_passage":
                road["elevated_points"] = [
                    [*xy[i], float(heights[i] + depth[i])] for i in chain
                ]
            exposed = []
            for a, b in zip(road["elevated_points"], road["elevated_points"][1:]):
                if (
                    min(terrain.height(*a[:2]) - a[2], terrain.height(*b[:2]) - b[2])
                    < cfg["clearance_m"] + cfg["roof_thickness_m"]
                ):
                    exposed.append(
                        LineString([a[:2], b[:2]]).buffer(
                            road["width"] / 2 + 0.4, cap_style=2, join_style=2
                        )
                    )
            cuts.extend(exposed)
            points = road["elevated_points"]
            road["tunnel_clearance_m"] = cfg["clearance_m"]
            road["tunnel_cover_m"] = [terrain.height(*p[:2]) - p[2] for p in points]
            records.append(
                {
                    "source_way": road["id"],
                    "name": road["tags"].get("name", ""),
                    "height_range_m": [
                        min(p[2] for p in points),
                        max(p[2] for p in points),
                    ],
                    "max_grade": max(
                        (
                            abs(b[2] - a[2]) / math.dist(a[:2], b[:2])
                            for a, b in zip(points, points[1:])
                            if math.dist(a[:2], b[:2]) > 0
                        ),
                        default=0,
                    ),
                    "shared_source_portal_nodes": sorted(
                        n for n in road["nodes"] if n in levels
                    ),
                    "profile_rule": "authored underground estimate; source-connected surface portals",
                }
            )
    city["tunnel_closed_nodes"] = sorted(set(closures))
    city["tunnel_profiles"] = records
    city["tunnel_terrain_cutout"] = mapping(
        unary_union(cuts).intersection(shape(city["bounds"]))
    )
    city["tunnel_profile_rules"] = cfg
    return tunnels


def clip_surface(geometry, city):
    """Remove exposed ramps from ordinary roads/shoulders, keeping bore cover.

    Apply after prepare() to surface road footprints and paving, before native
    meshing. Tunnel floors and overpass decks retain their own source geometry.
    """
    cutout = city.get("tunnel_terrain_cutout")
    return geometry.difference(shape(cutout)) if cutout else geometry


def road_surface(road):
    return LineString([p[:2] for p in road["elevated_points"]]).buffer(
        road["width"] / 2, cap_style=1, join_style=2
    )


def write_roads(writer, city, terrain):
    """Export native driveable floors per source way, isolating crossing levels."""
    from elevation import RoadField

    ids = set(city.get("tunnel_ways", []))
    bounds = shape(city["bounds"])
    for road in city["roads"]:
        if road["id"] in ids:
            field = RoadField([road], terrain, bridge=True)
            surface = road_surface(road).intersection(bounds)
            try:
                from road_surfaces import render
            except ImportError:
                writer.surface(surface, field, "road", road=True)
            else:
                render(
                    writer,
                    {"roads": [road], "bridge_ways": []},
                    surface,
                    field,
                    road_height=lambda r, x, n: field(x, n),
                    station_height=field.height_at_station,
                )


def surface_wall_caps(city):
    """Exact upper ground-road profiles that can cap exposed retaining walls.

    This changes shell collision only; it never connects crossed source ways
    or alters underground floors, covered roofs or profile headroom.
    """
    from elevation import RoadField

    ids = set(city.get("tunnel_ways", []))
    records = [
        (road_surface(road), RoadField([road], None, bridge=True))
        for road in city["roads"]
        if road["id"] not in ids
        and road["tags"].get("bridge") != "yes"
        and road.get("elevated_points")
    ]

    tree = STRtree([surface for surface, _ in records])

    def candidates(edge):
        return [
            records[int(index)] for index in tree.query(edge, predicate="intersects")
        ]

    return candidates


def shell_mesh(road, cfg, openings=(), closed_nodes=(), surface_caps=()):
    """Open-ended inward facing shell following exact floor cross sections."""
    wall, roof, lamps = [], [], []
    points = road["elevated_points"]
    half = road["width"] / 2
    covers = road.get("tunnel_cover_m", [math.inf] * len(points))
    sections = []
    for j, p in enumerate(points):
        a, b = points[max(0, j - 1)], points[min(len(points) - 1, j + 1)]
        dx, dn = b[0] - a[0], b[1] - a[1]
        length = max(math.hypot(dx, dn), 1e-6)
        sections.append(
            [
                (p[0] - dn / length * s * half, p[2], -p[1] - dx / length * s * half)
                for s in (-1, 1)
            ]
        )

    def quad(dest, a, b, c, d):
        # Native PKG meshes are visual plus triangle collision; both directions
        # keep the shell visible from above as well as from a driver's seat.
        dest.extend([(a, b, c), (a, c, d), (c, b, a), (d, c, a)])

    for i, (a, b) in enumerate(zip(sections, sections[1:])):
        for side in (0, 1):
            aa, bb = a[side], b[side]
            upa = (aa[0], aa[1] + min(cfg["clearance_m"], max(0.12, covers[i])), aa[2])
            upb = (
                bb[0],
                bb[1] + min(cfg["clearance_m"], max(0.12, covers[i + 1])),
                bb[2],
            )
            edge = LineString([(aa[0], -aa[2]), (bb[0], -bb[2])])
            # An exposed retaining wall can rise through a separately authored
            # upper ground junction. Cap only its protruding top, following the
            # exact upper road profile, while keeping the tunnel floor intact.
            if (
                min(covers[i], covers[i + 1])
                < cfg["clearance_m"] + cfg["roof_thickness_m"]
            ):
                candidates = (
                    surface_caps(edge) if callable(surface_caps) else surface_caps
                )
                for surface, field in candidates:
                    overlap = edge.intersection(surface)
                    if overlap.is_empty:
                        continue
                    probes = [overlap.representative_point()]
                    if overlap.geom_type == "LineString":
                        probes.extend(overlap.boundary.geoms)
                    cap = min(field(p.x, p.y) for p in probes) - 0.05
                    # A lower or same-level road is not an upper retaining-wall
                    # datum. Restrict this to a small protrusion at its top.
                    if (
                        max(aa[1], bb[1]) + 0.12 < cap
                        and min(upa[1], upb[1]) - 1.0 <= cap
                    ):
                        upa = (upa[0], min(upa[1], cap), upa[2])
                        upb = (upb[0], min(upb[1], cap), upb[2])
            # A branch can intersect the end of a five-metre wall panel even
            # when its midpoint is outside the aperture. Open the entire
            # touched panel so a turn cannot meet an invisible half-wall.
            if not any(opening.intersects(edge) for opening in openings):
                quad(wall, aa, bb, upb, upa)
        # DTM is surface ground. An exposed ramp has retaining walls, not a
        # full-height roof canopy sticking five metres above the street.
        if min(covers[i], covers[i + 1]) < cfg["clearance_m"] + cfg["roof_thickness_m"]:
            continue
        ra = [(p[0], p[1] + cfg["clearance_m"], p[2]) for p in a]
        rb = [(p[0], p[1] + cfg["clearance_m"], p[2]) for p in b]
        quad(roof, ra[0], rb[0], rb[1], ra[1])
        # Original pale ceiling fixtures, informed by the city's Klara photo.
        # These are static mesh bands, not a second lighting simulation.
        for offset in (0.24, 0.76):

            def lamp_point(section, t):
                start, end = section
                return (
                    start[0] * (1 - t) + end[0] * t,
                    start[1] * (1 - t) + end[1] * t + cfg["clearance_m"] - 0.06,
                    start[2] * (1 - t) + end[2] * t,
                )

            qa = lamp_point(a, offset - 0.02)
            qb = lamp_point(b, offset - 0.02)
            qc = lamp_point(b, offset + 0.02)
            qd = lamp_point(a, offset + 0.02)
            quad(lamps, qa, qb, qc, qd)
        topa = [(p[0], p[1] + cfg["roof_thickness_m"], p[2]) for p in ra]
        topb = [(p[0], p[1] + cfg["roof_thickness_m"], p[2]) for p in rb]
        quad(roof, topa[0], topb[0], topb[1], topa[1])
        if (
            i == 0
            or min(covers[i - 1], covers[i])
            < cfg["clearance_m"] + cfg["roof_thickness_m"]
        ):
            quad(roof, ra[0], ra[1], topa[1], topa[0])
        if (
            i == len(sections) - 2
            or min(covers[i + 1], covers[i + 2])
            < cfg["clearance_m"] + cfg["roof_thickness_m"]
        ):
            quad(roof, rb[0], rb[1], topb[1], topb[0])
    for node, section in (
        (road["nodes"][0], sections[0]),
        (road["nodes"][-1], sections[-1]),
    ):
        if node in closed_nodes:
            a, b = section
            quad(
                wall,
                a,
                b,
                (b[0], b[1] + cfg["clearance_m"], b[2]),
                (a[0], a[1] + cfg["clearance_m"], a[2]),
            )
    return [("tunnel_wall", wall), ("tunnel_roof", roof), ("tunnel_lamp", lamps)]


def write(out, city):
    """Return static collision shell placements for the standard props pathset."""
    from bridges import write_asset

    cfg = json.loads(RULES.read_text())
    (out / "geometry").mkdir(parents=True, exist_ok=True)
    (out / "texture").mkdir(parents=True, exist_ok=True)
    for name, base in (
        ("tunnel_wall", (143, 145, 137)),
        ("tunnel_roof", (89, 93, 88)),
        ("tunnel_lamp", (231, 231, 202)),
    ):
        image = Image.new("RGB", (32, 32))
        image.putdata(
            [
                tuple(max(0, min(255, c + ((x * 11 + y * 7) % 7) - 3)) for c in base)
                for y in range(32)
                for x in range(32)
            ]
        )
        image.save(out / f"texture/{name}.png")
    instances = []
    caps = surface_wall_caps(city)
    ids = set(city.get("tunnel_ways", []))
    for road in city["roads"]:
        if road["id"] not in ids:
            continue
        record = write_asset(
            out,
            f"sthlm_tunnel_{road['id']}",
            shell_mesh(
                road,
                cfg,
                [
                    road_surface(other).buffer(-0.05)
                    for other in city["roads"]
                    if other["id"] in ids
                    and other["id"] != road["id"]
                    and set(other["nodes"]) & set(road["nodes"])
                ],
                city.get("tunnel_closed_nodes", []),
                caps,
            ),
            f"way/{road['id']}",
        )
        record["kind"] = "tunnel_structure"
        instances.append(record)
    return instances

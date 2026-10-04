"""Original asphalt textures on disjoint native driveable road strips."""

import math
import random
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter
from shapely import prepare
from shapely.geometry import LineString, Point, Polygon, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

MAJOR = {"primary", "secondary", "tertiary", "trunk"}
TILE_LENGTH = 10.0  # Native RoadNoSidewalks chain_u, inspected rust-mm2 b3d9804.


def classification(road):
    """Authored Swedish urban-road convention, explicitly not surveyed markings."""
    tags = road.get("tags", {})
    oneway = tags.get("oneway") in {"yes", "1", "true", "-1"}
    width = road["width"]
    try:
        lanes = int(tags.get("lanes", "0"))
    except (ValueError, TypeError):
        lanes = 0
    if not 1 <= lanes <= 6:
        lanes = max(1, min(4, round(width / 3.3))) if oneway else 2
        if not oneway and width >= 12 and tags.get("highway") in MAJOR:
            lanes = 4
    marked = tags.get("lane_markings") != "no" and (
        tags.get("highway") in MAJOR
        or (tags.get("highway") in {"residential", "unclassified"} and width >= 7)
        or "lanes" in tags
    )
    if tags.get("highway") in {"service", "living_street", "pedestrian"}:
        marked = False
    from oldtown import material_for as oldtown_material

    if oldtown_material(road):
        marked = False
    return {
        "lanes": lanes,
        "oneway": oneway,
        "marked": marked,
        "width": round(width * 2) / 2,
    }


def junctions(city):
    """Unique shared graph edges; coincident grade-separated lines never connect."""
    arms = defaultdict(dict)
    positions = {}
    for road in sorted(city.get("roads", []), key=lambda r: r["id"]):
        if road["id"] in city.get("tunnel_ways", []):
            continue
        nodes, points = road["nodes"], road["points"]
        for node, point in zip(nodes, points):
            positions[node] = point
        for index, (a, b) in enumerate(zip(nodes, nodes[1:])):
            if index + 1 >= len(points) or a == b:
                continue
            arms[a][b] = road
            arms[b][a] = road
    out = []
    for node in sorted(arms):
        degree = len(arms[node])
        if degree < 3:
            continue
        roads = list(arms[node].values())
        major = sum(r.get("tags", {}).get("highway") in MAJOR for r in roads)
        roundabout = any(
            r.get("tags", {}).get("junction") == "roundabout" for r in roads
        )
        signal = (
            not roundabout
            and major >= 2
            and (
                degree >= 4
                or any(
                    r.get("tags", {}).get("highway")
                    in {"primary", "secondary", "trunk"}
                    for r in roads
                )
            )
        )
        design = (
            "roundabout"
            if roundabout
            else "signal_crossroads"
            if signal
            else "priority_t"
            if degree == 3 and major
            else "local_unmarked"
        )
        out.append(
            {
                "node": node,
                "position": positions[node],
                "degree": degree,
                "design": design,
                "signal": signal,
                "radius": max(r["width"] for r in roads) / 2 + 2,
                "arms": [
                    {
                        "neighbor": neighbor,
                        "road_id": road["id"],
                        "toward": positions[neighbor],
                    }
                    for neighbor, road in sorted(arms[node].items())
                ],
            }
        )
    return out


def signal_placements(city, height=lambda x, n: 2.0, *, road_height=None):
    """Deterministic verge signals facing arriving traffic; movable native props."""
    roads = {
        r["id"]: r
        for r in city.get("roads", [])
        if r["id"] not in city.get("tunnel_ways", [])
    }
    boundary = None
    if city.get("bounds"):
        boundary = shape(city["bounds"])
    footprint = (
        shape(city["road_surface"])
        if city.get("road_surface")
        else unary_union(
            [LineString(r["points"]).buffer(r["width"] / 2) for r in roads.values()]
        )
    )
    prepare(footprint)
    buildings = [
        shape(b["geometry"]) for b in city.get("buildings", []) if b.get("geometry")
    ]
    building_tree = STRtree(buildings) if buildings else None
    out = []
    for junction in junctions(city):
        if not junction["signal"]:
            continue
        x, n = junction["position"]
        for arm in junction["arms"]:
            road = roads[arm["road_id"]]
            ax, an = arm["toward"]
            length = math.hypot(ax - x, an - n)
            if length < 1:
                continue
            # Outward unit vector. The pole sits on arriving drivers' right.
            tx, tn = (ax - x) / length, (an - n) / length
            tags = road.get("tags", {})
            one = tags.get("oneway")
            if one in {"yes", "1", "true", "-1"}:
                line = LineString(road["points"])
                d = line.project(Point(x, n))
                sample = line.interpolate(min(line.length, d + 1))
                forward_out = (sample.x - x) * tx + (sample.y - n) * tn > 0.1
                if forward_out != (one == "-1"):
                    continue
            # Very short OSM graph edges still belong to a full junction arm.
            # Clamping to their length would place the pole in the crossing road.
            position = None
            for along in (0, 2, 4):
                for lateral in (0, 0.4, 0.8):
                    offset = junction["radius"] + 3 + along
                    verge = road["width"] / 2 + 0.45 + lateral
                    px, pn = x + tx * offset - tn * verge, n + tn * offset + tx * verge
                    pole = Point(px, pn).buffer(0.3)
                    if footprint.intersects(pole):
                        continue
                    if boundary is not None and not boundary.covers(pole):
                        continue
                    if building_tree is not None and len(
                        building_tree.query(pole, predicate="intersects")
                    ):
                        continue
                    position = px, pn
                    break
                if position is not None:
                    break
            if position is None:
                continue
            px, pn = position
            y = road_height(road, px, pn) if road_height else height(px, pn)
            out.append(
                {
                    "source": f"junction/{junction['node']}/way/{road['id']}",
                    "asset": "sthlm_signal",
                    "position": [px, y, -pn],
                    "direction": [px + tx, y, -pn - tn],
                    "breakable": False,
                    "movable": True,
                    "placement": junction["design"],
                    "timing": "static visual red; no active traffic controller",
                }
            )
    return out


def material_name(spec, approach=""):
    if not spec["marked"]:
        return "sthlm_asphalt"
    width = int(spec["width"] * 2)
    return f"sthlm_road_{spec['lanes']}_{int(spec['oneway'])}_{width}{approach}"


def asphalt(size=512):
    """Saved original ImageGen aggregate raster, resized offline for the package."""
    source = (
        Path(__file__).resolve().parents[1]
        / "assets/materials/roads/asphalt-original.png"
    )
    with Image.open(source) as img:
        return img.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)


def texture(spec, approach=""):
    """u runs left-to-right along the road, v top-to-bottom across its width."""
    img = asphalt()
    if not spec["marked"]:
        return img
    size = img.width
    mask = Image.new("L", img.size)
    draw = ImageDraw.Draw(mask)
    width = spec["width"]
    paint_px = max(2, round(0.12 / width * size))
    lanes = spec["lanes"]
    for divider in range(1, lanes):
        y = round(size * divider / lanes)
        # All Swedish direction/lane divisions use white paint. 3m dash/7m gap.
        draw.rectangle((0, y - paint_px // 2, size * 0.3, y + paint_px // 2), fill=238)
    if width >= 10 and lanes > 1:
        for y in (round(0.22 / width * size), round(size * (1 - 0.22 / width))):
            draw.line((0, y, size, y), fill=220, width=paint_px)
    if approach:
        # Zebra across both directions, 3m long with 0.5m stripes/gaps.
        cx = 0.6 if approach == "_approach" else 0.4
        draw.rectangle((size * (cx - 0.2), 0, size * (cx + 0.2), size), fill=0)
        for band in range(math.floor((width - 0.6) / 1.0)):
            y0 = (0.3 + band) / width * size
            draw.rectangle(
                (size * (cx - 0.15), y0, size * (cx + 0.15), y0 + 0.5 / width * size),
                fill=245,
            )
        # Stop line only on incoming carriageway, behind the pedestrian crossing.
        stop_x = cx - 0.24 if approach == "_approach" else cx + 0.24
        half = 0 if spec["oneway"] else size // 2
        ys = (half, size) if approach == "_approach" else (0, size - half)
        draw.rectangle((size * stop_x, ys[0], size * (stop_x + 0.04), ys[1]), fill=245)
    # Worn white paint without copied art or protruding geometry.
    rng = random.Random(71)
    for _ in range(1800):
        x, y = rng.randrange(size), rng.randrange(size)
        if mask.getpixel((x, y)):
            mask.putpixel((x, y), rng.randrange(100, 225))
    paint = Image.new("RGB", img.size, (224, 224, 207))
    return Image.composite(paint, img, mask.filter(ImageFilter.GaussianBlur(0.25)))


def write_textures(dest, city):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    asphalt().save(dest / "sthlm_asphalt.png")
    done = {"sthlm_asphalt"}
    for road in [*city.get("roads", []), *city.get("tunnel_roads", [])]:
        spec = classification(road)
        for approach in ("", "_approach", "_approach_reverse"):
            name = material_name(spec, approach)
            if name not in done:
                texture(spec, approach).save(dest / f"{name}.png")
                done.add(name)
    return sorted(done)


def render(
    writer,
    city,
    geom,
    height,
    *,
    road_height=None,
    station_height=None,
    bridge=False,
    triangle_sink=None,
):
    """Partition coverage exactly: native UV strips plus unmarked fan remainder.

    Only quads entirely in the exported road footprint are emitted. Conflicts,
    junction interiors and complex corners remain plain asphalt; no coplanar
    double surfaces, render-only markings, or world-UV faux lane lines.
    station_height(road, station_metres) pins both corners of each cross-section
    to the known source centreline station, avoiding XY projection onto bends.
    """
    if geom.is_empty:
        return {"strips": 0, "marked_area": 0, "remainder_area": 0}
    junction_list = junctions(city)
    junction_points = [Point(j["position"]) for j in junction_list]
    jtree = STRtree(junction_points) if junction_points else None
    bridges = set(city.get("bridge_ways", []))
    strips, footprints, strip_stations = [], [], []
    # Batch broad-phase candidate collisions; stable road id order wins overlaps.
    accepted = defaultdict(list)
    prepare(geom)
    for road in sorted(city.get("roads", []), key=lambda r: r["id"]):
        if road["id"] in city.get("tunnel_ways", []):
            continue
        if (road["id"] in bridges) != bridge:
            continue
        spec = classification(road)
        if not spec["marked"]:
            continue
        line = LineString(road["points"])
        half = road["width"] / 2 - 0.02
        for start in range(
            0, max(0, math.floor(line.length - TILE_LENGTH + 0.001) + 1), 10
        ):
            a, b = line.interpolate(start), line.interpolate(start + TILE_LENGTH)
            length = a.distance(b)
            if length < 9.9:  # tight curve: leave coherent plain asphalt.
                continue
            tx, tn = (b.x - a.x) / length, (b.y - a.y) / length
            points = [
                (a.x - tn * half, a.y + tx * half),
                (a.x + tn * half, a.y - tx * half),
                (b.x - tn * half, b.y + tx * half),
                (b.x + tn * half, b.y - tx * half),
            ]
            poly = Polygon([points[i] for i in (0, 1, 3, 2)])
            if not geom.covers(poly):
                continue
            keys = [
                (x, n)
                for x in range(
                    math.floor(poly.bounds[0] / 20), math.floor(poly.bounds[2] / 20) + 1
                )
                for n in range(
                    math.floor(poly.bounds[1] / 20), math.floor(poly.bounds[3] / 20) + 1
                )
            ]
            if any(
                poly.intersection(other).area > 1e-6
                for key in keys
                for other in accepted[key]
            ):
                continue
            approach = ""
            if jtree is not None:
                near = jtree.query(poly.buffer(25))
                if any(
                    poly.distance(junction_points[i]) < junction_list[i]["radius"]
                    for i in near
                ):
                    continue
                signals = [
                    i
                    for i in near
                    if junction_list[i]["signal"]
                    and 10 <= poly.centroid.distance(junction_points[i]) <= 22
                ]
                if signals:
                    closest = min(
                        signals,
                        key=lambda i: poly.centroid.distance(junction_points[i]),
                    )
                    jp = junction_points[closest]
                    approach = (
                        "_approach"
                        if jp.distance(b) < jp.distance(a)
                        else "_approach_reverse"
                    )
            for key in keys:
                accepted[key].append(poly)
            footprints.append(poly)
            strips.append((road, points, material_name(spec, approach), poly))
            strip_stations.append((float(start), start + TILE_LENGTH))
    # Pin fan boundary samples to the exact native strip plane. Fan meshing
    # inserts intermediate 5m boundary vertices; evaluating a curved height
    # profile there independently would open tiny vertical T-junction cracks.
    strip_levels = []
    for index, (road, points, _, _) in enumerate(strips):
        if station_height is not None:
            start, end = strip_stations[index]
            start_y = station_height(road, start)
            end_y = station_height(road, end)
            strip_levels.append([start_y, start_y, end_y, end_y])
        else:
            strip_levels.append(
                [
                    road_height(road, x, n)
                    if road_height
                    else height(x, n)
                    if callable(height)
                    else height
                    for x, n in points
                ]
            )
    strip_tree = STRtree(footprints) if footprints else None

    def seam_height(x, n):
        point = Point(x, n)
        if strip_tree is not None:
            nearest = int(strip_tree.nearest(point))
            poly = footprints[nearest]
            if poly.boundary.distance(point) < 0.0001:
                coords = strips[nearest][1]
                levels = strip_levels[nearest]
                edges = [(0, 1), (1, 3), (3, 2), (2, 0)]
                best = min(
                    edges,
                    key=lambda e: LineString([coords[e[0]], coords[e[1]]]).distance(
                        point
                    ),
                )
                a, b = best
                edge = LineString([coords[a], coords[b]])
                t = edge.project(point) / edge.length
                return round(levels[a] + t * (levels[b] - levels[a]), 5)
        return height(x, n) if callable(height) else height

    # Capture just rooms emitted by this layer, for exact bridge underside art.
    before = (
        {key: len(part.rooms) for key, part in writer.parts.items()}
        if hasattr(writer, "parts")
        else {None: len(writer.rooms)}
    )
    covered = unary_union(footprints)
    # Fan leftovers preserve the entire source footprint without lifting paint.
    remaining = geom.difference(covered)
    from oldtown import MATERIAL as oldtown_material
    from oldtown import road_partition

    # Keep elevated layer/color groups and their triangle sink unchanged.
    # Source bridge approach groups are asphalt even above Old Town stone land.
    stone, asphalt = (
        (Polygon(), remaining) if bridge else road_partition(remaining, city)
    )
    fan_height = seam_height if strips else height
    writer.surface(stone, fan_height, oldtown_material, road=True)
    writer.surface(asphalt, fan_height, "sthlm_asphalt", road=True)
    if triangle_sink is not None:
        parts = writer.parts.items() if hasattr(writer, "parts") else [(None, writer)]
        for key, part in parts:
            for _, attrs, _ in part.rooms[before.get(key, 0) :]:
                offset = 2
                while offset < len(attrs):
                    if attrs[offset] != 0xA9:
                        raise ValueError(
                            "unexpected attribute in native road fan capture"
                        )
                    triangle_sink.append(
                        [list(part.vertices[i]) for i in attrs[offset + 1 : offset + 4]]
                    )
                    offset += 4
    for index, (road, points, material, poly) in enumerate(strips):
        target = (
            writer.part(poly.centroid.x, poly.centroid.y)
            if hasattr(writer, "part")
            else writer
        )
        refs = [
            target.vertex((x, strip_levels[index][corner], n))
            for corner, (x, n) in enumerate(points)
        ]
        if triangle_sink is not None:
            for corners in ((0, 1, 2), (2, 1, 3)):
                triangle_sink.append([list(target.vertices[refs[i]]) for i in corners])
        attrs = target.texture(material) + [0x80 | (2 << 3) | 2, *refs]
        target.rooms.append(([refs[i] for i in (0, 1, 3, 2)], attrs, 8))
    return {
        "strips": len(strips),
        "marked_area": covered.area,
        "remainder_area": remaining.area,
        "surface_area": geom.area,
        "junctions": len(junction_list),
        "signal_junctions": sum(j["signal"] for j in junction_list),
    }


def render_bridge_layers(writer, city, terrain, *, triangle_sink=None):
    """Preserve overlapping upper/lower decks as separate native surfaces.

    A planar union of all decks destroys stacked roads even when their source
    profiles have correct clearance. Union only ways sharing an OSM layer;
    approach pieces inherit their connected deck's layer, keeping local seams.
    """
    from elevation import RoadField, bridge_approaches

    bridge_ids = set(city.get("bridge_ways", []))
    by_id = {r["id"]: r for r in city["roads"]}
    elevated = [r for r in city["roads"] if r["id"] in bridge_ids]
    ordinary = [
        r
        for r in city["roads"]
        if r["id"] not in bridge_ids and r["id"] not in city.get("tunnel_ways", [])
    ]
    _, pieces, seams, _ = bridge_approaches(ordinary, elevated)
    node_layers = defaultdict(set)
    positions = {}
    for road in elevated:
        layer = int(road["tags"].get("layer", 1))
        for node, position in zip(road["nodes"], road["points"]):
            node_layers[node].add(layer)
            positions[tuple(position)] = node
    layers = defaultdict(list)
    for piece in pieces:
        road = by_id[piece["id"]]
        if road["id"] in bridge_ids:
            layer = int(road["tags"].get("layer", 1))
        else:
            connected = set()
            for point in (piece["elevated_points"][0], piece["elevated_points"][-1]):
                connected.update(node_layers.get(positions.get(tuple(point[:2])), ()))
            layer = min(connected, default=int(road["tags"].get("layer", 0)))
        layers[layer].append(piece)
    bounds = shape(city["bounds"])
    # Source layer numbers are relative to nearby ground, not global altitude.
    # Two independent ramp buffers may overlap while both are tagged layer=1.
    # Keep height-incompatible overlaps out of the same planar mesh union.
    groups = {}
    for layer, layer_pieces in sorted(layers.items()):
        footprints = [
            LineString([p[:2] for p in r["elevated_points"]]).buffer(
                r["width"] / 2, cap_style=1, join_style=2
            )
            for r in layer_pieces
        ]
        tree = STRtree(footprints)
        fields = [RoadField([r], terrain, bridge=True) for r in layer_pieces]
        conflicts = defaultdict(set)
        for i, footprint in enumerate(footprints):
            for j in map(int, tree.query(footprint, predicate="intersects")):
                if j <= i:
                    continue
                overlap = footprint.intersection(footprints[j])
                if overlap.area < 1e-6:
                    continue
                point = overlap.representative_point()
                if abs(fields[i](point.x, point.y) - fields[j](point.x, point.y)) > 0.5:
                    conflicts[i].add(j)
                    conflicts[j].add(i)
        colors = {}
        for i in range(len(layer_pieces)):
            excluded = {colors[j] for j in conflicts[i] if j in colors}
            color = next(c for c in range(len(layer_pieces) + 1) if c not in excluded)
            colors[i] = color
            groups.setdefault((layer, color), []).append(layer_pieces[i])
    reports = {}
    for (layer, color), local_pieces in sorted(groups.items()):
        ids = {r["id"] for r in local_pieces}
        field = RoadField(local_pieces, terrain, bridge=True, junctions=seams)
        surface = unary_union(
            [
                LineString([p[:2] for p in r["elevated_points"]]).buffer(
                    r["width"] / 2, cap_style=1, join_style=2
                )
                for r in local_pieces
            ]
        ).intersection(bounds)
        local_city = {
            **city,
            "roads": [by_id[i] for i in sorted(ids)],
            "bridge_ways": sorted(ids),
        }
        reports[f"{layer}:{color}"] = render(
            writer,
            local_city,
            surface,
            field,
            road_height=field.height_for_road,
            station_height=field.height_at_station,
            bridge=True,
            triangle_sink=triangle_sink,
        )
    return {
        "layers": reports,
        "layer_count": len(layers),
        "surface_groups": len(reports),
    }

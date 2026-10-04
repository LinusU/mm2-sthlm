"""Full target-area normalization and bounded PSDL parts; no engine imports."""

import math
import json
from shapely import prepare
from shapely.geometry import LineString, Point, Polygon, box, mapping, shape
from shapely.ops import polygonize_full, unary_union
from shapely.strtree import STRtree
import sthlm

INCLUDED = {
    "Kungsholmen": (18.018, 59.332),
    "Södermalm": (18.072, 59.314),
    "Djurgården": (18.127, 59.326),
    "Norrmalm/Östermalm": (18.071, 59.341),
    "Gamla stan": (18.071, 59.324),
    "Riddarholmen": (18.064, 59.324),
    "Skeppsholmen": (18.083, 59.325),
    "Kastellholmen": (18.088, 59.322),
    "Långholmen": (18.029, 59.321),
    "Reimersholme": (18.024, 59.318),
    "Helgeandsholmen": (18.0686, 59.3284),
    "Beckholmen": (18.100005, 59.320760),
    "Strömsborg": (18.063056, 59.327113),
}
EXCLUDED = {
    "Lilla Essingen": (17.997, 59.323),
    "Stora Essingen": (17.989, 59.320),
    "Hammarby sjöstad": (18.099, 59.305),
    "Lidingö": (18.144, 59.352),
}
BRIDGES = {
    "Stadshusbron",
    "Kungsbron",
    "Barnhusbron",
    "Sankt Eriksbron",
    "Strömbron",
    "Norrbro",
    "Vasabron",
    "Riksbron",
    "Stallbron",
    "Slussbron",
    "Skeppsholmsbron",
    "Kastellholmsbron",
    "Djurgårdsbron",
    "Djurgårdsbrunnsbron",
    "Beckholmsbron",
    "Långholmsbron",
    "Reimersholmsbron",
    "Pålsundsbron",
    "Västerbron",
    "Lilla Västerbron",
    "Mariebergsbron",
}
BLOCKED = {
    "Tranebergsbron",
    "Essingeleden",
    "Lidingöbron",
    "Gamla Lidingöbron",
    "Liljeholmsbron",
    "Årstabron",
    "Skansbron",
    "Skanstullsbron",
    "Johanneshovsbron",
}


def internal_bridge_ways(ways, nodes, cfg, playable_mask):
    """Retain sourced internal motor bridges, including unnamed viaducts.

    A name whitelist misses split carriageways and trunk bridges. Only complete
    centreline geometry within the approved mask is accepted; explicitly blocked
    outward connections remain blocked even if the drawn mask covers a portion.
    Underground roads are a separate export problem and are not raised decks.
    """
    motor_classes = {
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
        "service",
        "living_street",
    }
    mask = playable_mask.buffer(1)
    allowed = []
    for wid, way in sorted(ways.items()):
        tags = way.get("tags", {})
        if (
            tags.get("bridge") in (None, "no")
            or tags.get("tunnel") not in (None, "no")
            or tags.get("highway") not in motor_classes
            or tags.get("name") in BLOCKED
            or tags.get("motor_vehicle") == "no"
            or len(way["nodes"]) < 2
            or any(n not in nodes for n in way["nodes"])
        ):
            continue
        line = LineString(
            [
                sthlm.project(nodes[n]["lon"], nodes[n]["lat"], cfg["origin"])
                for n in way["nodes"]
            ]
        )
        if mask.covers(line):
            allowed.append(wid)
    return allowed


def coast_water(source, cfg):
    """Polygonize real directed coastline clipped by the acquisition envelope.

    OSM coastline has land on its left. A nearest directed source segment
    classifies each complete face; no hand-drawn lake or guessed dry mainland.
    """
    nodes = {e["id"]: e for e in source["elements"] if e["type"] == "node"}
    boundary = box(
        *sthlm.project(*cfg["bounds"][:2], cfg["origin"]),
        *sthlm.project(*cfg["bounds"][2:], cfg["origin"]),
    )
    lines, segments = [], []
    for e in source["elements"]:
        if e["type"] != "way" or e.get("tags", {}).get("natural") != "coastline":
            continue
        pts = [
            sthlm.project(nodes[n]["lon"], nodes[n]["lat"], cfg["origin"])
            for n in e["nodes"]
        ]
        line = LineString(pts).intersection(boundary)
        if line.is_empty:
            continue
        lines.append(line)
        segments.extend(LineString([a, b]) for a, b in zip(pts, pts[1:]) if a != b)
    if not segments:
        raise ValueError("expanded coastline source missing")
    faces, cuts, dangles, invalid = polygonize_full(
        unary_union([boundary.boundary, *lines])
    )
    if any(not g.is_empty for g in (cuts, dangles, invalid)):
        raise ValueError("open local coastline; no guessed water fill")
    tree = STRtree(segments)
    waters = []
    for face in faces.geoms:
        p = face.representative_point()
        segment = segments[int(tree.nearest(p))]
        a, b = segment.coords
        if (b[0] - a[0]) * (p.y - a[1]) - (b[1] - a[1]) * (p.x - a[0]) < 0:
            waters.append(face)
    return unary_union(waters)


def northern_corridor(ways, nodes, cfg, envelope):
    """Use real E20 source nodes, including its underground alignment.

    The road is a geographic boundary reference. This does not invent drivable
    tunnel geometry. A 100 m north-side margin keeps the whole road corridor.
    """
    graph, positions, source_edges = {}, {}, {}
    for way in ways.values():
        tags = way.get("tags", {})
        if "E 20" not in tags.get("ref", "").split(";") or not tags.get("highway"):
            continue
        if max(nodes[n]["lat"] for n in way["nodes"]) < 59.338:
            continue
        for nid in way["nodes"]:
            node = nodes[nid]
            positions[nid] = sthlm.project(node["lon"], node["lat"], cfg["origin"])
        for a, b in zip(way["nodes"], way["nodes"][1:]):
            d = math.dist(positions[a], positions[b])
            graph.setdefault(a, {})[b] = d
            graph.setdefault(b, {})[a] = d
            source_edges[frozenset([a, b])] = way["id"]
    anchors = [(18.010, 59.343), (18.108, 59.352)]
    ends = [
        min(
            graph,
            key=lambda n: math.dist(positions[n], sthlm.project(*ll, cfg["origin"])),
        )
        for ll in anchors
    ]
    ids = sthlm.shortest(graph, *ends)
    points = [positions[n] for n in ids]
    left, bottom, right, _ = envelope.bounds
    limit = Polygon(
        [
            (left, points[0][1]),
            *points,
            (right, points[-1][1]),
            (right, bottom),
            (left, bottom),
        ]
    )
    if not limit.is_valid:
        raise ValueError("E20 boundary source path folds; refine source anchors")
    return limit.buffer(100), {
        "rule": "OSM E20 shared-node path Karlberg to Värtahamnen with 100 m corridor margin; underground alignment used only for geographic clipping",
        "source_way_ids": sorted(
            {source_edges[frozenset([a, b])] for a, b in zip(ids, ids[1:])}
        ),
        "source_nodes": ids,
        "points": points,
        "margin_m": 100,
    }


def normalized(source, cfg):
    nodes = {e["id"]: e for e in source["elements"] if e["type"] == "node"}
    ways = {e["id"]: e for e in source["elements"] if e["type"] == "way"}
    envelope = box(
        *sthlm.project(*cfg["bounds"][:2], cfg["origin"]),
        *sthlm.project(*cfg["bounds"][2:], cfg["origin"]),
    )
    waters = [coast_water(source, cfg)]
    lake_levels = []
    for r in source["elements"]:
        if r["type"] == "relation" and r.get("tags", {}).get("natural") == "water":
            lake = sthlm.assemble_relation(
                r, ways, nodes, cfg["origin"], envelope
            ).intersection(envelope)
            waters.append(lake)
            if r["tags"].get("name") == "Mälaren":
                lake_levels.append(
                    {
                        "geometry": mapping(lake),
                        "height_m": float(r["tags"]["ele"]),
                        "rule": "OSM ele tag; datum/instantaneous water level not surveyed",
                    }
                )
        elif (
            r["type"] == "way"
            and r.get("tags", {}).get("natural") == "water"
            and r["nodes"][0] == r["nodes"][-1]
        ):
            p = Polygon(
                [
                    sthlm.project(nodes[n]["lon"], nodes[n]["lat"], cfg["origin"])
                    for n in r["nodes"]
                ]
            )
            if p.is_valid:
                waters.append(p.intersection(envelope))
    water = unary_union(waters)
    land = envelope.difference(water)
    candidates = sthlm.pieces(land)
    included = []
    coverage = {}
    for name, ll in INCLUDED.items():
        point = Point(sthlm.project(*ll, cfg["origin"]))
        nearby = [p for p in candidates if p.distance(point) < 70]
        if not nearby:
            raise ValueError(f"no sourced land for included island {name}")
        p = min(nearby, key=lambda p: p.distance(point))
        included.append(p)
        coverage[name] = {"land_area_m2": round(p.area), "reference_lonlat": ll}
    # Retain entire sourced islands, then limit the northern mainland by the
    # approved envelope. Water separates excluded land even where the sketch
    # loosely encloses a sliver of its shore.
    target = shape(
        json.loads((sthlm.ROOT / "config/target-boundary.geojson").read_text())[
            "features"
        ][0]["geometry"]
    )
    target = Polygon(
        [sthlm.project(x, y, cfg["origin"]) for x, y in target.exterior.coords]
    )
    north_limit, north_metadata = northern_corridor(ways, nodes, cfg, envelope)
    target = target.intersection(north_limit)
    selected = unary_union(included).intersection(target)
    mainland = next(
        p
        for p in candidates
        if p.covers(
            Point(sthlm.project(*INCLUDED["Norrmalm/Östermalm"], cfg["origin"]))
        )
    )
    islands = unary_union([p for p in included if p != mainland])
    target = target.union(islands.buffer(15)).intersection(envelope)
    selected = unary_union(included).intersection(target)
    # Excluded components must never be selected. A coastline error that joins
    # included and excluded mainland/islands is a hard error, not a quiet leak.
    for name, ll in EXCLUDED.items():
        point = Point(sthlm.project(*ll, cfg["origin"]))
        if selected.distance(point) < 20:
            raise ValueError(f"excluded land leaked: {name}")
    playable_mask = target.difference(land.difference(selected))
    allowed = internal_bridge_ways(ways, nodes, cfg, playable_mask)
    from tunnels import internal_tunnel_ways

    tunnel_ids = internal_tunnel_ways(ways, nodes, cfg, playable_mask, BLOCKED)
    from oldtown import eligible_pedestrian_ways

    oldtown_alleys = eligible_pedestrian_ways(source, cfg, land=selected)
    settings = {
        **cfg,
        "allowed_surface_ways": oldtown_alleys,
        "allowed_tunnel_ways": tunnel_ids,
        "allow_internal_open_cuts": True,
        "report_bad_buildings": True,
        "allowed_bridge_ways": allowed,
        "road_classes": [
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
            "service",
            "living_street",
        ],
    }
    city = sthlm.normalize(
        source,
        settings,
        boundary=playable_mask,
        water_override=water.intersection(playable_mask),
    )
    # Keep centreline graph edges only when entirely within the playable mask;
    # do not reconnect cut ends or source crossings without shared OSM nodes.
    graph, positions = {}, {}
    slack = playable_mask.buffer(0.01)
    prepare(slack)
    widths = {r["width"] for r in city["roads"]}
    road_masks = {w: selected.buffer(w) for w in widths}
    for mask in road_masks.values():
        prepare(mask)
    roads = []
    for r in city["roads"]:
        if r["tags"].get("name") in BLOCKED:
            continue
        if (
            not road_masks[r["width"]].intersects(LineString(r["points"]))
            and r["id"] not in allowed
            and r["id"] not in tunnel_ids
        ):
            continue
        roads.append(r)
        for nid, p in zip(r["nodes"], r["points"]):
            positions[nid] = p
        for a, b in zip(r["nodes"], r["nodes"][1:]):
            if slack.covers(LineString([positions[a], positions[b]])):
                d = math.dist(positions[a], positions[b])
                graph.setdefault(a, {})[b] = d
                graph.setdefault(b, {})[a] = d
    city["roads"] = roads
    # Clipping the coarse water envelope can leave tiny pieces of excluded
    # shore buildings afloat. Buildings must touch included sourced land.
    # OSM building=ship describes hulls, which need authored props rather than
    # apartment-style facades; retain the omission explicitly.
    building_land = selected.buffer(1)
    prepare(building_land)
    retained = []
    for building in city["buildings"]:
        if building["tags"].get("building") == "ship" or not building_land.intersects(
            shape(building["geometry"])
        ):
            city["omitted"].append(
                {
                    "id": building["id"],
                    "reason": "ship requires a prop, or building has no included-land contact",
                }
            )
        else:
            retained.append(building)
    city["buildings"] = retained
    city["road_surface"] = mapping(
        unary_union(
            [
                LineString(r["points"]).buffer(
                    r["width"] / 2, cap_style=1, join_style=2
                )
                for r in roads
            ]
        ).intersection(playable_mask)
    )
    from ponds import normalized as normalize_ponds, footprint as pond_footprint

    city["shallow_water"] = normalize_ponds(source, cfg, playable_mask, coast=waters[0])
    shallow = pond_footprint(city)
    city["water"] = mapping(shape(city["water"]).difference(shallow))
    city["land"] = mapping(selected.union(shallow))
    city["water_regions"] = lake_levels
    city["coverage"] = coverage
    city["north_boundary"] = north_metadata
    city["bridge_ways"] = allowed
    city["tunnel_ways"] = tunnel_ids
    city["expanded"] = True
    city["source"] = json.loads(
        (sthlm.ROOT / "sources/expanded/manifest.json").read_text()
    )
    city["trees"] = [
        {"id": e["id"], "position": [*sthlm.project(e["lon"], e["lat"], cfg["origin"])]}
        for e in source["elements"]
        if e["type"] == "node"
        and e.get("tags", {}).get("natural") == "tree"
        and selected.covers(Point(sthlm.project(e["lon"], e["lat"], cfg["origin"])))
    ]
    start = min(graph, key=lambda n: math.dist(positions[n], city["route"][0]))
    destinations = {
        "west-kungsholmen": (17.997, 59.331),
        "karlberg": (18.014, 59.341),
        "vartahamnen": (18.108, 59.350),
        "djurgarden": (18.144, 59.323),
        "sodermalm": (18.072, 59.311),
        "gamla-stan": (18.071, 59.324),
        "skeppsholmen": (18.083, 59.325),
        "reimersholme": (18.024, 59.319),
    }
    # Discover the spawn's shared-node component once, preserving crossings.
    reachable = {start}
    pending = [start]
    while pending:
        for n in graph.get(pending.pop(), {}):
            if n not in reachable:
                reachable.add(n)
                pending.append(n)
    routes = {}
    for name, ll in destinations.items():
        p = sthlm.project(*ll, cfg["origin"])
        end = min(reachable, key=lambda n: math.dist(positions[n], p))
        distance = math.dist(positions[end], p)
        if distance > 200:
            raise ValueError(
                f"{name}: connected road is {distance:.0f} m from reference"
            )
        ids = sthlm.shortest(graph, start, end)
        routes[name] = {
            "reference_lonlat": ll,
            "endpoint_distance_m": distance,
            "nodes": ids,
            "points": [positions[n] for n in ids],
            "length_m": sum(
                math.dist(positions[a], positions[b]) for a, b in zip(ids, ids[1:])
            ),
        }
    city["connected_routes"] = routes
    city["connected_nodes"] = len(reachable)
    city["total_road_nodes"] = len(graph)
    return city


class ChunkedWriter:
    """Independent 750 m PSDL vertex pools; shared global coordinates.

    Dense facades use multiple vertical texture bands. A 1 km central-city
    pool can exceed the native 16-bit vertex limit when combined with roads.
    """

    PART_SIZE_M = 750

    def __init__(self, spawn):
        self.parts = {}
        self.primary = (
            math.floor(spawn[0] / self.PART_SIZE_M),
            math.floor(-spawn[2] / self.PART_SIZE_M),
        )

    def part(self, x, n):
        key = (math.floor(x / self.PART_SIZE_M), math.floor(n / self.PART_SIZE_M))
        if key not in self.parts:
            self.parts[key] = sthlm.PsdlWriter()
        return self.parts[key]

    def surface(self, geom, y, texture, road=False, water=False):
        if geom.is_empty:
            return
        # Node shared material edges before separate tile intersections.
        from elevation import conforming_boundary

        if callable(y):
            geom = conforming_boundary(geom)
        # Bisect geometry before clipping individual tiles. Intersecting the
        # entire connected road/shoreline polygon for every tile is quadratic.
        x0, n0, x1, n1 = geom.bounds

        def visit(area, left, bottom, right, top):
            if area.is_empty or area.area == 0:
                return
            if right - left <= 100 and top - bottom <= 100:
                self.part(left + 50, bottom + 50).surface(
                    area, y, texture, road=road, water=water
                )
                return
            if right - left >= top - bottom:
                middle = left + ((right - left) // 200) * 100
                visit(
                    area.intersection(box(left, bottom, middle, top)),
                    left,
                    bottom,
                    middle,
                    top,
                )
                visit(
                    area.intersection(box(middle, bottom, right, top)),
                    middle,
                    bottom,
                    right,
                    top,
                )
            else:
                middle = bottom + ((top - bottom) // 200) * 100
                visit(
                    area.intersection(box(left, bottom, right, middle)),
                    left,
                    bottom,
                    right,
                    middle,
                )
                visit(
                    area.intersection(box(left, middle, right, top)),
                    left,
                    middle,
                    right,
                    top,
                )

        visit(
            geom,
            math.floor(x0 / 100) * 100,
            math.floor(n0 / 100) * 100,
            math.ceil(x1 / 100) * 100,
            math.ceil(n1 / 100) * 100,
        )

    def building(self, poly, *args, **kwargs):
        self.part(poly.centroid.x, poly.centroid.y).building(poly, *args, **kwargs)

    def pyramid(self, poly, *args, **kwargs):
        self.part(poly.centroid.x, poly.centroid.y).pyramid(poly, *args, **kwargs)

    @property
    def vertices(self):
        return [v for p in self.parts.values() for v in p.vertices]

    @property
    def rooms(self):
        return [r for p in self.parts.values() for r in p.rooms]

    @property
    def water_rooms(self):
        return self.parts[self.primary].water_rooms

    def write(self, path, center):
        if len(self.parts) > sthlm.CITY_PART_LIMIT:
            raise ValueError("city chunk count exceeds native 129-part limit")
        paths = []
        for key, part in sorted(
            self.parts.items(), key=lambda kv: (kv[0] != self.primary, kv[0])
        ):
            dest = (
                path
                if key == self.primary
                else path.parent / "stockholm.parts" / f"part_{key[0]}_{key[1]}.psdl"
            )
            part.write(dest, center)
            dest.with_suffix(".water").write_text(
                "0.2\n" + "".join(f"{i}\n" for i in part.water_rooms)
            )
            paths.append(str(dest.relative_to(path.parent.parent)))
        path.with_suffix(".chunks").write_text(
            "MM2_CHUNKS 1\n" + "\n".join(paths[1:]) + "\n"
        )

import json
import gzip
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest

from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import bridges


def normal(tri):
    a, b, c = tri
    u, v = [[q[k] - a[k] for k in range(3)] for q in (b, c)]
    return (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )


class BridgeTests(unittest.TestCase):
    def test_closed_member_winding(self):
        a, b = (3, 4, 5), (17, 12, -1)
        mesh = bridges.beam(a, b, 0.8, 1.2)
        centre = [(a[k] + b[k]) / 2 for k in range(3)]
        self.assertEqual(len(mesh), 12)
        edges = {}
        for tri in mesh:
            n = normal(tri)
            midpoint = [sum(v[k] for v in tri) / 3 for k in range(3)]
            self.assertGreater(
                sum(n[k] * (midpoint[k] - centre[k]) for k in range(3)), 0
            )
            for p, q in zip(tri, tri[1:] + tri[:1]):
                edge = tuple(sorted((p, q)))
                edges[edge] = edges.get(edge, 0) + 1
        self.assertTrue(all(count == 2 for count in edges.values()))

    def test_underside_has_downward_normals_and_follows_deck(self):
        poly = Polygon([(0, 0), (20, 0), (20, 9), (0, 9)])

        def height(x, n):
            return 12 + x * 0.03

        mesh = bridges.deck_mesh(poly, height)
        bottom = [tri for tri in mesh if normal(tri)[1] < -0.01]
        self.assertTrue(bottom)
        self.assertAlmostEqual(sum(abs(normal(t)[1]) / 2 for t in bottom), poly.area)
        for tri in mesh:
            for x, y, z in tri:
                self.assertLessEqual(y, height(x, -z) - 0.039)
                self.assertGreaterEqual(y, height(x, -z) - 0.741)

    def test_slab_uses_exact_road_triangles_across_profile_bends(self):
        from expanded import ChunkedWriter

        surface = Polygon([(12, 7), (112, 7), (112, 16), (12, 16)])

        def height(x, n):
            # Deep concave bend: a different long chord bridges above roadway.
            return 20 + abs(x - 48) * 0.15 + abs(x - 73) * 0.07 + n * 0.015

        writer = ChunkedWriter([0, 0, 0])
        writer.surface(surface, height, "road", road=True)
        expected = {}
        for part in writer.parts.values():
            for _, attrs, _ in part.rooms:
                for index in range(2, len(attrs), 4):
                    triangle = tuple(
                        part.vertices[v] for v in attrs[index + 1 : index + 4]
                    )
                    key = tuple(sorted((v[0], v[2]) for v in triangle))
                    expected[key] = triangle
        slabs = list(bridges.captured_decks(surface, height, [0, 0, 0]))
        found = {}
        for mesh in slabs:
            for triangle in mesh:
                if normal(triangle)[1] <= 0.01:
                    continue
                key = tuple(sorted((v[0], v[2]) for v in triangle))
                self.assertIn(key, expected)
                found[key] = triangle
                road = {(v[0], v[2]): v[1] for v in expected[key]}
                for x, y, z in triangle:
                    self.assertAlmostEqual(road[x, z] - y, 0.04, places=8)
                # The identical vertices imply identical barycentric planes;
                # test an interior location as well as all source vertices.
                self.assertAlmostEqual(
                    sum(road[x, z] for x, _, z in triangle) / 3
                    - sum(v[1] for v in triangle) / 3,
                    0.04,
                    places=8,
                )
        self.assertEqual(set(found), set(expected))

    def test_island_reference_anchors_retain_exact_source_bridge_topology(self):
        root = Path(__file__).resolve().parents[1]
        anchors = json.loads(
            (root / "config/overrides/bridge-land-anchors.json").read_text()
        )["anchors"]
        with gzip.open(root / "sources/expanded/osm.json.gz") as stream:
            source = json.load(stream)
        ways = {e["id"]: e for e in source["elements"] if e["type"] == "way"}
        nodes = {e["id"]: e for e in source["elements"] if e["type"] == "node"}
        for anchor in anchors:
            endpoint = anchor["island_bridge_endpoint"]
            self.assertIn(endpoint, ways[anchor["island_road_way"]]["nodes"])
            self.assertTrue(
                any(endpoint in ways[wid]["nodes"] for wid in anchor["bridge_way_ids"])
            )
            for wid in anchor["bridge_way_ids"]:
                self.assertEqual(ways[wid]["tags"].get("bridge"), "yes")
            if "named_islet_way" in anchor:
                way = ways[anchor["named_islet_way"]]
                self.assertEqual(way["tags"]["name"], anchor["name"])
                self.assertEqual(way["tags"]["place"], "islet")
                poly = Polygon(
                    [(nodes[n]["lon"], nodes[n]["lat"]) for n in way["nodes"]]
                )
                from shapely.geometry import Point

                self.assertTrue(poly.covers(Point(anchor["reference_lonlat"])))

    def test_crossing_constraints_preserve_source_connectivity(self):
        roads = [
            {
                "id": 1,
                "nodes": [11, 12],
                "points": [(-50, 0), (50, 0)],
                "width": 9,
                "tags": {"layer": "2"},
            },
            {
                "id": 2,
                "nodes": [21, 22],
                "points": [(0, -50), (0, 50)],
                "width": 9,
                "tags": {"layer": "1"},
            },
            {
                "id": 3,
                "nodes": [12, 31],
                "points": [(50, 0), (50, 40)],
                "width": 9,
                "tags": {},
            },
        ]
        probes = bridges.crossing_constraints(roads, [1, 2])
        self.assertEqual(len(probes), 1)
        self.assertEqual((probes[0]["upper"], probes[0]["lower"]), (1, 2))
        self.assertEqual(probes[0]["position"], [0, 0])

    def test_estimated_crossing_lift_blends_into_connected_approach(self):
        roads = [
            {
                "id": 1,
                "nodes": [11, 12],
                "points": [(-150, 0), (150, 0)],
                "width": 9,
                "tags": {"layer": "1"},
                "elevated_points": [[x, 0, 2] for x in range(-150, 151, 10)],
            },
            {
                "id": 2,
                "nodes": [21, 22],
                "points": [(100, -50), (100, 50)],
                "width": 9,
                "tags": {},
                "elevated_points": [[100, y, 2] for y in range(-50, 51, 10)],
            },
            {
                "id": 3,
                "nodes": [12, 31],
                "points": [(150, 0), (300, 0)],
                "width": 9,
                "tags": {},
                "elevated_points": [[x, 0, 2] for x in range(150, 301, 10)],
            },
        ]
        report = bridges.enforce_crossing_clearance(roads, [1])
        self.assertGreaterEqual(
            report["probes"][0]["actual_vertical_separation_m"], 5.48
        )
        self.assertAlmostEqual(
            roads[0]["elevated_points"][-1][2], roads[2]["elevated_points"][0][2]
        )
        self.assertAlmostEqual(roads[2]["elevated_points"][-1][2], 2)
        # No introduced abrupt step along the approach's dense source samples.
        points = roads[2]["elevated_points"]
        self.assertLess(
            max(abs(a[2] - b[2]) / 10 for a, b in zip(points, points[1:])), 0.065
        )
        self.assertEqual([p[2] for p in roads[1]["elevated_points"]], [2] * 11)

    def test_bridge_railing_keeps_real_approach_portals_open(self):
        road = {
            "id": 1,
            "nodes": [11, 12],
            "points": [(0, 0), (100, 0)],
            "width": 9,
            "tags": {"name": "test"},
        }
        approach = {
            "id": 2,
            "nodes": [12, 13],
            "points": [(100, 0), (140, 0)],
            "width": 9,
            "tags": {},
        }
        groups = bridges.corridor_mesh(
            [road], {"roads": [road, approach]}, lambda x, n: 10, {"style": "girder"}
        )
        for _, mesh in groups:
            for tri in mesh:
                for x, y, z in tri:
                    if y > 10:
                        self.assertGreater(abs(z), 4.4)
                        self.assertGreater(x, 9.9)
                        self.assertLess(x, 90.1)

    def test_native_asset_world_mapping_and_chunk_limits(self):
        mesh = bridges.beam((-9, 4, 10), (12, 4, 10), 0.8)
        # More than one u16-safe native chunk must be generated.
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            (out / "geometry").mkdir()
            item = bridges.write_asset(
                out, "test", [("bridge_steel", mesh * 1800)], "authored"
            )
            data = (out / "geometry/test.pkg").read_bytes()
            self.assertTrue(item["static"])
            self.assertFalse(item["breakable"])
            offset = 4
            vertices = []
            while offset < len(data):
                self.assertEqual(data[offset : offset + 4], b"FILE")
                count = data[offset + 4]
                name = data[offset + 5 : offset + 5 + count].rstrip(b"\0")
                length = struct.unpack_from("<I", data, offset + 5 + count)[0]
                payload = offset + 9 + count
                if name != b"shaders":
                    count_vertices = struct.unpack_from("<I", data, payload + 4)[0]
                    self.assertLess(count_vertices, 65536)
                    for i in range(count_vertices):
                        vertices.append(
                            struct.unpack_from("<3f", data, payload + 36 + i * 20)
                        )
                offset = payload + length
            self.assertAlmostEqual(min(p[1] for p in vertices), 0)
            restored = [
                tuple(p[k] + item["position"][k] for k in range(3)) for p in vertices
            ]
            for k in range(3):
                self.assertAlmostEqual(
                    min(v[k] for v in restored),
                    min(v[k] for t in mesh for v in t),
                    places=5,
                )
                self.assertAlmostEqual(
                    max(v[k] for v in restored),
                    max(v[k] for t in mesh for v in t),
                    places=5,
                )

    def test_landmark_preserves_carriageways_and_has_two_spans(self):
        roads = [
            {"points": [(0, 100), (0, -500)], "width": 9},
            {"points": [(9, -500), (9, 100)], "width": 9},
        ]
        cfg = json.loads(bridges.OVERRIDE.read_text())
        groups = bridges.landmark_mesh(roads, lambda x, n: 24, cfg)
        self.assertEqual([g[0] for g in groups], ["bridge_concrete", "bridge_steel"])
        line = bridges.alignment(roads)
        self.assertGreater(line.coords[0][1], line.coords[-1][1])
        steel = groups[1][1]
        # Above-deck members are exclusively outside the sourced lane envelope.
        for tri in steel:
            for x, y, z in tri:
                if y > 24:
                    self.assertTrue(x < -4.5 or x > 13.5)
        # Steel appears under both arch crowns, well clear of the road surface.
        for a, b in zip(cfg["arch_stations"], cfg["arch_stations"][1:]):
            n = line.interpolate((a + b) / 2, normalized=True).y
            self.assertTrue(
                any(abs(-v[2] - n) < 10 and 20 < v[1] < 23 for t in steel for v in t)
            )
        self.assertTrue(
            all(math.isfinite(c) for _, m in groups for t in m for v in t for c in v)
        )


class InteriorBridgeJunctionTests(unittest.TestCase):
    def test_clearance_lift_preserves_interior_shared_source_junction(self):
        roads = [
            {
                "id": 1,
                "nodes": [1, 2, 3],
                "points": [(-100, 0), (0, 0), (100, 0)],
                "elevated_points": [[-100, 0, 5], [0, 0, 5], [100, 0, 5]],
                "tags": {"bridge": "yes", "layer": "1"},
                "width": 8,
            },
            {
                "id": 2,
                "nodes": [5, 6],
                "points": [(0, -50), (0, 50)],
                "elevated_points": [[0, -50, 10], [0, 50, 10]],
                "tags": {},
                "width": 8,
            },
            {
                "id": 3,
                "nodes": [2, 7],
                "points": [(0, 0), (50, 50)],
                "elevated_points": [[0, 0, 5], [50, 50, 5]],
                "tags": {},
                "width": 8,
            },
        ]
        report = bridges.enforce_crossing_clearance(roads, [1])
        self.assertGreaterEqual(
            report["probes"][0]["actual_vertical_separation_m"], 5.49
        )
        self.assertAlmostEqual(
            roads[0]["elevated_points"][1][2],
            roads[2]["elevated_points"][0][2],
            places=6,
        )

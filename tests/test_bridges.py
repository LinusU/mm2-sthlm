import json
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

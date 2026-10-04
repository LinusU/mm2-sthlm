import copy
import json
import math
import sys
import unittest
from pathlib import Path

from shapely.geometry import Point, Polygon, box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elevation import align_parallel_bridge_profiles  # noqa: E402
from road_surfaces import render_bridge_layers  # noqa: E402
from sthlm import PsdlWriter  # noqa: E402


class Terrain:
    def height(self, x, n):
        return 0


class AnchorCompatibleBridgeProfilesTest(unittest.TestCase):
    def fixture(self):
        return json.loads(
            (
                Path(__file__).parent
                / "fixtures/bridge-anchor-compatible-profiles.json"
            ).read_text()
        )["roads"]

    def test_native_floor_matches_source_at_exact_stall_and_held_guide(self):
        from bridges import source_bridge_groups
        from elevation import RoadField

        roads = self.fixture()
        before = copy.deepcopy(roads)
        anchors = []
        for _, members in source_bridge_groups(roads):
            degree = {}
            for road in members:
                for a, b in zip(road["nodes"], road["nodes"][1:]):
                    degree.setdefault(a, set()).add(b)
                    degree.setdefault(b, set()).add(a)
            anchors.extend(n for n, v in degree.items() if len(v) == 1)
        report = align_parallel_bridge_profiles(roads)
        self.assertEqual(len(report), 1)
        for old, road in zip(before, roads):
            self.assertEqual(old["nodes"], road["nodes"])
            self.assertEqual(old["points"], road["points"])
            for a, b in zip(old["elevated_points"], road["elevated_points"]):
                self.assertEqual(a[:2], b[:2])
                self.assertGreaterEqual(b[2], a[2])
            for n, xy in zip(road["nodes"], road["points"]):
                if n in anchors:
                    self.assertEqual(
                        next(p[2] for p in old["elevated_points"] if p[:2] == xy),
                        next(p[2] for p in road["elevated_points"] if p[:2] == xy),
                    )
        city = {
            "roads": roads,
            "bridge_ways": [r["id"] for r in roads],
            "bounds": mapping(box(1400, 0, 1750, 350)),
        }
        triangles = []
        render_bridge_layers(PsdlWriter(), city, Terrain(), triangle_sink=triangles)
        field = RoadField(roads, Terrain(), bridge=True)
        # Third point is the midpoint of the two independently observed native queries.
        for x, z in [
            (1596.0148, -96.75505),
            (1598.18487, -94.99115),
            (1597.099835, -95.8731),
        ]:
            normals = []
            levels = []
            for a, b, c in triangles:
                poly = Polygon([(p[0], p[2]) for p in (a, b, c)])
                if poly.distance(Point(x, z)) > 2:
                    continue
                u = [b[i] - a[i] for i in range(3)]
                v = [c[i] - a[i] for i in range(3)]
                n = [
                    u[1] * v[2] - u[2] * v[1],
                    u[2] * v[0] - u[0] * v[2],
                    u[0] * v[1] - u[1] * v[0],
                ]
                size = math.sqrt(sum(q * q for q in n))
                if size > 1e-12:
                    normals.append(abs(n[1]) / size)
                if poly.covers(Point(x, z)) and abs(n[1]) > 1e-9:
                    levels.append(a[1] - (n[0] * (x - a[0]) + n[2] * (z - a[2])) / n[1])
            self.assertTrue(normals)
            self.assertGreater(min(normals), 0.98)
            self.assertTrue(levels)
            self.assertLess(
                abs(max(levels) - field.height_for_road(1337078899, x, -z)), 0.04
            )

    def test_independent_source_bank_heights_do_not_use_exception(self):
        from bridges import physical_bridge_groups

        roads = self.fixture()
        opposite = next(r for r in roads if r["id"] == 959169606)
        for point in opposite["elevated_points"]:
            point[2] += 0.2
        self.assertEqual(len(physical_bridge_groups(roads)), 2)

    def test_genuine_stacked_layers_remain_separate(self):
        from bridges import physical_bridge_groups

        roads = self.fixture()
        opposite = next(r for r in roads if r["id"] == 959169606)
        opposite["tags"]["layer"] = "2"
        self.assertEqual(len(physical_bridge_groups(roads)), 2)

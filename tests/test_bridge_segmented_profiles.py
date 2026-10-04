import copy
import json
import math
import sys
import unittest
from pathlib import Path

from shapely.geometry import Point, Polygon, box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elevation import align_parallel_bridge_profiles, align_segmented_bridge_profiles  # noqa: E402
from road_surfaces import render_bridge_layers  # noqa: E402
from sthlm import PsdlWriter  # noqa: E402


class Terrain:
    def height(self, x, n):
        return 0


class SegmentedBridgeProfilesTest(unittest.TestCase):
    def test_native_floor_footprints_share_component_datum(self):
        fixture = json.loads(
            (
                Path(__file__).parent / "fixtures/bridge-segmented-profiles.json"
            ).read_text()
        )
        roads = fixture["roads"]
        before = copy.deepcopy(roads)
        bridge_ids = set(fixture["bridge_ways"])
        report = align_parallel_bridge_profiles(
            [r for r in roads if r["id"] in bridge_ids],
            anchor_nodes={
                n for r in roads if r["id"] not in bridge_ids for n in r["nodes"]
            },
        )
        self.assertEqual(len(report), 1)
        self.assertLess(report[0]["max_raise_m"], 1.56)
        for old, road in zip(before, roads):
            self.assertEqual(old["nodes"], road["nodes"])
            self.assertEqual(old["points"], road["points"])
            for a, b in zip(old["elevated_points"], road["elevated_points"]):
                self.assertEqual(a[:2], b[:2])
                self.assertGreaterEqual(b[2], a[2])
        city = {
            "roads": roads,
            "bridge_ways": list(bridge_ids),
            "bounds": mapping(box(-1500, 0, -1150, 350)),
        }
        triangles = []
        render_bridge_layers(PsdlWriter(), city, Terrain(), triangle_sink=triangles)
        # Exact old native body/next-guide footprints, with a two-metre wheel margin.
        for x, z in [
            (-1298.4471, -153.23096),
            (-1315.6173, -112.7724),
            (-1314.1775, -111.57),
            (-1319.067, -101.2665),
        ]:
            normals = []
            for a, b, c in triangles:
                if Polygon([(p[0], p[2]) for p in (a, b, c)]).distance(Point(x, z)) > 2:
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
            self.assertTrue(normals)
            self.assertGreater(min(normals), 0.98)

    def test_fixed_interior_land_anchor_skips_component_alignment(self):
        fixture = json.loads(
            (
                Path(__file__).parent / "fixtures/bridge-segmented-profiles.json"
            ).read_text()
        )
        roads = [r for r in fixture["roads"] if r["id"] in fixture["bridge_ways"]]
        before = copy.deepcopy(roads)
        self.assertEqual(
            align_segmented_bridge_profiles(roads, anchor_nodes={12384930823}), []
        )
        self.assertEqual(roads, before)

    def test_stacked_component_profiles_remain_independent(self):
        fixture = json.loads(
            (
                Path(__file__).parent / "fixtures/bridge-segmented-profiles.json"
            ).read_text()
        )
        roads = [r for r in fixture["roads"] if r["id"] in fixture["bridge_ways"]]
        opposite = next(r for r in roads if r["id"] == 100905137)
        opposite["tags"]["layer"] = "2"
        before = copy.deepcopy(roads)
        self.assertEqual(align_segmented_bridge_profiles(roads), [])
        self.assertEqual(roads, before)

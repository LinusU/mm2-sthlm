"""Opposite source carriageways share an authored physical bridge datum."""

import copy
import json
import math
from pathlib import Path
import sys
import unittest

from shapely.geometry import Point, Polygon, box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from elevation import align_parallel_bridge_profiles  # noqa: E402
from road_surfaces import render_bridge_layers  # noqa: E402
from sthlm import PsdlWriter  # noqa: E402


class Terrain:
    def height(self, x, north):
        return 0.0


class BridgeParallelProfileTests(unittest.TestCase):
    def roads(self):
        return json.loads(
            (
                Path(__file__).parent / "fixtures/bridge-parallel-profiles.json"
            ).read_text()
        )["roads"]

    def test_actual_parallel_deck_has_smooth_native_floor_at_all_three_stalls(self):
        roads = self.roads()
        before = copy.deepcopy(roads)
        reports = align_parallel_bridge_profiles(roads)
        self.assertEqual(reports[0]["source_ways"], [28345891, 162142154])
        for road, original in zip(roads, before):
            self.assertEqual(road["elevated_points"][0], original["elevated_points"][0])
            self.assertEqual(
                road["elevated_points"][-1], original["elevated_points"][-1]
            )
            self.assertEqual(road["nodes"], original["nodes"])
            for point, old in zip(road["elevated_points"], original["elevated_points"]):
                self.assertGreaterEqual(point[2], old[2])
        city = {
            "roads": roads,
            "bridge_ways": [r["id"] for r in roads],
            "bounds": mapping(box(980, -170, 1200, 50)),
        }
        triangles = []
        render_bridge_layers(PsdlWriter(), city, Terrain(), triangle_sink=triangles)
        for x, z in [
            (1060.7212, 23.614555),
            (1070.2966, 36.25343),
            (1087.5679, 56.986816),
        ]:
            with self.subTest(stall=(x, z)):
                normals = []
                for a, b, c in triangles:
                    if (
                        Polygon([(px, pz) for px, py, pz in (a, b, c)]).distance(
                            Point(x, z)
                        )
                        > 2
                    ):
                        continue
                    u = [b[i] - a[i] for i in range(3)]
                    v = [c[i] - a[i] for i in range(3)]
                    normal = [
                        u[1] * v[2] - u[2] * v[1],
                        u[2] * v[0] - u[0] * v[2],
                        u[0] * v[1] - u[1] * v[0],
                    ]
                    length = math.sqrt(sum(value * value for value in normal))
                    if length > 1e-12:
                        normals.append(abs(normal[1]) / length)
                self.assertGreater(len(normals), 0)
                # Original exact native fan slopes: normalY .766/.689/.561.
                # All original source heights and deck clearance are retained
                # or raised; this validates native facets, not an unseen field.
                self.assertGreater(min(normals), 0.9)

    def test_unconnected_stacked_or_distant_equal_named_decks_remain_independent(self):
        for kind in ("layer", "stacked", "distant", "same_direction"):
            roads = self.roads()
            if kind == "layer":
                roads[1]["tags"]["layer"] = "2"
            elif kind == "stacked":
                for point in roads[1]["elevated_points"]:
                    point[2] += 8
            elif kind == "distant":
                roads[1]["points"] = [[x + 40, n] for x, n in roads[1]["points"]]
                for point in roads[1]["elevated_points"]:
                    point[0] += 40
            else:
                roads[1]["nodes"].reverse()
                roads[1]["points"].reverse()
                roads[1]["elevated_points"].reverse()
            before = copy.deepcopy(roads)
            with self.subTest(kind=kind):
                self.assertEqual(align_parallel_bridge_profiles(roads), [])
                self.assertEqual(roads, before)

    def test_interior_source_approach_anchor_is_not_moved_without_join_alignment(self):
        roads = self.roads()
        before = copy.deepcopy(roads)
        self.assertEqual(
            align_parallel_bridge_profiles(roads, anchor_nodes=[roads[0]["nodes"][1]]),
            [],
        )
        self.assertEqual(roads, before)


if __name__ == "__main__":
    unittest.main()

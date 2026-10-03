import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from elevation import RoadField
from road_profiles import smooth


class RoadProfileTests(unittest.TestCase):
    def road(self, identifier, nodes, points, width=9):
        return {
            "id": identifier,
            "nodes": nodes,
            "points": points,
            "width": width,
            "tags": {},
        }

    def test_long_real_grade_survives_short_dtm_spike(self):
        class Terrain:
            def height(self, x, n):
                return 5 + 0.08 * x + (8 if abs(x - 150) < 5 else 0)

        road = self.road(1, [1, 2, 3], [(0, 0), (150, 0), (300, 0)])
        rows = smooth([road], Terrain(), {})
        self.assertLessEqual(rows[0]["max_grade"], 0.1601)
        self.assertLessEqual(rows[0]["max_vertical_curvature_per_m"], 0.0031)
        self.assertGreater(
            road["elevated_points"][-1][2] - road["elevated_points"][0][2], 23
        )
        centre = min(road["elevated_points"], key=lambda p: abs(p[0] - 150))
        self.assertLess(abs(centre[2] - 17), 1)

    def test_junction_has_one_shared_height(self):
        class Terrain:
            def height(self, x, n):
                return 10 + 0.04 * x + 0.02 * n

        roads = [
            self.road(1, [1, 2], [(-100, 0), (0, 0)]),
            self.road(2, [2, 3], [(0, 0), (100, 0)]),
            self.road(3, [2, 4], [(0, 0), (0, 100)]),
        ]
        smooth(roads, Terrain(), {})
        joint = roads[0]["elevated_points"][-1][2]
        for road in roads:
            for x, n, h in road["elevated_points"]:
                if math.hypot(x, n) < 1e-6:
                    self.assertAlmostEqual(h, joint)

    def test_source_sampling_does_not_attract_nearby_lower_road(self):
        class Terrain:
            def height(self, x, n):
                return 0

        roads = [
            {"id": 1, "width": 12, "elevated_points": [[0, 0, 20], [100, 0, 24]]},
            {"id": 2, "width": 8, "elevated_points": [[0, 5, 2], [100, 5, 2]]},
        ]
        field = RoadField(roads, Terrain())
        self.assertEqual(field.height_for_road(1, 50, 6), 22)
        self.assertEqual(field.height_for_road(2, 50, 0), 2)
        self.assertEqual(field.height_for_road(roads[0], 50, -6), 22)

    def test_source_connected_junction_uses_one_plane(self):
        roads = [
            self.road(1, [1, 2], [(-100, 0), (0, 0)]),
            self.road(2, [2, 3], [(0, 0), (100, 0)]),
            self.road(3, [2, 4], [(0, 0), (0, 100)]),
        ]

        class Terrain:
            def height(self, x, n):
                return 10 + 0.04 * x + 0.02 * n

        smooth(roads, Terrain(), {})
        field = RoadField(roads, Terrain())
        heights = [field.planar_height(10, 2, 2, r["id"]) for r in roads]
        self.assertLess(max(heights) - min(heights), 0.003)
        self.assertGreater(
            field.height_for_road(roads[1], 5, 0),
            field.height_for_road(roads[1], -5, 0),
        )

    def test_source_cache_refreshes_authored_profile_replacement(self):
        class Terrain:
            def height(self, x, n):
                return 0

        road = {"id": 1, "width": 9, "elevated_points": [[0, 0, 10], [100, 0, 10]]}
        field = RoadField([road], Terrain())
        self.assertEqual(field.height_for_road(road, 50, 0), 10)
        road["elevated_points"] = [[0, 0, 10], [100, 0, 6]]
        road["height_override"] = {"drop_m": 4}
        self.assertEqual(field.height_for_road(road, 50, 0), 8)

    def test_crossing_without_shared_osm_node_keeps_separate_levels(self):
        class Terrain:
            def height(self, x, n):
                return 20 if abs(n) < 1 else 2

        roads = [
            self.road(1, [1, 2], [(-100, 0), (100, 0)]),
            self.road(2, [3, 4], [(0, -100), (0, 100)]),
        ]
        smooth(roads, Terrain(), {})
        field = RoadField(roads, Terrain())
        self.assertGreater(
            field.height_for_road(1, 0, 0) - field.height_for_road(2, 0, 0), 15
        )

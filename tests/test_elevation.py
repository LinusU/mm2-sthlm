import sys
import unittest
from pathlib import Path

from shapely.geometry import box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from elevation import apply
from sthlm import PsdlWriter
from props import placements, tree_mesh


class Plane:
    metadata = {"datum": "test plane"}

    def height(self, x, n):
        return 2 + x * 0.01 + n * 0.02


class ElevationTests(unittest.TestCase):
    def road(self, id, nodes, points, bridge=False):
        return {
            "id": id,
            "nodes": nodes,
            "points": points,
            "width": 9,
            "tags": {"name": "Stadshusbron" if bridge else "road"},
        }

    def test_shared_road_junction_uses_one_height(self):
        roads = [
            self.road(1, [1, 2], [(0, 0), (100, 0)]),
            self.road(2, [2, 3], [(100, 0), (100, 100)]),
        ]
        city = {
            "roads": roads,
            "bridge_ways": [],
            "spawn": [0, 0, 0],
            "route": [(0, 0)],
            "buildings": [],
            "bounds": mapping(box(-20, -20, 120, 120)),
        }
        field, _, _, _ = apply(city, Plane())
        self.assertEqual(
            roads[0]["elevated_points"][-1], roads[1]["elevated_points"][0]
        )
        self.assertAlmostEqual(field(100, 0), 3)
        self.assertAlmostEqual(field.ground(100, 3), field(100, 3))
        self.assertEqual(city["spawn"][1], 3.5)

    def test_bridge_deck_matches_ends_without_flattening_underpass(self):
        roads = [
            self.road(1, [1, 2], [(0, 0), (100, 0)]),
            self.road(2, [2, 3, 4], [(100, 0), (200, 0), (300, 0)], True),
            self.road(3, [4, 5], [(300, 0), (400, 0)]),
            self.road(4, [6, 7], [(200, -100), (200, 100)]),
        ]
        city = {
            "roads": roads,
            "bridge_ways": [2],
            "spawn": [0, 0, 0],
            "route": [(0, 0)],
            "buildings": [],
            "bounds": mapping(box(-20, -120, 420, 120)),
        }
        ground, deck, _, _ = apply(city, Plane())
        self.assertAlmostEqual(deck(100, 0), ground(100, 0))
        self.assertAlmostEqual(deck(300, 0), ground(300, 0))
        self.assertGreater(deck(200, 0), ground(200, 0) + 5)
        self.assertIn("estimated", city["bridge_profiles"][0]["height_rule"])

    def test_height_surface_samples_inside_large_polygons(self):
        writer = PsdlWriter()
        writer.surface(box(0, 0, 100, 100), lambda x, n: x / 10, "grass")
        self.assertTrue(any(v[0] == 50 and v[1] == 5 for v in writer.vertices))
        self.assertTrue(all(abs(v[1] - v[0] / 10) < 1e-5 for v in writer.vertices))

    def test_trees_are_separate_grounded_breakable_assets(self):
        city = {"trees": [{"id": 4, "position": [30, 30]}], "buildings": []}
        props = placements(
            city, box(0, 0, 100, 100), box(0, 0, 10, 100), Plane().height
        )
        self.assertEqual(len(props), 1)
        self.assertAlmostEqual(props[0]["position"][1], 2.9)
        self.assertTrue(props[0]["breakable"])
        data = tree_mesh()
        self.assertTrue(data.startswith(b"PKG3"))
        self.assertIn(b"BREAK01_H\0", data)
        self.assertIn(b"BREAK02_H\0", data)

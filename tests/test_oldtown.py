import gzip
import json
import sys
import unittest
from pathlib import Path

from shapely.geometry import Point, box, mapping, shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import oldtown
from expanded import normalized


class OldTownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.cfg = json.loads((root / "config/expanded.json").read_text())
        cls.source = json.load(gzip.open(root / "sources/expanded/osm.json.gz"))
        cls.city = normalized(cls.source, cls.cfg)
        # Module coverage derives from the source independently of upstream
        # normalization island-reference corrections.
        cls.city["land"] = mapping(oldtown.source_land(cls.source, cls.cfg))
        cls.city["water"] = mapping(
            shape(cls.city["bounds"]).difference(shape(cls.city["land"]))
        )
        oldtown.apply(cls.source, cls.cfg, cls.city)

    def test_real_islands_have_stone_coverage(self):
        mask = shape(self.city["oldtown"]["stone_mask"])
        self.assertFalse(self.city["oldtown"]["missing_islands"])
        self.assertGreater(mask.area, 300000)
        for lonlat in [(18.0708, 59.3249), (18.0650, 59.3259)]:
            self.assertTrue(
                mask.covers(Point(oldtown.project(*lonlat, self.cfg["origin"])))
            )

    def test_all_named_green_areas_survive(self):
        preserved = self.city["oldtown"]["protected_features"]
        names = {p["name"] for p in preserved}
        self.assertTrue(
            {"Junotäppan", "Logården", "Strömparterren", "Bollhustäppan"} <= names
        )
        self.assertEqual(
            shape(self.city["oldtown"]["protected_mask"])
            .intersection(shape(self.city["oldtown"]["stone_mask"]))
            .area,
            0,
        )

    def test_water_and_mainland_are_outside_mask(self):
        stone = shape(self.city["oldtown"]["stone_mask"])
        self.assertLess(stone.intersection(shape(self.city["water"])).area, 1e-6)
        self.assertFalse(
            stone.covers(Point(oldtown.project(18.071, 59.332, self.cfg["origin"])))
        )

    def test_surface_partition_conserves_area_without_overlap(self):
        land = shape(self.city["land"])
        stone, other = oldtown.partition(land, self.city)
        self.assertAlmostEqual(stone.union(other).area, land.area, places=5)
        self.assertLess(stone.intersection(other).area, 1e-6)

    def test_ring_roads_bridges_and_tunnels_keep_asphalt(self):
        for tags in [
            {"highway": "trunk"},
            {"name": "Skeppsbron"},
            {"bridge": "yes"},
            {"tunnel": "yes"},
        ]:
            self.assertIsNone(
                oldtown.material_for(
                    {"tags": {"sthlm:surface": "oldtown_setts", **tags}}
                )
            )
        self.assertEqual(
            oldtown.material_for(
                {"tags": {"sthlm:surface": "oldtown_setts", "highway": "living_street"}}
            ),
            oldtown.MATERIAL,
        )

    def test_fan_partition_preserves_asphalt_overlap(self):
        city = {
            "roads": [
                {
                    "points": [[0, 0], [20, 0]],
                    "width": 4,
                    "tags": {"sthlm:surface": "oldtown_setts"},
                },
                {
                    "points": [[10, -10], [10, 10]],
                    "width": 4,
                    "tags": {"highway": "trunk"},
                },
            ],
            "oldtown": {"stone_mask": mapping(box(-5, -5, 25, 5))},
        }
        area = box(0, -2, 20, 2)
        stone, asphalt = oldtown.road_partition(area, city)
        self.assertFalse(stone.covers(Point(10, 0)))
        self.assertTrue(stone.covers(Point(3, 0)))
        self.assertAlmostEqual(stone.area + asphalt.area, area.area)

    def test_historic_pedestrian_selection_is_scoped_and_respects_width(self):
        allowed = oldtown.eligible_pedestrian_ways(
            self.source, self.cfg, land=shape(self.city["land"])
        )
        self.assertIn(1975, allowed)  # Västerlånggatan, source pedestrian sett street.
        self.assertEqual(allowed[1975], 3.5)
        self.assertIn(328131576, allowed)  # Storkyrkobrinken delivery alley.
        self.assertEqual(allowed[328131576], 4.0)
        self.assertNotIn(40291347, allowed)  # Kåkbrinken's two-metre pinch point.
        ways = {e["id"]: e for e in self.source["elements"] if e["type"] == "way"}
        self.assertTrue(
            all(ways[i]["tags"]["highway"] == "pedestrian" for i in allowed)
        )
        self.assertTrue(all(ways[i]["tags"].get("area") != "yes" for i in allowed))
        empty = oldtown.eligible_pedestrian_ways(
            self.source, self.cfg, land=box(-20, -20, 20, 20)
        )
        self.assertEqual(empty, {})

    def test_texture_reproducible_with_no_paint(self):
        self.assertEqual(oldtown.texture().tobytes(), oldtown.texture().tobytes())
        self.assertEqual(oldtown.texture().size, (500, 500))
        with self.assertRaises(ValueError):
            oldtown.texture(511)

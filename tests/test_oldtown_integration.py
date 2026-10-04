"""Native material hooks preserve physical fan coverage and source heights."""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from shapely.geometry import Polygon, box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import oldtown
import road_surfaces
import sthlm


class OldTownNativeIntegrationTests(unittest.TestCase):
    def city(self):
        return {
            "roads": [
                {
                    "id": 1,
                    "nodes": [1, 2],
                    "points": [[0, 0], [40, 0]],
                    "width": 4,
                    "tags": {
                        "highway": "residential",
                        "lanes": "2",
                        "sthlm:surface": "oldtown_setts",
                    },
                }
            ],
            "bridge_ways": [],
            "oldtown": {"road_stone_mask": mapping(box(0, -2, 20, 2))},
        }

    def test_builder_ground_excludes_both_stone_and_other_paving(self):
        # Execute the actual exporter through ground emission. Capture surfaces
        # before unrelated buildings/assets, rather than duplicate its formula.
        bounds = box(0, 0, 40, 40)
        water = box(0, 0, 5, 40)
        land = bounds.difference(water)
        road = box(10, 10, 30, 14)
        city = {
            "spawn": [15, 3.5, -12],
            "roads": [],
            "bridge_ways": [],
            "bounds": mapping(bounds),
            "water": mapping(water),
            "land": mapping(land),
            "road_surface": mapping(road),
            "bridge_approach_surface": mapping(Polygon()),
            "water_regions": [],
            "oldtown": {"stone_mask": mapping(box(0, 0, 22, 40))},
        }
        emitted = []

        class GroundFinished(Exception):
            pass

        class Writer:
            def __init__(self, spawn):
                pass

            def surface(self, geometry, height, material, **flags):
                if flags.get("water"):
                    raise GroundFinished()
                if not geometry.is_empty:
                    emitted.append((geometry, material))

        field = SimpleNamespace(
            ground=lambda x, n: 2,
            height_for_road=lambda r, x, n: 2,
            height_at_station=lambda r, station: 2,
        )

        def render(writer, city, geometry, height, **kwargs):
            writer.surface(geometry, height, "sthlm_asphalt", road=True)
            return {}

        with (
            tempfile.TemporaryDirectory() as temp,
            patch("expanded.normalized", return_value=city),
            patch("expanded.ChunkedWriter", Writer),
            patch("street_details.apply"),
            patch("street_details.wrap_field", side_effect=lambda field, city: field),
            patch("road_details.normalized", return_value={}),
            patch("road_details.surface_height", return_value=lambda x, n: 2),
            patch("oldtown.apply"),
            patch("terrain.TerrainGrid.from_project", return_value=object()),
            patch(
                "elevation.apply", return_value=(field, field.ground, road, Polygon())
            ),
            patch("road_surfaces.render", side_effect=render),
            patch("road_surfaces.render_bridge_layers", return_value={}),
        ):
            with self.assertRaises(GroundFinished):
                sthlm.build(Path(temp))
        self.assertTrue(any(material == oldtown.MATERIAL for _, material in emitted))
        self.assertTrue(any(material == "paving" for _, material in emitted))
        self.assertAlmostEqual(sum(geometry.area for geometry, _ in emitted), land.area)
        for index, (geometry, material) in enumerate(emitted):
            for other, other_material in emitted[index + 1 :]:
                self.assertLess(
                    geometry.intersection(other).area,
                    1e-6,
                    f"overlapping physical ground: {material}/{other_material}",
                )

    def test_stone_fan_partition_retains_native_area_heights_and_sink(self):
        city = self.city()
        writer = sthlm.PsdlWriter()
        sink = []
        geom = box(0, -2, 40, 2)
        report = road_surfaces.render(
            writer, city, geom, lambda x, n: 2 + x * 0.08, triangle_sink=sink
        )
        self.assertFalse(road_surfaces.classification(city["roads"][0])["marked"])
        self.assertEqual(report["strips"], 0)
        self.assertAlmostEqual(report["remainder_area"], geom.area)
        self.assertEqual(set(writer.textures), {oldtown.MATERIAL, "sthlm_asphalt"})
        self.assertAlmostEqual(
            sum(Polygon([(p[0], p[2]) for p in tri]).area for tri in sink), geom.area
        )
        for tri in sink:
            for x, y, z in tri:
                self.assertAlmostEqual(y, 2 + x * 0.08, places=5)
        self.assertTrue(all(attrs[2] == 0xA9 for _, attrs, _ in writer.rooms))

    def test_elevated_group_does_not_inherit_underlying_stone_mask(self):
        city = self.city()
        city["bridge_ways"] = [1]
        writer = sthlm.PsdlWriter()
        sink = []
        report = road_surfaces.render(
            writer, city, box(0, -2, 40, 2), 12, bridge=True, triangle_sink=sink
        )
        self.assertEqual(writer.textures, ["sthlm_asphalt"])
        self.assertAlmostEqual(report["remainder_area"], 160)
        self.assertAlmostEqual(
            sum(Polygon([(p[0], p[2]) for p in tri]).area for tri in sink), 160
        )
        self.assertEqual({p[1] for tri in sink for p in tri}, {12})

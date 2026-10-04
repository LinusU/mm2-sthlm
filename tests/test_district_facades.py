import copy
from pathlib import Path
import sys
import tempfile
import unittest

from shapely.geometry import box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import district_facades as facades
import sthlm


class DistrictFacadesTests(unittest.TestCase):
    def building(self, lon=18.07, lat=59.324, **extra):
        x, y = sthlm.project(lon, lat, [18.045, 59.328])
        return {
            "id": "way/12345",
            "tags": {"building": "apartments"},
            "geometry": mapping(box(x - 5, y - 5, x + 5, y + 5)),
            "height": 18,
            "base_y": 2,
            **extra,
        }

    def test_six_district_palettes_keep_source_unchanged(self):
        points = [
            (18.027, 59.334, "kungsholmen"),
            (18.060, 59.337, "norrmalm"),
            (18.081, 59.342, "ostermalm"),
            (18.075, 59.311, "sodermalm"),
            (18.07, 59.324, "gamla_stan"),
            (18.120, 59.327, "djurgarden"),
        ]
        for lon, lat, district in points:
            b = self.building(lon, lat)
            before = copy.deepcopy(b)
            self.assertEqual(facades.material_for(b)["district"], district)
            self.assertEqual(b, before)
        self.assertIsNone(
            facades.material_for(self.building(tags={"building": "church"}))
        )
        self.assertIsNone(facades.material_for(self.building(height=3)))

    def test_native_door_once_above_street_with_full_collision(self):
        b = self.building(18.045, 59.328)
        poly = box(-5, -5, 5, 5)
        roads = {"roads": [{"points": [[-20, -9], [20, -9]], "tags": {}}]}
        frontage = facades.StreetFrontages(roads, lambda x, y: 5)
        writer = sthlm.PsdlWriter()
        metadata = facades.export(writer, poly, b, frontage)
        attrs = writer.rooms[0][1]
        parsed = []
        index = 0
        texture = None
        while index < len(attrs):
            code = attrs[index]
            if code & 0xF8 == 0x50:
                texture = writer.textures[(code & 7) * 256 + attrs[index + 1] - 1]
                index += 2
            elif code == 0x5E:
                parsed.append((texture, attrs[index + 1 : index + 7]))
                index += 7
            elif code == 0x3C:
                index += 5
            elif code == 0xB1:
                index += 4
            else:
                self.fail(f"unexpected native attribute {code}")
        doors = [values for texture, values in parsed if texture.endswith("_door")]
        self.assertEqual(len(doors), 1)
        hb, ht, u, v, left, right = doors[0]
        self.assertEqual((u, v), (1, 1))
        self.assertAlmostEqual(writer.heights[hb], 5.06)
        self.assertAlmostEqual(
            abs(writer.vertices[left][0] - writer.vertices[right][0]), 1.6
        )
        self.assertAlmostEqual(metadata["entrance"]["bottom_m"], 5.06)
        # Four full-height collision bounds despite additional rendered bands.
        self.assertEqual(attrs.count(0x3C), 4)
        uppers = [values for texture, values in parsed if texture.endswith("_upper")]
        self.assertTrue(
            all(writer.heights[values[0]] >= writer.heights[ht] for values in uppers)
        )

    def test_hillside_ground_at_door_has_priority_over_lower_street(self):
        frontage = facades.StreetFrontages(
            {"roads": [{"points": [[-20, -9], [20, -9]], "tags": {}}]},
            lambda x, y: 8 if y >= -5 else 2,
        )
        entrance = frontage.entrance(box(-5, -5, 5, 5), 2, 20)
        self.assertAlmostEqual(entrance[2], 8.06)
        self.assertIsNone(frontage.entrance(box(-5, -5, 5, 5), 2, 10))

    def test_tunnels_bridges_remote_roads_do_not_attract_doors(self):
        poly = box(-5, -5, 5, 5)
        for tags, y in [
            ({"tunnel": "yes"}, -9),
            ({"bridge": "yes"}, -9),
            ({"layer": "1"}, -9),
            ({}, -90),
        ]:
            frontage = facades.StreetFrontages(
                {"roads": [{"points": [[-20, y], [20, y]], "tags": tags}]}, 2
            )
            self.assertIsNone(frontage.entrance(poly, 2, 20))

    def test_all_assets_reproducible_offline(self):
        with (
            tempfile.TemporaryDirectory() as first,
            tempfile.TemporaryDirectory() as second,
        ):
            facades.write(first)
            facades.write(second)
            files = list((Path(first) / "texture").glob("*.png"))
            self.assertEqual(len(files), 76)
            for file in files:
                self.assertEqual(
                    file.read_bytes(),
                    (Path(second) / "texture" / file.name).read_bytes(),
                )


if __name__ == "__main__":
    unittest.main()

import copy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import manor_materials

ROOT = Path(__file__).resolve().parents[1]


class ManorMaterialsTests(unittest.TestCase):
    def test_only_estate_features_match_without_mutating_source(self):
        with gzip.open(ROOT / "sources/expanded/osm.json.gz", "rt") as stream:
            source = json.load(stream)
        ways = {
            f"way/{element['id']}": element
            for element in source["elements"]
            if element["type"] == "way"
        }
        expected = {"way/88413902", "way/88413904", "way/88413905"}
        override = json.loads(manor_materials.OVERRIDE_PATH.read_text())
        self.assertEqual(set(override["source_features"]), expected)
        for feature_id in expected | {"way/35214623", "way/88413899", "way/730235044"}:
            feature = {**ways[feature_id], "id": feature_id}
            before = copy.deepcopy(feature)
            material = manor_materials.material_for(feature)
            self.assertEqual(material is not None, feature_id in expected)
            self.assertEqual(feature, before)
            if feature_id in expected:
                self.assertEqual(feature["tags"]["building:material"], "plaster")
                self.assertEqual(feature["tags"]["building:colour"], "yellow")

    def test_native_assets_are_deterministic_and_include_six_pane_trim(self):
        with (
            tempfile.TemporaryDirectory() as first,
            tempfile.TemporaryDirectory() as second,
        ):
            manor_materials.write(first)
            manor_materials.write(second)
            for name in ("manor_plaster", "manor_facade", "manor_tiles"):
                path = Path(first) / "texture" / f"{name}.png"
                self.assertEqual(
                    path.read_bytes(),
                    (Path(second) / "texture" / path.name).read_bytes(),
                )
                with Image.open(path) as image:
                    self.assertEqual(image.size, (256, 256))
                    self.assertEqual(image.mode, "RGB")
                    self.assertGreater(len(image.getcolors(65536)), 1)
            with Image.open(Path(first) / "texture/manor_facade.png") as facade:
                self.assertEqual(facade.getpixel((91, 69)), (163, 167, 145))
                for x in (110, 139):
                    for y in (88, 123, 158):
                        self.assertLess(facade.getpixel((x, y))[0], 90)
                self.assertGreater(facade.getpixel((20, 100))[0], 210)


if __name__ == "__main__":
    unittest.main()

import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

from shapely.geometry import Point, Polygon, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pavilion
import sthlm
from expanded import ChunkedWriter

ROOT = Path(__file__).resolve().parents[1]


def source_feature():
    with gzip.open(ROOT / "sources/expanded/osm.json.gz", "rt") as stream:
        source = json.load(stream)
    origin = json.loads((ROOT / "config/expanded.json").read_text())["origin"]
    nodes = {e["id"]: e for e in source["elements"] if e["type"] == "node"}
    way = next(
        e for e in source["elements"] if e["type"] == "way" and e["id"] == 1049742528
    )
    poly = Polygon(
        [sthlm.project(nodes[i]["lon"], nodes[i]["lat"], origin) for i in way["nodes"]]
    )
    return {"id": pavilion.BUILDING_ID, "geometry": mapping(poly), "base_y": 7.25}


class PavilionTests(unittest.TestCase):
    def test_source_partition_preserves_footprint(self):
        art = json.loads(pavilion.ART_PATH.read_text())
        footprint, centre, wings = pavilion.model_geometry(source_feature(), art)
        self.assertLess(centre.intersection(wings).area, 1e-8)
        self.assertLess(footprint.symmetric_difference(centre.union(wings)).area, 1e-8)
        self.assertGreater(centre.area, 210)
        self.assertLess(centre.area, 250)
        self.assertAlmostEqual(footprint.centroid.x, -1005.8, delta=0.1)
        self.assertAlmostEqual(footprint.centroid.y, 67.4, delta=0.1)

    def test_export_single_floor_source_elevation_native_package(self):
        feature = source_feature()
        original = json.loads(json.dumps(feature["geometry"]))
        footprint = Polygon(feature["geometry"]["coordinates"][0])
        writer = sthlm.PsdlWriter()
        with tempfile.TemporaryDirectory() as tmp:
            metadata = pavilion.export(writer, {"buildings": [feature]}, Path(tmp))
            self.assertEqual(metadata["source_feature"], pavilion.BUILDING_ID)
            self.assertEqual(
                set(writer.textures), {"bar_glass", "bar_wing", "bar_roof"}
            )
            self.assertAlmostEqual(min(p[1] for p in writer.vertices), 7.25)
            self.assertAlmostEqual(max(p[1] for p in writer.vertices), 13.45)
            for x, _, south in writer.vertices:
                self.assertTrue(footprint.buffer(0.0001).covers(Point(x, -south)))
            # First three rooms are the two wings and the centre. Every facade
            # keeps exactly one vertical repeat regardless of its eave height.
            for _, attrs, _ in writer.rooms[:3]:
                edge = 0
                while attrs[edge + 2] == 0x5E:
                    self.assertEqual(attrs[edge + 6], 1)
                    edge += 14
            for perimeter, attrs, _ in writer.rooms[3:]:
                if attrs[2] == 0xB1:
                    projected = Polygon(
                        [
                            (writer.vertices[i][0], writer.vertices[i][2])
                            for i in perimeter
                        ]
                    )
                    self.assertGreater(projected.area, 1)
                    a, b, c = [writer.vertices[i] for i in attrs[-3:]]
                    face_area = abs(
                        (b[0] - a[0]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[0] - a[0])
                    )
                    if face_area < 1e-6:
                        self.assertGreater(projected.area, 200)
            for name in writer.textures:
                self.assertTrue((Path(tmp) / "texture" / f"{name}.png").is_file())
            writer.write(Path(tmp) / "bar.psdl", [0, 0, 0])
            inspected = sthlm.inspect_psdl(Path(tmp) / "bar.psdl", Path(tmp))
            self.assertEqual(inspected["rooms"], len(writer.rooms))
            self.assertGreater(inspected["triangles"], 15)
        self.assertEqual(json.loads(json.dumps(feature["geometry"])), original)

    def test_chunked_export_keeps_same_height(self):
        writer = ChunkedWriter([0, 0, 0])
        with tempfile.TemporaryDirectory() as tmp:
            pavilion.export(writer, {"buildings": [source_feature()]}, Path(tmp))
        self.assertAlmostEqual(max(p[1] for p in writer.vertices), 13.45)
        self.assertTrue(writer.parts)

    def test_absent_feature_creates_nothing(self):
        writer = sthlm.PsdlWriter()
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(pavilion.export(writer, {"buildings": []}, Path(tmp)))
            self.assertEqual(writer.rooms, [])
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()

import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

from shapely.geometry import Polygon, Point, mapping, box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import courthouse
import sthlm

ROOT = Path(__file__).resolve().parents[1]


def source_feature():
    with gzip.open(ROOT / "sources/expanded/osm.json.gz", "rt") as stream:
        source = json.load(stream)
    origin = json.loads((ROOT / "config/expanded.json").read_text())["origin"]
    nodes = {e["id"]: e for e in source["elements"] if e["type"] == "node"}
    way = next(
        e for e in source["elements"] if e["type"] == "way" and e["id"] == 24488933
    )
    poly = Polygon(
        [sthlm.project(nodes[i]["lon"], nodes[i]["lat"], origin) for i in way["nodes"]]
    )
    return {"id": courthouse.BUILDING_ID, "geometry": mapping(poly), "base_y": 9.5}


class CourthouseTests(unittest.TestCase):
    def test_geometry_preserves_source_boundary_with_documented_courtyards(self):
        feature = source_feature()
        art = json.loads(courthouse.ART_PATH.read_text())
        footprint, body, tower = courthouse.model_geometry(feature, art)
        self.assertTrue(footprint.covers(body))
        self.assertLess(tower.difference(body).area, 1e-8)
        self.assertEqual(len(body.interiors), 2)
        self.assertGreater(body.area, footprint.area * 0.65)
        self.assertLess(body.area, footprint.area * 0.85)
        self.assertGreater(tower.area, 250)
        self.assertLess(tower.area, 300)
        # The real recorded exterior, rather than a replacement rectangle.
        self.assertAlmostEqual(
            body.union(footprint.difference(body)).area, footprint.area
        )

    def test_export_uses_elevation_keeps_ornaments_inside_building(self):
        feature = source_feature()
        original = json.loads(json.dumps(feature["geometry"]))
        writer = sthlm.PsdlWriter()
        with tempfile.TemporaryDirectory() as tmp:
            metadata = courthouse.export(writer, {"buildings": [feature]}, Path(tmp))
            self.assertEqual(metadata["source_feature"], courthouse.BUILDING_ID)
            footprint, body, _ = courthouse.model_geometry(
                feature, json.loads(courthouse.ART_PATH.read_text())
            )
            self.assertGreater(len(writer.rooms), 50)
            self.assertAlmostEqual(max(v[1] for v in writer.vertices), 62.5)
            self.assertAlmostEqual(min(v[1] for v in writer.vertices), 9.5)
            # Writer performs exactly one north-to-south conversion.
            for x, _, south in writer.vertices:
                self.assertTrue(footprint.buffer(0.0001).covers(Point(x, -south)))
                self.assertTrue(body.buffer(0.0001).covers(Point(x, -south)))
            for name in writer.textures:
                self.assertTrue((Path(tmp) / "texture" / f"{name}.png").is_file())
            writer.write(Path(tmp) / "courthouse.psdl", [0, 0, 0])
            binary = sthlm.inspect_psdl(Path(tmp) / "courthouse.psdl", Path(tmp))
            self.assertEqual(binary["rooms"], len(writer.rooms))
            self.assertGreater(binary["triangles"], 100)
        self.assertEqual(json.loads(json.dumps(feature["geometry"])), original)

    def test_copper_hip_faces_keep_upward_roof_winding(self):
        writer = sthlm.PsdlWriter()
        courthouse.frustum(
            writer, box(-9, -9, 9, 9), box(-5, -5, 5, 5), 28, 36, "court_copper"
        )
        self.assertEqual(len(writer.rooms), 8)
        for _, attrs, _ in writer.rooms:
            a, b, c = [writer.vertices[i] for i in attrs[-3:]]
            projected = (b[0] - a[0]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[0] - a[0])
            self.assertLess(projected, 0)  # Exactly one north-to-south flip.

    def test_vertical_copper_stage_supplies_room_for_outward_fans(self):
        writer = sthlm.PsdlWriter()
        courthouse.frustum(
            writer, box(-5, -5, 5, 5), box(-5, -5, 5, 5), 36.5, 42, "court_copper"
        )
        self.assertEqual(len(writer.rooms), 8)
        for perimeter, attrs, _ in writer.rooms:
            room = Polygon(
                [(writer.vertices[i][0], writer.vertices[i][2]) for i in perimeter]
            )
            self.assertAlmostEqual(room.area, 100)
            a, b, c = [writer.vertices[i] for i in attrs[-3:]]
            ab = [b[i] - a[i] for i in range(3)]
            ac = [c[i] - a[i] for i in range(3)]
            nx = ab[1] * ac[2] - ab[2] * ac[1]
            nz = ab[0] * ac[1] - ab[1] * ac[0]
            length = (nx * nx + nz * nz) ** 0.5
            mx, mz = sum(p[0] for p in [a, b, c]) / 3, sum(p[2] for p in [a, b, c]) / 3
            # Match the existing engine vertical_facing room test: the front
            # normal's offset is exterior, while the reverse offset is interior.
            # A triangle-only room projects to zero area, making both offsets
            # exterior and triggering the engine's inward tri_up fallback.
            self.assertFalse(
                room.contains(Point(mx + nx / length * 0.5, mz + nz / length * 0.5))
            )
            self.assertTrue(
                room.contains(Point(mx - nx / length * 0.5, mz - nz / length * 0.5))
            )

    def test_absent_feature_is_noop(self):
        writer = sthlm.PsdlWriter()
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(courthouse.export(writer, {"buildings": []}, Path(tmp)))
            self.assertEqual(writer.rooms, [])
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_chunked_export_matches_single_writer_height(self):
        from expanded import ChunkedWriter

        writer = ChunkedWriter([0, 0, 0])
        with tempfile.TemporaryDirectory() as tmp:
            courthouse.export(writer, {"buildings": [source_feature()]}, Path(tmp))
        self.assertAlmostEqual(max(v[1] for v in writer.vertices), 62.5)
        self.assertTrue(writer.parts)


if __name__ == "__main__":
    unittest.main()

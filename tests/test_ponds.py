import json
import sys
import tempfile
import unittest
from pathlib import Path

from shapely.geometry import Polygon, mapping, shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import ponds
import sthlm


class PondTests(unittest.TestCase):
    def test_navigable_water_remains_deep(self):
        for tags in (
            {"water": "canal"},
            {"water": "lock"},
            {"water": "basin", "disused:dock": "drydock"},
            {"natural": "water", "leisure": "marina"},
        ):
            self.assertFalse(ponds.classify(tags, 80))
        self.assertFalse(ponds.classify({"natural": "water", "water": "lake"}, 9000))
        self.assertTrue(ponds.classify({"natural": "water", "water": "pond"}, 900))

    def test_fountain_only_source_is_retained_but_marine_overlap_is_not(self):
        origin = [18.045, 59.328]
        corners = [
            (18.04, 59.33),
            (18.0402, 59.33),
            (18.0402, 59.3302),
            (18.04, 59.3302),
        ]
        source = {
            "elements": [
                {"type": "node", "id": i, "lon": lon, "lat": lat}
                for i, (lon, lat) in enumerate(corners)
            ]
            + [
                {
                    "type": "way",
                    "id": 123,
                    "nodes": [0, 1, 2, 3, 0],
                    "tags": {"amenity": "fountain"},
                }
            ]
        }
        polygon = Polygon([sthlm.project(*p, origin) for p in corners])
        config = {"origin": origin}
        features = ponds.normalized(source, config, polygon.buffer(1))
        self.assertEqual([f["id"] for f in features], ["way/123"])
        self.assertEqual(
            ponds.normalized(source, config, polygon.buffer(1), coast=polygon), []
        )
        source["elements"][-1]["id"] = 1291160189
        self.assertEqual(ponds.normalized(source, config, polygon.buffer(1)), [])

    def test_pond_relation_does_not_duplicate_tagged_outer_way(self):
        origin = [18.045, 59.328]
        corners = [
            (18.04, 59.33),
            (18.0402, 59.33),
            (18.0402, 59.3302),
            (18.04, 59.3302),
        ]
        source = {
            "elements": [
                {"type": "node", "id": i, "lon": lon, "lat": lat}
                for i, (lon, lat) in enumerate(corners)
            ]
            + [
                {
                    "type": "way",
                    "id": 123,
                    "nodes": [0, 1, 2, 3, 0],
                    "tags": {"natural": "water", "water": "pond"},
                },
                {
                    "type": "relation",
                    "id": 456,
                    "members": [{"type": "way", "ref": 123, "role": "outer"}],
                    "tags": {
                        "type": "multipolygon",
                        "natural": "water",
                        "water": "pond",
                    },
                },
            ]
        }
        polygon = Polygon([sthlm.project(*p, origin) for p in corners])
        features = ponds.normalized(source, {"origin": origin}, polygon.buffer(1))
        self.assertEqual([f["id"] for f in features], ["relation/456"])

    def test_high_ground_basin_is_shallow_without_deadly_refs(self):
        poly = Polygon([(0, 0), (20, 0), (20, 20), (0, 20)])
        city = {
            "bounds": mapping(poly.buffer(10)),
            "road_surface": mapping(Polygon()),
            "shallow_water": [
                {"id": "test", "geometry": mapping(poly), "depth_m": 0.2}
            ],
        }
        records = ponds.prepare(city, None, lambda x, n: 24)
        self.assertAlmostEqual(records[0]["water_level_m"], 23.96)
        self.assertAlmostEqual(records[0]["floor_level_m"], 23.76)
        writer = sthlm.PsdlWriter()
        ponds.write_mesh(writer, records, lambda x, n: 24)
        self.assertFalse(writer.water_rooms)
        self.assertAlmostEqual(min(p[1] for p in writer.vertices), 23.76)
        self.assertAlmostEqual(max(p[1] for p in writer.vertices), 24)
        self.assertGreater(ponds.partition_geometry(records).area, poly.area)

    def test_narrow_fountain_still_has_a_submerged_floor(self):
        poly = Polygon([(0, 0), (2, 0), (2, 5), (0, 5)])
        city = {
            "bounds": mapping(poly.buffer(10)),
            "road_surface": mapping(Polygon()),
            "shallow_water": [
                {"id": "narrow", "geometry": mapping(poly), "depth_m": 0.2}
            ],
        }
        records = ponds.prepare(city, None, lambda x, n: 24)
        writer = sthlm.PsdlWriter()
        ponds.write_mesh(writer, records, lambda x, n: 24)
        self.assertAlmostEqual(min(p[1] for p in writer.vertices), 23.76)
        self.assertFalse(writer.water_rooms)

    def test_neighboring_ponds_have_one_partitioned_collision_surface(self):
        polygons = [
            Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]),
            Polygon([(11, 0), (21, 0), (21, 10), (11, 10)]),
        ]
        city = {
            "bounds": mapping(polygons[0].union(polygons[1]).buffer(10)),
            "road_surface": mapping(Polygon()),
            "shallow_water": [
                {"id": str(i), "geometry": mapping(poly), "depth_m": 0.2}
                for i, poly in enumerate(polygons)
            ],
        }
        records = ponds.prepare(city, None, lambda x, n: 24 + x * 0.02)
        for record in records:
            for poly in polygons:
                self.assertAlmostEqual(
                    shape(record["bank_geometry"]).intersection(poly).area, 0
                )
        writer = sthlm.PsdlWriter()
        ponds.write_mesh(writer, records, lambda x, n: 24 + x * 0.02)
        emitted_area = 0
        for _, attrs, _ in writer.rooms:
            for index in range(2, len(attrs), 4):
                a, b, c = [writer.vertices[ref] for ref in attrs[index + 1 : index + 4]]
                emitted_area += (
                    abs((b[0] - a[0]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[0] - a[0]))
                    / 2
                )
        self.assertAlmostEqual(
            emitted_area, ponds.partition_geometry(records).area, places=3
        )
        self.assertFalse(writer.water_rooms)

    def test_other_road_layers_do_not_cut_surface_fountain(self):
        poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        city = {
            "bounds": mapping(poly.buffer(10)),
            "road_surface": mapping(poly),
            "ground_road_surface": mapping(Polygon()),
            "shallow_water": [
                {"id": "above-tunnel", "geometry": mapping(poly), "depth_m": 0.2}
            ],
        }
        records = ponds.prepare(city, None, lambda x, n: 24)
        self.assertEqual(len(records), 1)
        self.assertAlmostEqual(shape(records[0]["geometry"]).area, poly.area)
        city["shallow_water"] = [
            {"id": "ground-road", "geometry": mapping(poly), "depth_m": 0.2}
        ]
        city["ground_road_surface"] = mapping(poly)
        self.assertEqual(ponds.prepare(city, None, lambda x, n: 24), [])

    def test_water_art_appends_existing_native_decals(self):
        import struct

        poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        city = {
            "shallow_water": [
                {"id": "test", "geometry": mapping(poly), "water_level_m": 20}
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "texture").mkdir()
            (out / "city/stockholm").mkdir(parents=True)
            (out / "city/materials.csv").write_text("tex,phys\nroad,asphalt\n")
            (out / "city/materials.mtl").write_text("mtl asphalt {\n friction: 1\n}\n")
            path = out / "city/stockholm/decals.pathset"
            sentinel = b"old-decals-preserved"
            path.write_bytes(b"PTH1" + struct.pack("<II", 1, 0) + sentinel)
            ponds.write(out, city)
            data = path.read_bytes()
            self.assertEqual(struct.unpack_from("<I", data, 4)[0], 3)
            self.assertEqual(data[12 : 12 + len(sentinel)], sentinel)
            self.assertIn("road,asphalt", (out / "city/materials.csv").read_text())
            self.assertIn("drag: 0.119", (out / "city/materials.mtl").read_text())
            self.assertFalse(
                json.loads((out / "shallow-water.json").read_text())[
                    "deadly_water_refs"
                ]
            )


if __name__ == "__main__":
    unittest.main()

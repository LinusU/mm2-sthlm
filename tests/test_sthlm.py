import gzip
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from shapely.geometry import LineString, Polygon, box, shape
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import sthlm


class GeometryTests(unittest.TestCase):
    def test_coordinate_orientation_and_scale(self):
        origin = [18.045, 59.328]
        self.assertEqual(sthlm.project(*origin, origin), (0, 0))
        east = sthlm.project(18.046, 59.328, origin)
        north = sthlm.project(18.045, 59.329, origin)
        self.assertAlmostEqual(east[0], 56.7866, places=3)
        self.assertAlmostEqual(north[1], 111.3195, places=3)
        writer = sthlm.PsdlWriter()
        index = writer.vertex((east[0], 2, north[1]))
        self.assertLess(writer.vertices[index][2], 0)

    def test_polygon_hole_triangulation(self):
        p = Polygon(
            [(0, 0), (10, 0), (10, 10), (0, 10)], [[(2, 2), (8, 2), (8, 8), (2, 8)]]
        )
        tris = list(sthlm.triangulate(p))
        self.assertAlmostEqual(sum(Polygon(t).area for t in tris), 64)
        for t in tris:
            self.assertTrue(p.covers(Polygon(t)))
            a, b, c = t
            self.assertGreater(
                (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]), 0
            )

    def test_height_rules_deterministic(self):
        self.assertEqual(
            sthlm.estimated_height({"height": "22 m"}, "way/1"), (22, "height")
        )
        self.assertEqual(
            sthlm.estimated_height({"building:levels": "5"}, "way/1"),
            (16, "building:levels"),
        )
        self.assertEqual(
            sthlm.estimated_height({}, "way/1"), sthlm.estimated_height({}, "way/1")
        )
        self.assertEqual(
            sthlm.estimated_height({"height": "NaN"}, "way/1")[1], "estimated"
        )

    def test_malformed_missing_nodes(self):
        with self.assertRaisesRegex(ValueError, "incomplete referenced"):
            sthlm.normalize(
                {
                    "elements": [
                        {
                            "type": "way",
                            "id": 1,
                            "nodes": [1, 2],
                            "tags": {"building": "yes"},
                        }
                    ]
                },
                json.loads((sthlm.ROOT / "config/slice.json").read_text()),
            )

    def test_grade_separated_crossing_is_disconnected(self):
        graph = {1: {2: 10}, 2: {1: 10}, 3: {4: 10}, 4: {3: 10}}
        with self.assertRaisesRegex(ValueError, "disconnected"):
            sthlm.shortest(graph, 1, 4)

    def test_shared_node_connects_junction(self):
        graph = {1: {2: 10}, 2: {1: 10, 3: 10, 4: 10}, 3: {2: 10}, 4: {2: 10}}
        self.assertEqual(sthlm.shortest(graph, 1, 4), [1, 2, 4])

    def test_joined_surface_has_no_overlapping_collision_layers(self):
        roads = unary_union(
            [
                LineString([(-10, 0), (10, 0)]).buffer(3),
                LineString([(0, -10), (0, 10)]).buffer(3),
            ]
        )
        tris = [Polygon(t) for t in sthlm.triangulate(roads)]
        self.assertAlmostEqual(sum(t.area for t in tris), roads.area)
        self.assertTrue(roads.covers(box(-1, -1, 1, 1)))

    def test_writer_shared_seam_vertices_and_binary(self):
        writer = sthlm.PsdlWriter()
        writer.surface(box(0, 0, 200, 10), 2, "road", road=True)
        self.assertEqual(len(writer.vertices), len(set(writer.vertices)))
        self.assertTrue(any(v[0] == 100 for v in writer.vertices))
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "test.psdl"
            writer.write(p, [0, 2, 0])
            data = p.read_bytes()
            self.assertEqual(data[:4], b"PSD0")
            self.assertEqual(struct.unpack_from("<I", data, 8)[0], len(writer.vertices))

    def test_real_snapshot_route_clearance(self):
        with gzip.open(sthlm.ROOT / "sources/osm.json.gz", "rt") as f:
            source = json.load(f)
        cfg = json.loads((sthlm.ROOT / "config/slice.json").read_text())
        city = sthlm.normalize(source, cfg)
        road = shape(city["road_surface"])
        route = LineString(city["route"])
        self.assertGreater(len(city["buildings"]), 30)
        self.assertGreater(city["route_length"], 1000)
        self.assertTrue(road.covers(route.buffer(1.5)))
        landmark = next(b for b in city["buildings"] if b["id"] == "relation/29368")
        self.assertEqual(len(shape(landmark["geometry"]).interiors), 1)
        for building in city["buildings"]:
            self.assertFalse(
                shape(building["geometry"]).intersects(route.buffer(1.5)),
                building["id"],
            )
        self.assertGreater(shape(city["water"]).area, 100000)
        self.assertTrue(
            any(
                o.get("reason") == "grade-separated road excluded"
                for o in city["omitted"]
            )
        )

    def test_package_rejects_corruption_and_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p / "checksums.json").write_text('{"../escape":"abc"}')
            with self.assertRaisesRegex(ValueError, "escaping"):
                sthlm.validate(p)
            (p / "asset").write_text("x")
            (p / "checksums.json").write_text('{"asset":"abc"}')
            with self.assertRaisesRegex(ValueError, "corrupt"):
                sthlm.validate(p)


class EvidenceTests(unittest.TestCase):
    def test_incomplete_or_teleported_drive_is_rejected(self):
        good = "smoke=headless-physics world=city/stockholm.psdl status=pass travel=1500m sim=188s resets=0 finite=true race=Complete outcome=finished controls=800t/100b/300s"
        sthlm.validate_drive_record(good)
        for record in [
            good.replace("resets=0", "resets=1"),
            good.replace("race=Complete", "race=Running"),
            good.replace("sim=188s", "sim=20s"),
            good.replace("travel=1500m", "travel=20m"),
            good + " p_rec=1r/0e",
        ]:
            with self.assertRaisesRegex(ValueError, "acceptance failed"):
                sthlm.validate_drive_record(record)

    def test_psdl_validator_rejects_missing_texture(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            writer = sthlm.PsdlWriter()
            writer.surface(box(0, 0, 10, 10), 2, "missing", road=True)
            p = package / "map.psdl"
            writer.write(p, [0, 2, 0])
            with self.assertRaisesRegex(ValueError, "missing PSDL texture"):
                sthlm.inspect_psdl(p, package)


if __name__ == "__main__":
    unittest.main()

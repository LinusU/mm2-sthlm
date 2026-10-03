import copy
import sys
import struct
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from shapely.geometry import Point, box, mapping, shape
from elevation import RoadField
from street_details import apply, urinal_mesh, wrap_field, write


class Terrain:
    def height(self, x, n):
        return 20.0


class StreetDetailTests(unittest.TestCase):
    def city(self):
        return {
            "roads": [
                {
                    "id": 99763084,
                    "nodes": [1153261603, 1153261605],
                    "points": [[0, 0], [46.7, 3]],
                    "width": 9,
                    "tags": {},
                    "elevated_points": [[0, 0, 20], [46.7, 3, 24]],
                },
                {
                    "id": 123,
                    "nodes": [42, 1153261603],
                    "points": [[-20, 0], [0, 0]],
                    "width": 9,
                    "tags": {},
                    "elevated_points": [[-20, 0, 20], [0, 0, 20]],
                },
            ],
            "bridge_ways": [],
            "buildings": [
                {
                    "id": "way/390454703",
                    "height": 14,
                    "tags": {"building": "yes"},
                    "geometry": mapping(box(-8, 4, -2, 8)),
                },
                {
                    "id": "way/127586369",
                    "height": 10,
                    "tags": {"building": "yes", "amenity": "toilets"},
                    "geometry": mapping(box(30, 12, 34, 16)),
                },
                {
                    "id": "way/999",
                    "height": 18,
                    "tags": {"building": "yes", "amenity": "toilets"},
                    "geometry": mapping(box(40, 12, 44, 16)),
                },
            ],
        }

    def test_only_source_urinal_becomes_prop(self):
        city = self.city()
        original = copy.deepcopy(city["buildings"][1])
        apply(city)
        self.assertEqual(
            [b["id"] for b in city["buildings"]], ["way/390454703", "way/999"]
        )
        self.assertEqual(city["buildings"][0]["height"], 3)
        detail = next(d for d in city["street_details"] if d["kind"] == "urinal")
        self.assertEqual(detail["geometry"], original["geometry"])
        self.assertEqual(detail["tags"], original["tags"])

    def test_ramp_preserves_graph_entrance_height_cuts_ground(self):
        city = self.city()
        topology = copy.deepcopy([(r["nodes"], r["points"]) for r in city["roads"]])
        apply(city)
        field = wrap_field(RoadField(city["roads"], Terrain()), city)
        ramp = city["roads"][0]
        self.assertEqual([(r["nodes"], r["points"]) for r in city["roads"]], topology)
        self.assertEqual(
            ramp["elevated_points"][0][2], city["roads"][1]["elevated_points"][-1][2]
        )
        self.assertEqual(ramp["elevated_points"][-1][2], 16)
        self.assertAlmostEqual(field(23.35, 1.5), 18)
        self.assertAlmostEqual(field.ground(23.35, 1.5), 18)
        self.assertEqual(field.ground(23.35, 30), 20)
        self.assertTrue(
            all(
                a[2] > b[2]
                for a, b in zip(ramp["elevated_points"], ramp["elevated_points"][1:])
            )
        )

    def test_prepared_base_field_and_junction_state_survive(self):
        city = apply(self.city())
        prepared = RoadField(city["roads"], Terrain())
        prepared.shared_junctions = object()
        prepared.bridge_approaches = object()
        segments = prepared.segments
        field = wrap_field(prepared, city)
        self.assertIs(field.base, prepared)
        self.assertIs(field.shared_junctions, prepared.shared_junctions)
        self.assertIs(field.bridge_approaches, prepared.bridge_approaches)
        self.assertIs(field.segments, segments)
        self.assertAlmostEqual(field(23.35, 1.5), 18)
        self.assertAlmostEqual(field.ground(23.35, 1.5), 18)
        self.assertEqual(field(-10, 0), prepared(-10, 0))

    def test_unrelated_round_caps_preserve_bounds_clip(self):
        city = self.city()
        city["bounds"] = mapping(box(-22, -20, 44, 20))
        apply(city)
        surface = shape(city["road_surface"])
        self.assertTrue(shape(city["bounds"]).covers(surface))
        # This lies behind an unrelated road endpoint, inside its round cap.
        self.assertTrue(surface.covers(Point(-21, 0)))
        self.assertFalse(surface.covers(Point(-24, 0)))
        self.assertFalse(surface.covers(Point(46, 3)))

    def test_wrong_source_topology_fails_closed(self):
        city = self.city()
        city["roads"][0]["nodes"].append(777)
        with self.assertRaises(ValueError):
            apply(city)

    def test_native_panel_roof_faces_have_opposite_winding(self):
        data = urinal_mesh()
        offset = 4
        parts = {}
        while offset < len(data):
            self.assertEqual(data[offset : offset + 4], b"FILE")
            size = data[offset + 4]
            name = data[offset + 5 : offset + 5 + size - 1].decode()
            length = struct.unpack_from("<I", data, offset + 5 + size)[0]
            begin = offset + 9 + size
            parts[name] = data[begin : begin + length]
            offset = begin + length
        for name in ("BODY_H", "FRAME_H"):
            part = parts[name]
            count = struct.unpack_from("<I", part, 4)[0]
            vertices = [
                struct.unpack_from("<3f", part, 36 + i * 20) for i in range(count)
            ]
            triangles = [tuple(vertices[i : i + 3]) for i in range(0, count, 3)]
            self.assertTrue(triangles)
            faces = set(triangles)
            for a, b, c in triangles:
                self.assertIn((c, b, a), faces)
            if name == "BODY_H":
                # Seven panels, two triangles each, both sides; one entrance open.
                self.assertEqual(len(triangles), 28)
            else:
                # Roof slopes include both upward and downward native normals.
                normals = [
                    (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2])
                    for a, b, c in triangles
                    if min(a[1], b[1], c[1]) > 1
                ]
                self.assertTrue(any(n > 0 for n in normals))
                self.assertTrue(any(n < 0 for n in normals))

    def test_native_booth_stays_intact_uses_ground_origin(self):
        city = apply(self.city())
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            instances = write(out, city, lambda x, n: 20)
            self.assertEqual(instances[0]["position"], [32, 20, -14])
            self.assertEqual(instances[0]["source"], "way/127586369")
            self.assertTrue(instances[0]["movable"])
            self.assertFalse(instances[0]["breakable"])
            pkg = (out / "geometry/sthlm_kronoberg_urinal.pkg").read_bytes()
            self.assertTrue(pkg.startswith(b"PKG3"))
            self.assertNotIn(b"BREAK01", pkg)
            tuning = (
                out / "tune/banger/sthlm_kronoberg_urinal.dgbangerdata"
            ).read_text()
            self.assertIn("NumParts 0", tuning)
            self.assertIn("ImpulseLimit2 0", tuning)
            self.assertIn("CG 0 1.15 0", tuning)
            self.assertTrue((out / "texture/sthlm_hut_glass.png").is_file())
            self.assertTrue((out / "texture/sthlm_urinal_panel.png").is_file())

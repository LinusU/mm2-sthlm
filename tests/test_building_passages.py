import copy
import json
from pathlib import Path
import sys
import unittest

from shapely.geometry import LineString, Point, shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from building_passages import export, volume_for
from elevation import RoadField
from sthlm import PsdlWriter
from expanded import ChunkedWriter


class BuildingPassageTests(unittest.TestCase):
    def test_noe_arksgranden_bend_opens_lower_storey_preserves_roof(self):
        f = json.loads(
            (Path(__file__).parent / "fixtures/noe-arksgranden-portal.json").read_text()
        )
        building, roads = f["building"], f["roads"]
        roads[0]["width"] = 7.5
        volume = volume_for(building, roads)
        opening = shape(volume["opening_geometry"])
        lower = shape(volume["lower_geometry"])
        line = LineString(roads[0]["points"])
        self.assertGreater(line.intersection(opening).length, 20)
        self.assertTrue(line.intersection(lower).is_empty)
        self.assertEqual(volume["top_y_m"], building["base_y"] + building["height"])
        field = RoadField(roads, None, bridge=True)
        for x, n, _ in roads[0]["elevated_points"]:
            if opening.covers(Point(x, n)):
                self.assertGreaterEqual(
                    volume["underside_y_m"] - field.height_for_road(27351663, x, n),
                    5.5 - 1e-6,
                )
        writer = PsdlWriter()
        export(writer, shape(building["geometry"]), volume)
        self.assertTrue(writer.rooms)

    def fixture(self):
        return json.loads(
            (
                Path(__file__).parent / "fixtures/herkuleskopplet-building-passage.json"
            ).read_text()
        )

    def test_actual_blocking_volume_clears_whole_sloping_ramp(self):
        f = self.fixture()
        original = copy.deepcopy(f)
        b, roads = f["building"], f["roads"]
        result = volume_for(b, roads)
        field = RoadField(roads, None, bridge=True)
        footprint = shape(b["geometry"])
        samples = [
            p for p in roads[0]["elevated_points"] if footprint.covers(Point(p[:2]))
        ]
        self.assertTrue(samples)
        self.assertGreater(max(p[2] for p in samples), b["base_y"] + 5)
        # Baseline estimated body intersects the ramp's driving clearance.
        self.assertLess(b["base_y"] + b["height"] - max(p[2] for p in samples), 2)
        writer = PsdlWriter()
        export(writer, footprint, result)
        wall_bottoms = []
        for _, attrs, _ in writer.rooms:
            # Native kind7 facade collider starts at its referenced base vertex.
            for i in range(len(attrs) - 4):
                if attrs[i] == 0x3C:
                    wall_bottoms.append(writer.vertices[attrs[i + 3]][1])
        self.assertTrue(wall_bottoms)
        for x, n, _ in samples:
            self.assertGreaterEqual(
                min(wall_bottoms) - field.height_for_road(4695823, x, n), 5.49
            )
        self.assertEqual(f, original)
        self.assertAlmostEqual(result["top_y_m"] - result["underside_y_m"], 1.5)
        # The solid underside is visible from the driveable opening below it.
        _, attrs, _ = writer.rooms[-1]
        a, b, c = [writer.vertices[i] for i in attrs[3:6]]
        u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        self.assertLess(u[2] * v[0] - u[0] * v[2], 0)

    def test_unrelated_foundations_are_not_changed(self):
        self.assertIsNone(volume_for({"id": "unrelated"}, []))

    def test_chunked_export_owns_underside_vertices_in_same_pool(self):
        f = self.fixture()
        poly = shape(f["building"]["geometry"])
        volume = volume_for(f["building"], f["roads"])
        writer = ChunkedWriter((0, 0, 0))
        export(writer, poly, volume)
        self.assertEqual(set(writer.parts), {(1, 0)})
        part = writer.parts[(1, 0)]
        direct = PsdlWriter(vertex_limit=None)
        export(direct, poly, volume)
        self.assertEqual(part.vertices, direct.vertices)
        self.assertEqual(part.rooms, direct.rooms)
        self.assertEqual(part.textures, direct.textures)

    def test_stale_authored_road_identity_fails_instead_of_hiding_blocker(self):
        with self.assertRaisesRegex(ValueError, "lacks road"):
            volume_for(self.fixture()["building"], [])

    def test_hornsgatan_cutouts_preserve_office_above_two_tunnel_ramps(self):
        f = json.loads(
            (
                Path(__file__).parent / "fixtures/hornsgatan-building-cutout.json"
            ).read_text()
        )
        original = copy.deepcopy(f)
        building, roads = f["building"], f["roads"]
        poly = shape(building["geometry"])
        volume = volume_for(building, roads)
        lower, opening = (
            shape(volume["lower_geometry"]),
            shape(volume["opening_geometry"]),
        )
        self.assertAlmostEqual(lower.union(opening).area, poly.area)
        self.assertAlmostEqual(lower.intersection(opening).area, 0)
        self.assertGreater(lower.area, poly.area / 2)
        self.assertEqual(volume["top_y_m"], building["base_y"] + building["height"])
        writer = ChunkedWriter((0, 0, 0))
        export(writer, poly, volume)
        part = writer.parts[(1, -2)]
        counts = {10: 1, 2: 4, 5: 3, 6: 3, 11: 6, 7: 4}
        walls = []
        for _, attrs, _ in part.rooms:
            cursor = 0
            while cursor < len(attrs):
                kind = (attrs[cursor] >> 3) & 15
                words = attrs[cursor + 1 : cursor + 1 + counts[kind]]
                if kind == 7:
                    walls.append([part.vertices[v] for v in words[2:4]])
                cursor += counts[kind] + 1
        self.assertTrue(walls)
        crossing_walls = 0
        for road in roads:
            line = LineString(road["points"])
            self.assertGreater(line.intersection(opening).length, 5)
            for a, b in walls:
                wall = LineString([(a[0], -a[2]), (b[0], -b[2])])
                if wall.intersects(line):
                    crossing_walls += 1
                    self.assertGreaterEqual(a[1], volume["underside_y_m"] - 1e-5)
        self.assertGreater(crossing_walls, 0)
        self.assertEqual(f, original)

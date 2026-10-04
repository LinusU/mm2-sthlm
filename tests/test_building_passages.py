import copy
import json
from pathlib import Path
import sys
import unittest

from shapely.geometry import Point, shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from building_passages import export, volume_for
from elevation import RoadField
from sthlm import PsdlWriter
from expanded import ChunkedWriter


class BuildingPassageTests(unittest.TestCase):
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

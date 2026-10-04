"""Actual exported Slottskajen curved fan facets must retain usable normals."""

import json
import math
from pathlib import Path
import unittest
from shapely.geometry import Polygon
from shapely.ops import unary_union
from src.elevation import RoadField
from src.sthlm import improve_triangle_angles


class Terrain:
    def height(self, x, n):
        return 0


class HeightTriangleQualityTests(unittest.TestCase):
    def test_actual_slotts_fan_preserves_samples_coverage_boundary(self):
        fixture = json.loads(
            (
                Path(__file__).parent / "fixtures/slotts-native-skinny-facets.json"
            ).read_text()
        )
        field = RoadField(fixture["roads"], Terrain())
        before = [
            [(v[0], -v[2]) for v in tri] for tri in fixture["native_triangles_xyz"]
        ]
        after = improve_triangle_angles(before)

        def normal_y(tri):
            a, b, c = [(x, field.ground(x, n), n) for x, n in tri]
            u = [b[i] - a[i] for i in range(3)]
            v = [c[i] - a[i] for i in range(3)]
            cross = [
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0],
            ]
            return abs(cross[1]) / math.sqrt(sum(x * x for x in cross))

        def boundary(triangles):
            counts = {}
            for tri in triangles:
                for a, b in zip(tri, tri[1:] + tri[:1]):
                    edge = tuple(sorted((a, b)))
                    counts[edge] = counts.get(edge, 0) + 1
            return {edge for edge, count in counts.items() if count == 1}

        self.assertLess(min(map(normal_y, before)), 0.14)
        self.assertGreater(min(map(normal_y, after)), 0.9)
        self.assertEqual(len(after), len(before))
        self.assertEqual(
            {p for tri in before for p in tri}, {p for tri in after for p in tri}
        )
        self.assertEqual(boundary(before), boundary(after))
        original = unary_union([Polygon(t) for t in before])
        improved = unary_union([Polygon(t) for t in after])
        self.assertLess(original.symmetric_difference(improved).area, 1e-8)
        self.assertEqual(after, improve_triangle_angles(before))

    def test_concave_pair_is_not_flipped(self):
        triangles = [[(0, 0), (4, 0), (1, 1)], [(4, 0), (0, 0), (1, 0.5)]]
        self.assertEqual(triangles, improve_triangle_angles(triangles))

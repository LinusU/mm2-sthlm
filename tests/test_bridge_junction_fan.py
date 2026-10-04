"""Adjacent source junction tangent fits must emit a continuous bridge floor."""

import json
import math
from pathlib import Path
import sys
import unittest

from shapely.geometry import Point, Polygon, box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from elevation import RoadField, bridge_approaches  # noqa: E402
from road_surfaces import render_bridge_layers  # noqa: E402
from sthlm import PsdlWriter  # noqa: E402


class Terrain:
    def height(self, x, north):
        return 0.0


class BridgeJunctionFanTests(unittest.TestCase):
    def fixture(self):
        return json.loads(
            (Path(__file__).parent / "fixtures/bridge-junction-fan.json").read_text()
        )

    def test_overlapping_junction_fits_do_not_switch_height_at_nearest_boundary(self):
        roads = self.fixture()["roads"]
        elevated = [r for r in roads if r["tags"].get("bridge") == "yes"]
        ordinary = [r for r in roads if r not in elevated]
        _, pieces, seams, _ = bridge_approaches(ordinary, elevated)
        field = RoadField(pieces, Terrain(), bridge=True, junctions=seams)
        a = field.blended(68.292725, 720.654053)
        b = field.blended(68.331055, 720.77832)
        # Exact emitted native counterexample: 13.57669 -> 13.91901 over
        # 0.130 m, although the unchanged owning profile rises only 0.013 m.
        self.assertLess(abs(a - b), 0.04)
        for road in elevated:
            for x, n, y in road["elevated_points"]:
                self.assertAlmostEqual(field.height_for_road(road, x, n), y)

    def test_exact_source_bridge_fan_has_no_interior_near_vertical_triangles(self):
        roads = self.fixture()["roads"]
        city = {
            "roads": roads,
            "bridge_ways": [r["id"] for r in roads if r["tags"].get("bridge") == "yes"],
            "bounds": mapping(box(-100, 600, 180, 800)),
        }
        triangles = []
        render_bridge_layers(PsdlWriter(), city, Terrain(), triangle_sink=triangles)
        body = Point(68.80453, -719.6723)
        normals = []
        for a, b, c in triangles:
            if Polygon([(x, z) for x, y, z in (a, b, c)]).distance(body) > 2:
                continue
            u = [b[i] - a[i] for i in range(3)]
            v = [c[i] - a[i] for i in range(3)]
            normal = [
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0],
            ]
            length = math.sqrt(sum(component * component for component in normal))
            if length > 1e-12:
                normals.append(abs(normal[1]) / length)
        self.assertGreater(len(normals), 0)
        # Old original emitted fans had normal Y 0.13795 within the actual
        # car footprint, becoming upright collision faces in the native slab.
        # The retained natural source ramp should stay below a 26 degree grade.
        self.assertGreater(min(normals), 0.9)


if __name__ == "__main__":
    unittest.main()

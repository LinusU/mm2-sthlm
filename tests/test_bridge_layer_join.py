"""Native bridge-layer continuity without network, engine content or a GPU."""

import json
import math
from pathlib import Path
import sys
import unittest

from shapely.geometry import Point, Polygon, box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from elevation import RoadField  # noqa: E402
from road_surfaces import render_bridge_layers  # noqa: E402
from sthlm import PsdlWriter  # noqa: E402


class Terrain:
    def height(self, x, north):
        return 0.0


def floor_heights(triangles, x, z):
    heights = []
    for a, b, c in triangles:
        if not Polygon([(p[0], p[2]) for p in (a, b, c)]).covers(Point(x, z)):
            continue
        ux, uy, uz = (b[i] - a[i] for i in range(3))
        vx, vy, vz = (c[i] - a[i] for i in range(3))
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        if abs(ny) > 1e-9:
            heights.append(a[1] - (nx * (x - a[0]) + nz * (z - a[2])) / ny)
    return heights


def bridge(index, nodes, points, height, layer):
    return {
        "id": index,
        "nodes": nodes,
        "points": points,
        "elevated_points": [[x, n, height] for x, n in points],
        "width": 9.0,
        "tags": {"highway": "secondary", "bridge": "yes", "layer": str(layer)},
    }


class BridgeLayerJoinTests(unittest.TestCase):
    def test_source_layer_change_has_no_raised_native_round_cap(self):
        fixture = json.loads(
            (Path(__file__).parent / "fixtures/bridge-layer-join.json").read_text()
        )
        city = {
            "roads": fixture["roads"],
            "bridge_ways": fixture["bridge_ways"],
            "bounds": mapping(box(40, 680, 200, 950)),
        }
        triangles = []
        report = render_bridge_layers(
            PsdlWriter(), city, Terrain(), triangle_sink=triangles
        )
        queries = [
            (fixture["counterexample"]["query"], 16.930921),
            (fixture["counterexample"]["forward_query"], 17.444),
        ]
        for query, expected in queries:
            with self.subTest(position=query["position_xz"]):
                heights = floor_heights(triangles, *query["position_xz"])
                self.assertGreaterEqual(len(heights), 2)
                self.assertLess(max(heights) - min(heights), 0.04)
                self.assertLess(abs(max(heights) - expected), 0.04)
                self.assertTrue(all(math.isfinite(y) for y in heights))
        # Both layer groups still cover the round-cap overlap, but their
        # complete shared-source tangent fit must agree. The old native
        # triangles had floors 16.930921 and 17.341379 at this exact point.
        self.assertEqual(report["layer_count"], 2)

    def test_unconnected_stacked_bridge_crossing_stays_separated(self):
        city = {
            "roads": [
                bridge(1, [1, 2], [[0, 0], [100, 0]], 3, 1),
                bridge(2, [3, 4], [[50, -50], [50, 50]], 13, 2),
            ],
            "bridge_ways": [1, 2],
            "bounds": mapping(box(-10, -60, 110, 60)),
        }
        triangles = []
        report = render_bridge_layers(
            PsdlWriter(), city, Terrain(), triangle_sink=triangles
        )
        heights = floor_heights(triangles, 50, 0)
        self.assertEqual(report["layer_count"], 2)
        self.assertAlmostEqual(min(heights), 3)
        self.assertAlmostEqual(max(heights), 13)

    def test_shared_source_plane_wins_equal_distance_partial_local_fit(self):
        roads = [
            bridge(1, [1, 2], [[0, 0], [20, 0]], 10, 1),
            bridge(2, [1, 3], [[0, 0], [0, 20]], 10, 1),
        ]
        field = RoadField(
            roads,
            Terrain(),
            bridge=True,
            shared_planes=[(0, 0, 10, 0.1, 0, 5.5, {1, 2, 3})],
        )
        # Complete cross-layer fit includes an owner absent from this group;
        # an equally near plane made only from its flat local arms cannot win.
        self.assertAlmostEqual(field(2, 1), 10.2)


if __name__ == "__main__":
    unittest.main()

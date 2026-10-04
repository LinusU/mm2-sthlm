"""Parallel bridge datum lifts preserve exact source-connected approach joins."""

import copy
import json
import math
from pathlib import Path
import sys
import unittest

from shapely.geometry import Point, Polygon, box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from elevation import (  # noqa: E402
    align_parallel_bridge_profiles,
    _reconcile_bridge_profile_junctions,
)
from road_surfaces import render_bridge_layers  # noqa: E402
from sthlm import PsdlWriter  # noqa: E402


class Terrain:
    def height(self, x, north):
        return 0.0


class BridgeAlignmentJunctionTests(unittest.TestCase):
    def fixture(self):
        return json.loads(
            (
                Path(__file__).parent
                / "fixtures/bridge-alignment-source-junctions.json"
            ).read_text()
        )

    def node_heights(self, roads):
        heights = {}
        for road in roads:
            profiles = {tuple(p[:2]): p[2] for p in road["elevated_points"]}
            for node, point in zip(road["nodes"], road["points"]):
                heights.setdefault(node, []).append(profiles[tuple(point)])
        return heights

    def test_already_coherent_shared_datum_is_not_raised_again(self):
        roads = [
            {
                "id": owner,
                "nodes": [1, 2, 3],
                "points": [[0, 0], [50, 0], [100, 0]],
                "elevated_points": [
                    [x, 0, y]
                    for x, y in zip(
                        [0, 25, 45, 50, 55, 75, 100],
                        [5, 5.2, 5.8, 6, 5.8, 5.2, 5],
                    )
                ],
            }
            for owner in (1, 2)
        ]
        original = {r["id"]: [[*p[:2], 5] for p in r["elevated_points"]] for r in roads}
        before = copy.deepcopy(roads)
        self.assertEqual(
            _reconcile_bridge_profile_junctions(roads, original, {1, 3}), []
        )
        self.assertEqual(roads, before)

    def test_global_shared_nodes_and_fixed_ordinary_anchors_are_preserved(self):
        fixture = self.fixture()
        roads, anchors = fixture["roads"], fixture["anchor_nodes"]
        before = copy.deepcopy(roads)
        old_heights = self.node_heights(before)
        reports = align_parallel_bridge_profiles(roads, anchor_nodes=anchors)
        self.assertGreater(len(reports), 0)
        heights = self.node_heights(roads)
        for node, values in heights.items():
            with self.subTest(node=node):
                self.assertLess(max(values) - min(values), 1e-8)
                if node in anchors:
                    self.assertEqual(values, old_heights[node])
        for road, old in zip(roads, before):
            self.assertEqual(road["nodes"], old["nodes"])
            self.assertEqual(road["points"], old["points"])
            for point, previous in zip(road["elevated_points"], old["elevated_points"]):
                self.assertEqual(point[:2], previous[:2])
                self.assertGreaterEqual(point[2], previous[2])
        for node in fixture["expected_shared_nodes"]:
            self.assertGreater(max(heights[node]), max(old_heights[node]) + 0.001)

    def test_exact_stromsborg_connector_lift_is_smooth_not_one_raised_vertex(self):
        fixture = self.fixture()
        before = copy.deepcopy(fixture["roads"])
        align_parallel_bridge_profiles(
            fixture["roads"], anchor_nodes=fixture["anchor_nodes"]
        )
        old = next(r for r in before if r["id"] == 386722952)
        road = next(r for r in fixture["roads"] if r["id"] == 386722952)
        lifts = [
            p[2] - q[2] for p, q in zip(road["elevated_points"], old["elevated_points"])
        ]
        self.assertGreater(min(lifts), 0.7)
        for a, b, lift_a, lift_b in zip(
            road["elevated_points"], road["elevated_points"][1:], lifts, lifts[1:]
        ):
            self.assertLess(abs(lift_b - lift_a) / math.dist(a[:2], b[:2]), 0.07)
        reports = align_parallel_bridge_profiles(
            copy.deepcopy(before), anchor_nodes=fixture["anchor_nodes"]
        )
        lifts_report = reports[0]["source_junction_lifts"]
        self.assertTrue(any(r["source_node"] == 180946 for r in lifts_report))
        self.assertTrue(all(r["blend_radius_m"] >= 20 for r in lifts_report))

    def test_exact_vasa_source_connector_emits_continuous_native_facets(self):
        fixture = self.fixture()
        roads = fixture["roads"]
        align_parallel_bridge_profiles(roads, anchor_nodes=fixture["anchor_nodes"])
        selected = [r for r in roads if r["id"] in {28345891, 162142154, 386722952}]
        city = {
            "roads": selected,
            "bridge_ways": [r["id"] for r in selected],
            "bounds": mapping(box(1087, -88, 1107, -67)),
        }
        triangles = []
        render_bridge_layers(PsdlWriter(), city, Terrain(), triangle_sink=triangles)
        query = Point(1097.3555011543822, 77.38930999978118)
        normals = []
        for a, b, c in triangles:
            if Polygon([(p[0], p[2]) for p in (a, b, c)]).distance(query) > 2:
                continue
            u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
            n = [
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0],
            ]
            length = math.sqrt(sum(value * value for value in n))
            if length > 1e-12:
                normals.append(abs(n[1]) / length)
        self.assertGreater(len(normals), 0)
        self.assertGreater(min(normals), 0.9)


if __name__ == "__main__":
    unittest.main()

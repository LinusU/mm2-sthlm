import sys
import math
import unittest
from pathlib import Path

from shapely.geometry import LineString, Point, box, mapping, shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from elevation import RoadField, apply, conforming_boundary
from sthlm import PsdlWriter
from props import placements, tree_mesh
from expanded import ChunkedWriter


class Plane:
    metadata = {"datum": "test plane"}

    def height(self, x, n):
        return 2 + x * 0.01 + n * 0.02


class ElevationTests(unittest.TestCase):
    def road(self, id, nodes, points, bridge=False):
        return {
            "id": id,
            "nodes": nodes,
            "points": points,
            "width": 9,
            "tags": {"name": "Stadshusbron" if bridge else "road"},
        }

    def test_approach_seam_belongs_only_to_its_source_road(self):
        upper = self.road(1, [1, 2], [(0, 0), (100, 0)], True)
        lower = self.road(2, [3, 4], [(0, 2), (100, 2)], True)
        upper["elevated_points"] = [[0, 0, 18], [100, 0, 23]]
        lower["elevated_points"] = [[0, 2, 8], [100, 2, 8]]
        # Nearby upper approach patch must neither lift nor flatten the lower road.
        field = RoadField(
            [upper, lower],
            Plane(),
            bridge=True,
            junctions=[(50, 0, 20.5, 8, 1, 0.05, 0)],
        )
        self.assertAlmostEqual(field(50, 2), 8)
        self.assertAlmostEqual(field(53, 0), 20.65)

    def test_shared_road_junction_uses_one_height(self):
        roads = [
            self.road(1, [1, 2], [(0, 0), (100, 0)]),
            self.road(2, [2, 3], [(100, 0), (100, 100)]),
        ]
        city = {
            "roads": roads,
            "bridge_ways": [],
            "spawn": [0, 0, 0],
            "route": [(0, 0)],
            "buildings": [],
            "bounds": mapping(box(-20, -20, 120, 120)),
        }
        field, _, _, _ = apply(city, Plane())
        self.assertEqual(
            roads[0]["elevated_points"][-1], roads[1]["elevated_points"][0]
        )
        self.assertLess(abs(field(100, 0) - 3), 0.25)
        self.assertAlmostEqual(field.ground(100, 3), field(100, 3))
        self.assertEqual(city["spawn"][1], 3.5)

    def test_bridge_deck_matches_ends_without_flattening_underpass(self):
        roads = [
            self.road(1, [1, 2], [(0, 0), (100, 0)]),
            self.road(2, [2, 3, 4], [(100, 0), (200, 0), (300, 0)], True),
            self.road(3, [4, 5], [(300, 0), (400, 0)]),
            self.road(4, [6, 7], [(200, -100), (200, 100)]),
        ]
        city = {
            "roads": roads,
            "bridge_ways": [2],
            "spawn": [0, 0, 0],
            "route": [(0, 0)],
            "buildings": [],
            "bounds": mapping(box(-20, -120, 420, 120)),
        }
        ground, deck, _, _ = apply(city, Plane())
        self.assertAlmostEqual(deck(80, 0), ground(80, 0))
        self.assertAlmostEqual(deck(320, 0), ground(320, 0))
        self.assertGreater(deck(200, 0), ground(200, 0) + 5)
        self.assertIn("estimated", city["bridge_profiles"][0]["height_rule"])

    def test_bridge_approach_partition_has_shared_height_plane(self):
        roads = [
            self.road(1, [1, 2], [(0, 0), (100, 0)]),
            self.road(2, [2, 3, 4], [(100, 0), (200, 0), (300, 0)], True),
            self.road(3, [4, 5], [(300, 0), (400, 0)]),
        ]
        city = {
            "roads": roads,
            "bridge_ways": [2],
            "spawn": [0, 0, 0],
            "route": [(0, 0)],
            "buildings": [],
            "bounds": mapping(box(-20, -20, 420, 20)),
        }
        ground, deck, base, raised = apply(city, Plane())
        self.assertLess(base.intersection(raised).area, 1e-6)
        seam = base.boundary.intersection(raised.boundary)
        for part in seam.geoms:
            for x, n in part.coords:
                self.assertAlmostEqual(ground.ground(x, n), deck(x, n))
        self.assertEqual(len(city["bridge_approaches"]), 2)
        self.assertEqual(roads[0]["elevated_points"][-1][:2], [100, 0])

    def test_bridge_near_end_keeps_lower_crossing_road(self):
        class Bank:
            metadata = {"datum": "synthetic bridge bank"}

            def height(self, x, n):
                return 13 if x <= 100 and abs(n) < 5 else 4

        roads = [
            self.road(1, [1, 2], [(0, 0), (100, 0)]),
            self.road(2, [2, 3, 4], [(100, 0), (200, 0), (300, 0)], True),
            self.road(3, [4, 5], [(300, 0), (400, 0)]),
            self.road(4, [6, 7], [(108, -100), (108, 100)]),
        ]
        city = {
            "roads": roads,
            "bridge_ways": [2],
            "spawn": [0, 0, 0],
            "route": [(0, 0)],
            "buildings": [],
            "bounds": mapping(box(-20, -120, 420, 120)),
        }
        ground, deck, base, raised = apply(city, Bank())
        self.assertTrue(base.covers(Point(108, 0)))
        self.assertTrue(raised.covers(Point(108, 0)))
        self.assertAlmostEqual(ground.ground(108, 0), 4)
        self.assertGreater(deck(108, 0), ground(108, 0) + 5)

    def test_bridge_end_anchors_uphill_road_instead_of_bank_dtm(self):
        class Bank:
            metadata = {"datum": "synthetic shoreline dip"}

            def height(self, x, n):
                return 17 if abs(n) < 5 and (x <= 85 or x >= 315) else 4

        roads = [
            self.road(1, [1, 2], [(0, 0), (100, 0)]),
            self.road(2, [2, 3, 4], [(100, 0), (200, 0), (300, 0)], True),
            self.road(3, [4, 5], [(300, 0), (400, 0)]),
            self.road(4, [6, 7], [(108, -100), (108, 100)]),
        ]
        city = {
            "roads": roads,
            "bridge_ways": [2],
            "spawn": [0, 0, 0],
            "route": [(0, 0)],
            "buildings": [],
            "bounds": mapping(box(-20, -120, 420, 120)),
        }
        ground, deck, base, _ = apply(city, Bank())
        self.assertEqual(deck(100, 0), 17)
        self.assertEqual(roads[0]["elevated_points"][-1][2], 17)
        self.assertTrue(all(p[2] == 17 for p in roads[0]["elevated_points"]))
        grades = [
            abs(b[2] - a[2]) / math.dist(a[:2], b[:2])
            for a, b in zip(
                roads[0]["elevated_points"], roads[0]["elevated_points"][1:]
            )
        ]
        self.assertLessEqual(max(grades), 0.08)
        self.assertEqual(ground.ground(108, 0), 4)
        self.assertTrue(base.covers(Point(108, 0)))
        self.assertGreater(deck(108, 0), ground(108, 0) + 10)
        self.assertTrue(shape(city["bridge_approach_surface"]).covers(Point(92, 0)))
        self.assertFalse(shape(city["bridge_approach_surface"]).covers(Point(200, 0)))

    def test_height_surface_samples_inside_large_polygons(self):
        writer = PsdlWriter()
        writer.surface(box(0, 0, 100, 100), lambda x, n: x / 10, "grass")
        self.assertTrue(any(v[0] == 50 and v[1] == 5 for v in writer.vertices))
        self.assertTrue(all(abs(v[1] - v[0] / 10) < 1e-5 for v in writer.vertices))

    def boundary_mesh(self, writers, boundary):
        vertices, edges = set(), set()
        for writer in writers:
            for _, attrs, _ in writer.rooms:
                for k in range(2, len(attrs), 4):
                    triangle = [writer.vertices[i] for i in attrs[k + 1 : k + 4]]
                    for a, b in zip(triangle, triangle[1:] + triangle[:1]):
                        if (
                            all(
                                boundary.distance(Point(x, -z)) < 1e-5
                                for x, _, z in [a, b]
                            )
                            and boundary.distance(
                                Point((a[0] + b[0]) / 2, -(a[2] + b[2]) / 2)
                            )
                            < 1e-5
                        ):
                            vertices.update([a, b])
                            edges.add(tuple(sorted([a, b])))
        return vertices, edges

    def test_material_boundaries_keep_identical_mesh_edges(self):
        # A sloping road boundary crosses the mesher's 25m patch cuts.
        # With road=5m / shoulder=25m subdivisions, 36 seam vertices differ.
        road = LineString([(0, 0), (80, 29)]).buffer(4.5)
        shoulder = road.buffer(2).difference(road)

        def height(x, n):
            return 0.03 * x * x + 0.02 * n * n

        meshes = []
        for geom, is_road in [(road, True), (shoulder, False)]:
            writer = PsdlWriter()
            writer.surface(conforming_boundary(geom), height, "road", road=is_road)
            meshes.append(self.boundary_mesh([writer], road.boundary))
        # Compare actual native triangle edges, including their interpolated
        # endpoint heights, rather than just matching the height function.
        self.assertEqual(meshes[0], meshes[1])
        self.assertGreater(len(meshes[0][0]), 100)

    def test_material_boundaries_match_across_chunk_clipping(self):
        road = LineString([(-1030, -60), (-950, 29)]).buffer(4.5)
        shoulder = road.buffer(2).difference(road)
        meshes = []
        for geom, is_road in [(road, True), (shoulder, False)]:
            writer = ChunkedWriter([-990, 0, 0])
            writer.surface(geom, Plane().height, "road", road=is_road)
            meshes.append(self.boundary_mesh(writer.parts.values(), road.boundary))
            self.assertGreater(len(writer.parts), 1)
        self.assertEqual(meshes[0], meshes[1])

    def test_wide_road_matches_ground_at_roadway_edge(self):
        road = {
            "width": 30,
            "elevated_points": [[0, 0, 12], [100, 0, 12]],
        }
        field = RoadField([road], Plane())
        self.assertEqual(field.ground(50, 15), field(50, 15))
        self.assertEqual(field.ground(50, 17), field(50, 17))
        self.assertAlmostEqual(field.ground(50, 24), Plane().height(50, 24))

    def test_trees_are_separate_grounded_breakable_assets(self):
        city = {"trees": [{"id": 4, "position": [30, 30]}], "buildings": []}
        props = placements(
            city, box(0, 0, 100, 100), box(0, 0, 10, 100), Plane().height
        )
        self.assertEqual(len(props), 1)
        self.assertAlmostEqual(props[0]["position"][1], 2.9)
        self.assertTrue(props[0]["breakable"])
        data = tree_mesh()
        self.assertTrue(data.startswith(b"PKG3"))
        self.assertIn(b"BREAK01_H\0", data)
        self.assertIn(b"BREAK02_H\0", data)

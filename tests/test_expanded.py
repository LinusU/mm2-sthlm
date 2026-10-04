import sys
import unittest
from pathlib import Path

from shapely.geometry import Point, Polygon, box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from expanded import ChunkedWriter, internal_bridge_ways, northern_corridor
from sthlm import project


class ExpandedBoundaryTests(unittest.TestCase):
    def test_northern_limit_follows_e20_without_confusing_e18_20(self):
        cfg = {"origin": [18.045, 59.328]}
        nodes = {
            1: {"lon": 18.010, "lat": 59.343},
            2: {"lon": 18.060, "lat": 59.354},
            3: {"lon": 18.108, "lat": 59.352},
        }
        ways = {
            7: {
                "id": 7,
                "nodes": [1, 2, 3],
                "tags": {"ref": "E 20;277", "highway": "motorway", "tunnel": "yes"},
            },
            # A shorter direct path has a different road designation.
            8: {
                "id": 8,
                "nodes": [1, 3],
                "tags": {"ref": "E 18.20", "highway": "primary"},
            },
        }
        envelope = box(
            *project(17.970, 59.286, cfg["origin"]),
            *project(18.174, 59.373, cfg["origin"]),
        )
        limit, metadata = northern_corridor(ways, nodes, cfg, envelope)
        self.assertEqual(metadata["source_way_ids"], [7])
        self.assertEqual(metadata["source_nodes"], [1, 2, 3])
        self.assertTrue(limit.covers(Point(project(18.060, 59.353, cfg["origin"]))))
        self.assertFalse(limit.covers(Point(project(18.060, 59.363, cfg["origin"]))))


class InternalBridgeTests(unittest.TestCase):
    def test_internal_trunk_and_unnamed_viaducts_keep_boundary_exclusions(self):
        cfg = {"origin": [18.045, 59.328]}
        nodes = {
            1: {"lon": 18.045, "lat": 59.328},
            2: {"lon": 18.046, "lat": 59.328},
            3: {"lon": 18.065, "lat": 59.328},
        }

        def way(i, **tags):
            return {
                "id": i,
                "nodes": [1, 2],
                "tags": {"bridge": "yes", "highway": "trunk", **tags},
            }

        ways = {
            1: way(1, name="Centralbron"),
            2: way(2),
            3: way(3, name="Tranebergsbron"),
            4: way(4, highway="footway"),
            5: way(5, tunnel="yes"),
            6: way(6, motor_vehicle="no"),
            7: way(7, name="Skansbron"),
        }
        ways[8] = {**way(8), "nodes": [1, 3]}
        mask = box(-100, -100, 100, 100)
        self.assertEqual(internal_bridge_ways(ways, nodes, cfg, mask), [1, 2])

    def test_missing_bridge_geometry_is_not_invented(self):
        cfg = {"origin": [18.045, 59.328]}
        way = {
            "id": 9,
            "nodes": [1, 2],
            "tags": {"bridge": "yes", "highway": "primary"},
        }
        self.assertEqual(
            internal_bridge_ways({9: way}, {}, cfg, box(-100, -100, 100, 100)), []
        )


class NativeChunkTests(unittest.TestCase):
    def test_dense_city_chunk_boundary_keeps_complete_ground_and_exact_seams(self):
        writer = ChunkedWriter([695, 5, -20])
        geom = box(690, 10, 710, 30)
        writer.surface(geom, lambda x, n: 2 + x * 0.02 + n * 0.01, "road", road=True)
        self.assertEqual(set(writer.parts), {(0, 0), (1, 0)})
        edges = []
        area = 0
        for part in writer.parts.values():
            edges.append({(y, z) for x, y, z in part.vertices if x == 700})
            area += sum(
                Polygon(
                    [(part.vertices[i][0], part.vertices[i][2]) for i in border]
                ).area
                for border, _, _ in part.rooms
            )
        self.assertTrue(edges[0])
        self.assertEqual(edges[0], edges[1])
        self.assertAlmostEqual(area, geom.area)
        self.assertIsNot(writer.part(250, 20), writer.part(750, 20))

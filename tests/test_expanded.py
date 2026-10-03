import sys
import unittest
from pathlib import Path

from shapely.geometry import Point, box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from expanded import northern_corridor
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

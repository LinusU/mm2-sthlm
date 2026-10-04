import copy
import gzip
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from races_checkpoint import anchors, itinerary, load, validate_catalog  # noqa: E402


class CheckpointCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load()
        with gzip.open(ROOT / "sources/expanded/osm.json.gz", "rt") as handle:
            source = json.load(handle)
        cls.ways = {e["id"]: e for e in source["elements"] if e["type"] == "way"}

    def test_exact_source_ownership_for_every_gate(self):
        for event in self.catalog["events"]:
            for anchor in anchors(event):
                with self.subTest(event=event["id"], anchor=anchor["label"]):
                    self.assertIn(
                        anchor["node_id"], self.ways[anchor["way_id"]]["nodes"]
                    )
                    self.assertEqual(
                        anchor["street"], self.ways[anchor["way_id"]]["tags"]["name"]
                    )

    def test_any_order_rows_keep_finish_separate(self):
        for event in self.catalog["events"]:
            route = itinerary(event)
            self.assertEqual(route[0], event["start"])
            self.assertEqual(route[-1], event["finish"])
            self.assertCountEqual(route[1:-1], event["checkpoints"])

    def test_opponent_plans_cover_every_gate(self):
        for event in self.catalog["events"]:
            for order in event["opponent_orders"]:
                self.assertEqual(sorted(order), list(range(len(event["checkpoints"]))))
            self.assertLessEqual(
                max(event["opponent_order_lengths_m"]),
                event["suggested_route_length_m"] * 1.30 + 1,
            )

    def test_through_plans_keep_owned_edges_without_immediate_reversals(self):
        for event in self.catalog["events"]:
            for plan in event["opponent_route_via"]:
                nodes = [a["node_id"] for a in plan]
                self.assertFalse(
                    any(a == c for a, _, c in zip(nodes, nodes[1:], nodes[2:]))
                )
                for first, second in zip(plan, plan[1:]):
                    way = self.ways[first["way_id"]]
                    if way["tags"].get("highway") == "service":
                        self.assertTrue(way["tags"].get("name"))
                    source_nodes = way["nodes"]
                    self.assertTrue(
                        any(
                            {a, b} == {first["node_id"], second["node_id"]}
                            for a, b in zip(source_nodes, source_nodes[1:])
                        )
                    )

    def test_source_turnaround_in_through_plan_is_rejected(self):
        bad = copy.deepcopy(self.catalog)
        plan = bad["events"][0]["opponent_route_via"][0]
        plan.insert(2, copy.deepcopy(plan[0]))
        bad["events"][0]["route_via"] = plan
        with self.assertRaisesRegex(ValueError, "immediate source reversal"):
            validate_catalog(bad)

    def test_marker_radii_cannot_overlap_start_or_other_gates(self):
        for event in self.catalog["events"]:
            points = anchors(event)
            for i, first in enumerate(points):
                for second in points[i + 1 :]:
                    separation = math.dist(
                        first["east_north_m"], second["east_north_m"]
                    )
                    self.assertGreater(
                        separation, first["road_width_m"] + second["road_width_m"]
                    )

    def test_missing_gate_is_rejected(self):
        bad = copy.deepcopy(self.catalog)
        bad["events"][0]["suggested_order"] = [0]
        with self.assertRaisesRegex(ValueError, "every gate"):
            validate_catalog(bad)

    def test_geographic_coincidence_cannot_replace_source_ownership(self):
        roads = [{"id": 1, "nodes": [1, 2], "points": [[0, 0], [1, 0]], "width": 9}]
        with self.assertRaisesRegex(ValueError, "Missing retained anchor ownership"):
            validate_catalog(self.catalog, roads)

    def test_finish_cannot_overlap_start(self):
        bad = copy.deepcopy(self.catalog)
        bad["events"][0]["finish"] = copy.deepcopy(bad["events"][0]["start"])
        with self.assertRaisesRegex(ValueError, "distinct"):
            validate_catalog(bad)


if __name__ == "__main__":
    unittest.main()

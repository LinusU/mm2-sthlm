"""Geographic course checks against the retained offline OSM source."""

import gzip
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BlitzCourseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((ROOT / "config/races/blitz.json").read_text())
        with gzip.open(ROOT / "sources/expanded/osm.json.gz", "rt") as source:
            elements = json.load(source)["elements"]
        cls.ways = {item["id"]: item for item in elements if item["type"] == "way"}

    def test_native_any_order_catalog_has_ten_progressive_courses(self):
        events = self.catalog["events"]
        self.assertEqual(self.catalog["native_rule"], "AnyOrder")
        self.assertEqual([e["index"] for e in events], list(range(10)))
        lengths = [e["suggested_route_length_m"] for e in events]
        self.assertLessEqual(max(lengths), 6100)
        self.assertEqual([e["difficulty_rank"] for e in events], list(range(1, 11)))
        for event in events:
            self.assertEqual(
                event["suggested_order"], list(range(len(event["checkpoints"])))
            )
            self.assertGreater(len(event["checkpoints"]), 0)
            self.assertLess(len(event["checkpoints"]), 12)

    def test_routes_use_real_consecutive_nodes_on_the_claimed_source_way(self):
        for event in self.catalog["events"]:
            route = event["route_via"]
            ids = [p["node_id"] for p in route]
            self.assertEqual(ids[0], event["start"]["node_id"])
            self.assertEqual(ids[-1], event["finish"]["node_id"])
            for gate in [event["start"], *event["checkpoints"], event["finish"]]:
                self.assertIn(gate["node_id"], ids)
                self.assertIn(gate["node_id"], self.ways[gate["way_id"]]["nodes"])
            for a, b in zip(route, route[1:]):
                source = self.ways[a["way_id"]]["nodes"]
                edge = (a["node_id"], b["node_id"])
                edges = set(zip(source, source[1:]))
                self.assertTrue(
                    edge in edges or edge[::-1] in edges, (event["id"], edge)
                )
            for a, b in zip(ids, ids[2:]):
                self.assertNotEqual(a, b, event["id"])

    def test_clocks_allow_acceleration_corners_plus_difficulty_margin(self):
        for event in self.catalog["events"]:
            for mode, margin in (("amateur", 1.24), ("professional", 1.12)):
                params = event[mode]
                baseline = (
                    event["suggested_route_length_m"] / event["target_speed_mps"][mode]
                )
                rank = event["difficulty_rank"] - 1
                margin -= rank * (0.008 if mode == "amateur" else 0.006)
                allowance = (baseline + 8 + 2 * len(event["checkpoints"])) * margin
                self.assertGreaterEqual(params["TimeLimit"], math.floor(allowance))
                self.assertEqual(params["Opponents"], 0)
                self.assertEqual(params["Difficulty"], 1)
            self.assertLess(
                event["professional"]["TimeLimit"], event["amateur"]["TimeLimit"]
            )

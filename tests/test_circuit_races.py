"""Offline source topology checks for the ten authored ordered circuits."""

import gzip
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sthlm import project  # noqa: E402


class CircuitDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "config/races/circuit.json").read_text())
        with gzip.open(ROOT / "sources/expanded/osm.json.gz", "rt") as stream:
            source = json.load(stream)
        cls.nodes = {
            row["id"]: row for row in source["elements"] if row["type"] == "node"
        }
        cls.ways = {
            row["id"]: row for row in source["elements"] if row["type"] == "way"
        }
        cls.edges = {
            frozenset((a, b))
            for row in cls.ways.values()
            if row.get("tags", {}).get("highway")
            for a, b in zip(row["nodes"], row["nodes"][1:])
        }

    def test_inventory_matches_native_ordered_mode(self):
        self.assertEqual(self.config["native_rule"], "Ordered")
        self.assertEqual(len(self.config["events"]), 10)
        self.assertEqual(
            [event["id"] for event in self.config["events"]],
            [f"circuit:{index}" for index in range(10)],
        )

    def test_every_lap_closes_on_real_source_edges_without_reversing(self):
        for event in self.config["events"]:
            with self.subTest(event=event["id"]):
                anchors = event["route_via"]
                ids = [anchor["node_id"] for anchor in anchors]
                self.assertEqual(event["start"], anchors[0])
                self.assertGreater(len(ids), 3)
                for anchor in anchors:
                    way = self.ways[anchor["way_id"]]
                    self.assertIn(anchor["node_id"], way["nodes"])
                    self.assertNotIn(
                        way.get("tags", {}).get("name"),
                        {"Tranebergsbron", "Lidingöbron", "Essingeleden"},
                    )
                for index, node in enumerate(ids):
                    following = ids[(index + 1) % len(ids)]
                    self.assertNotEqual(node, following)
                    self.assertIn(frozenset((node, following)), self.edges)
                    self.assertNotEqual(ids[index - 1], following)

    def test_visible_gates_are_sparse_in_itinerary_order(self):
        for event in self.config["events"]:
            with self.subTest(event=event["id"]):
                route = [a["node_id"] for a in event["route_via"]]
                cursor = 1
                for gate in event["checkpoints"]:
                    cursor = route.index(gate["node_id"], cursor) + 1
                self.assertGreaterEqual(len(event["checkpoints"]), 3)
                self.assertLess(len(event["checkpoints"]), len(route) / 3)

    def test_distance_progression_matches_source_geometry(self):
        lengths = []
        for event in self.config["events"]:
            coords = [
                project(
                    self.nodes[a["node_id"]]["lon"],
                    self.nodes[a["node_id"]]["lat"],
                    [18.045, 59.328],
                )
                for a in event["route_via"]
            ]
            length = sum(
                math.dist(a, b) for a, b in zip(coords, coords[1:] + coords[:1])
            )
            self.assertAlmostEqual(
                length, event["design"]["reference_length_m"], delta=0.01
            )
            lengths.append(length)
        self.assertEqual(lengths, sorted(lengths))
        self.assertLess(lengths[0], 700)
        self.assertGreater(lengths[-1], 30000)
        self.assertLess(lengths[-1], 42195)

    def test_native_params_keep_circuits_free_of_cops_or_traffic(self):
        for event in self.config["events"]:
            for difficulty in ("amateur", "professional"):
                params = event[difficulty]
                self.assertEqual(params["Cops"], 0)
                self.assertEqual(params["Ambient"], 0)
                self.assertEqual(params["Peds"], 0)
                self.assertGreaterEqual(params["NumLaps"], 1)
                self.assertGreater(params["Opponents"], 0)
        self.assertEqual(self.config["events"][-1]["amateur"]["NumLaps"], 1)
        self.assertEqual(self.config["events"][-1]["professional"]["NumLaps"], 1)


if __name__ == "__main__":
    unittest.main()

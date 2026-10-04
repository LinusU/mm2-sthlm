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

        cls.edge_owners = {}
        for way in cls.ways.values():
            if not way.get("tags", {}).get("highway"):
                continue
            for a, b in zip(way["nodes"], way["nodes"][1:]):
                cls.edge_owners.setdefault(frozenset((a, b)), []).append(way)

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
        self.assertLess(lengths[0], lengths[1])
        self.assertLess(lengths[1], 2000)
        self.assertTrue(all(3000 < length < 7000 for length in lengths[2:6]))
        self.assertEqual(lengths[6:], sorted(lengths[6:]))
        self.assertLess(lengths[0], 700)
        self.assertGreater(lengths[-1], 30000)
        self.assertLess(lengths[-1], 42195)

    def test_sofo_loop_obeys_source_directions_without_carriageway_hairpins(self):
        anchors = self.config["events"][2]["route_via"]
        ids = [anchor["node_id"] for anchor in anchors]
        coords = [
            project(self.nodes[node]["lon"], self.nodes[node]["lat"], [18.045, 59.328])
            for node in ids
        ]
        turns = []
        for index, node in enumerate(ids):
            following = ids[(index + 1) % len(ids)]
            owners = self.edge_owners[frozenset((node, following))]
            legal = []
            for way in owners:
                forward = way["nodes"].index(following) > way["nodes"].index(node)
                direction = way.get("tags", {}).get("oneway", "no")
                legal.append(
                    direction not in {"yes", "1", "true", "-1"}
                    or (forward if direction != "-1" else not forward)
                )
            self.assertTrue(any(legal), (node, following))
            previous, current, after = (
                coords[index - 1],
                coords[index],
                coords[(index + 1) % len(ids)],
            )
            u = (current[0] - previous[0], current[1] - previous[1])
            v = (after[0] - current[0], after[1] - current[1])
            turns.append(
                math.degrees(
                    math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])
                )
            )
        self.assertLess(max(map(abs, turns)), 120)
        for index, turn in enumerate(turns):
            distance = 0
            for offset in range(1, len(ids)):
                a, b = (index + offset - 1) % len(ids), (index + offset) % len(ids)
                distance += math.dist(coords[a], coords[b])
                if distance > 25:
                    break
                other = turns[b]
                self.assertFalse(
                    turn * other > 0 and abs(turn + other) > 150,
                    (ids[index], ids[b], distance, turn, other),
                )

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

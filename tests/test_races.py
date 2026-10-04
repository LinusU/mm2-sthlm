import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

from shapely.geometry import Polygon, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from races import gate_heading, gate_radius, resolve_anchor, route, source_graph, write  # noqa: E402


def road(way, nodes, points, heights=None, width=9):
    return {
        "id": way,
        "nodes": nodes,
        "points": points,
        "width": width,
        "tags": {},
        "elevated_points": [
            [*p, h] for p, h in zip(points, heights or [2] * len(points))
        ],
    }


def anchor(node, way=10):
    return {"node_id": node, "way_id": way, "label": f"node-{node}"}


class SourceRaceRoutingTests(unittest.TestCase):
    def test_gate_normal_uses_waypoint_convention_and_owned_tangent(self):
        city = {
            "roads": [
                road(10, [1, 2], [[0, 0], [100, 100]]),
                road(20, [3, 4], [[0, 0], [0, 100]]),
            ]
        }
        graph = source_graph(city)
        self.assertAlmostEqual(gate_heading(graph, anchor(1)), 225)
        self.assertAlmostEqual(gate_heading(graph, anchor(3, 20)), 180)
        angle = math.radians(gate_heading(graph, anchor(1)))
        normal = [-math.sin(angle), math.cos(angle)]
        self.assertGreater(normal[0], 0)
        self.assertLess(normal[1], 0)

    def test_gate_radius_covers_road_and_passing_clearance(self):
        self.assertEqual(gate_radius(9), 8.5)
        self.assertEqual(gate_radius(3.5), 6)
        self.assertEqual(gate_radius(40), 15)

    def test_xy_crossing_cannot_join_unrelated_source_roads(self):
        city = {
            "roads": [
                road(10, [1, 2], [[-10, 0], [10, 0]]),
                road(20, [3, 4], [[0, -10], [0, 10]]),
            ]
        }
        with self.assertRaisesRegex(ValueError, "Disconnected"):
            route(city, [anchor(1), anchor(4, 20)])

    def test_boundary_hole_removes_entire_crossing_edge(self):
        bounds = Polygon(
            [[-20, -20], [20, -20], [20, 20], [-20, 20]],
            holes=[[[-2, -2], [2, -2], [2, 2], [-2, 2]]],
        )
        city = {
            "bounds": mapping(bounds),
            "roads": [road(10, [1, 2], [[-10, 0], [10, 0]])],
        }
        graph = source_graph(city)
        self.assertNotIn(1, graph.adjacency)
        with self.assertRaisesRegex(ValueError, "boundary-safe"):
            resolve_anchor(city, anchor(1), graph)

    def test_upper_lower_crossing_resolves_exact_owner_height(self):
        city = {
            "roads": [
                road(10, [1, 2, 3], [[-10, 0], [0, 0], [10, 0]], [14, 14, 14]),
                road(20, [4, 5, 6], [[0, -10], [0, 0], [0, 10]], [2, 2, 2]),
            ]
        }
        graph = source_graph(city)
        self.assertEqual(resolve_anchor(city, anchor(2), graph)["position"], [0, 14, 0])
        self.assertEqual(
            resolve_anchor(city, anchor(5, 20), graph)["position"], [0, 2, 0]
        )
        with self.assertRaisesRegex(ValueError, "Disconnected"):
            route(city, [anchor(1), anchor(6, 20)], graph=graph)

    def test_dense_profile_keeps_height_and_direction_on_owned_edge(self):
        r = road(10, [1, 2], [[0, 0], [20, 0]], [2, 6])
        r["elevated_points"] = [[0, 0, 2], [10, 0, 8], [20, 0, 6]]
        city = {"roads": [r]}
        forward = route(city, [anchor(1), anchor(2)])
        reverse = route(city, [anchor(2), anchor(1)])
        self.assertEqual(forward["points"], list(reversed(reverse["points"])))
        self.assertIn([10, 8, 0], forward["points"])
        self.assertTrue(
            all(
                math.dist(a, b) <= 8
                for a, b in zip(forward["points"], forward["points"][1:])
            )
        )
        self.assertEqual(forward["edges"], [{"from": 1, "to": 2, "way_id": 10}])

    def test_exact_node_join_rejects_incompatible_owned_elevations(self):
        city = {
            "roads": [
                road(10, [1, 2], [[0, 0], [10, 0]], [2, 2]),
                road(20, [2, 3], [[10, 0], [20, 0]], [10, 10]),
            ]
        }
        with self.assertRaisesRegex(ValueError, "incompatible heights"):
            route(city, [anchor(1), anchor(3, 20)])


class NativeRaceExportTests(unittest.TestCase):
    def setUp(self):
        self.city = {
            "roads": [
                road(
                    10,
                    [0, 1, 2, 3, 4, 1],
                    [[-100, 0], [0, 0], [100, 0], [100, 100], [0, 100], [0, 0]],
                )
            ]
        }
        self.params = {
            "CarType": 0,
            "TimeofDay": 1,
            "Weather": 0,
            "Opponents": 4,
            "Cops": 0,
            "Ambient": 0.1,
            "Peds": 0,
            "NumLaps": 3,
            "TimeLimit": 0,
            "Difficulty": 1,
        }

    def event(self, family):
        event = {
            "id": f"{family}:0",
            "index": 0,
            "name": "Source Test",
            "start": anchor(1),
            "checkpoints": [anchor(2), anchor(3)],
            "finish": anchor(4),
            "suggested_order": [0, 1],
            "opponent_orders": [[0, 1], [1, 0]],
            "amateur": dict(self.params),
            "professional": {**self.params, "Ambient": 0.2},
            "target_speed_mps": {"amateur": 15, "professional": 18},
        }
        if family == "circuit":
            event["checkpoints"].append(anchor(4))
            event["route_via"] = [anchor(1), anchor(2), anchor(3), anchor(4)]
            event["opponent_orders"] = [[0, 1, 2]]
        if family == "blitz":
            for rank in ("amateur", "professional"):
                event[rank]["Opponents"] = 0
                event[rank]["TimeLimit"] = 30
        return event

    def test_all_native_modes_keep_sparse_rules_and_complete_rosters(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for family in ("race", "blitz", "circuit"):
                path = Path(directory) / f"{family}.json"
                path.write_text(
                    json.dumps(
                        {
                            "schema": 1,
                            "family": family,
                            "native_rule": "Ordered"
                            if family == "circuit"
                            else "AnyOrder",
                            "events": [self.event(family)],
                        }
                    )
                )
                paths.append(path)
            output = Path(directory) / "package"
            result = write(output, self.city, paths)
            races = output / "race/stockholm"
            self.assertEqual(len(result["events"]), 3)
            for family, table in (
                ("race", "mmracedata.csv"),
                ("blitz", "mmblitzdata.csv"),
                ("circuit", "mmcircuitdata.csv"),
            ):
                self.assertEqual(len((races / table).read_text().splitlines()), 2)
                self.assertEqual(
                    len((races / f"{family}0waypoints.csv").read_text().splitlines()), 5
                )
            aimap = (races / "race0.aimap").read_text()
            opponent_row = next(
                row for row in aimap.splitlines() if "race0-a-0.opp" in row
            )
            tail = opponent_row.split()[2:]
            self.assertEqual(len(tail), 10)
            self.assertGreater(float(tail[9]), 0)
            self.assertEqual(tail[6:8], ["1", "1"])
            self.assertEqual(len(list(races.glob("race0-*.opp"))), 8)
            self.assertEqual(len(list(races.glob("circuit0-*.opp"))), 8)
            self.assertEqual(len(list(races.glob("blitz0-*.opp"))), 0)
            for event in result["events"]:
                guide = output / event["variants"]["amateur"]["qa_guide"]
                self.assertTrue(guide.exists())
                self.assertTrue(guide.read_text().startswith("x,y,z,brake,"))
                self.assertEqual(event["visible_waypoint_rows"], 4)
                self.assertGreater(len(event["route"]["points"]), 40)
                self.assertEqual(
                    event["variants"]["amateur"]["time_limit_s"],
                    30 if event["family"] == "blitz" else None,
                )
                self.assertEqual(
                    len(event["grid"]), 1 if event["family"] == "blitz" else 5
                )
                self.assertEqual(event["grid"][0]["position"], [0, 2, 0])
                if event["family"] == "circuit":
                    self.assertEqual(
                        event["route"]["points"][0], event["route"]["points"][-1]
                    )
                else:
                    self.assertEqual(event["anchors"][-1]["node_id"], 4)
            self.assertNotEqual(
                (races / "race0-a-0.opp").read_text(),
                (races / "race0-a-1.opp").read_text(),
            )

    def test_visible_gate_cylinders_cannot_overlap(self):
        self.city["roads"][0]["points"][2] = [10, 0]
        self.city["roads"][0]["elevated_points"][2] = [10, 0, 2]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "race.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "family": "race",
                        "native_rule": "AnyOrder",
                        "events": [self.event("race")],
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, "cylinders overlap"):
                write(Path(directory) / "package", self.city, [path])

    def test_dense_guide_that_misses_gameplay_gate_fails_closed(self):
        event = self.event("race")
        event["route_via"] = [anchor(1), anchor(4)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "race.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "family": "race",
                        "native_rule": "AnyOrder",
                        "events": [event],
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, "misses gameplay gate"):
                write(Path(directory) / "package", self.city, [path])


if __name__ == "__main__":
    unittest.main()

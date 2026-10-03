import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from shapely.geometry import box, mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import road_details


def road(tags=None, width=10):
    return {
        "id": 1,
        "nodes": [10, 20],
        "points": [[0, 0], [60, 0]],
        "width": width,
        "tags": tags or {},
    }


class RoadDetailsTests(unittest.TestCase):
    def test_source_road_controls_grade_separated_paint_and_signals(self):
        lower = road({"lanes": "2"})
        upper = {**road({"lanes": "2", "bridge": "yes"}), "id": 2}
        city = {
            "roads": [lower, upper],
            "road_details": [
                {
                    "id": 10,
                    "road_id": 1,
                    "position": [30, 0],
                    "tags": {"highway": "traffic_signals"},
                },
                {
                    "id": 20,
                    "road_id": 2,
                    "position": [30, 0],
                    "tags": {"highway": "traffic_signals"},
                },
            ],
        }

        def level(r, x, n):
            return 4 if r["id"] == 1 else 15

        paint = road_details.ribbons(city, road_height=level)
        for ribbon in paint:
            expected = 4 if ribbon["source"] == "way/1" else 15
            self.assertEqual({p[1] for p in ribbon["points"]}, {expected})
        signals = road_details.placements(city, road_height=level)
        self.assertEqual([p["position"][1] for p in signals], [4, 15])

    def test_height_selector_preserves_lower_road_and_short_raised_approach(self):
        lower = road()
        upper = {**road(), "id": 2}
        approach = {**road(), "id": 3}
        city = {
            "roads": [lower, upper, approach],
            "bridge_ways": [2],
            "bridge_approaches": [
                {"source_way": 3, "points": [[30, 0, 12], [60, 0, 12]]}
            ],
        }
        sample = road_details.surface_height(city, lambda x, n: 4, lambda x, n: 12)
        self.assertEqual(sample(lower, 45, 0), 4)
        self.assertEqual(sample(upper, 45, 0), 12)
        self.assertEqual(sample(approach, 45, 0), 12)
        self.assertEqual(sample(approach, 5, 0), 4)

    def test_width_does_not_invent_signals_or_lane_count(self):
        city = {"roads": [road(width=14)]}
        self.assertEqual(road_details.placements(city), [])
        self.assertEqual(road_details.ribbons(city), [])

    def test_lane_marking_explicit_opt_out(self):
        self.assertEqual(
            road_details.ribbons(
                {"roads": [road({"lanes": "4", "lane_markings": "no"})]}
            ),
            [],
        )

    def test_single_lane_oneway_has_no_divider(self):
        self.assertEqual(
            road_details.ribbons({"roads": [road({"lanes": "1", "oneway": "yes"})]}), []
        )

    def test_three_lanes_use_width_for_divider_offsets(self):
        paint = road_details.ribbons(
            {"roads": [road({"lanes": "3", "oneway": "yes"}, width=9)]}
        )
        self.assertEqual(
            {round(sum(p[2] for p in r["points"]) / 4, 1) for r in paint}, {-1.5, 1.5}
        )

    def test_backward_signal_uses_opposite_verge(self):
        detail = {
            "id": 10,
            "road_id": 1,
            "position": [30, 0],
            "tags": {"highway": "traffic_signals"},
        }
        city = {"roads": [road()], "road_details": [detail]}
        forward = road_details.placements(city, lambda x, n: 7)[0]
        self.assertEqual(forward["position"], [30, 7, 5.4])
        self.assertLess(forward["direction"][0], forward["position"][0])
        detail["tags"]["traffic_signals:direction"] = "backward"
        backward = road_details.placements(city)[0]
        self.assertEqual(backward["position"][2], -5.4)
        self.assertGreater(backward["direction"][0], backward["position"][0])

    def test_crossing_requires_marking_evidence(self):
        detail = {
            "id": 10,
            "road_id": 1,
            "position": [30, 0],
            "tags": {"highway": "crossing", "crossing": "unmarked"},
        }
        city = {"roads": [road()], "road_details": [detail]}
        self.assertEqual(road_details.ribbons(city), [])
        detail["tags"]["crossing:markings"] = "zebra"
        paint = road_details.ribbons(city)
        self.assertTrue(paint)
        self.assertTrue(all(p["source"] == "node/10" for p in paint))
        detail["tags"]["crossing:markings"] = "no"
        self.assertEqual(road_details.ribbons(city), [])

    def test_native_decal_file_and_shared_pathset_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            shared = out / "city/stockholm/props.pathset"
            shared.parent.mkdir(parents=True)
            shared.write_bytes(b"shared")
            city = {"roads": [road({"lanes": "2"})]}
            self.assertEqual(road_details.write(out, city), [])
            data = (out / "city/stockholm/decals.pathset").read_bytes()
            self.assertEqual(data[:4], b"PTH1")
            self.assertGreater(struct.unpack_from("<I", data, 4)[0], 0)
            self.assertEqual(data[-4:], bytes([2, 20, 0, 0]))
            self.assertEqual(shared.read_bytes(), b"shared")
            self.assertEqual(
                (out / "geometry/sthlm_signal.pkg").read_bytes()[:4], b"PKG3"
            )
            tune = (out / "tune/banger/sthlm_signal.dgbangerdata").read_text()
            self.assertIn("CG 0 1.9 0", tune)
            self.assertIn("Size 0.34 3.8 0.44", tune)
            self.assertIn("NumParts 0", tune)

    def test_grouped_ribbons_preserve_only_original_quads(self):
        paint = [
            {
                "asset": "sthlm_paint",
                "points": [[x, 0, 0], [x, 0, 1], [x + 1, 0, 0], [x + 1, 0, 1]],
            }
            for x in (0, 10, 30)
        ]
        paths = road_details.grouped_ribbons(paint)
        self.assertEqual(len(paths), 1)
        points = paths[0]["points"]
        visible = []
        # Same normal test as native build_ribbon: cross(sum(along), across).
        for i in range(0, len(points) - 2, 2):
            a, b, c, d = points[i : i + 4]
            along = [c[j] - a[j] + d[j] - b[j] for j in range(3)]
            across = [b[j] - a[j] for j in range(3)]
            normal = [
                along[1] * across[2] - along[2] * across[1],
                along[2] * across[0] - along[0] * across[2],
                along[0] * across[1] - along[1] * across[0],
            ]
            if any(normal):
                visible.append([a, b, c, d])
        self.assertEqual(visible, [r["points"] for r in paint])

    def test_native_limits_split_large_ribbon_set(self):
        rectangle = {
            "asset": "sthlm_paint",
            "points": [[0, 0, 0], [0, 0, 1], [1, 0, 0], [1, 0, 1]],
        }
        paths = road_details.grouped_ribbons([rectangle] * 21882)
        self.assertEqual(len(paths), 3)
        self.assertTrue(all(len(p["points"]) <= 65536 for p in paths))
        self.assertEqual(
            road_details.grouped_ribbons([rectangle] * 3, max_points=12)[0]["points"],
            road_details.grouped_ribbons([rectangle] * 2)[0]["points"],
        )

    def test_large_native_file_has_valid_record_bounds(self):
        rectangle = {
            "asset": "sthlm_paint",
            "points": [[0, 0, 0], [0, 0, 1], [1, 0, 0], [1, 0, 1]],
        }
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(road_details, "ribbons", return_value=[rectangle] * 21882),
        ):
            out = Path(tmp)
            road_details.write(out, {"roads": []})
            data = (out / "city/stockholm/decals.pathset").read_bytes()
            count, current = struct.unpack_from("<II", data, 4)
            self.assertEqual((count, current), (3, 0))
            cursor = 12
            for _ in range(count):
                self.assertEqual(
                    data[cursor : cursor + 32].split(b"\0")[0], b"sthlm_paint"
                )
                points, selection = struct.unpack_from("<II", data, cursor + 32)
                self.assertLessEqual(points, 65536)
                self.assertEqual(points % 2, 0)
                self.assertEqual(selection, 0)
                cursor += 40 + 16 * points
                self.assertEqual(data[cursor : cursor + 4], bytes([2, 20, 0, 0]))
                cursor += 4
            self.assertEqual(cursor, len(data))

    def test_playable_bounds_reject_outside_nodes_poles_and_paint(self):
        detail = {
            "id": 10,
            "road_id": 1,
            "position": [30, 0],
            "tags": {"highway": "traffic_signals"},
        }
        city = {
            "roads": [road({"lanes": "2"})],
            "road_details": [detail],
            "bounds": mapping(box(0, -1, 60, 1)),
        }
        self.assertEqual(road_details.placements(city), [])
        self.assertTrue(road_details.ribbons(city))
        city["bounds"] = mapping(box(0, 10, 60, 11))
        self.assertEqual(road_details.ribbons(city), [])
        source = {
            "elements": [
                {
                    "type": "node",
                    "id": 10,
                    "lon": 18,
                    "lat": 59,
                    "tags": {"highway": "traffic_signals"},
                }
            ]
        }
        self.assertEqual(
            road_details.normalized(source, {"origin": [18, 59]}, city), []
        )

    def test_clipped_member_nodes_do_not_stamp_outside_road(self):
        cfg = {"origin": [18, 59]}
        source = {
            "elements": [
                {
                    "type": "node",
                    "id": 10,
                    "lon": 18.01,
                    "lat": 59,
                    "tags": {"highway": "traffic_signals"},
                }
            ]
        }
        self.assertEqual(road_details.normalized(source, cfg, {"roads": [road()]}), [])

    def test_normalization_keeps_source_identity(self):
        cfg = {"origin": [18, 59]}
        source = {
            "elements": [
                {
                    "type": "node",
                    "id": 10,
                    "lon": 18,
                    "lat": 59,
                    "tags": {"highway": "traffic_signals"},
                }
            ]
        }
        found = road_details.normalized(source, cfg, {"roads": [road()]})
        self.assertEqual(found[0]["road_id"], 1)
        self.assertEqual(found[0]["id"], 10)

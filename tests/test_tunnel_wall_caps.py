import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tunnels import shell_mesh, surface_wall_caps


class TunnelWallCapsTest(unittest.TestCase):
    def fixture(self):
        fixture = json.loads(
            (
                Path(__file__).parent / "fixtures/tunnel-surface-wall-intrusion.json"
            ).read_text()
        )
        road = next(r for r in fixture["roads"] if r["id"] == 31062851)
        city = {"roads": fixture["roads"], "tunnel_ways": [31062851, 31062848]}
        cfg = {"clearance_m": 5.2, "roof_thickness_m": 0.5}
        return road, city, cfg

    def test_authored_upper_ground_junction_keeps_retaining_wall_below_road(self):
        road, city, cfg = self.fixture()
        original = copy.deepcopy(road)
        before = shell_mesh(road, cfg)
        after = shell_mesh(road, cfg, surface_caps=surface_wall_caps(city))
        near = [
            triangle
            for triangle in after[0][1]
            if min(v[0] for v in triangle) <= -1189.9175 <= max(v[0] for v in triangle)
            and min(v[2] for v in triangle) - 2.5
            <= -418.60782
            <= max(v[2] for v in triangle) + 2.5
        ]
        self.assertTrue(near)
        self.assertLess(max(v[1] for t in near for v in t), 16.95859)
        self.assertEqual(before[1:], after[1:])
        self.assertEqual(len(before[0][1]), len(after[0][1]))
        self.assertEqual(original, road)

    def test_covered_shell_or_lower_road_does_not_change(self):
        road, city, cfg = self.fixture()
        covered = copy.deepcopy(road)
        covered["tunnel_cover_m"] = [20] * len(covered["elevated_points"])
        self.assertEqual(
            shell_mesh(covered, cfg),
            shell_mesh(covered, cfg, surface_caps=surface_wall_caps(city)),
        )
        lower = copy.deepcopy(city)
        for source in lower["roads"]:
            if source["id"] not in lower["tunnel_ways"]:
                for point in source["elevated_points"]:
                    point[2] = 0
        self.assertEqual(
            shell_mesh(road, cfg),
            shell_mesh(road, cfg, surface_caps=surface_wall_caps(lower)),
        )

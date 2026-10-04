import sys
import tempfile
import unittest
from pathlib import Path

from shapely.geometry import box, mapping, shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tunnels import (
    clip_surface,
    components,
    internal_tunnel_ways,
    prepare,
    shell_mesh,
    write,
)


class Flat:
    def height(self, x, n):
        return 12.0


def road(wid, nodes, points, tunnel=False):
    return {
        "id": wid,
        "nodes": nodes,
        "points": points,
        "width": 8,
        "tags": {
            "name": "Klaratunneln" if tunnel else "street",
            "tunnel": "yes" if tunnel else "no",
        },
        "elevated_points": [[*p, 12] for p in points],
    }


class TunnelTests(unittest.TestCase):
    def city(self):
        return {
            "roads": [
                road(1, [1, 2], [(0, 0), (200, 0)], True),
                road(2, [2, 3], [(200, 0), (400, 0)], True),
                road(3, [0, 1], [(-50, 0), (0, 0)]),
                road(4, [3, 4], [(400, 0), (450, 0)]),
                road(5, [8, 9], [(200, -50), (200, 50)]),
            ],
            "tunnel_ways": [1, 2],
            "bounds": mapping(box(-100, -100, 500, 100)),
        }

    def test_profile_buried_source_splits_continuous_surface_untouched(self):
        city = self.city()
        terrain = Flat()
        roads = prepare(city, terrain)
        self.assertEqual(
            roads[0]["elevated_points"][-1], roads[1]["elevated_points"][0]
        )
        self.assertEqual(roads[0]["elevated_points"][0][2], 12)
        self.assertEqual(roads[1]["elevated_points"][-1][2], 12)
        self.assertEqual(roads[0]["elevated_points"][-1][2], 4)
        self.assertTrue(all(p[2] == 12 for p in city["roads"][-1]["elevated_points"]))
        self.assertTrue(all(p["max_grade"] < 0.1 for p in city["tunnel_profiles"]))
        # Covered bore keeps its overlying land. Portal ramps alone are open.
        cut = shape(city["tunnel_terrain_cutout"])
        self.assertFalse(cut.covers(box(190, -2, 210, 2)))
        self.assertTrue(cut.covers(box(10, -2, 20, 2)))

    def test_tunnel_arms_do_not_create_surface_signal_junctions(self):
        from road_surfaces import junctions

        city = self.city()
        city["roads"][0]["tags"]["highway"] = "primary"
        city["roads"][1]["tags"]["highway"] = "primary"
        city["roads"].append(road(6, [2, 11], [(200, 0), (200, 80)], True))
        city["tunnel_ways"].append(6)
        self.assertEqual(junctions(city), [])

    def test_xy_crossing_does_not_create_source_junction(self):
        a = road(1, [1, 2], [(-10, 0), (10, 0)], True)
        b = road(2, [3, 4], [(0, -10), (0, 10)], True)
        self.assertEqual(len(components([a, b])), 2)
        b["nodes"][0] = 2
        self.assertEqual(len(components([a, b])), 1)

    def test_boundary_cut_endpoint_not_fabricated_portal(self):
        city = self.city()
        city["roads"] = city["roads"][:2]
        prepare(city, Flat())
        self.assertTrue(
            all(not r["shared_source_portal_nodes"] for r in city["tunnel_profiles"])
        )
        self.assertTrue(shape(city["tunnel_terrain_cutout"]).is_empty)

    def test_selector_retains_complete_public_motor_tunnel(self):
        nodes = {1: {"lon": 18, "lat": 59}, 2: {"lon": 18.001, "lat": 59}}
        cfg = {"origin": [18, 59]}
        ways = {
            1: {
                "id": 1,
                "nodes": [1, 2],
                "tags": {
                    "tunnel": "yes",
                    "highway": "trunk",
                    "name": "Blekholmstunneln",
                },
            },
            2: {
                "id": 2,
                "nodes": [1, 2],
                "tags": {"tunnel": "yes", "highway": "service"},
            },
            3: {
                "id": 3,
                "nodes": [1, 2],
                "tags": {
                    "tunnel": "yes",
                    "highway": "motorway",
                    "name": "Fredhällstunneln",
                },
            },
            4: {
                "id": 4,
                "nodes": [1, 999],
                "tags": {"tunnel": "yes", "highway": "trunk"},
            },
        }
        nodes[3] = {"lon": 17.9999, "lat": 59}
        nodes[4] = {"lon": 18.0011, "lat": 59}
        ways[5] = {"id": 5, "nodes": [3, 1], "tags": {"highway": "trunk"}}
        ways[6] = {"id": 6, "nodes": [2, 4], "tags": {"highway": "trunk"}}
        self.assertEqual(
            internal_tunnel_ways(ways, nodes, cfg, box(-100, -1, 100, 100)), [1]
        )
        self.assertEqual(
            internal_tunnel_ways(ways, nodes, cfg, box(-1, -1, 20, 100)), []
        )

    def test_paired_one_lane_bores_do_not_use_citywide_nine_metre_width(self):
        city = self.city()
        city["roads"][0]["tags"]["lanes"] = "1"
        prepare(city, Flat())
        self.assertEqual(city["roads"][0]["width"], 5)
        city["roads"][0]["tags"]["width"] = "8"
        city["roads"][0]["width"] = 8
        prepare(city, Flat())
        self.assertEqual(city["roads"][0]["width"], 8)

    def test_surface_clipping_removes_exposed_caps_but_keeps_covered_street(self):
        city = self.city()
        prepare(city, Flat())
        ordinary = box(-10, -10, 210, 10)
        result = clip_surface(ordinary, city)
        cutout = shape(city["tunnel_terrain_cutout"])
        self.assertTrue(result.intersection(cutout).area < 1e-8)
        self.assertTrue(result.covers(box(90, -2, 110, 2)))
        self.assertLess(result.area, ordinary.area)
        # The same operation applies to shoulders; no profile mutation occurs.
        original = [list(p) for p in city["roads"][0]["elevated_points"]]
        self.assertLess(
            clip_surface(ordinary.buffer(2), city).area, ordinary.buffer(2).area
        )
        self.assertEqual(original, city["roads"][0]["elevated_points"])
        self.assertTrue(clip_surface(ordinary, {}).equals(ordinary))

    def test_shell_wall_bottom_meets_floor_edge_without_blue_gap(self):
        city = self.city()
        prepare(city, Flat())
        walls = shell_mesh(city["roads"][0], city["tunnel_profile_rules"])[0][1]
        self.assertTrue(all(abs(v[2]) == 4 for tri in walls for v in tri))

    def test_exposed_portal_ramp_has_no_roof_canopy(self):
        city = self.city()
        prepare(city, Flat())
        cfg = city["tunnel_profile_rules"]
        r = city["roads"][0]
        groups = shell_mesh(r, cfg)
        # The surface-height entrance has short retaining edges; the roof
        # starts only below sufficient overburden, with a framed cut-in edge.
        roofvertices = [v for tri in groups[1][1] for v in tri]
        self.assertTrue(roofvertices)
        self.assertTrue(all(v[0] > 0 for v in roofvertices))
        self.assertLessEqual(max(v[1] for v in roofvertices), 12)

    def test_branch_opens_even_when_intersection_misses_panel_midpoint(self):
        city = self.city()
        prepare(city, Flat())
        cfg = city["tunnel_profile_rules"]
        r = city["roads"][0]
        full = shell_mesh(r, cfg)
        # First panel spans x=0..5; aperture ends at x=2.45, before midpoint.
        opened = shell_mesh(r, cfg, [box(-2.45, 0, 2.45, 30)])
        self.assertLess(len(opened[0][1]), len(full[0][1]))

    def test_shell_opens_source_branches_and_closes_boundary_ends(self):
        city = self.city()
        prepare(city, Flat())
        cfg = city["tunnel_profile_rules"]
        r = city["roads"][0]
        full = shell_mesh(r, cfg)
        opened = shell_mesh(r, cfg, [box(195, -8, 205, 8)])
        self.assertLess(len(opened[0][1]), len(full[0][1]))
        closed = shell_mesh(r, cfg, closed_nodes=[1])
        self.assertEqual(len(closed[0][1]), len(full[0][1]) + 4)

    def test_native_shell_open_ends_clear_driving_aperture(self):
        city = self.city()
        prepare(city, Flat())
        cfg = city["tunnel_profile_rules"]
        groups = shell_mesh(city["roads"][0], cfg)
        self.assertTrue(all(tris for _, tris in groups))
        wall = [v for tri in groups[0][1] for v in tri]
        self.assertTrue(all(abs(v[2]) >= 4 for v in wall))
        with tempfile.TemporaryDirectory() as tmp:
            instances = write(Path(tmp), city)
            self.assertEqual(len(instances), 2)
            self.assertTrue(all(i["static"] and not i["movable"] for i in instances))
            self.assertEqual(
                (Path(tmp) / "geometry/sthlm_tunnel_1.pkg").read_bytes()[:4], b"PKG3"
            )

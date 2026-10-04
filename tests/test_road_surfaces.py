import sys
import math
import json
import tempfile
import unittest
from pathlib import Path
from shapely.geometry import LineString, Point, box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import road_surfaces
import sthlm


def road(index=1, points=None, nodes=None, tags=None, width=9):
    return {
        "id": index,
        "points": points or [[0, 0], [100, 0]],
        "nodes": nodes or [1, 2],
        "tags": tags or {"highway": "secondary"},
        "width": width,
    }


class RoadSurfaceTests(unittest.TestCase):
    def test_marked_strip_profile_carries_into_neighbouring_native_fan(self):
        from shapely.geometry import Polygon

        triangles = []
        road_surfaces.render(
            sthlm.PsdlWriter(),
            {"roads": [road()]},
            box(-10, -10, 110, 10),
            lambda x, n: 10.0,
            road_height=lambda r, x, n: 10.4,
            station_height=lambda r, station: 10.4,
            triangle_sink=triangles,
        )
        # A body just outside a strip boundary must meet a continuous fan.
        # Previously the exact boundary pin dropped 40 cm within 1 cm.
        heights = []
        for a, b, c in triangles:
            if not Polygon([(v[0], v[2]) for v in (a, b, c)]).covers(Point(25, -4.49)):
                continue
            ux, uy, uz = (b[i] - a[i] for i in range(3))
            vx, vy, vz = (c[i] - a[i] for i in range(3))
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            self.assertGreater(abs(ny) / math.sqrt(nx * nx + ny * ny + nz * nz), 0.95)
            heights.append(a[1] - (nx * (25 - a[0]) + nz * (-4.49 - a[2])) / ny)
        self.assertTrue(heights)
        for h in heights:
            self.assertAlmostEqual(h, 10.4, delta=0.02)

    def test_vasabron_same_level_carriageways_have_one_collision_floor(self):
        from shapely.geometry import Polygon

        fixture = json.loads(
            (Path(__file__).parent / "fixtures/vasabron-overlap.json").read_text()
        )

        class Terrain:
            def height(self, x, n):
                return 0.9

        triangles = []
        road_surfaces.render_bridge_layers(
            sthlm.PsdlWriter(),
            {**fixture["city"], "roads": fixture["roads"]},
            Terrain(),
            triangle_sink=triangles,
        )
        x, z = 1128.0331, 114.072074
        heights = []
        for a, b, c in triangles:
            if not Polygon([(v[0], v[2]) for v in (a, b, c)]).covers(Point(x, z)):
                continue
            denominator = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
            u = ((b[2] - c[2]) * (x - c[0]) + (c[0] - b[0]) * (z - c[2])) / denominator
            v = ((c[2] - a[2]) * (x - c[0]) + (a[0] - c[0]) * (z - c[2])) / denominator
            heights.append(u * a[1] + v * b[1] + (1 - u - v) * c[1])
        self.assertTrue(heights)
        self.assertLess(max(heights) - min(heights), 0.04)

    def test_stacked_bridge_levels_survive_native_export(self):
        from shapely.geometry import Polygon

        a = road(
            1,
            [[-50, 0], [50, 0]],
            [1, 2],
            {"highway": "trunk", "bridge": "yes", "layer": "2"},
        )
        b = road(
            2,
            [[0, -50], [0, 50]],
            [3, 4],
            {"highway": "trunk", "bridge": "yes", "layer": "1"},
        )
        for r, h in [(a, 18), (b, 8)]:
            r["elevated_points"] = [[*p, h] for p in r["points"]]
        city = {
            "roads": [a, b],
            "bridge_ways": [1, 2],
            "bounds": mapping(box(-100, -100, 100, 100)),
        }

        class Terrain:
            def height(self, x, n):
                return 2

        triangles = []
        report = road_surfaces.render_bridge_layers(
            sthlm.PsdlWriter(), city, Terrain(), triangle_sink=triangles
        )
        self.assertEqual(report["layer_count"], 2)
        heights = {
            triangle[0][1]
            for triangle in triangles
            if Polygon([(p[0], p[2]) for p in triangle]).covers(Point(0, 0))
        }
        self.assertEqual(heights, {8, 18})

    def test_same_source_layer_does_not_merge_different_height_ramps(self):
        from shapely.geometry import Polygon

        a = road(
            1,
            [[-50, 0], [50, 0]],
            [1, 2],
            {"highway": "trunk", "bridge": "yes", "layer": "1"},
        )
        b = road(
            2,
            [[0, -50], [0, 50]],
            [3, 4],
            {"highway": "trunk", "bridge": "yes", "layer": "1"},
        )
        for r, h in [(a, 18), (b, 8)]:
            r["elevated_points"] = [[*p, h] for p in r["points"]]
        city = {
            "roads": [a, b],
            "bridge_ways": [1, 2],
            "bounds": mapping(box(-100, -100, 100, 100)),
        }

        class Terrain:
            def height(self, x, n):
                return 2

        triangles = []
        report = road_surfaces.render_bridge_layers(
            sthlm.PsdlWriter(), city, Terrain(), triangle_sink=triangles
        )
        self.assertEqual(report["surface_groups"], 2)
        heights = {
            t[0][1]
            for t in triangles
            if Polygon([(p[0], p[2]) for p in t]).covers(Point(0, 0))
        }
        self.assertEqual(heights, {8, 18})

    def test_width_class_oneway_and_explicit_opt_out(self):
        self.assertEqual(road_surfaces.classification(road(width=14))["lanes"], 4)
        self.assertEqual(
            road_surfaces.classification(road(tags={"highway": "service"}))["marked"],
            False,
        )
        self.assertFalse(
            road_surfaces.classification(
                road(tags={"highway": "secondary", "lane_markings": "no"})
            )["marked"]
        )
        spec = road_surfaces.classification(
            road(tags={"highway": "secondary", "oneway": "yes", "lanes": "3"})
        )
        self.assertTrue(spec["oneway"])
        self.assertEqual(spec["lanes"], 3)

    def test_same_coverage_without_duplicate_collision(self):
        r = road()
        surface = LineString(r["points"]).buffer(4.5)
        writer = sthlm.PsdlWriter()
        report = road_surfaces.render(writer, {"roads": [r]}, surface, 3)
        self.assertGreater(report["strips"], 0)
        self.assertAlmostEqual(
            report["surface_area"],
            report["marked_area"] + report["remainder_area"],
            places=6,
        )
        strips = [attrs for _, attrs, _ in writer.rooms if attrs[2] == 0x92]
        self.assertEqual(len(strips), report["strips"])
        self.assertTrue(all(len(attrs) == 7 for attrs in strips))
        self.assertTrue(all(len(set(attrs[3:])) == 4 for attrs in strips))

    def test_source_height_on_strip_corners(self):
        r = road()
        writer = sthlm.PsdlWriter()
        road_surfaces.render(
            writer,
            {"roads": [r]},
            LineString(r["points"]).buffer(4.5),
            3,
            road_height=lambda road, x, n: 12,
        )
        for _, attrs, _ in writer.rooms:
            if attrs[2] == 0x92:
                self.assertEqual({writer.vertices[i][1] for i in attrs[3:]}, {12})

    def test_graph_junction_does_not_connect_crossing_without_shared_node(self):
        a = road(points=[[-50, 0], [0, 0], [50, 0]], nodes=[1, 2, 3])
        b = road(2, [[0, -50], [0, 0], [0, 50]], [4, 5, 6])
        self.assertEqual(road_surfaces.junctions({"roads": [a, b]}), [])
        b["nodes"][1] = 2
        city = {"roads": [a, b], "bounds": mapping(box(-100, -100, 100, 100))}
        j = road_surfaces.junctions(city)
        self.assertEqual(j[0]["design"], "signal_crossroads")
        self.assertEqual(len(road_surfaces.signal_placements(city)), 4)
        self.assertTrue(
            all(p["movable"] for p in road_surfaces.signal_placements(city))
        )

    def test_textures_are_deterministic_with_transverse_lane_separation(self):
        spec = road_surfaces.classification(
            road(tags={"highway": "secondary", "lanes": "2"})
        )
        img = road_surfaces.texture(spec)
        self.assertEqual(img.tobytes(), road_surfaces.texture(spec).tobytes())
        self.assertGreater(img.getpixel((50, 256))[0], 180)
        self.assertEqual(
            img.getpixel((300, 256)), road_surfaces.asphalt().getpixel((300, 256))
        )
        with tempfile.TemporaryDirectory() as tmp:
            names = road_surfaces.write_textures(Path(tmp), {"roads": [road()]})
            self.assertIn("sthlm_asphalt", names)
            self.assertTrue(
                all((Path(tmp) / f"{name}.png").is_file() for name in names)
            )

    def test_junction_interior_remains_plain_asphalt(self):
        a = road(points=[[-50, 0], [0, 0], [50, 0]], nodes=[1, 2, 3])
        b = road(2, [[0, -50], [0, 0], [0, 50]], [4, 2, 6])
        geom = (
            LineString(a["points"])
            .buffer(4.5)
            .union(LineString(b["points"]).buffer(4.5))
        )
        writer = sthlm.PsdlWriter()
        report = road_surfaces.render(writer, {"roads": [a, b]}, geom, 3)
        self.assertGreater(report["strips"], 0)
        for _, attrs, _ in writer.rooms:
            if attrs[2] == 0x92:
                self.assertTrue(
                    all(
                        (writer.vertices[i][0] ** 2 + writer.vertices[i][2] ** 2) ** 0.5
                        >= 6.5
                        for i in attrs[3:]
                    )
                )

    def test_native_facet_capture_matches_strip_diagonal_and_closes_fan_seam(self):
        r = road(points=[[0, 0], [20, 0]])
        writer = sthlm.PsdlWriter()
        facets = []
        road_surfaces.render(
            writer,
            {"roads": [r]},
            LineString(r["points"]).buffer(4.5),
            lambda x, n: x * x / 100,
            triangle_sink=facets,
        )
        strips = [attrs for _, attrs, _ in writer.rooms if attrs[2] == 0x92]
        first = strips[0][3:]
        self.assertIn([list(writer.vertices[first[i]]) for i in (0, 1, 2)], facets)
        self.assertIn([list(writer.vertices[first[i]]) for i in (2, 1, 3)], facets)
        fan_vertices = [
            writer.vertices[i]
            for _, attrs, _ in writer.rooms
            if attrs[2] == 0xA9
            for offset in range(2, len(attrs), 4)
            for i in attrs[offset + 1 : offset + 4]
        ]
        seam = [
            p for p in fan_vertices if 0 < p[0] < 10 and abs(abs(p[2]) - 4.48) < 1e-4
        ]
        self.assertTrue(seam)
        # Native quad edge follows a chord, not the independently sampled parabola.
        self.assertTrue(all(abs(p[1] - p[0] / 10) < 1e-4 for p in seam))

    def test_tunnel_materials_export_without_merging_surface_geometry(self):
        tunnel = road(
            tags={"highway": "primary", "oneway": "yes", "lanes": "3"}, width=12
        )
        with tempfile.TemporaryDirectory() as tmp:
            names = road_surfaces.write_textures(
                Path(tmp), {"roads": [], "tunnel_roads": [tunnel]}
            )
            self.assertIn(
                road_surfaces.material_name(road_surfaces.classification(tunnel)), names
            )

    def test_short_graph_edges_never_put_poles_in_crossing_carriageway(self):
        a = road(
            points=[[-50, 0], [-2, 0], [0, 0], [2, 0], [50, 0]], nodes=[1, 2, 3, 4, 5]
        )
        b = road(2, [[0, -50], [0, -2], [0, 0], [0, 2], [0, 50]], [6, 7, 3, 8, 9])
        geom = (
            LineString(a["points"])
            .buffer(4.5)
            .union(LineString(b["points"]).buffer(4.5))
        )
        city = {"roads": [a, b], "road_surface": mapping(geom)}
        placements = road_surfaces.signal_placements(city)
        self.assertEqual(len(placements), 4)
        self.assertTrue(
            all(
                not geom.intersects(
                    Point(p["position"][0], -p["position"][2]).buffer(0.3)
                )
                for p in placements
            )
        )

    def test_bending_road_corners_use_known_source_stations_without_quad_warp(self):
        r = road(points=[[0, 0], [20, 0], [20, 20]], nodes=[1, 2, 3])
        line = LineString(r["points"])
        writer = sthlm.PsdlWriter()
        sampled = []

        def station_height(source, distance):
            self.assertIs(source, r)
            sampled.append(distance)
            return distance * 0.3

        def offset_projection(source, x, n):
            # At the bend the two offset corners project to different segments.
            return line.project(Point(x, n)) * 0.3

        self.assertGreater(
            abs(offset_projection(r, 20, 4.48) - offset_projection(r, 20, -4.48)), 1.3
        )
        road_surfaces.render(
            writer,
            {"roads": [r]},
            line.buffer(4.5),
            lambda x, n: line.project(Point(x, n)) * 0.3,
            road_height=offset_projection,
            station_height=station_height,
        )
        strips = [attrs for _, attrs, _ in writer.rooms if attrs[2] == 0x92]
        self.assertGreater(len(strips), 1)
        self.assertEqual(len(sampled), len(strips) * 2)
        self.assertTrue(all(distance % 10 == 0 for distance in sampled))
        for index, attrs in enumerate(strips):
            ys = [writer.vertices[i][1] for i in attrs[3:]]
            self.assertEqual(
                ys, [sampled[index * 2] * 0.3] * 2 + [sampled[index * 2 + 1] * 0.3] * 2
            )
        fan_vertices = [
            writer.vertices[i]
            for _, attrs, _ in writer.rooms
            if attrs[2] == 0xA9
            for offset in range(2, len(attrs), 4)
            for i in attrs[offset + 1 : offset + 4]
        ]
        # Both sides of the bend's transverse strip boundary share station20m.
        seam = [p for p in fan_vertices if abs(p[0] - 20) < 1e-4 and abs(p[2]) <= 4.48]
        self.assertTrue(seam)
        self.assertTrue(all(abs(p[1] - 6) < 1e-4 for p in seam))

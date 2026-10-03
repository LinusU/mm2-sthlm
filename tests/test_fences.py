import gzip
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

from shapely.geometry import LineString, Point, box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import fences


class FenceTests(unittest.TestCase):
    def setUp(self):
        self.city = {
            "origin": [18.045, 59.328],
            "bounds": mapping(box(-1000, -1000, 1000, 1000)),
        }
        with gzip.open(fences.ROOT / "sources/expanded/osm.json.gz", "rt") as stream:
            self.source = json.load(stream)
        self.nodes = {
            e["id"]: e for e in self.source["elements"] if e["type"] == "node"
        }

    def test_projection_matches_map_coordinates(self):
        import sthlm

        self.assertEqual(
            fences.project(18.0399655, 59.3271334, self.city["origin"]),
            sthlm.project(18.0399655, 59.3271334, self.city["origin"]),
        )

    def test_three_authored_openings_remain_clear(self):
        cfg, lines = fences.fence_lines(self.city, self.source)
        self.assertEqual(len(cfg["openings"]), 3)
        for gap in cfg["openings"]:
            node = self.nodes[gap["node"]]
            p = Point(fences.project(node["lon"], node["lat"], self.city["origin"]))
            self.assertGreaterEqual(
                min(r["line"].distance(p) for r in lines), gap["width"] / 2 - 0.15
            )

    def test_source_open_ends_not_closed(self):
        cfg, lines = fences.fence_lines(self.city, self.source)
        original = [
            e
            for e in self.source["elements"]
            if e["type"] == "way" and e["id"] in cfg["ways"]
        ]
        original_length = sum(
            LineString(
                [
                    fences.project(
                        self.nodes[n]["lon"], self.nodes[n]["lat"], self.city["origin"]
                    )
                    for n in w["nodes"]
                ]
            ).length
            for w in original
        )
        self.assertAlmostEqual(
            sum(r["line"].length for r in lines), original_length - 24, places=6
        )
        self.assertTrue(all(not r["line"].is_ring for r in lines))
        # No invented connection bridges either source way's end points.
        for r in lines:
            self.assertIn(r["source"], ["way/28975066", "way/1013162648"])

    def test_directed_grounded_panels_cover_only_fence_lines(self):
        def height(x, n):
            return 3 + x * 0.02 + n * 0.01

        placements = fences.placements(self.city, height, self.source)
        self.assertGreater(len(placements), 100)
        for p in placements:
            x, y, z = p["position"]
            self.assertAlmostEqual(y, height(x, -z))
            a, b = p["endpoints"]
            self.assertLessEqual(math.dist(a, b), 2.5 + 1e-6)
            self.assertEqual(p["direction"], [b[0], y, -b[1]])
            self.assertTrue(p["breakable"])
            self.assertEqual(p["kind"], "fence")
            _, pieces = fences.panel_mesh(p["mesh"])
            vertices = [v for group in pieces for tri in group for v in tri]
            # Local +X corresponds to increasing line distance.
            self.assertAlmostEqual(
                min(v[0] for v in vertices), -math.dist(a, b) / 2, places=4
            )
            self.assertAlmostEqual(
                max(v[0] for v in vertices), math.dist(a, b) / 2, places=4
            )
            self.assertLessEqual(
                max(v[2] for v in vertices) - min(v[2] for v in vertices), 0.22 + 1e-6
            )

    def test_engine_yaw_preserves_grounded_source_endpoints(self):
        def height(x, n):
            return 3 + x * 0.02 + n * 0.01

        records = fences.placements(self.city, height, self.source)
        records += fences.wooden_placements(self.city, height, self.source)
        for record in records:
            px, py, pz = record["position"]
            dx, _, dz = record["direction"]
            dx, dz = dx - px, dz - pz
            norm = math.hypot(dx, dz)
            dx, dz = dx / norm, dz / norm
            _, pieces = fences.panel_mesh(record["mesh"])
            vertices = [v for group in pieces for tri in group for v in tri]
            length = record["mesh"]["length"]
            for sign, endpoint in [
                (-1, record["endpoints"][0]),
                (1, record["endpoints"][1]),
            ]:
                local_x = sign * length / 2
                # Engine yawed_basis maps local +X to the Directed forward.
                wx, wn = px + local_x * dx, -(pz + local_x * dz)
                self.assertAlmostEqual(wx, endpoint[0], places=4)
                self.assertAlmostEqual(wn, endpoint[1], places=4)
                authored_offset = record["mesh"]["left_y" if sign == -1 else "right_y"]
                self.assertAlmostEqual(
                    py + authored_offset, height(*endpoint), places=4
                )
                end_vertices = [v for v in vertices if abs(v[0] - local_x) < 1e-4]
                self.assertTrue(end_vertices)
                expected_bottom = -0.06 if record["mesh"]["fence_type"] == "iron" else 0
                # Wood/gate slats start 5cm above ground; posts/rear rails
                # need not sit exactly on every endpoint.
                if record["mesh"]["fence_type"] == "iron":
                    bottom = (
                        min(v[1] for v in end_vertices)
                        + record["mesh"]["height"] / 2
                        + py
                    )
                    self.assertAlmostEqual(
                        bottom, height(*endpoint) + expected_bottom, places=4
                    )

    def test_emit_assets_without_overwriting_pathset(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            target = out / "city/stockholm/props.pathset"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"sentinel")
            records = fences.write(out, self.city, source=self.source)
            self.assertEqual(target.read_bytes(), b"sentinel")
            for asset in {r["asset"] for r in records}:
                pkg = (out / f"geometry/{asset}.pkg").read_bytes()
                self.assertEqual(pkg[:4], b"PKG3")
                self.assertIn(b"BREAK01_H", pkg)
                native = (out / f"tune/banger/{asset}.dgbangerdata").read_text()
                expected = (
                    3
                    if asset.startswith("sthlm_fence")
                    and next(r for r in records if r["asset"] == asset)["mesh"][
                        "fence_type"
                    ]
                    == "iron"
                    else (2 if asset.startswith("sthlm_gate") else 1)
                )
                self.assertIn(f"NumParts {expected}", native)
                self.assertIn("CG 0 0.950000 0", native)
                self.assertTrue(
                    (out / f"tune/banger/{asset}_break01.dgbangerdata").exists()
                )
            for texture in ("iron", "gold", "stone"):
                self.assertTrue((out / f"texture/fence_{texture}.png").exists())

    def test_breakable_wooden_gate_fills_authored_gap(self):
        records = fences.wooden_placements(self.city, lambda x, n: 2.0, self.source)
        gate = [r for r in records if r["mesh"]["fence_type"] == "gate"]
        self.assertEqual(len(gate), 1)
        gate = gate[0]
        self.assertEqual(gate["gate_node"], 318607298)
        self.assertEqual(gate["gate_width"], 5)
        self.assertTrue(gate["breakable"])
        pkg, pieces = fences.panel_mesh(gate["mesh"])
        self.assertEqual(len(pieces), 2)
        self.assertIn(b"BREAK01_H", pkg)
        self.assertIn(b"BREAK02_H", pkg)
        for r in records:
            if r is gate:
                continue
            self.assertEqual(r["mesh"]["fence_type"], "wood")
            self.assertGreaterEqual(
                Point(gate["position"][0], -gate["position"][2]).distance(
                    LineString(r["endpoints"])
                ),
                2.49,
            )

    def test_missing_or_wrong_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "requires source"):
            fences.placements(self.city, source={"elements": []})

    def test_city_outside_fence_has_no_instances(self):
        city = dict(self.city, bounds=mapping(box(500, 500, 600, 600)))
        self.assertEqual(fences.placements(city, source=self.source), [])


if __name__ == "__main__":
    unittest.main()

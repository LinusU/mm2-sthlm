"""Source, duplicate and native geometry regressions for the additional seventy."""

import copy
import gzip
import hashlib
import json
import math
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from shapely.geometry import box, mapping, shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import additional_landmarks as more
import landmarks
from expanded import normalized
from sthlm import PsdlWriter

ROOT = Path(__file__).resolve().parents[1]


class AdditionalLandmarksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot_path = ROOT / "sources/expanded/osm.json.gz"
        with gzip.open(cls.snapshot_path, "rt") as stream:
            source = json.load(stream)
        cfg = json.loads((ROOT / "config/expanded.json").read_text())
        cls.city = normalized(source, cfg)
        cls.by_id = {b["id"]: b for b in cls.city["buildings"]}

    def test_exactly_one_hundred_unique_including_nested_aliases(self):
        first = landmarks.inventory()
        entries = more.validate_inventory(first)
        self.assertEqual(len(first + entries), 100)
        self.assertEqual(
            len(set(more.source_ids(first + entries))),
            len(more.source_ids(first + entries)),
        )
        for collision in ["way/8049504", "relation/17957127"]:
            amended = copy.deepcopy(first)
            amended[0].setdefault("source_aliases", []).append(entries[0]["source_id"])
            with self.assertRaisesRegex(ValueError, "nested source alias"):
                more.validate_inventory(amended)
            self.assertNotIn(collision, more.source_ids(entries))

    def test_nested_alias_collision_in_additional_inventory_is_rejected(self):
        entries = more.inventory()
        entries[0]["source_aliases"] = ["relation/17957127"]
        with patch.object(more, "_entries", return_value=entries):
            with self.assertRaisesRegex(ValueError, "nested source alias"):
                more.validate_inventory(landmarks.inventory())

    def test_belfry_has_open_legs_below_shuttered_bell_stage(self):
        class RecordingWriter(PsdlWriter):
            def __init__(self):
                super().__init__()
                self.blocks = []

            def building(self, poly, height, texture, roof="roof", base=2, **kwargs):
                self.blocks.append((poly, height, base))
                return super().building(poly, height, texture, roof, base, **kwargs)

        art = next(a for a in more.inventory() if a["kind"] == "belfry")
        footprint = box(0, 0, 9, 8)
        writer = RecordingWriter()
        more.render(
            writer,
            {"id": art["source_id"], "geometry": mapping(footprint), "base_y": 3},
            art,
        )
        legs = [p for p, h, base in writer.blocks if base == 3 and h == 8]
        self.assertEqual(len(legs), 4)
        self.assertLess(sum(p.area for p in legs), footprint.area * 0.1)
        self.assertTrue(
            any(
                base == 11 and h == art["body_height_m"] - 8
                for p, h, base in writer.blocks
            )
        )

    def test_every_entry_is_included_from_pinned_offline_snapshot(self):
        data = json.loads(more.ART_PATH.read_text())
        self.assertEqual(
            data["snapshot_sha256"],
            hashlib.sha256(self.snapshot_path.read_bytes()).hexdigest(),
        )
        for art in more.inventory():
            with self.subTest(landmark=art["name"]):
                feature = self.by_id[art["source_id"]]
                self.assertEqual(feature["tags"]["name"], art["name"])
                footprint = shape(feature["geometry"])
                self.assertFalse(footprint.is_empty)
                self.assertTrue(
                    shape(self.city["bounds"]).buffer(0.01).covers(footprint)
                )
                self.assertLess(
                    math.dist(footprint.centroid.coords[0], art["anchor_east_north_m"]),
                    0.02,
                )
                self.assertTrue(art["reference_url"].startswith("https://"))
                self.assertTrue(art["reference_image_page"].startswith("https://"))
                self.assertTrue(more.replaces(feature))

    def test_native_geometry_uses_actual_source_plan_with_finite_heights(self):
        total_vertices = 0
        for art in more.inventory():
            with self.subTest(landmark=art["name"]):
                feature = dict(self.by_id[art["source_id"]], base_y=8)
                writer = PsdlWriter()
                more.render(writer, feature, art)
                footprint = shape(feature["geometry"]).buffer(0.08)
                # Door panels stand 4 cm outside the sourced wall to avoid z-fighting.
                self.assertTrue(writer.rooms)
                for x, y, south in writer.vertices:
                    self.assertTrue(all(math.isfinite(v) for v in (x, y, south)))
                    from shapely.geometry import Point

                    self.assertTrue(footprint.covers(Point(x, -south)))
                    self.assertGreaterEqual(y, 8)
                self.assertAlmostEqual(
                    max(p[1] for p in writer.vertices),
                    8 + art["total_height_m"],
                    delta=3,
                )
                total_vertices += len(writer.vertices)
        # Allow detailed sourced perimeters while preventing accidental per-window
        # mesh growth in the seventy new silhouettes.
        self.assertLess(total_vertices, 28000)

    def test_roofs_do_not_close_source_courtyard_voids(self):
        class RecordingWriter(PsdlWriter):
            def __init__(self):
                super().__init__()
                self.surfaces = []

            def surface(self, geom, y, texture, **kwargs):
                self.surfaces.append(geom)
                return super().surface(geom, y, texture, **kwargs)

        art = next(a for a in more.inventory() if a["kind"] == "hip")
        footprint = box(0, 0, 80, 50).difference(box(20, 15, 55, 35))
        writer = RecordingWriter()
        more.render(
            writer, {"id": art["source_id"], "geometry": mapping(footprint)}, art
        )
        self.assertTrue(writer.surfaces)
        for surface in writer.surfaces:
            self.assertLess(surface.difference(footprint).area, 1e-6)
        from shapely.ops import unary_union

        self.assertAlmostEqual(unary_union(writer.surfaces).area, footprint.area)

    def test_export_appends_seventy_keeps_first_thirty_resources(self):
        city = copy.deepcopy(self.city)
        city["landmarks"] = [
            {"source_feature": a["source_id"]} for a in landmarks.inventory()
        ]
        first = copy.deepcopy(city["landmarks"])
        with tempfile.TemporaryDirectory() as temp:
            output = more.export(PsdlWriter(), city, temp)
            self.assertEqual(len(output), 70)
            self.assertEqual(len(city["landmarks"]), 100)
            self.assertEqual(city["landmarks"][:30], first)
            for art in more.inventory():
                self.assertTrue(
                    (Path(temp) / "texture" / f"{more.wall_texture(art)}.png").is_file()
                )
            self.assertEqual(len({a["source_feature"] for a in city["landmarks"]}), 100)


if __name__ == "__main__":
    unittest.main()

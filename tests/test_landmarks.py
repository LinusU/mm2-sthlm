"""Offline regressions for source anchoring and landmark-specific silhouettes."""

import math
import sys
import tempfile
import unittest
from pathlib import Path

from shapely.geometry import box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import landmarks
from sthlm import PsdlWriter


class LandmarkTests(unittest.TestCase):
    def test_thirty_unique_source_anchored_landmarks(self):
        art = landmarks.inventory()
        self.assertEqual(len(art), 30)
        self.assertEqual(len({a["source_id"] for a in art}), 30)
        self.assertEqual(sum(a["kind"] == "existing" for a in art), 4)
        for entry in art:
            self.assertGreater(entry["total_height_m"], entry["body_height_m"])
            self.assertTrue(entry["reference_url"].startswith(("https://", "assets/")))
            self.assertEqual(len(entry["anchor_east_north_m"]), 2)

    def test_every_override_emits_finite_native_geometry(self):
        for art in landmarks.inventory():
            with self.subTest(landmark=art["name"]):
                feature = {
                    "id": art["source_id"],
                    "geometry": mapping(
                        box(-470, -1220, -370, -1100)
                        if art["kind"] == "twin"
                        else box(0, 0, 70, 40)
                    ),
                    "base_y": 7,
                }
                if art["kind"] == "existing":
                    self.assertFalse(landmarks.replaces(feature))
                    continue
                writer = PsdlWriter()
                meta = landmarks.render(writer, feature, art)
                self.assertTrue(writer.rooms)
                self.assertTrue(
                    all(
                        math.isfinite(value)
                        for point in writer.vertices
                        for value in point
                    )
                )
                self.assertGreater(len(writer.vertices), 15)
                self.assertEqual(meta["source_feature"], feature["id"])
                self.assertAlmostEqual(
                    max(p[1] for p in writer.vertices),
                    7 + art["total_height_m"],
                    delta=3,
                )

    def test_export_keeps_existing_authored_landmarks(self):
        arts = landmarks.inventory()
        city = {
            "buildings": [
                {
                    "id": a["source_id"],
                    "geometry": mapping(box(0, 0, 70, 40)),
                    "rendering": {"preserved": True},
                }
                for a in arts
            ]
        }
        with tempfile.TemporaryDirectory() as temp:
            output = landmarks.export(PsdlWriter(), city, temp)
            self.assertEqual(len(output), 30)
            for art, feature in zip(arts, city["buildings"]):
                if art["kind"] == "existing":
                    self.assertEqual(feature["rendering"], {"preserved": True})
            self.assertTrue((Path(temp) / "texture/lm_ochre_clerestory.png").is_file())

    def test_nested_hogalids_relation_cannot_make_a_third_generic_spire(self):
        self.assertTrue(landmarks.replaces({"id": "relation/17957127"}))
        self.assertTrue(landmarks.replaces({"id": "relation/1257127"}))
        art = next(a for a in landmarks.inventory() if a["kind"] == "twin")
        feature = {
            "id": art["source_id"],
            "geometry": mapping(box(-460, -1200, -380, -1100)),
        }
        writer = PsdlWriter()
        landmarks.render(
            writer, feature, art, body_footprint=box(-455, -1190, -395, -1152)
        )
        tops = [p for p in writer.vertices if p[1] == 2 + art["total_height_m"]]
        self.assertEqual(len(tops), 2)
        for east, north in art["tower_centres_east_north_m"]:
            self.assertTrue(
                any(math.dist((p[0], -p[2]), (east, north)) < 1 for p in tops)
            )

    def test_concert_hall_columns_stand_in_open_portico(self):
        class RecordingWriter(PsdlWriter):
            def __init__(self):
                super().__init__()
                self.blocks = []

            def building(self, poly, height, texture, roof="roof", base=2, **kwargs):
                self.blocks.append((poly, height, texture))
                super().building(poly, height, texture, roof, base, **kwargs)

        art = next(a for a in landmarks.inventory() if a["kind"] == "columns")
        writer = RecordingWriter()
        landmarks.render(
            writer,
            {"id": art["source_id"], "geometry": mapping(box(0, 0, 70, 40))},
            art,
        )
        hall = next(
            poly
            for poly, height, texture in writer.blocks
            if texture == "lm_blue_bay" and height == art["body_height_m"]
        )
        columns = [
            poly
            for poly, height, texture in writer.blocks
            if texture == "lm_blue" and height == art["body_height_m"] - 2
        ]
        self.assertEqual(len(columns), 10)
        self.assertTrue(all(not hall.contains(column.centroid) for column in columns))
        self.assertLess(hall.area, 70 * 40 * 0.8)

    def test_library_is_rotunda_hogalids_is_twin(self):
        by_id = {a["source_id"]: a for a in landmarks.inventory()}
        self.assertEqual(by_id["way/31990167"]["kind"], "rotunda")
        self.assertEqual(by_id["relation/1257127"]["kind"], "twin")
        self.assertEqual(by_id["way/23841420"]["kind"], "lattice")


if __name__ == "__main__":
    unittest.main()

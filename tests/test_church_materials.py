import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import church_materials


class ChurchMaterialsTests(unittest.TestCase):
    def test_source_anchored_selection_does_not_repaint_other_churches(self):
        selected = church_materials.material_for({"id": "relation/1257127"})
        self.assertEqual(selected["textures"]["facade"], "church_facade")
        self.assertEqual(
            church_materials.material_for({"id": "relation/17957127"}), selected
        )
        self.assertIsNone(
            church_materials.material_for(
                {"id": "way/123", "tags": {"building": "church"}}
            )
        )
        self.assertIsNotNone(
            church_materials.material_for(
                {"id": "way/123", "tags": {"sthlm:material": "brick_church"}}
            )
        )

    def test_masonry_has_staggered_courses_and_muted_mortar(self):
        art = church_materials.profile()
        image = church_materials.masonry(art)
        mortar = tuple(art["mortar_rgb"])
        self.assertEqual(image.getpixel((0, 1)), mortar)
        self.assertNotEqual(image.getpixel((8, 1)), mortar)
        self.assertEqual(image.getpixel((8, 5)), mortar)
        self.assertNotEqual(image.getpixel((0, 5)), mortar)
        # Horizontal mortar courses meet both tile edges without a partial row.
        self.assertEqual(image.getpixel((0, 0)), image.getpixel((511, 0)))
        colors = set(image.getdata())
        self.assertGreater(len(colors), 10)
        self.assertTrue(all(max(color) < 180 for color in colors))

    def test_arch_is_narrow_tall_with_rounded_head_and_copper_sill(self):
        art = church_materials.profile()
        image = church_materials.masonry(art)
        original = image.copy()
        church_materials.arched_bay(image, art)
        glass = tuple(art["glass_rgb"])
        # Rounded head: near its corner remains masonry; center opens to glass.
        self.assertEqual(image.getpixel((214, 74)), original.getpixel((214, 74)))
        self.assertEqual(image.getpixel((252, 80)), glass)
        self.assertEqual(image.getpixel((230, 386)), glass)
        self.assertEqual(image.getpixel((230, 438)), tuple(art["copper_rgb"]))
        # Quiet side masonry instead of multiple rows of apartment windows.
        self.assertEqual(image.getpixel((70, 180)), original.getpixel((70, 180)))

    def test_export_is_deterministic_complete_and_uses_large_bays(self):
        with (
            tempfile.TemporaryDirectory() as first,
            tempfile.TemporaryDirectory() as second,
        ):
            metadata = church_materials.write(first)
            church_materials.write(second)
            self.assertEqual(metadata["facade_repeat_height_m"], 12)
            for name in metadata["textures"].values():
                a = Path(first) / "texture" / f"{name}.png"
                b = Path(second) / "texture" / f"{name}.png"
                self.assertEqual(
                    hashlib.sha256(a.read_bytes()).digest(),
                    hashlib.sha256(b.read_bytes()).digest(),
                )
                with Image.open(a) as image:
                    self.assertEqual(image.size, (512, 512))
                    self.assertEqual(image.mode, "RGB")

    def test_writer_uses_church_repeat_without_changing_legacy_defaults(self):
        from shapely.geometry import box
        import sthlm

        footprint = box(0, 0, 12, 6)
        legacy = sthlm.PsdlWriter()
        legacy.building(footprint, 24, "ochre")
        church = sthlm.PsdlWriter()
        church.building(
            footprint,
            24,
            "church_facade",
            "church_copper",
            facade_repeat_width_m=6,
            facade_repeat_height_m=12,
        )
        old_attrs = legacy.rooms[0][1]
        new_attrs = church.rooms[0][1]
        self.assertEqual([old_attrs[i] for i in (6, 20, 34, 48)], [8] * 4)
        self.assertEqual([new_attrs[i] for i in (6, 20, 34, 48)], [2] * 4)
        self.assertEqual([new_attrs[i] for i in (5, 19, 33, 47)], [1, 2, 1, 2])
        # The facade setting only changes material repeat attributes.
        self.assertEqual(legacy.vertices, church.vertices)

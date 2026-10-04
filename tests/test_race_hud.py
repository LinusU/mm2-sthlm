import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from minimap import read_chunks
from race_hud import arrow_package, glyph, validate_race_hud, write_race_hud


class RaceHudTests(unittest.TestCase):
    def test_zero_and_eight_have_distinct_readable_middle_segments(self):
        zero = glyph("0", (41, 56))
        eight = glyph("8", (41, 56))
        self.assertEqual(zero.getpixel((20, 28))[3], 0)
        self.assertEqual(eight.getpixel((20, 28))[3], 255)
        for digit in map(str, range(10)):
            image = glyph(digit, (21, 28))
            self.assertGreater(image.getchannel("A").getbbox()[2], 5)

    def test_arrow_native_geometry_faces_north_with_two_distinct_paints(self):
        chunks = read_chunks(arrow_package((0, 1, 0, 1)))
        self.assertEqual(struct.unpack_from("<2I", chunks["shaders"]), (2, 1))
        geometry = chunks["H"]
        self.assertEqual(struct.unpack_from("<5I", geometry), (1, 7, 9, 0, 2))
        vertices = [struct.unpack_from("<3f", geometry, 36 + i * 12) for i in range(7)]
        self.assertLess(vertices[0][2], 0)
        self.assertAlmostEqual(sum(v[0] for v in vertices), 0)

    def test_complete_native_stems_reproduce_identical_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            metadata = write_race_hud(out)
            before = {
                p: hashlib.sha256((out / p).read_bytes()).hexdigest()
                for p in metadata["resources"]
            }
            self.assertEqual(validate_race_hud(out)["glyphs"], 22)
            write_race_hud(out)
            self.assertEqual(
                before,
                {
                    p: hashlib.sha256((out / p).read_bytes()).hexdigest()
                    for p in metadata["resources"]
                },
            )
            (out / "texture/digitac_5_half.png").unlink()
            with self.assertRaisesRegex(ValueError, "Missing"):
                validate_race_hud(out)

"""Native manifest budget and unchanged world geometry across smaller pools."""

from pathlib import Path
import sys
import tempfile
import unittest

from shapely.geometry import Polygon, box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import sthlm
from expanded import ChunkedWriter


class CityChunkTests(unittest.TestCase):
    def manifest(self, package, entries):
        path = package / "city/stockholm.chunks"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("MM2_CHUNKS 1\n" + "\n".join(entries) + "\n")
        return {"city/stockholm.psdl": "verified", **dict.fromkeys(entries, "verified")}

    def test_native_accepts_at_most_129_parts_including_main(self):
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp)
            entries = [f"city/stockholm.parts/p{i}.psdl" for i in range(128)]
            checks = self.manifest(package, entries)
            self.assertEqual(len(sthlm.validated_city_parts(package, checks)), 129)
            entries.append("city/stockholm.parts/overflow.psdl")
            checks = self.manifest(package, entries)
            with self.assertRaisesRegex(ValueError, "129-part limit"):
                sthlm.validated_city_parts(package, checks)

    def test_native_paths_reject_duplicate_self_escape_or_unverified(self):
        for entries in [
            ["city/stockholm.psdl"],
            ["city/a.psdl", "city/a.psdl"],
            ["city/../a.psdl"],
            ["city//a.psdl"],
            ["city/./a.psdl"],
            ["geometry/a.psdl"],
            ["city/a.pkg"],
            ["city/a:b.psdl"],
            ["city/a\\b.psdl"],
        ]:
            with self.subTest(entries=entries), tempfile.TemporaryDirectory() as temp:
                package = Path(temp)
                checks = self.manifest(package, entries)
                with self.assertRaisesRegex(ValueError, "invalid or unverified"):
                    sthlm.validated_city_parts(package, checks)
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp)
            self.manifest(package, ["city/unverified.psdl"])
            with self.assertRaisesRegex(ValueError, "unverified"):
                sthlm.validated_city_parts(package, {})

    def test_comments_blank_lines_follow_native_parser(self):
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp)
            checks = self.manifest(package, ["city/a.psdl"])
            (package / "city/stockholm.chunks").write_text(
                "# comment\n MM2_CHUNKS 1 \n\n city/a.psdl \n# tail\n"
            )
            self.assertEqual(
                sthlm.validated_city_parts(package, checks),
                ["city/stockholm.psdl", "city/a.psdl"],
            )

    def test_no_additional_part_is_invalid_native_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp)
            checks = self.manifest(package, [])
            with self.assertRaisesRegex(ValueError, "no additional parts"):
                sthlm.validated_city_parts(package, checks)

    def test_750_m_pool_keeps_area_and_matching_world_seams(self):
        self.assertEqual(ChunkedWriter.PART_SIZE_M, 750)
        writer = ChunkedWriter([680, 8, -50])
        polygon = box(600, 0, 900, 200)
        writer.surface(
            polygon,
            lambda east, north: 4 + east * 0.003 + north * 0.001,
            "road",
            road=True,
        )
        self.assertEqual(set(writer.parts), {(0, 0), (1, 0)})
        seams = [set(part.vertices) for part in writer.parts.values()]
        common = seams[0] & seams[1]
        self.assertTrue(common)
        for east, height, south in common:
            self.assertAlmostEqual(height, 4 + east * 0.003 - south * 0.001, places=5)
        # Room boundaries retain source coverage in common global coordinates.
        area = sum(
            Polygon([(part.vertices[i][0], -part.vertices[i][2]) for i in room[0]]).area
            for part in writer.parts.values()
            for room in part.rooms
        )
        self.assertAlmostEqual(area, polygon.area)

    def test_writer_rejects_overflow_before_writing_assets(self):
        writer = ChunkedWriter([0, 2, 0])
        for i in range(130):
            writer.part(i * 750 + 5, 5).surface(
                box(i * 750, 0, i * 750 + 1, 1), 0, "grass"
            )
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "city/stockholm.psdl"
            with self.assertRaisesRegex(ValueError, "129-part limit"):
                writer.write(path, [0, 0, 0])
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()

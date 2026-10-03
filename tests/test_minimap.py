import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest

from PIL import Image
from shapely.geometry import box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from minimap import PALETTE, park_geometry, render, to_pixel, validate, write


def source_polygon(id, coords, tags):
    radius = 6378137
    nodes = [
        {
            "type": "node",
            "id": id * 10 + i,
            "lon": math.degrees(x / radius),
            "lat": math.degrees(n / radius),
        }
        for i, (x, n) in enumerate(coords)
    ]
    ids = [n["id"] for n in nodes]
    return nodes + [{"type": "way", "id": id, "nodes": ids + ids[:1], "tags": tags}]


def chunks(data):
    assert data[:4] == b"PKG3"
    out, pos = {}, 4
    while pos < len(data):
        assert data[pos : pos + 4] == b"FILE"
        length = data[pos + 4]
        name = data[pos + 5 : pos + 4 + length].decode()
        start = pos + 5 + length
        size = struct.unpack_from("<I", data, start)[0]
        out[name] = data[start + 4 : start + 4 + size]
        pos = start + 4 + size
    assert pos == len(data)
    return out


class MinimapTests(unittest.TestCase):
    def city(self):
        return {
            "origin": [0, 0],
            "land": mapping(box(0, 0, 1000, 1000)),
            "bounds": mapping(box(-100, -100, 1100, 1100)),
            "water": mapping(
                box(-100, -100, 1100, 1100).difference(box(0, 0, 1000, 1000))
            ),
            "roads": [{"points": [(100, 300), (900, 300)], "width": 10}],
        }

    def test_north_up_is_uniform_scale_and_places_source_features(self):
        source = {
            "elements": source_polygon(
                1, [(500, 650), (850, 650), (850, 950), (500, 950)], {"leisure": "park"}
            )
        }
        image, bounds, stats = render(self.city(), source, size=512)
        self.assertEqual(bounds[2] - bounds[0], bounds[3] - bounds[1])
        self.assertLess(to_pixel(500, 800, bounds)[1], to_pixel(500, 300, bounds)[1])
        self.assertLess(to_pixel(100, 500, bounds)[0], to_pixel(900, 500, bounds)[0])
        for point, color in [
            ((700, 800), "park"),
            ((200, 800), "land"),
            ((-100, 500), "water"),
            ((500, 300), "road"),
        ]:
            pixel = tuple(round(v) for v in to_pixel(*point, bounds, size=512))
            self.assertLessEqual(
                max(abs(a - b) for a, b in zip(image.getpixel(pixel), PALETTE[color])),
                15,
            )
        self.assertEqual(stats["polygons"], 1)

    def test_real_park_relation_preserves_hole_and_clips_excluded_land(self):
        elements = source_polygon(
            1, [(100, 100), (1200, 100), (1200, 900), (100, 900)], {}
        )
        elements += source_polygon(
            2, [(400, 400), (600, 400), (600, 600), (400, 600)], {}
        )
        elements.append(
            {
                "type": "relation",
                "id": 3,
                "tags": {"type": "multipolygon", "landuse": "grass"},
                "members": [
                    {"type": "way", "ref": 1, "role": "outer"},
                    {"type": "way", "ref": 2, "role": "inner"},
                ],
            }
        )
        from shapely.geometry import Point

        geometry, stats = park_geometry(
            self.city(), {"elements": elements}, box(0, 0, 1000, 1000)
        )
        self.assertTrue(geometry.covers(Point(200, 200)))
        self.assertFalse(geometry.covers(Point(500, 500)))
        self.assertFalse(geometry.covers(Point(1100, 500)))
        self.assertEqual(stats["polygons"], 1)

    def test_native_quad_uvs_match_north_up_texture_and_marker_paints(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            metadata = write(out, self.city())
            for path in metadata["resources"]:
                self.assertTrue((out / path).is_file(), path)
            geo = chunks((out / "geometry/hudmap_stockholm.pkg").read_bytes())["H"]
            self.assertEqual(struct.unpack_from("<5I", geo), (1, 4, 6, 0, 0x102))
            vertices = [struct.unpack_from("<5f", geo, 36 + i * 20) for i in range(4)]
            bounds = metadata["bounds_east_north_m"]
            for x, _, z, u, v in vertices:
                px, py = to_pixel(x, -z, bounds, size=1)
                self.assertAlmostEqual(u, px)
                self.assertAlmostEqual(1 - v, py)
            for marker, paints in [("tri", 10), ("square", 9)]:
                shaders = chunks((out / f"geometry/hudmap_{marker}.pkg").read_bytes())[
                    "shaders"
                ]
                self.assertEqual(struct.unpack_from("<2I", shaders), (paints, 1))
            with Image.open(out / metadata["texture"]) as image:
                self.assertEqual(image.mode, "RGB")
            (out / "minimap.json").write_text(json.dumps(metadata))
            self.assertEqual(validate(out)["tiles"], 1)
            data = bytearray((out / "geometry/hudmap_stockholm.pkg").read_bytes())
            # First tile X coordinate lives after PKG/chunk/header/strip records.
            struct.pack_into("<f", data, 51, 12345)
            (out / "geometry/hudmap_stockholm.pkg").write_bytes(data)
            with self.assertRaisesRegex(ValueError, "bounds/UV"):
                validate(out)
            tune = (out / "tune/stockholm.mmhudmap").read_text()
            self.assertIn("ZoomOutDistFS 6000", tune)
            self.assertIn("Ocean Color 0.047059 0.670588 0.835294", tune)

    def test_minimal_profile_fallback_is_deterministic(self):
        city = self.city()
        del city["land"]
        first, bounds, _ = render(city, size=128)
        second, again, _ = render(city, size=128)
        self.assertEqual(bounds, again)
        self.assertEqual(
            hashlib.sha256(first.tobytes()).digest(),
            hashlib.sha256(second.tobytes()).digest(),
        )
        center = tuple(round(v) for v in to_pixel(500, 700, bounds, size=128))
        self.assertEqual(first.getpixel(center), PALETTE["land"])

"""Original native race-instrument artwork; no proprietary fonts or sprites."""

import json
import struct

from PIL import Image, ImageDraw

from minimap import package, read_chunks

FULL_SIZE = (41, 56)
HALF_SIZE = (21, 28)
INK = (255, 255, 245, 255)
ACCENT = (255, 222, 72, 255)
SEGMENTS = (
    "abcedf",
    "bc",
    "abged",
    "abgcd",
    "fgbc",
    "afgcd",
    "afgecd",
    "abc",
    "abcdefg",
    "abfgcd",
)
ARROW_PAINTS = {
    "hudarrow01": (0.29, 0.89, 0.55, 1.0),
    "hudarrow_blitz01": (1.0, 0.36, 0.35, 1.0),
    "hudarrow_cc01": (0.72, 0.53, 0.98, 1.0),
}
BEHIND = tuple(c / 255 for c in ACCENT)


def glyph(character, size):
    """Draw a clean, bevel-ended seven-segment numeral on transparent pixels."""
    scale = 4
    image = Image.new("RGBA", (size[0] * scale, size[1] * scale))
    draw = ImageDraw.Draw(image)

    def polygon(points, color=INK):
        draw.polygon(
            [
                (round(x * scale * size[0] / 41), round(y * scale * size[1] / 56))
                for x, y in points
            ],
            fill=color,
        )

    def horizontal(y):
        return [(8, y), (33, y), (37, y + 3), (33, y + 6), (8, y + 6), (4, y + 3)]

    def vertical(x, y):
        return [
            (x + 3, y),
            (x + 6, y + 4),
            (x + 6, y + 17),
            (x + 3, y + 21),
            (x, y + 17),
            (x, y + 4),
        ]

    if character == ":":
        for y in (18, 36):
            polygon([(16, y), (23, y), (23, y + 7), (16, y + 7)], ACCENT)
    else:
        positions = {
            "a": horizontal(2),
            "g": horizontal(25),
            "d": horizontal(48),
            "f": vertical(3, 6),
            "b": vertical(32, 6),
            "e": vertical(3, 29),
            "c": vertical(32, 29),
        }
        for segment in SEGMENTS[int(character)]:
            polygon(positions[segment])
    return image.resize(size, Image.Resampling.LANCZOS)


def arrow_package(ahead):
    """A centred original arrow in XZ, tip toward -Z, with two native paints."""
    vertices = [
        (0, 0, -1.0),
        (0.9, 0, 0.1),
        (-0.9, 0, 0.1),
        (-0.32, 0, 0.1),
        (0.32, 0, 0.1),
        (0.32, 0, 1.0),
        (-0.32, 0, 1.0),
    ]
    return package(vertices, [0, 1, 2, 3, 4, 5, 3, 5, 6], [ahead, BEHIND])


def write_race_hud(out):
    """Write native texture/geometry stems and an original-art provenance record."""
    for directory in ("texture", "geometry"):
        (out / directory).mkdir(parents=True, exist_ok=True)
    resources = []
    for character in [*map(str, range(10)), ":"]:
        base = f"digitac_{character}" if character != ":" else "digi_colon"
        for suffix, size in (("", FULL_SIZE), ("_half", HALF_SIZE)):
            path = f"texture/{base}{suffix}.png"
            glyph(character, size).save(out / path)
            resources.append(path)
    for stem, ahead in ARROW_PAINTS.items():
        path = f"geometry/{stem}.pkg"
        (out / path).write_bytes(arrow_package(ahead))
        resources.append(path)
    metadata = {
        "schema": 1,
        "provenance": "Original procedural seven-segment polygons and arrow geometry authored in mm2-sthlm; Pillow is the rasterizer. No font, retail artwork or engine UI source copied.",
        "native_contract": "rust-mm2 069768a racetime.rs, racestat.rs, navarrow.rs: 22 glyph stems; full and half digits; two-paint flat XZ navigation arrows.",
        "full_glyph_px": list(FULL_SIZE),
        "half_glyph_px": list(HALF_SIZE),
        "resources": resources,
    }
    (out / "race_hud.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    )
    return metadata


def validate_race_hud(out):
    metadata = json.loads((out / "race_hud.json").read_text())
    for path in metadata["resources"]:
        if not (out / path).is_file():
            raise ValueError(f"Missing race HUD resource: {path}")
        if path.endswith(".png"):
            with Image.open(out / path) as image:
                expected = HALF_SIZE if "_half" in path else FULL_SIZE
                if image.mode != "RGBA" or image.size != expected:
                    raise ValueError(f"Invalid race HUD glyph: {path}")
                alpha = image.getchannel("A")
                if alpha.getextrema() != (0, 255) or alpha.getbbox() is None:
                    raise ValueError(f"Unreadable race HUD glyph: {path}")
        else:
            chunks = read_chunks((out / path).read_bytes())
            if struct.unpack_from("<2I", chunks["shaders"]) != (2, 1):
                raise ValueError(f"Invalid navigation arrow paints: {path}")
    return {"status": "pass", "glyphs": 22, "arrow_packages": 3}

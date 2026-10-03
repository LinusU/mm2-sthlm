"""Opt-in church materials authored from reference, without copied photo pixels.

Selection is source anchored: being a church alone does not imply red brick.
The same original material can be reused with the explicit sthlm:material tag.
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw

ART_PATH = Path(__file__).resolve().parents[1] / "assets/materials/church-brick.json"
SIZE = 512


def profile():
    return json.loads(ART_PATH.read_text())


def material_for(building):
    """Return a fresh profile for Högalid or explicitly opted-in source features."""
    art = profile()
    if (
        building.get("id") in art["source_features"]
        or building.get("tags", {}).get("sthlm:material") == art["profile"]
    ):
        return art
    return None


def masonry(art):
    """Running-bond brick: small courses, muted mortar, deterministic clay grain."""
    image = Image.new("RGB", (SIZE, SIZE), tuple(art["mortar_rgb"]))
    pixels = image.load()
    # A 6 x 12 m repeat: 16px bricks are 19cm wide; 4px courses are 9cm high.
    # The integer period wraps across both boundaries, including odd courses.
    for y in range(SIZE):
        row = y // 4
        for x in range(SIZE):
            # Thirty-two 16px bricks wrap exactly. The stagger is half a brick.
            column = (x + (8 if row % 2 else 0)) // 16
            if y % 4 == 0 or (x + (8 if row % 2 else 0)) % 16 == 0:
                continue
            variation = ((column * 13 + row * 7) % 15) - 7
            grain = ((x * 11 + y * 17) % 5) - 2
            pixels[x, y] = tuple(
                max(0, min(255, value + variation + grain))
                for value in art["brick_rgb"]
            )
    return image


def arched_bay(image, art, tower=False):
    """One tall narrow bay; the surrounding repeat remains quiet church masonry."""
    overlay = Image.new("RGBA", (256, 256))
    d = ImageDraw.Draw(overlay)
    left, right = (110, 145) if tower else (107, 148)
    top, bottom = (38, 211) if tower else (37, 217)
    radius = (right - left) // 2
    spring = top + radius
    # Brick arch surround with a dark recessed slot, never bright house frames.
    surround = tuple(value + 13 for value in art["brick_rgb"])
    d.ellipse((left - 4, top - 4, right + 4, spring + radius + 4), fill=surround)
    d.rectangle((left - 4, spring, right + 4, bottom + 4), fill=surround)
    glass = tuple(art["glass_rgb"])
    frame = tuple(art["frame_rgb"])
    d.ellipse((left, top, right, spring + radius), fill=glass, outline=frame, width=2)
    d.rectangle((left, spring, right, bottom), fill=glass)
    d.line(
        (left, spring, left, bottom, right, bottom, right, spring), fill=frame, width=2
    )
    center = (left + right) // 2
    d.line((center, top + 2, center, bottom), fill=frame, width=2)
    for y in range(spring + 12, bottom, 15):
        d.line((left + 2, y, right - 2, y), fill=frame, width=2)
        if tower:
            d.line((left + 3, y + 3, right - 3, y + 3), fill=(26, 32, 30), width=2)
    # Weathered green copper sill is restrained, matching the reference palette.
    d.polygon(
        [
            (left - 2, bottom + 1),
            (right + 2, bottom + 1),
            (right + 5, bottom + 6),
            (left - 5, bottom + 6),
        ],
        fill=tuple(art["copper_rgb"]),
    )
    overlay = overlay.resize(image.size, Image.Resampling.NEAREST)
    image.paste(overlay, (0, 0), overlay)


def copper(art):
    image = Image.new("RGB", (SIZE, SIZE))
    pixels = image.load()
    for y in range(SIZE):
        for x in range(SIZE):
            grain = ((x * 7 + y * 3) % 9) - 4
            seam = -22 if x % 32 < 2 else -9 if y % 64 == 0 else 0
            pixels[x, y] = tuple(
                max(0, value + grain + seam) for value in art["copper_rgb"]
            )
    return image


def write(out):
    """Write material PNGs to a map package's texture directory; return metadata."""
    art = profile()
    dest = Path(out) / "texture"
    dest.mkdir(parents=True, exist_ok=True)
    brick = masonry(art)
    brick.save(dest / f"{art['textures']['brick']}.png")
    for name, tower in [("facade", False), ("tower", True)]:
        image = brick.copy()
        arched_bay(image, art, tower=tower)
        image.save(dest / f"{art['textures'][name]}.png")
    copper(art).save(dest / f"{art['textures']['roof']}.png")
    return art

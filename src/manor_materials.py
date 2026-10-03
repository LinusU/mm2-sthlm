"""Original repeatable materials for Kristinehovs malmgård's three buildings."""

import json
from pathlib import Path
import random

from PIL import Image, ImageDraw

OVERRIDE_PATH = (
    Path(__file__).resolve().parents[1] / "config/overrides/kristinehov-materials.json"
)


def material_for(building):
    """Return an explicit source-ID override, leaving unrelated buildings alone."""
    override = json.loads(OVERRIDE_PATH.read_text())
    if building["id"] not in override["source_features"]:
        return None
    return {
        **override["materials"],
        "source_features": override["source_features"],
        "rule": override["rule"],
    }


def _plaster():
    image = Image.new("RGB", (256, 256))
    pixels = image.load()
    grain_source = random.Random(1790)
    for y in range(256):
        for x in range(256):
            # Seeded fine grain avoids directional bands and unstable outputs.
            grain = grain_source.randrange(-3, 4)
            pixels[x, y] = tuple(c + grain for c in (222, 214, 164))
    return image


def _facade():
    image = _plaster()
    draw = ImageDraw.Draw(image)
    # One tall six-pane window per 4.2 m bay, inspired by the supplied photo.
    # The muted gray-green surround belongs to the estate, unlike white modern
    # apartment frames. Window art is original; no photo pixels are sampled.
    draw.rectangle((90, 68, 165, 193), fill=(163, 167, 145))
    draw.rectangle((96, 74, 159, 187), fill=(81, 94, 78))
    for col in range(2):
        for row in range(3):
            left, top = 100 + col * 29, 78 + row * 35
            draw.rectangle(
                (left, top, left + 23, top + 29),
                fill=(67 + row * 3, 81 + row * 3, 73 + row * 2),
            )
            draw.line((left + 2, top + 2, left + 20, top + 2), fill=(94, 107, 93))
    draw.rectangle((87, 194, 168, 198), fill=(145, 154, 137))
    # Restrained eave molding and stone plinth stay at the bay's top and foot.
    draw.rectangle((0, 9, 255, 13), fill=(196, 192, 151))
    draw.line((0, 14, 255, 14), fill=(234, 227, 181), width=2)
    draw.rectangle((0, 244, 255, 255), fill=(157, 158, 139))
    return image


def _tiles():
    image = Image.new("RGB", (256, 256), (137, 105, 77))
    draw = ImageDraw.Draw(image)
    # Eight rows of narrow clay tiles: subdued aged ochre/terracotta with a few
    # moss-darkened tiles, rather than bright new red shingles or flat metal.
    for row in range(8):
        top = row * 32
        for col in range(16):
            left = col * 16
            variation = (row * 19 + col * 13) % 23 - 11
            color = tuple(c + variation for c in (146, 112, 79))
            if (row * 7 + col * 11) % 17 == 0:
                color = (116, 119, 80)
            draw.rectangle((left, top, left + 15, top + 31), fill=color)
            draw.line((left, top, left, top + 31), fill=(102, 87, 64), width=2)
            draw.line(
                (left + 4, top + 3, left + 4, top + 29),
                fill=tuple(c + 12 for c in color),
            )
            draw.line(
                (left, top + 30, left + 15, top + 30), fill=(101, 85, 61), width=2
            )
    return image


def write(out):
    """Write deterministic native PNG assets into a map output's texture folder."""
    destination = Path(out) / "texture"
    destination.mkdir(parents=True, exist_ok=True)
    for name, image in {
        "manor_plaster": _plaster(),
        "manor_facade": _facade(),
        "manor_tiles": _tiles(),
    }.items():
        image.save(destination / f"{name}.png")

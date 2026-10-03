#!/usr/bin/env python3
"""Opt-in native HUD-map binding and windowed evidence; not part of CI."""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sthlm import ROOT, sha, validate, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    engine = args.engine.resolve()
    package = ROOT / "dist/stockholm"
    validate(package)
    meta = json.loads((package / "map.json").read_text())
    output = ROOT / "evidence/minimap"
    output.mkdir(parents=True, exist_ok=True)
    common = [
        str(engine),
        "--mods",
        str(package.parent),
        "--city",
        "stockholm",
        "--no-profile",
        "--spawn=" + ",".join(map(str, meta["spawn"])),
        "--parked",
        "--time-of-day",
        "1",
    ]
    reports = {}
    modes = [
        ("cruise", ["--headless", "--frames", "120"]),
        ("circuit", ["--event", "circuit:0", "--headless", "--frames", "120"]),
        ("restart", ["--headless", "--frames", "400", "--restart-at", "650"]),
    ]
    if args.capture:
        modes += [
            ("inset", ["--frames", "60", "--screenshot", str(output / "inset.png")]),
            (
                "fullscreen",
                [
                    "--pause-map",
                    "--frames",
                    "60",
                    "--screenshot",
                    str(output / "fullscreen.png"),
                ],
            ),
        ]
    with tempfile.TemporaryDirectory(prefix="sthlm-minimap-cwd-") as cwd:
        for name, flags in modes:
            command = common + flags
            result = subprocess.run(
                command,
                cwd=cwd,
                env={**os.environ, "RUST_LOG": "info"},
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=240,
            )
            (output / f"{name}.log").write_text(result.stdout)
            revision = re.search(r"mm2-smoke commit=([^\s]+)", result.stdout)
            if not revision or revision[1] not in meta["compatible_revisions"]:
                raise RuntimeError(f"untested engine revision: {name}")
            records = [s for s in result.stdout.splitlines() if s.startswith("smoke=")]
            if result.returncode or not records or "status=pass" not in records[-1]:
                raise RuntimeError(f"native map probe failed: {name}")
            record = records[-1]
            if name in {"cruise", "circuit", "restart"}:
                match = re.search(r" map=([^ ]+)", record)
                if not match or "/hudmap_stockholm.pkg/1t/" not in match[1]:
                    raise RuntimeError(f"native map not bound: {name}")
                markers = int(match[1].rsplit("/", 1)[1].removesuffix("m"))
                expected = (
                    len(
                        json.loads((package / "normalized.json").read_text())[
                            "drive_gates"
                        ]
                    )
                    if name == "circuit"
                    else 1
                )
                if markers != expected:
                    raise RuntimeError(
                        f"unexpected map marker count: {name}: {markers} != {expected}"
                    )
                if name == "restart" and "rs=1" not in record:
                    raise RuntimeError("restart did not execute")
            else:
                if not (output / f"{name}.png").is_file():
                    raise RuntimeError(f"capture missing: {name}")
                palette = json.loads((package / "minimap.json").read_text())[
                    "palette_rgb"
                ]
                with Image.open(output / f"{name}.png") as image:
                    image = image.convert("RGB")
                    counts = Counter(image.getdata())
                    palette_pixels = {
                        key: counts[tuple(palette[key])]
                        for key in ["water", "land", "park"]
                    }
                    if not all(count > 100 for count in palette_pixels.values()):
                        raise RuntimeError(
                            f"authored map palette not preserved: {name}"
                        )
                    if name == "fullscreen":
                        corners = [
                            (0, 0),
                            (image.width - 1, 0),
                            (0, image.height - 1),
                            (image.width - 1, image.height - 1),
                        ]
                        if any(
                            image.getpixel(p) != tuple(palette["water"])
                            for p in corners
                        ):
                            raise RuntimeError(
                                "full-screen map background is not opaque ocean"
                            )
            reports[name] = {
                "command": command,
                "record": record,
                "engine_revision": revision[1],
            }
            if name in {"inset", "fullscreen"}:
                reports[name]["palette_pixel_counts"] = palette_pixels
    write_json(
        output / "acceptance.json",
        {
            "status": "pass",
            "package_manifest_sha256": sha(package / "checksums.json"),
            "engine_binary_sha256": sha(engine),
            "reports": reports,
            "screenshots": {
                f"{name}.png": sha(output / f"{name}.png")
                for name in ["inset", "fullscreen"]
                if args.capture
            },
            "processing": "Unmodified in-game PNGs; headless records are binding evidence only.",
        },
    )
    print("minimap=pass native-map=bound")


if __name__ == "__main__":
    main()

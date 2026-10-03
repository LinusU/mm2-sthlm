#!/usr/bin/env python3
"""Explicit engine integration; normal offline map CI does not run this."""

import argparse
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import sthlm
from shapely.geometry import box


def run(engine, args, cwd, log):
    result = subprocess.run(
        [str(engine), *args],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    log.write_text(result.stdout)
    if result.returncode:
        raise RuntimeError(f"engine failed ({result.returncode}): {log}")
    records = [
        s for s in result.stdout.splitlines() if s.startswith("smoke=headless-physics ")
    ]
    if not records or "status=pass " not in records[-1]:
        raise RuntimeError(f"no passing engine record: {log}")
    return records[-1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--engine", required=True, type=Path)
    p.add_argument(
        "--output", type=Path, help="Evidence directory; keeps historical runs separate"
    )
    args = p.parse_args()
    engine = args.engine.resolve()
    package = sthlm.ROOT / "dist/stockholm"
    sthlm.validate(package)
    meta = json.loads((package / "map.json").read_text())
    output = args.output or sthlm.ROOT / (
        "evidence/expanded" if meta.get("profile") == "expanded" else "evidence"
    )
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mm2-sthlm-portability-") as tmp:
        root = Path(tmp)
        (root / "empty-cwd").mkdir()
        relocated = root / "maps/stockholm"
        shutil.copytree(package, relocated)
        # Verify without sources/config/generator next to the copied package.
        sthlm.validate(relocated)
        spawn = "--spawn=" + ",".join(str(v) for v in meta["spawn"])
        drive = run(
            engine,
            [
                "--mods",
                str(relocated.parent),
                "--city",
                "stockholm",
                "--no-profile",
                spawn,
                "--event",
                "circuit:0",
                "--bot",
                "--bot-speed",
                "8",
                "--headless",
                "--frames",
                "15000",
            ],
            root / "empty-cwd",
            output / "portability.log",
        )
        sthlm.validate_drive_record(drive)
        writer = sthlm.PsdlWriter()
        writer.surface(box(-20, -20, 20, 100), 2, "road", road=True)
        tiny = root / "tiny-maps/triangle"
        writer.write(tiny / "city/triangle.psdl", [0, 2, 0])
        second = sthlm.PsdlWriter()
        second.surface(box(-20, 100, 20, 400), 2, "road", road=True)
        second.write(tiny / "city/triangle.parts/north.psdl", [0, 2, -200])
        (tiny / "city/triangle.chunks").write_text(
            "MM2_CHUNKS 1\ncity/triangle.parts/north.psdl\n"
        )
        sthlm.textures(tiny / "texture")
        (tiny / "mod.toml").write_text(
            '[mod]\nid="triangle"\nname="Independent test map"\nversion="1"\n'
        )
        tiny_record = run(
            engine,
            [
                "--mods",
                str(tiny.parent),
                "--city",
                "triangle",
                "--spawn=0,3.5,0,0",
                "--no-profile",
                "--headless",
                "--frames",
                "800",
            ],
            root / "empty-cwd",
            output / "second-map.log",
        )
        # Missing chunks must fail loudly, even with a valid primary PSDL.
        (tiny / "city/triangle.parts/north.psdl").unlink()
        broken = subprocess.run(
            [
                str(engine),
                "--mods",
                str(tiny.parent),
                "--city",
                "triangle",
                "--no-profile",
                "--headless",
                "--frames",
                "10",
            ],
            cwd=root / "empty-cwd",
            capture_output=True,
            text=True,
        )
        (output / "missing-part.log").write_text(broken.stdout + broken.stderr)
        if broken.returncode == 0 or "status=fail" not in broken.stdout + broken.stderr:
            raise RuntimeError("missing chunk silently accepted")
        sthlm.write_json(
            output / "portability.json",
            {
                "status": "pass",
                "stockholm_record": drive,
                "second_map_record": tiny_record,
                "missing_chunk_rejected": True,
                "working_directory": "empty temporary directory",
                "source_tree_beside_package": False,
                "package_manifest_sha256": sthlm.sha(package / "checksums.json"),
                "engine": str(engine),
                "engine_binary_sha256": sthlm.sha(engine),
                "engine_revision": re.search(
                    r"mm2-smoke commit=([^\s]+)",
                    (output / "portability.log").read_text(),
                ).group(1),
            },
        )
    print("portability=pass second-independent-city=pass")


if __name__ == "__main__":
    main()

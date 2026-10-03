#!/usr/bin/env python3
"""Explicit engine integration; normal offline map CI does not run this."""

import argparse
import json
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
    args = p.parse_args()
    engine = args.engine.resolve()
    package = sthlm.ROOT / "dist/stockholm"
    sthlm.validate(package)
    output = sthlm.ROOT / "evidence"
    meta = json.loads((package / "map.json").read_text())
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
        writer.surface(box(-20, -20, 20, 250), 2, "road", road=True)
        tiny = root / "tiny-maps/triangle"
        writer.write(tiny / "city/triangle.psdl", [0, 2, 0])
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
                "400",
            ],
            root / "empty-cwd",
            output / "second-map.log",
        )
        sthlm.write_json(
            output / "portability.json",
            {
                "status": "pass",
                "stockholm_record": drive,
                "second_map_record": tiny_record,
                "working_directory": "empty temporary directory",
                "source_tree_beside_package": False,
                "package_manifest_sha256": sthlm.sha(package / "checksums.json"),
                "engine": str(engine),
            },
        )
    print("portability=pass second-independent-city=pass")


if __name__ == "__main__":
    main()

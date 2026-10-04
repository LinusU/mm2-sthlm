#!/usr/bin/env python3
"""Optional external-engine shallow basin probe. No engine/network in normal CI."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image
from shapely.geometry import Polygon, box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import ponds
import sthlm


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output / "mods/shallow-probe"
    (out / "texture").mkdir(parents=True, exist_ok=True)
    (out / "city/stockholm").mkdir(parents=True, exist_ok=True)
    poly = box(0, 0, 20, 20)
    city = {
        "bounds": mapping(box(-50, -50, 100, 80)),
        "road_surface": mapping(Polygon()),
        "shallow_water": [
            {"id": "probe/24m-basin", "geometry": mapping(poly), "depth_m": 0.2}
        ],
    }
    records = ponds.prepare(city, None, lambda x, n: 24)
    writer = sthlm.PsdlWriter()
    deep = box(65, 40, 90, 65)
    writer.surface(
        box(-50, -50, 100, 80)
        .difference(ponds.partition_geometry(records))
        .difference(deep),
        24,
        "grass",
    )
    ponds.write_mesh(writer, records, lambda x, n: 24)
    writer.surface(deep, 0, "water", water=True)
    writer.write(out / "city/stockholm.psdl", [-10, 24, -10])
    (out / "city/stockholm.water").write_text(
        "0.2\n" + "".join(f"{r}\n" for r in writer.water_rooms)
    )
    for name, rgb in {
        "grass": (90, 120, 80),
        "paving": (140, 140, 125),
        "water": (30, 70, 120),
    }.items():
        Image.new("RGB", (8, 8), rgb).save(out / f"texture/{name}.png")
    ponds.write(out, city)
    (out / "mod.toml").write_text(
        '[mod]\nid="shallow-probe"\nname="Original shallow-water probe"\nversion="1.0.0"\nauthor="mm2-sthlm contributors"\n'
    )
    results = []
    for frames in (180, 260, 600):
        cmd = [
            str(args.engine),
            "--mods",
            str(args.output / "mods"),
            "--city",
            "stockholm",
            "--no-profile",
            "--headless",
            "--frames",
            str(frames),
            "--spawn=-10,25.5,-10,270",
        ]
        result = subprocess.run(
            cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        (args.output / f"drive-{frames}.log").write_text(result.stdout)
        lines = [line for line in result.stdout.splitlines() if "smoke=" in line]
        results.append(
            {
                "command": cmd,
                "exit_code": result.returncode,
                "smoke": lines[-1] if lines else "missing",
            }
        )
        print(json.dumps(results[-1]))
    sthlm.write_json(args.output / "probe-results.json", results)
    positions = [
        re.search(r"final=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)", r["smoke"])
        for r in results
    ]
    if (
        not all(positions)
        or not 0 < float(positions[1][1]) < 20
        or float(positions[2][1]) <= 24
    ):
        raise SystemExit("vehicle did not demonstrate entry and exit across basin")
    if any(
        r["exit_code"] != 0
        or "resets=0" not in r["smoke"]
        or "finite=true" not in r["smoke"]
        or "wheels=4/4" not in r["smoke"]
        or " rcv=" in r["smoke"]
        for r in results
    ):
        raise SystemExit("native probe failed; inspect evidence logs")


if __name__ == "__main__":
    main()

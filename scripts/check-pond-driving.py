#!/usr/bin/env python3
"""Optional real-source shallow basin crossings in a separately built engine."""

import argparse
import hashlib
import json
import re
import subprocess
import shutil
import tempfile
from pathlib import Path
from shapely.geometry import LineString, Point, shape

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("way/219139744", 1460.2599200533741, -449.08899758578923, 480),
    ("way/28165044", -187.63303302607116, -847.1082855519375, 800),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    engine = args.engine.resolve()
    package = ROOT / "dist/stockholm"
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sthlm-source-ponds-") as tmp:
        relocated = Path(tmp) / "mods/stockholm"
        shutil.copytree(package, relocated)
        return run_cases(engine, relocated, output)


def run_cases(engine, package, output):
    city = json.loads((package / "normalized.json").read_text())
    basins = {record["id"]: record for record in city["shallow_water"]}
    results = []
    for source, x, z, frames in CASES:
        basin = basins[source]
        poly = shape(basin["geometry"])
        spawn = [x, basin["water_level_m"] + 1.6, z, 270]
        if poly.covers(Point(x, -z)) or not poly.intersects(
            LineString([(x, -z), (x + 100, -z)])
        ):
            raise ValueError(
                source + ": source basin no longer lies ahead of the approach"
            )
        command = [
            str(engine),
            "--mods",
            str(package.parent),
            "--city",
            "stockholm",
            "--no-profile",
            "--headless",
            "--frames",
            str(frames),
            "--spawn=" + ",".join(map(str, spawn)),
        ]
        run = subprocess.run(command, capture_output=True, text=True)
        log = run.stdout + run.stderr
        name = source.replace("/", "-")
        (output / (name + ".log")).write_text(log)
        records = [
            line
            for line in log.splitlines()
            if line.startswith("smoke=headless-physics ")
        ]
        record = records[-1] if records else ""
        final = re.search(r"final=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)", record)
        endpoint = [float(value) for value in final.groups()] if final else None
        traversed = bool(
            endpoint
            and not poly.covers(Point(endpoint[0], -endpoint[2]))
            and endpoint[0] > poly.bounds[2] + 1
            and LineString([(x, -z), (endpoint[0], -endpoint[2])])
            .intersection(poly)
            .length
            > 1
        )
        passed = (
            run.returncode == 0
            and traversed
            and all(
                token in record
                for token in [
                    "status=pass ",
                    "impacts=0 ",
                    "resets=0 ",
                    "finite=true ",
                    "wheels=4/4 ",
                ]
            )
            and "w_rec=" not in record
        )
        results.append(
            {
                "source_id": source,
                "water_level_m": basin["water_level_m"],
                "depth_m": basin["depth_m"],
                "command": command,
                "record": record,
                "far_bank_exit": traversed,
                "passed": passed,
            }
        )
        print(source, "PASS" if passed else "FAIL", record, flush=True)
    (output / "source-basin-probes.json").write_text(
        json.dumps(
            {
                "engine_binary_sha256": hashlib.sha256(engine.read_bytes()).hexdigest(),
                "package_manifest_sha256": hashlib.sha256(
                    (package / "checksums.json").read_bytes()
                ).hexdigest(),
                "scope": "Actual source basin crossings with authored shallow depth. Hold driver, zero steering; final position beyond far bank. Normal map CI does not require this engine.",
                "results": results,
            },
            indent=2,
        )
        + "\n"
    )
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

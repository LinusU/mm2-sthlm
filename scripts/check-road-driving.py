#!/usr/bin/env python3
"""Optional native source-road probes in a separate temporary map package."""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from shapely.geometry import LineString

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from elevation import RoadField  # noqa: E402
from terrain import TerrainGrid  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--case",
        action="append",
        required=True,
        help="source_way:start_station:end_station",
    )
    parser.add_argument("--frames", type=int, default=800)
    parser.add_argument("--speed", type=float, default=6)
    args = parser.parse_args()
    if args.frames <= 0 or args.speed <= 0:
        parser.error("frames and speed must be positive")
    original = ROOT / "dist/stockholm"
    city = json.loads((original / "normalized.json").read_text())
    terrain = TerrainGrid.from_project(ROOT, city["origin"])
    roads = {r["id"]: r for r in city["roads"]}
    args.output.mkdir(parents=True, exist_ok=True)
    reports = []
    with tempfile.TemporaryDirectory(prefix="sthlm-road-probes-") as tmp:
        package = Path(tmp) / "stockholm"
        shutil.copytree(original, package)
        race = package / "race/stockholm/circuit0waypoints.csv"
        for case in args.case:
            way, start, end = case.split(":")
            way, start, end = int(way), float(start), float(end)
            road = roads[way]
            line = LineString(road["points"])
            if not 0 <= start < end <= line.length:
                raise ValueError(f"invalid source stations: {case}")
            field = RoadField([road], terrain, bridge=True)
            stations = [start + i * 5 for i in range(math.ceil((end - start) / 5))] + [
                end
            ]
            gates = []
            for station in stations:
                p = line.interpolate(station)
                gates.append([p.x, field.height_at_station(road, station), -p.y])
            a, b = gates[:2]
            spawn = [
                a[0],
                a[1] + 1.5,
                a[2],
                math.degrees(math.atan2(-(b[0] - a[0]), -(b[2] - a[2]))),
            ]
            csv = (
                "x,y,z,a,poly count,frame rate,state changes,texture changes,msg\n"
                + "".join(f"{x:.5f},{y:.5f},{z:.5f},0,5,0,0,0,\n" for x, y, z in gates)
            )
            race.write_text(csv)
            command = [
                str(args.engine.resolve()),
                "--mods",
                tmp,
                "--city",
                "stockholm",
                "--no-profile",
                "--spawn=" + ",".join(map(str, spawn)),
                "--event",
                "circuit:0",
                "--bot",
                "--bot-speed",
                str(args.speed),
                "--headless",
                "--frames",
                str(args.frames),
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            log = result.stdout + result.stderr
            (args.output / f"way-{way}.log").write_text(log)
            records = [
                s for s in log.splitlines() if s.startswith("smoke=headless-physics ")
            ]
            record = records[-1] if records else ""
            travel = re.search(r"travel=([0-9.]+)m", record)
            minimum_travel = min(
                (end - start) / 2, max(5, (args.frames - 180) / 60 * args.speed * 0.8)
            )
            passed = (
                travel is not None
                and float(travel[1]) >= minimum_travel
                and result.returncode == 0
                and all(
                    t in record
                    for t in (
                        "status=pass ",
                        "impacts=0 ",
                        "resets=0 ",
                        "finite=true ",
                        "wheels=4/4 ",
                    )
                )
            )
            report = {
                "case": case,
                "gates": gates,
                "course_csv_sha256": hashlib.sha256(csv.encode()).hexdigest(),
                "command": command,
                "record": record,
                "passed": passed,
                "minimum_travel_m": minimum_travel,
            }
            reports.append(report)
            print(f"{case}: {'PASS' if passed else 'FAIL'} {record}", flush=True)
    manifest = {
        "engine_binary_sha256": hashlib.sha256(args.engine.read_bytes()).hexdigest(),
        "package_manifest_sha256": hashlib.sha256(
            (original / "checksums.json").read_bytes()
        ).hexdigest(),
        "scope": "Open source-road courses, not complete race loops. Temporary race fixtures alter only the CSV; main package is unchanged.",
        "reports": reports,
    }
    (args.output / "source-road-probes.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    if not all(r["passed"] for r in reports):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

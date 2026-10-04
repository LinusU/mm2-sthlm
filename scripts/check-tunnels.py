#!/usr/bin/env python3
"""Explicit native-engine source-corridor trips; never part of offline map CI."""

import argparse
import hashlib
import shutil
import tempfile
import json
import math
import re
import subprocess
import sys
from pathlib import Path

from shapely.geometry import LineString, Point

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from elevation import RoadField
from terrain import TerrainGrid
from races import OPP_HEADER

ROOT = Path(__file__).resolve().parents[1]


def source_course(city, terrain, way_id, approach_m=0, start_m=30, spacing=5):
    """Return native XYZ gates using only retained, genuinely connected sources.

    This helper also works for upper/lower bridge courses. Heights come from
    each source way separately so an XY crossing cannot select another level.
    """
    roads = {r["id"]: r for r in city["roads"]}
    road = roads[way_id]
    pieces = []
    if approach_m:
        node = road["nodes"][0]
        candidates = sorted(
            (
                r
                for r in city["roads"]
                if r["id"] != way_id
                and r["id"] not in city.get("tunnel_ways", [])
                and node in (r["nodes"][0], r["nodes"][-1])
            ),
            key=lambda r: r["id"],
        )
        if not candidates:
            raise ValueError(f"way/{way_id}: no retained source-connected approach")
        approach = candidates[0]
        line = LineString(approach["points"])
        if approach["nodes"][-1] == node:
            pieces.append((approach, max(0, line.length - approach_m), line.length))
        else:
            pieces.append((approach, min(approach_m, line.length), 0))
        start_m = 0
    line = LineString(road["points"])
    if start_m >= line.length - 10:
        start_m = 0
    pieces.append((road, start_m, line.length - 5))
    gates, sources, distance = [], [], 0.0
    for source, start, end in pieces:
        line = LineString(source["points"])
        field = RoadField([source], terrain, bridge=True)
        count = max(1, math.ceil(abs(end - start) / spacing))
        for i in range(count + 1):
            station = start + (end - start) * i / count
            p = line.interpolate(station)
            y = (
                field.height_at_station(source, station)
                if hasattr(field, "height_at_station")
                else field(p.x, p.y)
            )
            gate = [p.x, y, -p.y]
            if gates and math.dist(gate[::2], gates[-1][::2]) < 0.01:
                continue
            if gates:
                distance += math.dist(gate[::2], gates[-1][::2])
            gates.append(gate)
        sources.append(source["id"])
    return gates, sources, distance


def run_probe(
    engine,
    package,
    city,
    terrain,
    way_id,
    approach_m,
    output,
    speed=6,
    frames=1800,
    guided=False,
):
    gates, sources, length = source_course(city, terrain, way_id, approach_m)
    if len(gates) < 3:
        raise ValueError(f"way/{way_id}: source course is too short")
    a, b = gates[:2]
    yaw = math.degrees(math.atan2(-(b[0] - a[0]), -(b[2] - a[2])))
    spawn = [a[0], a[1] + 1.5, a[2], yaw]
    # Finish before an open course circuit tries to return through a fictitious
    # closing edge. This is a driving probe, not a new distributed race route.
    frames = min(
        frames,
        max(
            240,
            int((length - (3 if approach_m and length < 100 else 15)) / speed * 60)
            + 180,
        ),
    )
    command = [
        str(engine),
        "--mods",
        str(package.parent),
        "--city",
        "stockholm",
        "--no-profile",
        "--spawn=" + ",".join(map(str, spawn)),
        "--event",
        "circuit:0",
        "--bot",
        "--bot-speed",
        str(speed),
        "--headless",
        "--frames",
        str(frames),
    ]
    if guided:
        guide = package / "qa/source-probe.opp"
        guide.parent.mkdir(parents=True, exist_ok=True)
        guide.write_text(
            OPP_HEADER
            + "".join(
                ",".join(map(str, [*point, yaw if i == 0 else 0, 0, 0, speed, 0, 0]))
                + "\n"
                for i, point in enumerate(gates)
            )
        )
        command += ["--bot-route", str(guide)]
    route = package / "race/stockholm/circuit0waypoints.csv"
    original = route.read_bytes()
    label = f"{'portal' if approach_m else 'way'}-{way_id}"
    try:
        route.write_text(
            "x,y,z,a,poly count,frame rate,state changes,texture changes,msg\n"
            + "".join(
                f"{x:.5f},{y:.5f},{z:.5f},"
                f"{math.degrees(math.atan2(-(gates[min(i + 1, len(gates) - 1)][0] - gates[max(0, i - 1)][0]), gates[min(i + 1, len(gates) - 1)][2] - gates[max(0, i - 1)][2])):.5f},"
                "5,0,0,0,\n"
                for i, (x, y, z) in enumerate(gates)
            )
        )
        result = subprocess.run(command, capture_output=True, text=True)
    finally:
        route.write_bytes(original)
    log = result.stdout + result.stderr
    (output / f"{label}.log").write_text(log)
    records = [s for s in log.splitlines() if s.startswith("smoke=headless-physics")]
    record = records[-1] if records else ""
    travel = re.search(r"travel=([0-9.]+)m", record)
    final = re.search(r"final=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)", record)
    final_station = (
        LineString([(point[0], point[2]) for point in gates]).project(
            Point(float(final[1]), float(final[3]))
        )
        if final
        else None
    )
    crossed_join = not approach_m or (
        final_station is not None and final_station > approach_m + 1
    )
    required = max(5, (frames - 180) / 60 * speed * 0.8)
    passed = (
        result.returncode == 0
        and all(
            token in record
            for token in (
                "status=pass ",
                "impacts=0 ",
                "resets=0 ",
                "finite=true ",
                "wheels=4/4 ",
            )
        )
        and ("p_rec=" not in record or "p_rec=0r/0e" in record)
        and crossed_join
        and travel is not None
        and float(travel[1]) >= required
    )
    return {
        "source_way": way_id,
        "course_sources": sources,
        "approach_m": approach_m,
        "course_length_m": length,
        "minimum_travel_m": required,
        "final_source_station_m": final_station,
        "crossed_source_join": crossed_join,
        "command": command,
        "record": record,
        "passed": passed,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--package", type=Path, default=ROOT / "dist/stockholm")
    parser.add_argument("--output", type=Path, default=ROOT / "evidence/tunnels")
    parser.add_argument(
        "--way",
        action="append",
        type=int,
        help="Drive a retained source road; may repeat for bridge layers",
    )
    parser.add_argument(
        "--portal-way",
        action="append",
        type=int,
        help="Include 40 m of a real shared-node surface approach",
    )
    parser.add_argument("--frames", type=int, default=1800)
    parser.add_argument("--speed", type=float, default=6)
    parser.add_argument(
        "--guided",
        action="store_true",
        help="Requires the generic explicit-route engine support in PR6",
    )
    args = parser.parse_args()
    if args.speed <= 0 or args.frames < 240:
        parser.error("speed must be positive; frames must be at least 240")
    original_package = args.package.resolve()
    sandbox = tempfile.TemporaryDirectory(prefix="stockholm-tunnel-probes-")
    package = Path(sandbox.name) / "stockholm"
    shutil.copytree(original_package, package)
    fixture = package / "qa/waterfront"
    if fixture.exists():
        # Isolated zero-opponent probe, independent of authored player races.
        shutil.copytree(fixture, package / "race/stockholm", dirs_exist_ok=True)
    city = json.loads((package / "normalized.json").read_text())
    terrain = TerrainGrid.from_project(ROOT, city["origin"])
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cases = [(wid, 0) for wid in args.way or []] + [
        (wid, 40) for wid in args.portal_way or []
    ]
    if not cases:
        cases = [(432147270, 0), (20278071, 0), (151884980, 0), (4700200, 40)]
    reports = []
    for way_id, approach in cases:
        report = run_probe(
            args.engine.resolve(),
            package,
            city,
            terrain,
            way_id,
            approach,
            output,
            args.speed,
            args.frames,
            args.guided,
        )
        report["engine_sha256"] = hashlib.sha256(
            args.engine.resolve().read_bytes()
        ).hexdigest()
        report["package_manifest_sha256"] = hashlib.sha256(
            (original_package / "checksums.json").read_bytes()
        ).hexdigest()
        reports.append(report)
        print(
            f"way/{way_id}: {'PASS' if report['passed'] else 'FAIL'} {report['record']}",
            flush=True,
        )
    (output / "native-source-probes.json").write_text(
        json.dumps(reports, indent=2) + "\n"
    )
    sandbox.cleanup()
    return 0 if all(r["passed"] for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())

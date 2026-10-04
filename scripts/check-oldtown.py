#!/usr/bin/env python3
"""Opt-in actual-engine Old Town captures and source-street vehicle drives."""

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

from shapely.geometry import LineString, Point

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from oldtown import project  # noqa: E402
from sthlm import shortest  # noqa: E402

EXPECTED_ENGINE = "b3d9804489bdcd576dd4b85b3f40fec75c545071"


def street_route(city, name):
    graph, positions, heights = {}, {}, {}
    roads = [r for r in city["roads"] if r["tags"].get("name") == name]
    for road in roads:
        samples = road["elevated_points"]
        line = LineString([p[:2] for p in samples])
        stations = [line.project(Point(p[:2])) for p in samples]
        for node, point in zip(road["nodes"], road["points"]):
            positions[node] = point
            station = line.project(Point(point))
            nearest = min(range(len(samples)), key=lambda i: abs(stations[i] - station))
            heights[node] = samples[nearest][2]
        for a, b in zip(road["nodes"], road["nodes"][1:]):
            length = math.dist(positions[a], positions[b])
            graph.setdefault(a, {})[b] = length
            graph.setdefault(b, {})[a] = length
    ends = [n for n in graph if len(graph[n]) == 1]
    candidates = []
    for a in ends:
        for b in ends:
            if a == b:
                continue
            try:
                path = shortest(graph, a, b)
            except ValueError:
                continue
            length = sum(
                math.dist(positions[x], positions[y]) for x, y in zip(path, path[1:])
            )
            candidates.append((length, path))
    _, nodes = max(candidates)
    return [[*positions[n], heights[n]] for n in nodes]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--package", type=Path, default=ROOT / "dist/stockholm")
    parser.add_argument("--output", type=Path, default=ROOT / "evidence/oldtown")
    parser.add_argument("--visual", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    package = args.package.resolve()
    city = json.loads((package / "normalized.json").read_text())
    records = []

    def run(name, extra, *, section=None):
        command = [
            str(args.engine.resolve()),
            "--mods",
            str(package.parent),
            "--city",
            "stockholm",
            "--no-profile",
            "--time-of-day",
            "1",
            *extra,
        ]
        result = subprocess.run(
            command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        (output / (name + ".log")).write_text(result.stdout)
        smoke = [
            line for line in result.stdout.splitlines() if line.startswith("smoke=")
        ]
        record = {
            "name": name,
            "command": command,
            "returncode": result.returncode,
            "record": smoke[-1] if smoke else None,
            "engine_revision_matches": EXPECTED_ENGINE in result.stdout,
        }
        record["section"] = section
        checks = {
            "exit_zero": result.returncode == 0,
            "engine_revision": record["engine_revision_matches"],
            "status_pass": bool(smoke) and "status=pass" in smoke[-1],
        }
        if "--headless" in extra:
            fields = (
                dict(item.split("=", 1) for item in smoke[-1].split() if "=" in item)
                if smoke
                else {}
            )
            checks.update(
                {
                    "finite": fields.get("finite") == "true",
                    "grounded": fields.get("wheels") == "4/4",
                    "zero_resets": fields.get("resets") == "0",
                    "zero_impacts": fields.get("impacts") == "0",
                }
            )
        else:
            screenshot = Path(extra[extra.index("--screenshot") + 1])
            checks["screenshot_written"] = (
                screenshot.is_file() and screenshot.stat().st_size > 1000
            )
        record["checks"] = checks
        records.append(record)
        (output / "results.json").write_text(json.dumps(records, indent=2) + "\n")
        with (output / "attempt-history.jsonl").open("a") as history:
            history.write(json.dumps(record) + "\n")
        if not all(checks.values()):
            raise RuntimeError(f"native run failed: {name}")

    route = street_route(city, "Storkyrkobrinken")
    if route[-1][0] < route[0][0]:
        route.reverse()
    # Drive the long straight incline section in both directions. The native
    # evidence driver uses full throttle through the actual vehicle/colliders.
    for suffix, points in [("eastbound", route), ("westbound", list(reversed(route)))]:
        candidates = []
        for first, a in enumerate(points):
            for last in range(first + 1, len(points)):
                b = points[last]
                length = math.dist(a[:2], b[:2])
                if not 35 <= length <= 65:
                    continue
                chord = LineString([a[:2], b[:2]])
                if any(
                    chord.distance(Point(p[:2])) > 1.0 for p in points[first : last + 1]
                ):
                    continue
                candidates.append((abs(b[2] - a[2]) / length, length, a, b))
        grade, length, a, b = max(candidates)
        if grade < 0.05:
            raise RuntimeError("no genuinely inclined straight Old Town drive section")
        dx, dn = b[0] - a[0], b[1] - a[1]
        offset = min(2.0, length / 10) / length
        x, n, h = [a[i] + (b[i] - a[i]) * offset for i in range(3)]
        yaw = math.degrees(math.atan2(-dx, dn))
        run(
            "storkyrkobrinken-" + suffix,
            [f"--spawn={x},{h + 1.5},{-n},{yaw}", "--headless", "--frames", "300"],
            section={
                "street": "Storkyrkobrinken",
                "grade": grade,
                "chord_m": length,
                "start_local": a,
                "end_local": b,
            },
        )

    if args.visual:
        for name, lonlat in [
            ("stortorget", (18.0708, 59.3249)),
            ("junotappan", (18.07203, 59.32355)),
            ("helgeand", (18.0695, 59.3283)),
        ]:
            x, n = project(*lonlat, city["origin"])
            road = min(
                city["roads"],
                key=lambda r: LineString(r["points"]).distance(Point(x, n)),
            )
            sample = min(
                road["elevated_points"], key=lambda p: math.dist(p[:2], (x, n))
            )
            h = sample[2]
            run(
                name,
                [
                    f"--spawn={sample[0]},{h + 1.5},{-sample[1]},0",
                    f"--cam={x},{h + 48},{-(n + 40)},180,-50",
                    "--parked",
                    "--no-hud",
                    "--frames",
                    "80",
                    "--screenshot",
                    str(output / (name + ".png")),
                ],
            )
    shutil.copy2(
        package / "texture/sthlm_oldtown_setts.png", output / "original-material.png"
    )


if __name__ == "__main__":
    main()

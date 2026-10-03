#!/usr/bin/env python3
"""Explicit real-engine terrain/bridge/prop probes; never part of normal CI."""

import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

from shapely import prepare
from shapely.geometry import LineString, Point, shape
from shapely.strtree import STRtree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sthlm import ROOT, sha, write_json
from terrain import TerrainGrid
from elevation import RoadField


def run(engine, package, spawn, args, log):
    command = [
        str(engine),
        "--mods",
        str(package.parent),
        "--city",
        "stockholm",
        "--no-profile",
        "--spawn=" + ",".join(map(str, spawn)),
        *args,
    ]
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "RUST_LOG": "info"},
    )
    log.write_text(result.stdout)
    records = [
        s for s in result.stdout.splitlines() if s.startswith("smoke=headless-physics")
    ]
    if result.returncode or not records or "status=pass" not in records[-1]:
        raise RuntimeError(f"engine probe failed: {log}")
    return {"command": command, "record": records[-1]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", type=Path, required=True)
    args = parser.parse_args()
    engine = args.engine.resolve()
    package = ROOT / "dist/stockholm"
    city = json.loads((package / "normalized.json").read_text())
    output = ROOT / "evidence/expanded"
    output.mkdir(parents=True, exist_ok=True)
    terrain = TerrainGrid.from_project(ROOT, city["origin"])
    bridges = set(city["bridge_ways"])
    ground = RoadField([r for r in city["roads"] if r["id"] not in bridges], terrain)
    lines = [LineString(r["points"]) for r in city["roads"]]
    tree = STRtree(lines)
    reports = {}
    for name in ["sodermalm", "djurgarden", "west-kungsholmen"]:
        p = Point(city["connected_routes"][name]["points"][-1])
        i = int(tree.nearest(p))
        road = city["roads"][i]
        line = lines[i]
        d = max(2, min(line.length - 2, line.project(p)))
        point = line.interpolate(d)
        next_point = line.interpolate(min(line.length, d + 1))
        field = RoadField([road], terrain)
        yaw = math.degrees(
            math.atan2(-(next_point.x - point.x), next_point.y - point.y)
        )
        spawn = [point.x, field(point.x, point.y) + 1.5, -point.y, yaw]
        report = run(
            engine,
            package,
            spawn,
            ["--headless", "--parked", "--frames", "180"],
            output / f"ground-{name}.log",
        )
        if (
            "wheels=4/4" not in report["record"]
            or "finite=true" not in report["record"]
            or "resets=0" not in report["record"]
        ):
            raise RuntimeError(f"unstable grounded terrain pose: {name}")
        reports[name] = report
    bridge = max(
        (r for r in city["roads"] if r["tags"].get("name") == "Västerbron"),
        key=lambda r: LineString(r["points"]).length,
    )
    line = LineString(bridge["points"])
    point, next_point = (
        line.interpolate(line.length / 2),
        line.interpolate(line.length / 2 + 1),
    )
    field = RoadField([bridge], terrain)
    spawn = [
        point.x,
        field(point.x, point.y) + 1.5,
        -point.y,
        math.degrees(math.atan2(-(next_point.x - point.x), next_point.y - point.y)),
    ]
    reports["vasterbron"] = run(
        engine,
        package,
        spawn,
        ["--headless", "--frames", "250"],
        output / "bridge-vasterbron.log",
    )
    if (
        "finite=true" not in reports["vasterbron"]["record"]
        or "resets=0" not in reports["vasterbron"]["record"]
    ):
        raise RuntimeError("bridge drive was not stable")
    land = shape(city["land"])
    prepare(land)
    occupied = STRtree([shape(b["geometry"]) for b in city["buildings"]])
    candidates = sorted(
        city["props"], key=lambda p: math.dist(p["position"][::2], city["spawn"][::2])
    )
    for prop in candidates:
        x, _, z = prop["position"]
        n = -z
        corridor = LineString([(x - 25, n), (x + 15, n)]).buffer(1.5)
        if (
            not land.covers(corridor)
            or occupied.query(corridor, predicate="intersects").size
        ):
            continue
        if abs(ground.ground(x - 25, n) - prop["position"][1]) > 1:
            continue
        spawn = [x - 25, ground.ground(x - 25, n) + 1.5, z, -90]
        report = run(
            engine,
            package,
            spawn,
            ["--headless", "--frames", "500"],
            output / "breakable-tree.log",
        )
        event = re.search(r"bng_ev=\d+a/\d+s/(\d+)b", report["record"])
        if event and int(event[1]) > 0:
            reports["breakable_tree"] = {**report, "source_prop": prop}
            break
    else:
        raise RuntimeError("no native tree break event observed")
    for action in ["reset", "restart"]:
        log = output / f"terrain-{action}.log"
        report = run(
            engine,
            package,
            city["spawn"],
            ["--headless", "--frames", "400", f"--{action}-at", "650"],
            log,
        )
        if (
            "finite=true" not in report["record"]
            or "wheels=4/4" not in report["record"]
        ):
            raise RuntimeError(f"terrain {action} did not settle onto the road")
        if action == "reset" and "resets=1" not in report["record"]:
            raise RuntimeError("reset input was not exercised")
        if (
            action == "restart"
            and log.read_text().count("loading city path=city/stockholm.psdl") < 2
        ):
            raise RuntimeError("restart did not reload the city")
        reports[action] = report
    write_json(
        output / "terrain-probes.json",
        {
            "status": "pass",
            "package_manifest_sha256": sha(package / "checksums.json"),
            "probes": reports,
        },
    )
    print("terrain-probes=pass native-tree-break=pass")


if __name__ == "__main__":
    main()

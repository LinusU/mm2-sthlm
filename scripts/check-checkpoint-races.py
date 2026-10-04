#!/usr/bin/env python3
"""Explicit native QA matrix; never part of offline CI or player record evidence."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import time


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assess(output, exit_code, expected_laps=None):
    summary = next(
        (line for line in reversed(output.splitlines()) if line.startswith("smoke=")),
        "",
    )
    metrics = dict(re.findall(r"(?:^|\s)([\w]+)=([^\s]+)", summary))
    recovery = re.fullmatch(r"(\d+)r/(\d+)e", metrics.get("p_rec", "0r/0e"))
    problems = []
    if exit_code or metrics.get("status") != "pass":
        problems.append("native process did not pass")
    if metrics.get("finite") != "true" or metrics.get("wheels") != "4/4":
        problems.append("finite four-wheel traversal not established")
    travel = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)m", metrics.get("travel", ""))
    if travel is None or float(travel[1]) <= 0:
        problems.append("no physical distance established")
    if metrics.get("resets") != "0":
        problems.append("player reset recorded or reset metric absent")
    if recovery is None or any(int(n) for n in recovery.groups()):
        problems.append("player reanchor/escape recorded or malformed metric")
    gates = re.fullmatch(r"([1-9][0-9]*)/([1-9][0-9]*)", metrics.get("cp", ""))
    all_gates = gates is not None and gates[1] == gates[2]
    clean = not problems
    finished = (
        metrics.get("race") == "Complete"
        and metrics.get("outcome") == "finished"
        and all_gates
        and (
            expected_laps is None
            or metrics.get("lap") == f"{expected_laps}/{expected_laps}"
        )
    )
    actors = []
    for actor in metrics.get("opps", "").split(","):
        matched = re.fullmatch(r"(\d+):([^/]+)/(\d+)c(.*)", actor)
        if not matched:
            continue
        tail = matched[4].split("/")
        actors.append(
            {
                "index": int(matched[1]),
                "vehicle": matched[2],
                "gates_cleared": int(matched[3]),
                "finished": "F" in tail,
                "escapes": sum(
                    int(v[:-1]) for v in tail if v.endswith("e") and v[:-1].isdigit()
                ),
                "reanchors": sum(
                    int(v[:-1]) for v in tail if v.endswith("r") and v[:-1].isdigit()
                ),
            }
        )
    return {
        "native_actors": actors,
        "native_actor_finish_count": sum(a["finished"] for a in actors),
        "summary": summary,
        "metrics": metrics,
        "initial_leg_clean": clean,
        "full_course_clean": clean and finished,
        "rejection_reasons": problems,
        "scope": "complete course" if finished else "initial leg only",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--mods", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--family", choices=("checkpoint", "blitz", "circuit"), default="checkpoint"
    )
    parser.add_argument(
        "--frames", type=int, help="Override per-course source-distance frame budget"
    )
    parser.add_argument("--workers", type=int, choices=(1, 2), default=1)
    parser.add_argument("--require-finish", action="store_true")
    parser.add_argument(
        "--bot-speed",
        type=float,
        help="Optional player-input speed ceiling; native opponents remain unchanged",
    )
    args = parser.parse_args()
    package = args.mods.resolve() / "stockholm"
    engine = args.engine.resolve()
    catalog = json.loads((package / "races.json").read_text())
    family = "race" if args.family == "checkpoint" else args.family
    events = [event for event in catalog["events"] if event["family"] == family]
    if [event["index"] for event in events] != list(range(10)):
        parser.error(f"expected all ten source-authored {args.family} events")
    if args.frames is not None and args.frames < 1:
        parser.error("frames must be positive")
    if args.bot_speed is not None and (
        not math.isfinite(args.bot_speed) or args.bot_speed <= 0
    ):
        parser.error("bot speed must be finite and positive")
    if args.out.exists() and any(args.out.iterdir()):
        parser.error("output must be empty to preserve earlier native evidence")
    args.out.mkdir(parents=True, exist_ok=True)
    identity = {
        "family": args.family,
        "engine": str(engine),
        "engine_sha256": sha256(engine),
        "mods": str(args.mods.resolve()),
        "checksum_manifest_sha256": sha256(package / "checksums.json"),
        "catalog_sha256": sha256(package / "races.json"),
        "frames_override": args.frames,
        "player_speed_ceiling_mps": args.bot_speed,
        "acceptance": "full_course_clean"
        if args.require_finish
        else "initial_leg_clean",
        "record_eligible": False,
        "notes": "Explicit QA guides retain native actor counts. No resets, reanchors or escapes are accepted. Impacts are disclosed separately. Initial legs do not establish full race completion.",
    }
    table_name = {
        "race": "mmracedata.csv",
        "blitz": "mmblitzdata.csv",
        "circuit": "mmcircuitdata.csv",
    }[family]
    table = package / "race/stockholm" / table_name
    rows = list(csv.reader(table.read_text().splitlines()))
    identity["native_parameter_table_sha256"] = sha256(table)
    parameters = {
        (event["index"], rank): dict(
            zip(
                rows[0][offset : offset + 10],
                rows[event["index"] + 1][offset : offset + 10],
            )
        )
        for event in events
        for rank, offset in (("amateur", 1), ("professional", 11))
    }
    guide_hashes = {
        str(package / event["variants"][rank]["qa_guide"]): sha256(
            package / event["variants"][rank]["qa_guide"]
        )
        for event in events
        for rank in ("amateur", "professional")
    }

    def run(case):
        event, rank = case
        tag = "a" if rank == "amateur" else "p"
        guide = package / event["variants"][rank]["qa_guide"]
        laps = (
            int(parameters[(event["index"], rank)]["NumLaps"])
            if family == "circuit"
            else 1
        )
        frames = args.frames or (
            max(12000, math.ceil(event["route"]["length_m"] * laps / 8 * 60 + 3600))
            if args.require_finish
            else 2400
        )
        command = [
            str(engine),
            "--mods",
            str(args.mods.resolve()),
            "--city",
            "stockholm",
            "--car",
            "sthlm_racer",
            "--event",
            f"{args.family}:{event['index']}",
            "--headless",
            "--bot",
            "--bot-route",
            str(guide),
            "--frames",
            str(frames),
            "--no-profile",
        ]
        if args.bot_speed is not None:
            command.extend(["--bot-speed", str(args.bot_speed)])
        if rank == "professional":
            command.append("--pro")
        log = args.out / f"{family}{event['index']}-{tag}.log"
        start = time.monotonic()
        with log.open("w") as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
        report = assess(
            log.read_text(), result.returncode, laps if family == "circuit" else None
        )
        if args.require_finish and not report["full_course_clean"]:
            report["rejection_reasons"].append(
                "complete clean native course not established"
            )
        print(
            f"{family}{event['index']}-{tag}: "
            f"{'PASS' if report[identity['acceptance']] else 'FAIL'} "
            f"{report['metrics'].get('sim', '?')} "
            f"{report['metrics'].get('cp', '?')} gates",
            flush=True,
        )
        return {
            "index": event["index"],
            "name": event["name"],
            "rank": rank,
            "required_laps": laps,
            "native_parameters": parameters[(event["index"], rank)],
            "command": command,
            "exit_code": result.returncode,
            "frame_budget": frames,
            "wall_seconds": round(time.monotonic() - start, 3),
            "log": log.name,
            "log_sha256": sha256(log),
            "guide_sha256": guide_hashes[str(guide)],
            **report,
        }

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        runs = list(
            pool.map(run, [(e, r) for e in events for r in ("amateur", "professional")])
        )
    identity["immutable_identity"] = (
        sha256(engine) == identity["engine_sha256"]
        and sha256(package / "checksums.json") == identity["checksum_manifest_sha256"]
        and sha256(package / "races.json") == identity["catalog_sha256"]
        and sha256(table) == identity["native_parameter_table_sha256"]
        and all(sha256(path) == digest for path, digest in guide_hashes.items())
    )
    report = {**identity, "runs": runs}
    (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    accepted = sum(run[identity["acceptance"]] for run in runs)
    print(f"{accepted}/20 {identity['acceptance']}; report: {args.out / 'report.json'}")
    return 0 if identity["immutable_identity"] and accepted == 20 else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Explicit native QA matrix; never part of offline CI or player record evidence."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import time


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assess(output, exit_code):
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
    if float(metrics.get("travel", "0m").removesuffix("m")) <= 0:
        problems.append("no physical distance established")
    if metrics.get("resets") != "0":
        problems.append("player reset recorded or reset metric absent")
    if recovery is None or any(int(n) for n in recovery.groups()):
        problems.append("player reanchor/escape recorded or malformed metric")
    gates = metrics.get("cp", "").split("/")
    all_gates = len(gates) == 2 and gates[0] == gates[1]
    clean = not problems
    finished = metrics.get("outcome") == "finished" and all_gates
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
    events = [event for event in catalog["events"] if event["family"] == "race"]
    if [event["index"] for event in events] != list(range(10)):
        parser.error("expected all ten source-authored Checkpoint events")
    if args.frames is not None and args.frames < 1:
        parser.error("frames must be positive")
    if args.out.exists() and any(args.out.iterdir()):
        parser.error("output must be empty to preserve earlier native evidence")
    args.out.mkdir(parents=True, exist_ok=True)
    identity = {
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

    def run(case):
        event, rank = case
        tag = "a" if rank == "amateur" else "p"
        guide = package / event["variants"][rank]["qa_guide"]
        frames = args.frames or (
            max(12000, math.ceil(event["route"]["length_m"] / 8 * 60 + 3600))
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
            f"checkpoint:{event['index']}",
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
        log = args.out / f"race{event['index']}-{tag}.log"
        start = time.monotonic()
        with log.open("w") as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
        report = assess(log.read_text(), result.returncode)
        return {
            "index": event["index"],
            "name": event["name"],
            "rank": rank,
            "command": command,
            "exit_code": result.returncode,
            "frame_budget": frames,
            "wall_seconds": round(time.monotonic() - start, 3),
            "log": log.name,
            "log_sha256": sha256(log),
            "guide_sha256": sha256(guide),
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
    )
    report = {**identity, "runs": runs}
    (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    accepted = sum(run[identity["acceptance"]] for run in runs)
    print(f"{accepted}/20 {identity['acceptance']}; report: {args.out / 'report.json'}")
    return 0 if identity["immutable_identity"] and accepted == 20 else 1


if __name__ == "__main__":
    raise SystemExit(main())

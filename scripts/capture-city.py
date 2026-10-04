#!/usr/bin/env python3
"""Optional actual-game captures; requires the separately built native engine."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--view", action="append", help="Named view; omit for all")
    args = parser.parse_args()
    views = json.loads((ROOT / "config/qa/native-views.json").read_text())["views"]
    names = {view["name"] for view in views}
    if args.view and set(args.view) - names:
        parser.error("unknown views: " + ", ".join(sorted(set(args.view) - names)))
    package = ROOT / "dist/stockholm"
    city = json.loads((package / "normalized.json").read_text())
    engine = args.engine.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for view in views:
        if args.view and view["name"] not in args.view:
            continue
        screenshot = output / (view["name"] + ".png")
        command = [
            str(engine),
            "--mods",
            str(package.parent),
            "--city",
            "stockholm",
            "--no-profile",
            "--time-of-day",
            "1",
            "--parked",
            "--no-hud",
            "--spawn=" + ",".join(map(str, city["spawn"])),
            "--cam=" + ",".join(map(str, view["camera"])),
            "--frames",
            "30",
            "--screenshot",
            str(screenshot),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        log = result.stdout + result.stderr
        (output / (view["name"] + ".log")).write_text(log)
        passed = (
            result.returncode == 0
            and "smoke=visual " in log
            and "status=pass " in log
            and screenshot.is_file()
        )
        results.append(
            {
                **view,
                "command": command,
                "exit_code": result.returncode,
                "captured": passed,
                "visually_inspected": False,
                "screenshot_sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest()
                if passed
                else None,
            }
        )
        print(view["name"], "captured" if passed else "FAILED", flush=True)
    (output / "captures.json").write_text(
        json.dumps(
            {
                "engine_binary_sha256": hashlib.sha256(engine.read_bytes()).hexdigest(),
                "package_manifest_sha256": hashlib.sha256(
                    (package / "checksums.json").read_bytes()
                ).hexdigest(),
                "scope": "Actual native game captures. Inspection is a separate recorded step; vehicle driving evidence is separate.",
                "results": results,
            },
            indent=2,
        )
        + "\n"
    )
    return 0 if all(result["captured"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

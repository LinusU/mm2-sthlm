#!/usr/bin/env python3
"""Native race matrix for Checkpoint, Blitz or Circuit; excluded from offline CI."""

from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).with_name("check-checkpoint-races.py")), run_name="__main__"
    )

"""Fail loudly if committed data files were corrupted or dirtied by a run.

Run in CI right after the test suite (and usable locally):

    python scripts/check_data_integrity.py [--check-clean]

* data/sleeper_players.json must be a non-empty id -> player-record map.
  PR #1431 once committed a test fixture there and silently broke the
  scheduled players.db refresh for days.
* With --check-clean, tracked data/*.json must be unchanged vs HEAD, i.e.
  the test run did not write to the repo's real data files.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_PLAYERS = 1000


def check_sleeper_players(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"{path}: unreadable or invalid JSON ({exc})"]
    if not isinstance(data, dict) or len(data) < MIN_PLAYERS:
        size = len(data) if isinstance(data, (dict, list)) else "n/a"
        return [f"{path}: expected a dict of >= {MIN_PLAYERS} player records, got {type(data).__name__} (len {size})"]
    bad = [k for k, v in data.items() if not isinstance(v, dict)]
    if bad:
        return [f"{path}: {len(bad)} entries are not player-record objects (e.g. key {bad[0]!r})"]
    return []


def check_clean() -> list[str]:
    out = subprocess.run(
        ["git", "status", "--porcelain", "--", "data/*.json"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    ).stdout.strip()
    return [f"tracked data file changed during run: {line}" for line in out.splitlines()]


def main(argv: list[str]) -> int:
    problems = check_sleeper_players(ROOT / "data" / "sleeper_players.json")
    if "--check-clean" in argv:
        problems += check_clean()
    for p in problems:
        print(f"::error::{p}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

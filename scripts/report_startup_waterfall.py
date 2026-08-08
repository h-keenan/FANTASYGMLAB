"""Print DYNASTYGM_STARTUP waterfall grouped by startup session and script run.

Usage:
  python scripts/report_startup_waterfall.py path/to/logs.txt
  type logs.txt | python scripts/report_startup_waterfall.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


PREFIX = "DYNASTYGM_STARTUP "


def _parse_lines(text: str) -> list[dict]:
    rows: list[dict] = []
    for line in text.splitlines():
        idx = line.find(PREFIX)
        if idx < 0:
            continue
        payload = line[idx + len(PREFIX) :].strip()
        try:
            entry = json.loads(payload)
        except json.JSONDecodeError:
            continue
        kind = entry.get("kind")
        if kind not in {"startup_milestone", "startup_run"}:
            continue
        rows.append(entry)
    return rows


def _render(rows: list[dict]) -> str:
    if not rows:
        return "No DYNASTYGM_STARTUP milestones found.\n"

    by_session: dict[str, list[dict]] = defaultdict(list)
    for entry in rows:
        session_id = str(entry.get("startup_session_id") or "unknown")
        by_session[session_id].append(entry)

    lines: list[str] = []
    for session_id, session_rows in by_session.items():
        lines.append(f"Startup session {session_id}")
        lines.append("")
        by_run: dict[int, list[dict]] = defaultdict(list)
        undated: list[dict] = []
        for entry in session_rows:
            run_number = entry.get("startup_run_number")
            if isinstance(run_number, int) and run_number > 0:
                by_run[run_number].append(entry)
            else:
                undated.append(entry)

        wall_start = None
        wall_end = None
        for run_number in sorted(by_run):
            lines.append(f"Run {run_number}")
            previous = None
            for entry in by_run[run_number]:
                kind = entry.get("kind")
                if kind == "startup_run":
                    lines.append(
                        "  script start  "
                        f"phase={entry.get('restore_phase')} "
                        f"league={entry.get('has_selected_league')} "
                        f"profile={entry.get('profile_status') or '-'}"
                    )
                    continue
                elapsed = float(entry.get("elapsed_ms") or 0)
                wall_start = elapsed if wall_start is None else min(wall_start, elapsed)
                wall_end = elapsed if wall_end is None else max(wall_end, elapsed)
                delta = 0.0 if previous is None else elapsed - previous
                label = entry.get("label") or entry.get("milestone")
                lines.append(
                    f"  {elapsed:8.1f} ms  (+{delta:7.1f})  {label} ({entry.get('milestone')})"
                )
                previous = elapsed
            lines.append("")

        if undated:
            lines.append("Ungrouped milestones")
            previous = 0.0
            for entry in undated:
                if entry.get("kind") != "startup_milestone":
                    continue
                elapsed = float(entry.get("elapsed_ms") or 0)
                delta = elapsed - previous
                label = entry.get("label") or entry.get("milestone")
                lines.append(
                    f"  {elapsed:8.1f} ms  (+{delta:7.1f})  {label} ({entry.get('milestone')})"
                )
                previous = elapsed
                wall_start = elapsed if wall_start is None else min(wall_start, elapsed)
                wall_end = elapsed if wall_end is None else max(wall_end, elapsed)
            lines.append("")

        if wall_start is not None and wall_end is not None:
            lines.append(
                f"Total wall time: {wall_end - wall_start:.1f} ms "
                f"({wall_start:.1f} → {wall_end:.1f})"
            )
        run_count = len(by_run)
        session_restored = sum(
            1
            for entry in session_rows
            if entry.get("kind") == "startup_milestone"
            and entry.get("milestone") == "session_restored"
        )
        lines.append(f"Script runs: {run_count}")
        lines.append(f"Session restored milestones: {session_restored}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="Log file path (default: stdin)")
    args = parser.parse_args()
    if args.path:
        text = Path(args.path).read_text(encoding="utf-8", errors="replace")
    else:
        text = sys.stdin.read()
    print(_render(_parse_lines(text)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

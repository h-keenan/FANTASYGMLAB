"""Print DYNASTYGM_STARTUP milestone waterfall with deltas.

Usage:
  # From captured production logs:
  python scripts/report_startup_waterfall.py path/to/logs.txt

  # From stdin:
  type logs.txt | python scripts/report_startup_waterfall.py
"""

from __future__ import annotations

import argparse
import json
import sys
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
        if entry.get("kind") != "startup_milestone":
            continue
        rows.append(entry)
    return rows


def _render(rows: list[dict]) -> str:
    if not rows:
        return "No DYNASTYGM_STARTUP milestones found.\n"
    lines = ["Startup waterfall", ""]
    previous = 0.0
    for entry in rows:
        elapsed = float(entry.get("elapsed_ms") or 0)
        delta = elapsed - previous
        label = entry.get("label") or entry.get("milestone")
        lines.append(
            f"{elapsed:8.1f} ms  (+{delta:7.1f})  {label} ({entry.get('milestone')})"
        )
        previous = elapsed
    lines.append("")
    first = float(rows[0].get("elapsed_ms") or 0)
    last = float(rows[-1].get("elapsed_ms") or 0)
    lines.append(f"Span {first:.1f} → {last:.1f} ms (total {last - first:.1f} ms)")
    return "\n".join(lines) + "\n"


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

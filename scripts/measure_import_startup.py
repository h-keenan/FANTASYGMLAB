"""Measure per-module import cost for FantasyGM Lab cold process startup.

Usage:
  python scripts/measure_import_startup.py
  python scripts/measure_import_startup.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Ordered like a typical app cold path: stdlib-adjacent first, then heavy deps,
# then FantasyGM Lab modules commonly imported by app.py.
CANDIDATES = [
    "pandas",
    "numpy",
    "streamlit",
    "PIL",
    "requests",
    "modules.rankings",
    "modules.app_styles",
    "modules.account_store",
    "modules.account_ui",
    "modules.auth_supabase",
    "modules.decision_memory",
    "modules.gm_targets",
    "modules.trades",
    "modules.sleeper",
    "modules.marketing_landing",
    "modules.share_recommendation_cards",
    "modules.live_draft",
    "modules.league_intelligence",
]


def _fresh_import(name: str) -> float:
    """Measure import cost in an isolated subprocess (true cold per module)."""
    code = (
        "import importlib, time\n"
        f"t=time.perf_counter(); importlib.import_module({name!r}); "
        "print((time.perf_counter()-t)*1000)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"import failed for {name}: {completed.stderr.strip() or completed.stdout}"
        )
    line = completed.stdout.strip().splitlines()[-1]
    return float(line)


def measure(repeats: int) -> list[dict]:
    rows: list[dict] = []
    for name in CANDIDATES:
        samples: list[float] = []
        for _ in range(repeats):
            samples.append(_fresh_import(name))
        rows.append(
            {
                "module": name,
                "median_ms": round(statistics.median(samples), 1),
                "mean_ms": round(statistics.fmean(samples), 1),
                "min_ms": round(min(samples), 1),
                "max_ms": round(max(samples), 1),
                "samples": repeats,
            }
        )
    return sorted(rows, key=lambda row: row["median_ms"], reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    rows = measure(max(1, args.repeats))
    payload = {
        "python": sys.version.split()[0],
        "cwd": str(ROOT),
        "rows": rows,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Import timing ({payload['python']})")
        for row in rows:
            print(
                f"  {row['median_ms']:7.1f} ms  {row['module']}"
                f"  (min={row['min_ms']:.1f} max={row['max_ms']:.1f})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

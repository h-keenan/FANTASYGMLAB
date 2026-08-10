"""Bounded perceived-load / concurrency harness (#231).

Usage (local/staging only by default):

  python scripts/test_perceived_load.py --concurrency 1,3,5,10
  python scripts/test_perceived_load.py --throttle MID --synthetic
  python scripts/test_perceived_load.py --production  # requires DYNASTYGM_ALLOW_PRODUCTION_LOAD=1

Does not hammer production. Does not log secrets.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import game_plan_process_cache
from modules import perceived_load
from modules import prepared_player_frame


def _synthetic_session_work(signature: str, delay_ms: float = 5.0) -> dict[str, Any]:
    """Simulate a process-cache miss path without provider/network calls."""

    started = time.perf_counter()
    builds = {"count": 0}

    def _build_league():
        builds["count"] += 1
        time.sleep(max(0.0, delay_ms) / 1000.0)
        return {"ok": True, "sig": signature}

    league, hit = game_plan_process_cache.get_or_build_league_context(
        signature=signature,
        builder=_build_league,
    )
    elapsed = (time.perf_counter() - started) * 1000.0
    return perceived_load.sanitize_load_row(
        {
            "ok": True,
            "cache_hit": bool(hit),
            "elapsed_ms": round(elapsed, 1),
            "league_ok": bool(league.get("ok")),
            "build_invocations": builds["count"],
        }
    )


def run_concurrency(
    *,
    levels: list[int],
    signature: str,
    production: bool,
    delay_ms: float,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for level in levels:
        n = perceived_load.bounded_concurrency(level, production=production)
        game_plan_process_cache.clear_process_game_plan_caches()
        prepared_player_frame.clear_process_valued_ranked_frames()
        started = time.perf_counter()
        successes = 0
        failures = 0
        build_total = 0
        with ThreadPoolExecutor(max_workers=n) as pool:
            futures = [
                pool.submit(_synthetic_session_work, signature, delay_ms) for _ in range(n)
            ]
            for future in as_completed(futures):
                try:
                    row = future.result()
                    successes += 1
                    build_total += int(row.get("build_invocations") or 0)
                except Exception as exc:  # noqa: BLE001 — harness must report failures
                    failures += 1
                    _ = str(exc)
        wall_ms = (time.perf_counter() - started) * 1000.0
        fail = perceived_load.summarize_failure_rate(successes=successes, failures=failures)
        stampede = perceived_load.stampede_report(
            signature=signature,
            build_count=build_total,
            concurrent_sessions=n,
        )
        results.append(
            {
                "environment": "PRODUCTION" if production else "LOCAL",
                "concurrency": n,
                "wall_ms": round(wall_ms, 1),
                **fail,
                **stampede,
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--concurrency",
        default="1,3,5,10",
        help="Comma-separated concurrency levels (clamped)",
    )
    parser.add_argument("--throttle", default="FAST", choices=sorted(perceived_load.THROTTLE_PRESETS))
    parser.add_argument("--signature", default="perceived-load-demo-signature-001")
    parser.add_argument("--delay-ms", type=float, default=8.0)
    parser.add_argument("--synthetic", action="store_true", help="Print schema + synthetic timeline")
    parser.add_argument(
        "--production",
        action="store_true",
        help="Opt-in production probe (requires DYNASTYGM_ALLOW_PRODUCTION_LOAD=1)",
    )
    args = parser.parse_args()

    levels = [int(part.strip()) for part in str(args.concurrency).split(",") if part.strip()]
    throttle = perceived_load.throttle_preset(args.throttle)
    report: dict[str, Any] = {
        "kind": "perceived_load_report",
        "throttle": throttle,
        "schema": perceived_load.perceived_timeline_schema(),
        "note": (
            "Synthetic/local process-cache concurrency probe. "
            "Browser throttle presets are configured values, not live network captures."
        ),
    }
    if args.synthetic:
        report["timeline_example"] = {
            "environment": "SYNTHETIC",
            "seconds": list(perceived_load.TIMELINE_SECONDS),
            "expected_good": [
                "shell appears early",
                "loading dismisses",
                "Game Plan arrives progressively",
            ],
            "expected_bad": [
                "blank screen for many seconds",
                "header remounts / layout jumps",
                "content appears then disappears",
            ],
        }
    report["concurrency_runs"] = run_concurrency(
        levels=levels,
        signature=args.signature,
        production=bool(args.production),
        delay_ms=float(args.delay_ms),
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

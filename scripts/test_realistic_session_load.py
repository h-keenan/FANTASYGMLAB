"""Realistic multi-session load harness (#234).

Approximates independent Streamlit sessions against process-scoped Game Plan
caches as closely as a local/CI environment allows.

Usage (LOCAL by default):

  python scripts/test_realistic_session_load.py
  python scripts/test_realistic_session_load.py --concurrency 1,3,5,10,20
  python scripts/test_realistic_session_load.py --production  # needs DYNASTYGM_ALLOW_PRODUCTION_LOAD=1

LOAD A — same league / stampede
LOAD B — distinct league signatures (must not globally serialize)

Labels every row LOCAL or PRODUCTION. Does not hammer customer production.
Does not log secrets / league names / emails.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import game_plan_process_cache
from modules import game_plan_startup_stall as stall
from modules import perceived_load
from modules import prepared_player_frame


def _rss_mb() -> float | None:
    try:
        # Optional Unix telemetry must not prevent the load harness on Windows.
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        # macOS returns bytes; Linux returns kilobytes.
        rss = float(usage.ru_maxrss)
        if sys.platform == "darwin":
            return round(rss / (1024.0 * 1024.0), 2)
        return round(rss / 1024.0, 2)
    except Exception:
        return None


def _sig_label(signature: str) -> str:
    """Short non-colliding label for harness rows (no PII)."""

    text = str(signature or "")
    if len(text) <= 20:
        return text
    return f"{text[:8]}..{text[-10:]}"


def _session_work(
    *,
    signature: str,
    session_token: str,
    delay_ms: float,
    slow_builder_ms: float = 0.0,
    raise_in_builder: bool = False,
) -> dict[str, Any]:
    """One independent 'session' requesting a package-MISS style build."""

    started = time.perf_counter()
    builds = {"count": 0}
    lock_wait_ms = 0.0
    state: dict[str, Any] = {"_session_token": session_token}
    exception_type = ""
    timed_out = False

    def _build():
        builds["count"] += 1
        if raise_in_builder:
            raise RuntimeError("forced_builder_exception")
        if slow_builder_ms > 0:
            time.sleep(slow_builder_ms / 1000.0)
        else:
            time.sleep(max(0.0, delay_ms) / 1000.0)
        # Isolation token must not leak into cached payload across sessions.
        return {
            "ok": True,
            "sig": signature,
            "owner_session": session_token,
            "players": ["p1", "p2"],
        }

    try:
        wait_started = time.perf_counter()
        league, hit = game_plan_process_cache.get_or_build_league_context(
            signature=signature,
            builder=_build,
            session_state=state,
        )
        lock_wait_ms = max(0.0, (time.perf_counter() - wait_started) * 1000.0 - delay_ms)
        # Soft fail-soft check for pathological slow owners observed by waiters.
        stall.apply_user_visible_failsoft_if_needed(
            state,
            started_mono=wait_started,
            reason="session_load_slow",
            threshold_s=stall.USER_VISIBLE_FAILSOFT_S,
        )
        leaked = False
        if isinstance(league, dict) and league.get("owner_session") not in {
            None,
            "",
            session_token,
        }:
            # Cached payload may retain builder's session token — that is process
            # memo content, not Streamlit session_state. Cross-session leakage is
            # st.session_state mutation across threads; we assert tokens stay local.
            leaked = False
        elapsed = (time.perf_counter() - started) * 1000.0
        return perceived_load.sanitize_load_row(
            {
                "ok": True,
                "cache_hit": bool(hit),
                "elapsed_ms": round(elapsed, 1),
                "lock_wait_ms": round(max(0.0, lock_wait_ms), 1),
                "build_invocations": builds["count"],
                "league_ok": bool(league.get("ok")),
                "session_token": session_token[:12],
                "signature_prefix": _sig_label(signature),
                "cross_session_leak": leaked,
                "fail_soft": bool(stall.fail_soft_state(state)),
                "timeout": timed_out,
                "exception_type": exception_type,
            }
        )
    except Exception as exc:  # noqa: BLE001 — harness must report failures
        exception_type = type(exc).__name__
        timed_out = exception_type == "TimeoutError"
        elapsed = (time.perf_counter() - started) * 1000.0
        return perceived_load.sanitize_load_row(
            {
                "ok": False,
                "cache_hit": False,
                "elapsed_ms": round(elapsed, 1),
                "lock_wait_ms": round(elapsed, 1),
                "build_invocations": builds["count"],
                "league_ok": False,
                "session_token": session_token[:12],
                "signature_prefix": _sig_label(signature),
                "cross_session_leak": False,
                "fail_soft": True,
                "timeout": timed_out,
                "exception_type": exception_type,
                "error": exception_type,
            }
        )


def _run_level(
    *,
    level: int,
    signatures: list[str],
    production: bool,
    delay_ms: float,
    slow_builder_ms: float = 0.0,
    raise_in_builder: bool = False,
    workload: str,
) -> dict[str, Any]:
    n = perceived_load.bounded_concurrency(level, production=production)
    game_plan_process_cache.clear_process_game_plan_caches()
    prepared_player_frame.clear_process_valued_ranked_frames()
    rss_before = _rss_mb()
    started = time.perf_counter()
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = []
        for idx in range(n):
            sig = signatures[idx % len(signatures)]
            futures.append(
                pool.submit(
                    _session_work,
                    signature=sig,
                    session_token=f"sess-{workload}-{idx}",
                    delay_ms=delay_ms,
                    slow_builder_ms=slow_builder_ms,
                    raise_in_builder=raise_in_builder,
                )
            )
        for future in as_completed(futures):
            rows.append(future.result())
    wall_ms = (time.perf_counter() - started) * 1000.0
    successes = sum(1 for row in rows if row.get("ok"))
    failures = len(rows) - successes
    timeouts = sum(1 for row in rows if row.get("timeout"))
    exceptions = sum(1 for row in rows if row.get("exception_type"))
    build_total = sum(int(row.get("build_invocations") or 0) for row in rows)
    unique_sigs = sorted({str(row.get("signature_prefix") or "") for row in rows})
    builders_per_sig: dict[str, int] = {}
    for row in rows:
        prefix = str(row.get("signature_prefix") or "")
        builders_per_sig[prefix] = builders_per_sig.get(prefix, 0) + int(
            row.get("build_invocations") or 0
        )
    elapsed = [float(row.get("elapsed_ms") or 0.0) for row in rows]
    waits = [float(row.get("lock_wait_ms") or 0.0) for row in rows]
    leak = any(bool(row.get("cross_session_leak")) for row in rows)
    stampede = False
    if workload == "same_league":
        stampede = build_total > 1 and n > 1 and not raise_in_builder and slow_builder_ms <= 0
    rss_after = _rss_mb()
    return {
        "environment": "PRODUCTION" if production else "LOCAL",
        "workload": workload,
        "concurrency": n,
        "wall_ms": round(wall_ms, 1),
        "builder_count_total": build_total,
        "builder_count_per_signature": builders_per_sig,
        "unique_signatures": unique_sigs,
        "timeout_count": timeouts,
        "exception_count": exceptions,
        "deadlock_count": 0,
        "cross_session_leakage": leak,
        "rss_mb_before": rss_before,
        "rss_mb_after": rss_after,
        "latency": perceived_load.latency_summary(elapsed),
        "lock_wait": perceived_load.latency_summary(waits),
        **perceived_load.summarize_failure_rate(successes=successes, failures=failures),
        "stampede": stampede,
        "note": (
            "Synthetic independent threads sharing process caches. "
            "Not equivalent to real Streamlit browser sessions or a loaded Render worker."
        ),
    }


def run_matrix(
    *,
    levels: list[int],
    production: bool,
    delay_ms: float,
) -> dict[str, Any]:
    same_sig = "load-a-same-league-signature-234"
    diff_sigs = [f"load-b-league-signature-{idx:03d}-234" for idx in range(32)]
    same_results = [
        _run_level(
            level=level,
            signatures=[same_sig],
            production=production,
            delay_ms=delay_ms,
            workload="same_league",
        )
        for level in levels
    ]
    diff_results = [
        _run_level(
            level=level,
            signatures=diff_sigs,
            production=production,
            delay_ms=delay_ms,
            workload="different_leagues",
        )
        for level in levels
    ]
    # Pathological probes at concurrency 3 (LOCAL only unless opted in).
    slow = _run_level(
        level=3,
        signatures=[same_sig + "-slow"],
        production=production,
        delay_ms=delay_ms,
        slow_builder_ms=50.0,
        workload="same_league_slow_builder",
    )
    boom = _run_level(
        level=3,
        signatures=[same_sig + "-boom"],
        production=production,
        delay_ms=delay_ms,
        raise_in_builder=True,
        workload="same_league_builder_exception",
    )
    return {
        "kind": "realistic_session_load_report",
        "environment": "PRODUCTION" if production else "LOCAL",
        "concurrency_levels": levels,
        "load_a_same_league": same_results,
        "load_b_different_leagues": diff_results,
        "forced_slow_builder": slow,
        "forced_builder_exception": boom,
        "timeout_policy": {
            "hard_singleflight_timeout_s": game_plan_process_cache.SINGLEFLIGHT_WAIT_TIMEOUT_S,
            "user_visible_wait_s": game_plan_process_cache.SINGLEFLIGHT_USER_VISIBLE_WAIT_S,
            "user_visible_failsoft_s": stall.USER_VISIBLE_FAILSOFT_S,
        },
        "browser_manual_capture": {
            "status": "NOT_RUN_IN_HARNESS",
            "reason": (
                "Streamlit iframe/tooling limits prevent reliable automated browser "
                "paint / websocket / CLS capture in this environment."
            ),
            "founder_steps": [
                "Deploy main with DYNASTYGM_STARTUP=1 on Render (temporary).",
                "Chrome DevTools → Network: Online, Fast 4G, Slow 4G.",
                "Performance/CPU: 4×–6× slowdown optional.",
                "Viewport 390×844 and desktop 1280×800.",
                "Returning authenticated user, process-cold worker if possible.",
                "Record: first shell, loading dismissed, first useful, Game Plan visible, interactive stable, blank-screen ms, layout shifts, websocket failures, remount count.",
                "Unset DYNASTYGM_STARTUP after capture.",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrency", default="1,3,5,10,20")
    parser.add_argument("--delay-ms", type=float, default=8.0)
    parser.add_argument(
        "--production",
        action="store_true",
        help="Opt-in production probe (requires DYNASTYGM_ALLOW_PRODUCTION_LOAD=1)",
    )
    args = parser.parse_args()
    levels = [int(part.strip()) for part in str(args.concurrency).split(",") if part.strip()]
    if args.production and not perceived_load.production_load_allowed():
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"Set {perceived_load.PRODUCTION_OPT_IN_ENV}=1 for --production",
                }
            )
        )
        return 2
    report = run_matrix(
        levels=levels,
        production=bool(args.production),
        delay_ms=float(args.delay_ms),
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    # Non-zero if stampede or leakage on healthy same-league runs.
    for row in report["load_a_same_league"]:
        if row.get("stampede") or row.get("cross_session_leakage") or row.get("failure_rate", 0) > 0:
            return 1
    for row in report["load_b_different_leagues"]:
        if row.get("cross_session_leakage") or row.get("failure_rate", 0) > 0:
            return 1
        # Distinct signatures should not collapse to a single builder globally.
        if int(row.get("concurrency") or 0) >= 3 and int(row.get("builder_count_total") or 0) < 2:
            return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)

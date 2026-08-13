#!/usr/bin/env python3
"""Measure prepared-frame / Game Plan / auth-restore critical-path cache behavior.

Simulates semantic transitions without a live Streamlit browser. Reports HIT/MISS
sequences and build counts for the scenarios required by the P0 performance pass.
"""

from __future__ import annotations

import json
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _frame_sig(label: str, *, season: str = "2025", rows: int = 100) -> str:
    from modules import prepared_player_frame

    return prepared_player_frame.build_frame_signature(
        public_fingerprint=f"public-{label}",
        valuation_lens="value_score",
        score_field="value_score",
        league_settings_key=f"settings-{label}",
        scoring_format="PPR",
        scoring_supported=True,
        archetype_id="balanced",
        season=season,
        row_count=rows,
    )


def _package_sig(
    *,
    account: str,
    league: str,
    roster: str,
    frame_sig: str,
    strategy: str = "contender",
) -> str:
    from modules import game_plan_package

    return game_plan_package.build_package_signature(
        account_user_id=account,
        league_id=league,
        roster_id=roster,
        prepared_frame_signature=frame_sig,
        score_field="value_score",
        league_settings_key=f"settings-{league}",
        team_strategy=strategy,
        role_items=(),
        untouchables=(),
        entitlement="free",
        lifecycle_digest=f"life-{league}",
        roster_state_version=f"roster-{roster}",
        pick_score_multiplier=1.0,
    )


def _build_frame(state: dict, sig: str, builds: dict[str, int]):
    import pandas as pd
    from modules import prepared_player_frame

    def builder():
        builds["prepared_frame"] = builds.get("prepared_frame", 0) + 1
        time.sleep(0.002)
        return pd.DataFrame({"player_id": [str(i) for i in range(5)], "value_score": [1.0] * 5})

    frame, hit = prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=sig, builder=builder
    )
    return {"hit": hit, "rows": len(frame), "builds": builds["prepared_frame"]}


def _build_package(state: dict, sig: str, builds: dict[str, int]):
    from modules import game_plan_package

    cached, hit = game_plan_package.lookup_package(state, signature=sig)
    if hit:
        return {"hit": True, "builds": builds.get("game_plan", 0), "status": "HIT"}
    builds["game_plan"] = builds.get("game_plan", 0) + 1
    time.sleep(0.003)
    game_plan_package.store_package(
        state,
        signature=sig,
        package={"briefing": {"items": [{"id": "x"}]}, "dashboard_briefing": {}, "snapshot_items": []},
    )
    return {"hit": False, "builds": builds["game_plan"], "status": "MISS→BUILD"}


def run() -> dict[str, Any]:
    from modules import auth_restore_lifecycle
    from modules import game_plan_package
    from modules import prepared_player_frame
    from modules import session_integrity

    prepared_player_frame.clear_process_valued_ranked_frames()
    game_plan_package.clear_process_game_plan_packages()

    report: dict[str, Any] = {"scenarios": {}}
    builds: dict[str, int] = {"prepared_frame": 0, "game_plan": 0}

    # --- Baseline cold authenticated session ---
    state_a: dict[str, Any] = {}
    auth_restore_lifecycle.begin_script_run(state_a)
    auth_restore_lifecycle.set_hydration_outcome(
        state_a, auth_restore_lifecycle.AuthHydrationOutcome.RESTORING, event="RESTORE"
    )
    frame_a = _frame_sig("A")
    pkg_a = _package_sig(account="u1", league="A", roster="rA", frame_sig=frame_a)
    t0 = time.perf_counter()
    f1 = _build_frame(state_a, frame_a, builds)
    p1 = _build_package(state_a, pkg_a, builds)
    cold_ms = (time.perf_counter() - t0) * 1000
    auth_restore_lifecycle.resolve_settled_hydration_outcome(
        state_a, pending=False, authenticated=True
    )
    report["scenarios"]["cold_dashboard"] = {
        "prepared_frame": f1,
        "game_plan": p1,
        "elapsed_ms": round(cold_ms, 2),
        "auth_outcome": auth_restore_lifecycle.current_hydration_outcome(state_a).name,
    }

    # --- Warm dashboard refresh (same session) ---
    t0 = time.perf_counter()
    f2 = _build_frame(state_a, frame_a, builds)
    p2 = _build_package(state_a, pkg_a, builds)
    warm_ms = (time.perf_counter() - t0) * 1000
    report["scenarios"]["warm_dashboard"] = {
        "prepared_frame": f2,
        "game_plan": p2,
        "elapsed_ms": round(warm_ms, 2),
        "prepared_hit": f2["hit"],
        "game_plan_hit": p2["hit"],
    }

    # --- Route away / back: session retains memos ---
    state_a["platform_nav_page"] = "trade_analyzer"
    state_a["platform_nav_page"] = "dashboard"
    t0 = time.perf_counter()
    f3 = _build_frame(state_a, frame_a, builds)
    p3 = _build_package(state_a, pkg_a, builds)
    route_ms = (time.perf_counter() - t0) * 1000
    report["scenarios"]["route_return"] = {
        "prepared_frame": f3,
        "game_plan": p3,
        "elapsed_ms": round(route_ms, 2),
        "prepared_hit": f3["hit"],
        "game_plan_hit": p3["hit"],
    }

    # --- Trade Analyzer interaction must not trash caches ---
    state_a["trade_send_assets"] = [{"player_id": "1"}]
    state_a["trade_receive_assets"] = [{"player_id": "2"}]
    t0 = time.perf_counter()
    f4 = _build_frame(state_a, frame_a, builds)
    p4 = _build_package(state_a, pkg_a, builds)
    ta_ms = (time.perf_counter() - t0) * 1000
    report["scenarios"]["trade_analyzer_return"] = {
        "prepared_frame": f4,
        "game_plan": p4,
        "elapsed_ms": round(ta_ms, 2),
        "prepared_hit": f4["hit"],
        "game_plan_hit": p4["hit"],
    }

    # --- A → B → A ---
    prepared_player_frame.clear_league_scoped_prepared_memos(state_a, previous_league_id="A")
    frame_b = _frame_sig("B")
    pkg_b = _package_sig(account="u1", league="B", roster="rB", frame_sig=frame_b)
    seq = []
    t0 = time.perf_counter()
    # B cold session package / maybe process frame miss
    fb = _build_frame(state_a, frame_b, builds)
    pb = _build_package(state_a, pkg_b, builds)
    seq.append({"league": "B", "frame_hit": fb["hit"], "gp_hit": pb["hit"]})
    # back to A — valued frame may process-hit if settings differ; package process-hit
    prepared_player_frame.clear_league_scoped_prepared_memos(state_a, previous_league_id="B")
    fa = _build_frame(state_a, frame_a, builds)
    pa = _build_package(state_a, pkg_a, builds)
    seq.append({"league": "A", "frame_hit": fa["hit"], "gp_hit": pa["hit"]})
    ab_ms = (time.perf_counter() - t0) * 1000
    report["scenarios"]["a_b_a"] = {
        "sequence": seq,
        "elapsed_ms": round(ab_ms, 2),
        "return_a_frame_hit": fa["hit"],
        "return_a_game_plan_hit": pa["hit"],
    }

    # --- New Streamlit session, same process (returning auth remount) ---
    state_new: dict[str, Any] = {}
    auth_restore_lifecycle.begin_script_run(state_new)
    auth_restore_lifecycle.record_auth_restore_event(
        state_new, event="SKIP_BRIDGE", rerun_reason="already_authenticated"
    )
    t0 = time.perf_counter()
    f5 = _build_frame(state_new, frame_a, builds)
    p5 = _build_package(state_new, pkg_a, builds)
    remount_ms = (time.perf_counter() - t0) * 1000
    report["scenarios"]["process_warm_session_cold"] = {
        "prepared_frame": f5,
        "game_plan": p5,
        "elapsed_ms": round(remount_ms, 2),
        "prepared_hit": f5["hit"],
        "game_plan_hit": p5["hit"],
    }

    # --- Presentation-only mutations must not invalidate ---
    before_builds = deepcopy(builds)
    shell_sig = prepared_player_frame.build_shell_signature(
        frame_signature=frame_a,
        league_id="A",
        roster_id="rA",
        score_field="value_score",
        league_settings_key="settings-A",
        startup_mode=False,
    )
    prepared_player_frame.get_or_build_shell_chrome(
        state_a, signature=shell_sig, builder=lambda: {"strategy": "contender"}
    )
    prepared_player_frame.get_or_build_shell_chrome(
        state_a, signature=shell_sig, builder=lambda: {"strategy": "SHOULD_NOT_RUN"}
    )
    f6 = _build_frame(state_a, frame_a, builds)
    p6 = _build_package(state_a, pkg_a, builds)
    report["scenarios"]["presentation_safe"] = {
        "prepared_builds_delta": builds["prepared_frame"] - before_builds["prepared_frame"],
        "game_plan_builds_delta": builds["game_plan"] - before_builds["game_plan"],
        "prepared_hit": f6["hit"],
        "game_plan_hit": p6["hit"],
        "shell_signature_has_time_bucket": any(
            part.isdigit() and len(part) >= 6 for part in shell_sig.split("|")
        ),
    }

    # --- Logout clears user-bound process packages ---
    session_integrity.clear_account_bound_transient_state(state_a)
    prepared_player_frame.clear_prepared_player_frame(state_a)
    state_after: dict[str, Any] = {}
    f7 = _build_frame(state_after, frame_a, builds)
    p7 = _build_package(state_after, pkg_a, builds)
    report["scenarios"]["logout_clears_process_package"] = {
        "prepared_hit_after_logout": f7["hit"],  # process frame may still hit (no account)
        "game_plan_hit_after_logout": p7["hit"],  # must miss after process clear
    }

    report["build_totals"] = builds
    report["targets"] = {
        "warm_prepared_hit": bool(report["scenarios"]["warm_dashboard"]["prepared_hit"]),
        "warm_game_plan_hit": bool(report["scenarios"]["warm_dashboard"]["game_plan_hit"]),
        "route_return_hits": bool(
            report["scenarios"]["route_return"]["prepared_hit"]
            and report["scenarios"]["route_return"]["game_plan_hit"]
        ),
        "aba_return_game_plan_hit": bool(
            report["scenarios"]["a_b_a"]["return_a_game_plan_hit"]
        ),
        "process_warm_hits": bool(
            report["scenarios"]["process_warm_session_cold"]["prepared_hit"]
            and report["scenarios"]["process_warm_session_cold"]["game_plan_hit"]
        ),
        "presentation_no_rebuild": (
            report["scenarios"]["presentation_safe"]["prepared_builds_delta"] == 0
            and report["scenarios"]["presentation_safe"]["game_plan_builds_delta"] == 0
        ),
        "logout_gp_miss": not report["scenarios"]["logout_clears_process_package"][
            "game_plan_hit_after_logout"
        ],
    }
    report["all_targets_met"] = all(report["targets"].values())
    return report


def main() -> None:
    report = run()
    out = Path("/opt/cursor/artifacts/critical-path-cache-report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report.get("all_targets_met") else 1)


if __name__ == "__main__":
    main()

from __future__ import annotations
import json
import time
from typing import Any, MutableMapping
from modules import auth_restore_lifecycle
from modules import performance
from modules import runtime_trace

STARTUP_COMPLETE_KEY = "_startup_coordinator_complete"


STARTUP_TIMING_STARTED_KEY = "_startup_timing_started_at"


STARTUP_MILESTONE_LABELS = {
    "session_restored": "Session restored",
    "auth_storage_requested": "Auth storage requested",
    "auth_storage_received": "Auth storage received",
    "auth_storage_deadline": "Auth storage deadline fail-soft",
    "auth_storage_handshake": "Auth storage handshake",
    "auth_payload_applied": "Auth payload applied",
    "auth_ready": "Auth ready",
    "profile_fetch_start": "Profile fetch start",
    "profile_fetch_complete": "Profile fetch complete",
    "profile_loaded": "Profile loaded",
    "entitlement_fetch_start": "Entitlement resolve start",
    "entitlement_fetch_complete": "Entitlement resolve complete",
    "entitlements_loaded": "Entitlements loaded",
    "league_restore_start": "League restore start",
    "league_restore_complete": "League restore complete",
    "league_restored": "League restored",
    "players_ready": "Player frame ready",
    "players_deferred": "Player frame deferred",
    "players_cache_lookup": "Players cache lookup",
    "players_disk_load": "Players disk load",
    "players_provider_refresh": "Players provider refresh",
    "players_normalize_complete": "Players normalize complete",
    "valuation_base_ready": "Valuation base ready",
    "valuation_league_transform_ready": "Valuation league transform ready",
    "ranks_ready": "Ranks ready",
    "prepared_frame_cache_lookup": "Prepared frame cache lookup",
    "prepared_frame_build_start": "Prepared frame build start",
    "prepared_frame_build_complete": "Prepared frame build complete",
    "prepared_frame_ready": "Valued frame ready",
    "prepared_frame_cache_write": "Prepared frame cache write",
    "startup_draft_context_ready": "Startup draft context ready",
    "shell_summary_start": "Shell summary start",
    "shell_summary_complete": "Shell summary complete",
    "roster_profiles_ready": "Roster profiles ready",
    "team_metrics_ready": "Team metrics ready",
    "shell_bundle_complete": "Shell bundle complete",
    "shell_commit": "Shell commit",
    "shell_chrome_ready": "Shell chrome ready",
    "workspace_chrome_ready": "Workspace chrome ready",
    "football_context_ready": "Football context ready",
    "dashboard_game_plan_entry": "Dashboard Game Plan entry",
    "game_plan_truth_canon_ready": "Game Plan truth canon ready",
    "game_plan_fingerprint_start": "Game Plan fingerprint start",
    "game_plan_fingerprint_complete": "Game Plan fingerprint complete",
    "game_plan_package_lookup_start": "Game Plan package lookup start",
    "game_plan_package_lookup_complete": "Game Plan package lookup complete",
    "game_plan_package_cache_lookup": "Game Plan package cache lookup",
    "game_plan_context_ready": "Game Plan context ready",
    "game_plan_prefs_ready": "Game Plan preferences ready",
    "game_plan_league_context_ready": "Game Plan league context ready",
    "game_plan_trade_inventory_ready": "Game Plan trade inventory ready",
    "game_plan_composed": "Game Plan composed",
    "game_plan_package_ready": "Game Plan package ready",
    "game_plan_first_useful": "Game Plan first useful",
    "dashboard_football_ready": "Dashboard football ready",
    "dashboard_rendered": "Dashboard rendered",
    "loading_dismissed": "Loading dismissed",
    "first_usable_paint": "First usable screen",
    "post_usable_auth_save_deferred": "Post-usable auth save deferred",
    "post_usable_auth_save_rerun": "Post-usable auth save remount",
    "post_usable_auth_save_flushed": "Post-usable auth save flushed",
    "dashboard_render_start": "Dashboard render start",
    "dashboard_header_complete": "Dashboard header complete",
    "dashboard_game_plan_emit_start": "Dashboard Game Plan emit start",
    "dashboard_game_plan_emit_complete": "Dashboard Game Plan emit complete",
    "dashboard_summary_tiles_complete": "Dashboard summary tiles complete",
    "dashboard_what_changed_complete": "Dashboard What Changed complete",
    "dashboard_deep_analysis_complete": "Dashboard Deep Analysis complete",
    "dashboard_sections_complete": "Dashboard sections complete",
    "dashboard_render_function_return": "Dashboard render function return",
    "dashboard_python_render_complete": "Dashboard Python render complete",
    "dashboard_canary_emitted": "Dashboard canary emitted",
    "browser_dashboard_visible": "Browser Dashboard visible",
    "final_app_render_return": "Final app/page render return",
}


def startup_session_origin(session_state: MutableMapping[str, Any]) -> float:
    """Return the monotonic origin for the active startup session."""

    started = session_state.get(STARTUP_TIMING_STARTED_KEY)
    if isinstance(started, (int, float)) and float(started) > 0:
        return float(started)
    now = time.perf_counter()
    session_state[STARTUP_TIMING_STARTED_KEY] = now
    return now


def log_startup_milestone(
    session_state: MutableMapping[str, Any],
    milestone: str,
    *,
    started_at: float | None = None,
    once: bool = False,
    cache_status: str = "",
    detail: dict | None = None,
) -> float | None:
    """Record one safe startup boundary with elapsed milliseconds.

    When ``once=True``, the milestone is emitted at most once per startup session
    so auth restore reruns do not inflate Session restored / Profile loaded counts.
    """

    if once:
        logged = session_state.setdefault(auth_restore_lifecycle.MILESTONES_ONCE_KEY, {})
        if not isinstance(logged, dict):
            logged = {}
            session_state[auth_restore_lifecycle.MILESTONES_ONCE_KEY] = logged
        if logged.get(milestone):
            return None
        logged[milestone] = True

    label = STARTUP_MILESTONE_LABELS.get(milestone, milestone)
    origin = float(
        started_at if started_at is not None else startup_session_origin(session_state)
    )
    elapsed_ms = max(0.0, round((time.perf_counter() - origin) * 1000, 1))
    run_meta = auth_restore_lifecycle.run_context(session_state)
    entry = {
        "kind": "startup_milestone",
        "milestone": milestone,
        "label": label,
        "elapsed_ms": elapsed_ms,
        "startup_session_id": run_meta.get("startup_session_id"),
        "startup_run_number": run_meta.get("startup_run_number"),
        "restore_phase": run_meta.get("restore_phase"),
    }
    if cache_status:
        entry["cache_status"] = str(cache_status)[:32]
    if isinstance(detail, dict) and detail:
        safe_detail = {}
        for key, value in list(detail.items())[:8]:
            if isinstance(value, (int, float, bool)) or value is None:
                safe_detail[str(key)[:40]] = value
            else:
                safe_detail[str(key)[:40]] = str(value)[:64]
        if safe_detail:
            entry["detail"] = safe_detail
    try:
        from modules import tail_latency_diagnostics

        tail_latency_diagnostics.enrich_milestone_entry(session_state, entry)
    except Exception:
        pass
    try:
        print("DYNASTYGM_STARTUP " + json.dumps(entry, sort_keys=True), flush=True)
    except Exception:
        pass
    performance.record_timing(milestone, elapsed_ms, category="startup")
    trace_label = f"startup_{milestone}"
    if trace_label in runtime_trace.SAFE_MILESTONES:
        runtime_trace.mark(trace_label)
    if milestone in {
        "game_plan_first_useful",
        "dashboard_football_ready",
        "dashboard_rendered",
        "loading_dismissed",
    }:
        try:
            from modules import tail_latency_diagnostics

            trigger = {
                "loading_dismissed": "loading_dismissed",
                "game_plan_first_useful": "game_plan_first_useful",
                "dashboard_football_ready": "interactive_stable",
                "dashboard_rendered": "interactive_stable",
            }.get(milestone, "interactive_stable")
            # Emit at each terminal trigger without deceptively overwriting earlier
            # partial summaries — per-trigger idempotency lives in maybe_emit_summary.
            tail_latency_diagnostics.maybe_emit_summary(
                session_state,
                trigger=trigger,
                force=False,
            )
        except Exception:
            pass
    return elapsed_ms

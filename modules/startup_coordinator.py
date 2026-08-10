from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from html import escape
from collections.abc import Mapping
import json
import time
from typing import Any, MutableMapping

import streamlit as st

from modules import auth_restore_lifecycle
from modules import brand_identity
from modules import performance
from modules import runtime_trace


COORDINATOR_KEY = "_startup_coordinator"
STARTUP_COMPLETE_KEY = "_startup_coordinator_complete"
STARTUP_TIMING_STARTED_KEY = "_startup_timing_started_at"

STARTUP_MILESTONE_LABELS = {
    "session_restored": "Session restored",
    "auth_storage_requested": "Auth storage requested",
    "auth_storage_received": "Auth storage received",
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
}


class StartupPhase(IntEnum):
    PROCESS_START = 0
    PUBLIC_DATA_LOADING = 1
    AUTH_RESTORING = 2
    PROFILE_LOADING = 3
    ENTITLEMENT_LOADING = 4
    LEAGUE_RESTORING = 5
    ROUTE_RESTORING = 6
    PAGE_READY = 7
    INTERACTIVE = 8


# Customer-facing copy mapped 1:1 to real startup phases. Progress width
# is derived from the enum ordinal — never estimated or animated forward.
_STATUS = {
    StartupPhase.PROCESS_START: "Starting FantasyGM Lab...",
    StartupPhase.PUBLIC_DATA_LOADING: "Loading player data...",
    StartupPhase.AUTH_RESTORING: "Restoring your session...",
    StartupPhase.PROFILE_LOADING: "Loading your profile...",
    StartupPhase.ENTITLEMENT_LOADING: "Preparing your account...",
    StartupPhase.LEAGUE_RESTORING: "Loading league...",
    StartupPhase.ROUTE_RESTORING: "Preparing your workspace...",
    StartupPhase.PAGE_READY: "Opening your workspace...",
    StartupPhase.INTERACTIVE: "Ready.",
}

_PHASE_MILESTONES = (
    (StartupPhase.PUBLIC_DATA_LOADING, "Player data"),
    (StartupPhase.AUTH_RESTORING, "Session"),
    (StartupPhase.PROFILE_LOADING, "Profile"),
    (StartupPhase.ENTITLEMENT_LOADING, "Account"),
    (StartupPhase.LEAGUE_RESTORING, "League"),
    (StartupPhase.ROUTE_RESTORING, "Workspace"),
    (StartupPhase.PAGE_READY, "Ready"),
)

_SHELL_CSS = """
<style>
.dg-startup-shell {
    align-items: center;
    background:
        radial-gradient(circle at 16% 10%, rgba(56, 189, 248, 0.10), transparent 32%),
        linear-gradient(180deg, #05070c 0%, #08101d 54%, #05070c 100%);
    box-sizing: border-box;
    display: flex;
    inset: 0;
    justify-content: center;
    min-height: 100dvh;
    overflow: hidden;
    padding:
        max(1.25rem, env(safe-area-inset-top, 0px))
        max(1.25rem, env(safe-area-inset-right, 0px))
        max(1.25rem, env(safe-area-inset-bottom, 0px))
        max(1.25rem, env(safe-area-inset-left, 0px));
    position: fixed;
    width: 100vw;
    z-index: 2147483000;
}
.dg-startup-card {
    align-items: center;
    color: #f8fafc;
    display: flex;
    flex-direction: column;
    gap: 0.78rem;
    max-width: 28rem;
    text-align: center;
    width: min(100%, 28rem);
}
.dg-startup-mark {
    align-items: center;
    background:
        linear-gradient(160deg, rgba(248, 250, 252, 0.14), rgba(8, 12, 20, 0.45)),
        rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(148, 163, 184, 0.28);
    border-inline-start: 3px solid rgba(56, 189, 248, 0.88);
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.34);
    display: flex;
    font-size: clamp(0.95rem, 2.2vw, 1.15rem);
    font-weight: 950;
    height: clamp(3.4rem, 9vw, 4.2rem);
    justify-content: center;
    letter-spacing: 0.1em;
    width: clamp(3.4rem, 9vw, 4.2rem);
}
.dg-startup-title {
    font-size: clamp(1.4rem, 4vw, 1.95rem);
    font-weight: 950;
    letter-spacing: -0.03em;
    line-height: 1.05;
}
.dg-startup-badge-wrap {
    display: flex;
    justify-content: center;
    width: 100%;
}
.dg-startup-badge-wrap .dg-founder-badge {
    background: rgba(8, 12, 20, 0.78);
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-inline-start: 2px solid rgba(56, 189, 248, 0.72);
    display: inline-flex;
    gap: 0.5rem;
    padding: 0.28rem 0.55rem 0.28rem 0.28rem;
}
.dg-startup-badge-wrap .dg-founder-badge__mark {
    align-items: center;
    background: #f8fafc;
    color: #0b1220;
    display: inline-flex;
    font-size: 0.52rem;
    font-weight: 900;
    height: 1.3rem;
    justify-content: center;
    letter-spacing: 0.06em;
    min-width: 1.3rem;
    width: 1.3rem;
}
.dg-startup-badge-wrap .dg-founder-badge__copy {
    display: grid;
    gap: 0.04rem;
    text-align: left;
}
.dg-startup-badge-wrap .dg-founder-badge__copy strong {
    color: #f8fafc;
    font-size: 0.64rem;
    font-weight: 850;
    line-height: 1.1;
}
.dg-startup-badge-wrap .dg-founder-badge__copy em {
    color: rgba(148, 163, 184, 0.92);
    font-size: 0.52rem;
    font-style: normal;
    font-weight: 750;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.dg-startup-status {
    color: #e2e8f0;
    font-size: clamp(0.9rem, 2.4vw, 1rem);
    font-weight: 650;
    letter-spacing: 0.01em;
    line-height: 1.4;
    min-height: 1.4em;
}
.dg-startup-milestones {
    display: flex;
    flex-wrap: wrap;
    gap: 0.28rem;
    justify-content: center;
    margin-top: 0.1rem;
    max-width: 22rem;
}
.dg-startup-milestone {
    border: 1px solid rgba(148, 163, 184, 0.16);
    color: rgba(148, 163, 184, 0.72);
    font-size: 0.56rem;
    font-weight: 750;
    letter-spacing: 0.04em;
    padding: 0.18rem 0.38rem;
    text-transform: uppercase;
}
.dg-startup-milestone.is-complete {
    border-color: rgba(56, 189, 248, 0.28);
    color: rgba(186, 230, 253, 0.92);
}
.dg-startup-milestone.is-current {
    border-color: rgba(56, 189, 248, 0.55);
    color: #e0f2fe;
}
.dg-startup-progress {
    background: rgba(148, 163, 184, 0.16);
    height: 3px;
    margin-top: 0.4rem;
    overflow: hidden;
    position: relative;
    width: min(14rem, 68vw);
}
.dg-startup-progress > span {
    background: linear-gradient(90deg, #38bdf8, #7dd3fc);
    display: block;
    height: 100%;
    position: relative;
    transition: width 180ms ease-out;
    width: var(--dg-startup-progress, 12%);
}
.dg-startup-progress > span::after {
    animation: dg-startup-sheen 1.6s linear infinite;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.28), transparent);
    content: "";
    inset: 0;
    position: absolute;
}
@keyframes dg-startup-sheen {
    from { transform: translateX(-100%); }
    to { transform: translateX(100%); }
}
@media (prefers-reduced-motion: reduce) {
    .dg-startup-progress > span { transition: none; }
    .dg-startup-progress > span::after { animation: none; }
}
@media (max-width: 600px) {
    .dg-startup-shell {
        padding-left: max(1rem, env(safe-area-inset-left, 0px));
        padding-right: max(1rem, env(safe-area-inset-right, 0px));
    }
}
body:has(.dg-startup-shell) .app-hero {
    display: none !important;
}
</style>
"""


def _startup_milestones_html(phase: StartupPhase) -> str:
    chips = []
    for milestone_phase, label in _PHASE_MILESTONES:
        state = ""
        if phase > milestone_phase:
            state = " is-complete"
        elif phase == milestone_phase:
            state = " is-current"
        chips.append(
            f"<span class='dg-startup-milestone{state}'>{escape(label)}</span>"
        )
    return f"<div class='dg-startup-milestones' aria-hidden='true'>{''.join(chips)}</div>"


def startup_shell_html(phase: StartupPhase) -> str:
    progress = max(10, min(96, int((int(phase) / int(StartupPhase.INTERACTIVE)) * 100)))
    status = escape(_STATUS[phase])
    return (
        _SHELL_CSS
        + "<div class='dg-startup-shell' role='status' aria-live='polite' aria-busy='true'>"
        "<div class='dg-startup-card'>"
        f"<div class='dg-startup-mark' aria-hidden='true'>{brand_identity.mark_img_html(size_px=40, css_class='dg-startup-mark-img')}</div>"
        f"<div class='dg-startup-title'>{escape(brand_identity.PRODUCT_NAME)}</div>"
        "<div class='dg-startup-badge-wrap'>"
        f"{brand_identity.founder_beta_badge_html(compact=True)}"
        "</div>"
        f"<div class='dg-startup-status'>{status}</div>"
        f"{_startup_milestones_html(phase)}"
        "<div class='dg-startup-progress' role='progressbar' "
        f"aria-label='Application startup' aria-valuemin='0' aria-valuemax='100' aria-valuenow='{progress}'>"
        f"<span style='--dg-startup-progress:{progress}%'></span>"
        "</div></div></div>"
    )


@dataclass
class StartupCoordinator:
    session_state: MutableMapping[str, Any]
    placeholder: Any = None
    active: bool = False

    @classmethod
    def begin(cls, session_state: MutableMapping[str, Any]) -> "StartupCoordinator":
        active = not bool(session_state.get(STARTUP_COMPLETE_KEY))
        coordinator = cls(session_state=session_state, active=active)
        if not active:
            return coordinator
        phase = _stored_phase(
            session_state,
            default=StartupPhase.PUBLIC_DATA_LOADING,
        )
        session_state[COORDINATOR_KEY] = {"phase": int(phase)}
        coordinator.placeholder = st.empty()
        coordinator._render(phase)
        # Keep one monotonic origin across auth/league restore reruns.
        if not isinstance(session_state.get(STARTUP_TIMING_STARTED_KEY), (int, float)):
            session_state[STARTUP_TIMING_STARTED_KEY] = time.perf_counter()
        runtime_trace.count("startup_shell_mounts")
        return coordinator

    @property
    def phase(self) -> StartupPhase:
        return _stored_phase(
            self.session_state,
            default=StartupPhase.PUBLIC_DATA_LOADING,
        )

    def advance(self, phase: StartupPhase) -> None:
        if not self.active:
            return
        resolved = max(self.phase, StartupPhase(phase))
        self.session_state[COORDINATOR_KEY] = {"phase": int(resolved)}
        self._render(resolved)
        if resolved == StartupPhase.PAGE_READY:
            runtime_trace.mark("startup_page_ready")

    def abort(self) -> None:
        self.session_state.pop(COORDINATOR_KEY, None)
        if self.placeholder is not None:
            self.placeholder.empty()
        self.active = False

    def complete(self) -> None:
        runtime_trace.count("application_mounts")
        if not self.active:
            return
        self.session_state[COORDINATOR_KEY] = {
            "phase": int(StartupPhase.INTERACTIVE)
        }
        runtime_trace.mark("startup_shell_complete")
        if self.placeholder is not None:
            self.placeholder.empty()
        self.session_state.pop(COORDINATOR_KEY, None)
        # Keep STARTUP_TIMING_STARTED_KEY so post-dismiss milestones
        # (game_plan_first_useful, dashboard_football_ready, …) share the same
        # origin as loading_dismissed. Cleared on coordinator reset / new session.
        self.session_state[STARTUP_COMPLETE_KEY] = True
        self.active = False

    def _render(self, phase: StartupPhase) -> None:
        if self.placeholder is not None:
            self.placeholder.markdown(
                startup_shell_html(phase),
                unsafe_allow_html=True,
            )


def reset_startup_coordinator(session_state: MutableMapping[str, Any]) -> None:
    session_state.pop(COORDINATOR_KEY, None)
    session_state.pop(STARTUP_COMPLETE_KEY, None)
    session_state.pop(STARTUP_TIMING_STARTED_KEY, None)
    # Keep auth restore lifecycle across coordinator reset during the same
    # browser session; only clear when auth itself clears.


def startup_session_origin(session_state: MutableMapping[str, Any]) -> float:
    """Return the monotonic origin for the active startup session."""

    started = session_state.get(STARTUP_TIMING_STARTED_KEY)
    if isinstance(started, (int, float)) and float(started) > 0:
        return float(started)
    now = time.perf_counter()
    session_state[STARTUP_TIMING_STARTED_KEY] = now
    return now


# Back-compat alias used by existing call sites and tests.
_startup_started_at = startup_session_origin


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


def fail_startup_with_error(
    coordinator: "StartupCoordinator",
    session_state: MutableMapping[str, Any],
    *,
    message: str,
    started_at: float | None = None,
) -> None:
    """Dismiss the loading shell and surface a recoverable startup failure."""

    coordinator.abort()
    log_startup_milestone(
        session_state,
        "loading_dismissed",
        started_at=started_at,
    )
    st.error(message)
    st.button("Refresh page", key="_startup_recovery_refresh", use_container_width=True)


def _stored_phase(
    session_state: MutableMapping[str, Any],
    *,
    default: StartupPhase,
) -> StartupPhase:
    raw_state = session_state.get(COORDINATOR_KEY)
    raw_phase = raw_state.get("phase") if isinstance(raw_state, Mapping) else default
    try:
        return StartupPhase(int(raw_phase))
    except (TypeError, ValueError):
        return default

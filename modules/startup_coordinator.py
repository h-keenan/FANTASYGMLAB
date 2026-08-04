from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from html import escape
from collections.abc import Mapping
import json
import time
from typing import Any, MutableMapping

import streamlit as st

from modules import performance
from modules import runtime_trace


COORDINATOR_KEY = "_startup_coordinator"
STARTUP_COMPLETE_KEY = "_startup_coordinator_complete"
STARTUP_TIMING_STARTED_KEY = "_startup_timing_started_at"

STARTUP_MILESTONE_LABELS = {
    "session_restored": "Session restored",
    "profile_loaded": "Profile loaded",
    "entitlements_loaded": "Entitlements loaded",
    "league_restored": "League restored",
    "dashboard_rendered": "Dashboard rendered",
    "loading_dismissed": "Loading dismissed",
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


_STATUS = {
    StartupPhase.PROCESS_START: "Starting DynastyGM...",
    StartupPhase.PUBLIC_DATA_LOADING: "Loading player data...",
    StartupPhase.AUTH_RESTORING: "Restoring your session...",
    StartupPhase.PROFILE_LOADING: "Loading your profile...",
    StartupPhase.ENTITLEMENT_LOADING: "Preparing your account...",
    StartupPhase.LEAGUE_RESTORING: "Loading your league...",
    StartupPhase.ROUTE_RESTORING: "Preparing your dashboard...",
    StartupPhase.PAGE_READY: "Finishing setup...",
    StartupPhase.INTERACTIVE: "Ready.",
}

_SHELL_CSS = """
<style>
.dg-startup-shell {
    align-items: center;
    background:
        radial-gradient(circle at 18% 12%, rgba(56, 189, 248, 0.12), transparent 30%),
        radial-gradient(circle at 82% 10%, rgba(168, 85, 247, 0.10), transparent 28%),
        linear-gradient(180deg, #05070c 0%, #08101d 52%, #05070c 100%);
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
    gap: 0.7rem;
    max-width: 32rem;
    text-align: center;
    width: min(100%, 32rem);
}
.dg-startup-mark {
    align-items: center;
    background: linear-gradient(145deg, rgba(56, 189, 248, 0.20), rgba(168, 85, 247, 0.16));
    border: 1px solid rgba(125, 211, 252, 0.30);
    border-radius: 18px;
    box-shadow: 0 18px 52px rgba(0, 0, 0, 0.34);
    display: flex;
    font-size: clamp(1rem, 2.4vw, 1.25rem);
    font-weight: 900;
    height: clamp(3.5rem, 10vw, 4.5rem);
    justify-content: center;
    letter-spacing: 0.06em;
    width: clamp(3.5rem, 10vw, 4.5rem);
}
.dg-startup-title {
    font-size: clamp(1.35rem, 4vw, 2rem);
    font-weight: 900;
    line-height: 1.05;
}
.dg-startup-status {
    color: #cbd5e1;
    font-size: clamp(0.9rem, 2.5vw, 1rem);
    line-height: 1.4;
    min-height: 1.4em;
}
.dg-startup-progress {
    background: rgba(148, 163, 184, 0.16);
    border-radius: 999px;
    height: 3px;
    margin-top: 0.35rem;
    overflow: hidden;
    width: min(13rem, 62vw);
}
.dg-startup-progress > span {
    background: linear-gradient(90deg, #38bdf8, #a855f7);
    display: block;
    height: 100%;
    width: var(--dg-startup-progress, 12%);
}
@media (max-width: 600px) {
    .dg-startup-shell {
        padding-left: max(1rem, env(safe-area-inset-left, 0px));
        padding-right: max(1rem, env(safe-area-inset-right, 0px));
    }
}
</style>
"""


def startup_shell_html(phase: StartupPhase) -> str:
    progress = max(10, min(96, int((int(phase) / int(StartupPhase.INTERACTIVE)) * 100)))
    status = escape(_STATUS[phase])
    return (
        _SHELL_CSS
        + "<div class='dg-startup-shell' role='status' aria-live='polite' aria-busy='true'>"
        "<div class='dg-startup-card'>"
        "<div class='dg-startup-mark' aria-hidden='true'>DGM</div>"
        "<div class='dg-startup-title'>DynastyGM</div>"
        f"<div class='dg-startup-status'>{status}</div>"
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


def _startup_started_at(session_state: MutableMapping[str, Any]) -> float:
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
) -> float:
    """Record one safe startup boundary with elapsed milliseconds."""

    label = STARTUP_MILESTONE_LABELS.get(milestone, milestone)
    origin = float(started_at if started_at is not None else _startup_started_at(session_state))
    elapsed_ms = round((time.perf_counter() - origin) * 1000, 1)
    entry = {
        "kind": "startup_milestone",
        "milestone": milestone,
        "label": label,
        "elapsed_ms": elapsed_ms,
    }
    try:
        print("DYNASTYGM_STARTUP " + json.dumps(entry, sort_keys=True), flush=True)
    except Exception:
        pass
    performance.record_timing(milestone, elapsed_ms, category="startup")
    trace_label = f"startup_{milestone}"
    if trace_label in runtime_trace.SAFE_MILESTONES:
        runtime_trace.mark(trace_label)
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
    if st.button("Refresh page", key="_startup_recovery_refresh", use_container_width=True):
        st.rerun()


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

"""Dashboard Python→browser visibility boundary (#240).

Distinguishes Streamlit Python render completion from browser DOM receipt.
Diagnostics are gated by DYNASTYGM_STARTUP=1 and must not create remount loops
(no setTriggerValue on the visibility probe).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, MutableMapping
from typing import Any

import streamlit as st

from modules import performance
from modules import startup_cold_path


# Probe component: observes DOM markers and logs to console only.
# Intentionally does NOT call setTriggerValue — that would remount Streamlit.
DASHBOARD_VISIBILITY_PROBE = st.components.v2.component(
    "dashboard_visibility_probe",
    html=(
        '<div id="fgl-dashboard-visibility-probe" '
        'data-fgl-visibility-probe="1" aria-hidden="true"></div>'
    ),
    js="""
    export default function(component) {
      const { data } = component
      if (!data || !data.enabled) return
      const sessionId = String((data && data.startup_session_id) || '')
      const runNumber = Number((data && data.startup_run_number) || 0)
      const token = sessionId + ':' + runNumber
      if (window.__fglDashVisToken === token) return
      const emitConsole = (payload) => {
        try {
          console.info('DYNASTYGM_STARTUP ' + JSON.stringify(payload))
        } catch (error) {}
      }
      const styleProbe = (el) => {
        if (!el || typeof window.getComputedStyle !== 'function') return null
        try {
          const cs = window.getComputedStyle(el)
          return {
            display: cs.display,
            visibility: cs.visibility,
            opacity: cs.opacity,
            height: cs.height,
            overflow: cs.overflow,
            zIndex: cs.zIndex,
          }
        } catch (error) {
          return null
        }
      }
      const inspect = () => {
        const useful = document.querySelector('[data-fgl-dashboard-useful="1"]')
        const complete = document.querySelector('[data-fgl-dashboard-complete="1"]')
        const root = document.querySelector('[data-fgl-dashboard-root="1"]')
        const shell = document.querySelector('.dg-startup-shell')
        const gamePlan = document.querySelector('.dashboard-workflow-shell')
          || document.body
        const overlayAbsent = !shell
        const usefulPresent = Boolean(useful || root)
        if (!usefulPresent) return false
        window.__fglDashVisToken = token
        document.documentElement.setAttribute('data-fgl-browser-dashboard-visible', '1')
        if (overlayAbsent) {
          document.documentElement.setAttribute('data-fgl-browser-overlay-absent', '1')
        }
        if (complete) {
          document.documentElement.setAttribute('data-fgl-browser-dashboard-complete', '1')
        }
        emitConsole({
          kind: 'browser_dashboard_visible',
          startup_session_id: sessionId,
          startup_run_number: runNumber,
          useful_present: usefulPresent,
          complete_present: Boolean(complete),
          overlay_absent: overlayAbsent,
          shell_style: styleProbe(shell),
          workflow_style: styleProbe(gamePlan),
          browser_ack_ms: (typeof performance !== 'undefined' && performance.now)
            ? Math.round(performance.now() * 10) / 10
            : 0,
        })
        return true
      }
      // rAF + short delayed checks — no Streamlit trigger, no remount loop.
      try {
        requestAnimationFrame(() => {
          if (inspect()) return
          setTimeout(inspect, 50)
          setTimeout(inspect, 250)
        })
      } catch (error) {
        setTimeout(inspect, 0)
      }
    }
    """,
    isolate_styles=False,
)


def diagnostics_enabled(*, environ: Mapping[str, Any] | None = None) -> bool:
    return startup_cold_path.startup_diagnostics_enabled(environ=environ)


def log_python_render_milestone(
    session_state: MutableMapping[str, Any],
    milestone: str,
    *,
    once: bool = True,
    detail: dict | None = None,
) -> None:
    """Python-side Dashboard presentation milestones (DYNASTYGM_STARTUP only)."""

    if not diagnostics_enabled():
        # Still record once-gated flags so callers can branch consistently.
        if once:
            logged = session_state.setdefault("_dashboard_render_milestones_once", {})
            if isinstance(logged, dict):
                if logged.get(milestone):
                    return
                logged[milestone] = True
        return
    if once:
        logged = session_state.setdefault("_dashboard_render_milestones_once", {})
        if not isinstance(logged, dict):
            logged = {}
            session_state["_dashboard_render_milestones_once"] = logged
        if logged.get(milestone):
            return
        logged[milestone] = True
    try:
        from modules import startup_coordinator

        startup_coordinator.log_startup_milestone(
            session_state,
            milestone,
            once=False,
            detail=detail,
        )
    except Exception:
        payload = {
            "kind": "startup_milestone",
            "milestone": performance._safe_label(milestone)[:64],
        }
        if isinstance(detail, dict) and detail:
            payload["detail"] = {
                str(k)[:40]: (v if isinstance(v, (int, float, bool)) else str(v)[:64])
                for k, v in list(detail.items())[:6]
            }
        try:
            print("DYNASTYGM_STARTUP " + json.dumps(payload, sort_keys=True), flush=True)
        except Exception:
            pass


def mount_browser_visibility_probe(session_state: MutableMapping[str, Any]) -> None:
    """Mount console-only browser ack probe after Dashboard Python render."""

    enabled = diagnostics_enabled()
    try:
        from modules import auth_restore_lifecycle

        session_id = str(
            session_state.get(auth_restore_lifecycle.STARTUP_SESSION_ID_KEY) or ""
        )
        run_number = int(
            session_state.get(auth_restore_lifecycle.STARTUP_RUN_NUMBER_KEY) or 0
        )
    except Exception:
        session_id = ""
        run_number = 0
    log_python_render_milestone(
        session_state,
        "dashboard_python_render_complete",
        once=True,
        detail={"probe_enabled": bool(enabled)},
    )
    try:
        DASHBOARD_VISIBILITY_PROBE(
            key="fgl_dashboard_visibility_probe",
            data={
                "enabled": bool(enabled),
                "startup_session_id": session_id[:16],
                "startup_run_number": run_number,
            },
            width=1,
            height=1,
        )
    except ValueError as exc:
        if "is not registered" not in str(exc):
            raise
    except Exception:
        pass

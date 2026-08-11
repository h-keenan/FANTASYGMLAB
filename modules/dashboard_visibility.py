"""Dashboard Python→browser visibility boundary (#240/#241).

#241: The #240 probe queried the component iframe document, so production never
logged browser_dashboard_visible even when (or if) the parent Streamlit DOM
mounted Dashboard markers. This module:

- observes window.parent.document (top-level Streamlit app)
- MutationObserver for marker/shell/block-container churn
- overlay watchdog that removes stale .dg-startup-shell after useful paint
- one stable setTriggerValue ack back to Python (no Date.now identity)

Visible canaries and FGL_SAFE_VISIBILITY_MODE CSS bypasses were removed in
#246 after the #244 GM-orb :has() root-collapse fix. Server-side milestones
remain gated by DYNASTYGM_STARTUP=1.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, MutableMapping
from typing import Any

import streamlit as st

from modules import performance
from modules import startup_cold_path


BROWSER_VISIBILITY_ACK_KEY = "_fgl_browser_dashboard_visibility_ack"
BROWSER_VISIBILITY_ACK_LOGGED_KEY = "_fgl_browser_dashboard_visibility_ack_logged"
CANARY_RENDERED_KEY = "_fgl_dashboard_canary_rendered"

# Retired in #246 — kept only so old env vars do not crash imports.
SAFE_VISIBILITY_ENV_KEY = "FGL_SAFE_VISIBILITY_MODE"
SAFE_VISIBILITY_CSS = ""


DASHBOARD_VISIBILITY_PROBE = st.components.v2.component(
    "dashboard_visibility_probe",
    html=(
        '<div id="fgl-dashboard-visibility-probe" '
        'data-fgl-visibility-probe="1" aria-hidden="true"></div>'
    ),
    js="""
    export default function(component) {
      const { data, setTriggerValue } = component
      if (!data || !data.enabled) return

      const sessionId = String((data && data.startup_session_id) || '')
      const runNumber = Number((data && data.startup_run_number) || 0)
      const route = String((data && data.route) || 'dashboard')
      const alreadyAcked = Boolean(data && data.already_acked)
      const allowAck = Boolean(data && data.allow_ack)
      const safeMode = Boolean(data && data.safe_visibility_mode)
      const canaryToken = String((data && data.canary_token) || '')
      const host = (window.parent && window.parent !== window) ? window.parent : window
      const doc = host.document || document

      const emitConsole = (payload) => {
        try {
          host.console.info('DYNASTYGM_STARTUP ' + JSON.stringify(payload))
        } catch (error) {
          try { console.info('DYNASTYGM_STARTUP ' + JSON.stringify(payload)) } catch (e2) {}
        }
      }

      const styleProbe = (el) => {
        if (!el || typeof host.getComputedStyle !== 'function') return null
        try {
          const cs = host.getComputedStyle(el)
          return {
            display: cs.display,
            visibility: cs.visibility,
            opacity: cs.opacity,
            height: cs.height,
            width: cs.width,
            overflow: cs.overflow,
            position: cs.position,
            zIndex: cs.zIndex,
            pointerEvents: cs.pointerEvents,
            transform: cs.transform,
          }
        } catch (error) {
          return null
        }
      }

      const rectProbe = (el) => {
        if (!el || typeof el.getBoundingClientRect !== 'function') return null
        try {
          const r = el.getBoundingClientRect()
          return {
            x: Math.round(r.x),
            y: Math.round(r.y),
            width: Math.round(r.width),
            height: Math.round(r.height),
            top: Math.round(r.top),
            left: Math.round(r.left),
          }
        } catch (error) {
          return null
        }
      }

      const nearestHiddenAncestor = (el) => {
        let node = el
        while (node && node !== doc.documentElement) {
          try {
            const cs = host.getComputedStyle(node)
            if (
              cs.display === 'none'
              || cs.visibility === 'hidden'
              || Number(cs.opacity) === 0
              || (node.hidden === true)
            ) {
              return {
                tag: String(node.tagName || '').toLowerCase(),
                className: String(node.className || '').slice(0, 80),
                display: cs.display,
                visibility: cs.visibility,
                opacity: cs.opacity,
              }
            }
          } catch (error) {}
          node = node.parentElement
        }
        return null
      }

      const wsState = () => {
        try {
          if (host.navigator && host.navigator.onLine === false) return -1
        } catch (error) {}
        return null
      }

      const dismissStaleStartupOverlay = () => {
        const shells = Array.from(doc.querySelectorAll('.dg-startup-shell'))
        if (!shells.length) return { removed: 0 }
        let removed = 0
        shells.forEach((shell) => {
          try {
            // Only remove the startup overlay itself — never dialogs/modals.
            shell.setAttribute('data-fgl-overlay-force-dismissed', '1')
            shell.style.setProperty('display', 'none', 'important')
            shell.style.setProperty('visibility', 'hidden', 'important')
            shell.style.setProperty('opacity', '0', 'important')
            shell.style.setProperty('pointer-events', 'none', 'important')
            shell.style.setProperty('z-index', '-1', 'important')
            if (shell.parentNode) {
              shell.parentNode.removeChild(shell)
              removed += 1
            }
          } catch (error) {}
        })
        return { removed }
      }

      const installMutationObserver = () => {
        const key = '__fglDashVisObserverInstalled'
        if (host[key]) return
        host[key] = true
        const interesting = (node) => {
          if (!node || node.nodeType !== 1) return false
          const el = node
          if (el.matches && (
            el.matches('[data-fgl-dashboard-root="1"]')
            || el.matches('[data-fgl-dashboard-useful="1"]')
            || el.matches('[data-fgl-dashboard-complete="1"]')
            || el.matches('.dg-startup-shell')
            || el.matches('.block-container')
            || el.matches('[data-testid="stAppViewContainer"]')
          )) return true
          if (el.querySelector && (
            el.querySelector('[data-fgl-dashboard-root="1"]')
            || el.querySelector('[data-fgl-dashboard-useful="1"]')
            || el.querySelector('.dg-startup-shell')
          )) return true
          return false
        }
        const logMutation = (type, node) => {
          try {
            const el = node
            emitConsole({
              kind: 'browser_dashboard_mutation',
              mutation: type,
              startup_session_id: sessionId,
              startup_run_number: runNumber,
              tag: String(el.tagName || '').toLowerCase().slice(0, 24),
              className: String(el.className || '').slice(0, 64),
              has_useful: Boolean(el.matches && el.matches('[data-fgl-dashboard-useful="1"]')),
              has_root: Boolean(el.matches && el.matches('[data-fgl-dashboard-root="1"]')),
              has_shell: Boolean(el.matches && el.matches('.dg-startup-shell')),
              browser_ms: (typeof host.performance !== 'undefined' && host.performance.now)
                ? Math.round(host.performance.now() * 10) / 10
                : 0,
            })
          } catch (error) {}
        }
        try {
          const obs = new host.MutationObserver((records) => {
            for (const rec of records) {
              rec.addedNodes && rec.addedNodes.forEach((n) => {
                if (interesting(n)) logMutation('added', n)
              })
              rec.removedNodes && rec.removedNodes.forEach((n) => {
                if (interesting(n)) logMutation('removed', n)
              })
            }
          })
          obs.observe(doc.documentElement || doc.body, {
            childList: true,
            subtree: true,
          })
        } catch (error) {}
      }

      const snapshot = () => {
        const useful = doc.querySelector('[data-fgl-dashboard-useful="1"]')
        const complete = doc.querySelector('[data-fgl-dashboard-complete="1"]')
        const root = doc.querySelector('[data-fgl-dashboard-root="1"]')
        const shells = Array.from(doc.querySelectorAll('.dg-startup-shell'))
        const workflow = doc.querySelector('.dashboard-workflow-shell')
        const block = doc.querySelector('.block-container')
        const statusWidgets = doc.querySelectorAll(
          '[data-testid="stStatusWidget"], [data-testid="stSpinner"], .stSpinner'
        ).length
        let gamePlanText = false
        let canaryPresent = false
        let gamePlanEl = null
        try {
          const bodyText = String((doc.body && doc.body.innerText) || '')
          gamePlanText = bodyText.indexOf("Today's Game Plan") >= 0
          if (canaryToken) canaryPresent = bodyText.indexOf(canaryToken) >= 0
          const candidates = doc.querySelectorAll('h1,h2,h3,h4,div,span,p,section')
          for (const el of candidates) {
            const t = String(el.textContent || '')
            if (t.indexOf("Today's Game Plan") < 0) continue
            try {
              const r = el.getBoundingClientRect()
              if (r.width > 0 && r.height > 0) {
                gamePlanEl = el
                break
              }
            } catch (error) {}
          }
        } catch (error) {}
        // Prefer a real content node — empty marker shells report height 0.
        const dimTarget = gamePlanEl || block
          || doc.querySelector('[data-testid="stMain"]')
          || doc.querySelector('[data-testid="stAppViewContainer"]')
          || workflow
        const target = dimTarget || root || useful
        const rect = rectProbe(dimTarget || target)
        const style = styleProbe(dimTarget || target)
        let inViewport = false
        if (rect) {
          const vh = host.innerHeight || 0
          const vw = host.innerWidth || 0
          inViewport = rect.width > 0 && rect.height > 0
            && rect.top < vh && (rect.top + rect.height) > 0
            && rect.left < vw && (rect.left + rect.width) > 0
        }
        return {
          useful_present: Boolean(useful),
          complete_present: Boolean(complete),
          root_present: Boolean(root),
          useful_count: doc.querySelectorAll('[data-fgl-dashboard-useful="1"]').length,
          root_count: doc.querySelectorAll('[data-fgl-dashboard-root="1"]').length,
          shell_count: shells.length,
          shell_style: styleProbe(shells[0] || null),
          overlay_absent: shells.length === 0,
          game_plan_text_present: gamePlanText,
          canary_present: canaryPresent,
          status_widget_count: statusWidgets,
          root_style: style,
          root_rect: rect,
          hidden_ancestor: nearestHiddenAncestor(target),
          intersects_viewport: inViewport,
          non_zero_dimensions: Boolean(rect && rect.width > 0 && rect.height > 0),
          document_visibility: doc.visibilityState || '',
          document_hidden: Boolean(doc.hidden),
          ready_state: doc.readyState || '',
          websocket_state: wsState(),
          probe_document: (host === window) ? 'same' : 'parent',
        }
      }

      if (safeMode) {
        try { doc.documentElement.setAttribute('data-fgl-safe-visibility', '1') } catch (error) {}
      }

      installMutationObserver()

      const maybeAck = (snap, overlay, phase) => {
        if (!allowAck || alreadyAcked) return
        if (host.__fglDashVisAcked === sessionId) return
        // Require useful marker + no overlay. Prefer Game Plan text when present,
        // but still ack on useful+dimensions so marker-only paths are diagnosable.
        const visible = Boolean(
          snap.useful_present
          && snap.overlay_absent
          && snap.non_zero_dimensions
        )
        if (!visible) {
          host.__fglDashVisFirstSeenAt = 0
          return
        }
        const now = (typeof host.performance !== 'undefined' && host.performance.now)
          ? host.performance.now()
          : Date.now()
        if (!host.__fglDashVisFirstSeenAt) {
          host.__fglDashVisFirstSeenAt = now
          emitConsole({
            kind: 'browser_dashboard_first_seen',
            startup_session_id: sessionId,
            startup_run_number: runNumber,
            phase: phase || 'inspect',
            browser_ms: Math.round(now * 10) / 10,
          })
        }
        // Defer setTriggerValue until ≥5s continuous visibility so the ack
        // remount cannot erase the paint we are proving.
        const elapsed = now - host.__fglDashVisFirstSeenAt
        const stableEnough = elapsed >= 5000 || phase === 't5000'
        if (!stableEnough) return
        host.__fglDashVisAcked = sessionId
        const payload = {
          kind: 'browser_dashboard_visible',
          route,
          startup_session_id: sessionId,
          startup_run_number: runNumber,
          overlay_removed: Number((overlay && overlay.removed) || 0),
          browser_ack_ms: Math.round(now * 10) / 10,
          stable_visible_ms: Math.round(elapsed * 10) / 10,
          useful_present: snap.useful_present,
          complete_present: snap.complete_present,
          root_present: snap.root_present,
          game_plan_text_present: snap.game_plan_text_present,
          overlay_absent: snap.overlay_absent,
          non_zero_dimensions: snap.non_zero_dimensions,
          intersects_viewport: snap.intersects_viewport,
          shell_count: snap.shell_count,
          probe_document: snap.probe_document,
          document_visibility: snap.document_visibility,
          ready_state: snap.ready_state,
          canary_present: snap.canary_present,
        }
        emitConsole(payload)
        try {
          doc.documentElement.setAttribute('data-fgl-browser-dashboard-visible', '1')
          if (snap.overlay_absent) {
            doc.documentElement.setAttribute('data-fgl-browser-overlay-absent', '1')
          }
          if (snap.complete_present) {
            doc.documentElement.setAttribute('data-fgl-browser-dashboard-complete', '1')
          }
        } catch (error) {}
        // Stable identity (no Date.now) — one remount max per startup session.
        try {
          setTriggerValue('visibility_ack', {
            kind: 'browser_dashboard_visible',
            route,
            startup_session_id: sessionId,
            startup_run_number: runNumber,
            useful_present: snap.useful_present,
            root_present: snap.root_present,
            game_plan_text_present: snap.game_plan_text_present,
            overlay_absent: snap.overlay_absent,
            non_zero_dimensions: snap.non_zero_dimensions,
            intersects_viewport: snap.intersects_viewport,
            display: snap.root_style && snap.root_style.display,
            visibility: snap.root_style && snap.root_style.visibility,
            opacity: snap.root_style && snap.root_style.opacity,
            width: snap.root_rect && snap.root_rect.width,
            height: snap.root_rect && snap.root_rect.height,
            shell_count: snap.shell_count,
            probe_document: snap.probe_document,
            document_visibility: snap.document_visibility,
            ready_state: snap.ready_state,
            websocket_state: snap.websocket_state,
            canary_present: snap.canary_present,
            stable_visible_ms: Math.round(elapsed * 10) / 10,
            ack_token: sessionId,
          })
        } catch (error) {}
      }

      const inspect = (phase) => {
        let snap = snapshot()
        let overlay = { removed: 0 }
        if (snap.useful_present && snap.shell_count > 0) {
          overlay = dismissStaleStartupOverlay()
          snap = snapshot()
          emitConsole({
            kind: 'browser_startup_overlay_watchdog',
            startup_session_id: sessionId,
            startup_run_number: runNumber,
            removed: overlay.removed,
            shell_count_after: snap.shell_count,
            phase: phase || 'inspect',
          })
        }
        emitConsole({
          kind: 'browser_dashboard_inspect',
          startup_session_id: sessionId,
          startup_run_number: runNumber,
          phase: phase || 'inspect',
          useful_present: snap.useful_present,
          root_present: snap.root_present,
          game_plan_text_present: snap.game_plan_text_present,
          overlay_absent: snap.overlay_absent,
          shell_count: snap.shell_count,
          non_zero_dimensions: snap.non_zero_dimensions,
          intersects_viewport: snap.intersects_viewport,
          probe_document: snap.probe_document,
          canary_present: snap.canary_present,
          hidden_ancestor: snap.hidden_ancestor,
          root_rect: snap.root_rect,
          root_style: snap.root_style,
        })
        // Set DOM attr early for Playwright; defer setTriggerValue to ≥5s.
        if (snap.useful_present && snap.overlay_absent && snap.non_zero_dimensions) {
          try {
            doc.documentElement.setAttribute('data-fgl-browser-dashboard-visible', '1')
            doc.documentElement.setAttribute('data-fgl-browser-overlay-absent', '1')
          } catch (error) {}
        }
        maybeAck(snap, overlay, phase)
        return Boolean(snap.useful_present && snap.overlay_absent)
      }

      try {
        host.requestAnimationFrame(() => {
          inspect('raf')
          host.setTimeout(() => inspect('t50'), 50)
          host.setTimeout(() => inspect('t250'), 250)
          host.setTimeout(() => inspect('t1000'), 1000)
          host.setTimeout(() => inspect('t5000'), 5000)
        })
      } catch (error) {
        try { setTimeout(() => inspect('fallback'), 0) } catch (e2) {}
      }
    }
    """,
    isolate_styles=False,
)


def diagnostics_enabled(*, environ: Mapping[str, Any] | None = None) -> bool:
    return startup_cold_path.startup_diagnostics_enabled(environ=environ)


def safe_visibility_mode_enabled(*, environ: Mapping[str, Any] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    return str(env.get(SAFE_VISIBILITY_ENV_KEY, "")).strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def log_python_render_milestone(
    session_state: MutableMapping[str, Any],
    milestone: str,
    *,
    once: bool = True,
    detail: dict | None = None,
) -> None:
    """Python-side Dashboard presentation milestones (DYNASTYGM_STARTUP only)."""

    if not diagnostics_enabled():
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


def _session_ids(session_state: MutableMapping[str, Any]) -> tuple[str, int]:
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
    return session_id, run_number


def render_dashboard_canary(session_state: MutableMapping[str, Any]) -> str:
    """Server-side only token for DYNASTYGM_STARTUP probe correlation.

    Never emits visible Streamlit UI (#246 cleanup).
    """

    if not diagnostics_enabled():
        return ""
    session_id, _ = _session_ids(session_state)
    token = f"dash_vis_{session_id[:16] or 'none'}"
    if not session_state.get(CANARY_RENDERED_KEY):
        session_state[CANARY_RENDERED_KEY] = True
        log_python_render_milestone(
            session_state,
            "dashboard_visibility_token_ready",
            once=True,
            detail={"token_prefix": token[:32]},
        )
    return token


def apply_safe_visibility_css_if_enabled() -> bool:
    """Retired (#246). Safe-visibility CSS bypass removed after #244 root fix."""

    return False


def _log_browser_ack(
    session_state: MutableMapping[str, Any],
    ack: Mapping[str, Any],
) -> None:
    if session_state.get(BROWSER_VISIBILITY_ACK_LOGGED_KEY):
        return
    session_state[BROWSER_VISIBILITY_ACK_LOGGED_KEY] = True
    session_state[BROWSER_VISIBILITY_ACK_KEY] = dict(ack)
    detail = {
        str(k)[:40]: (
            v if isinstance(v, (int, float, bool)) or v is None else str(v)[:64]
        )
        for k, v in list(ack.items())[:16]
    }
    log_python_render_milestone(
        session_state,
        "browser_dashboard_visible",
        once=True,
        detail=detail,
    )
    try:
        print(
            "DYNASTYGM_STARTUP "
            + json.dumps(
                {
                    "kind": "browser_dashboard_visible",
                    "source": "python_ack",
                    **detail,
                },
                sort_keys=True,
            ),
            flush=True,
        )
    except Exception:
        pass


def mount_browser_visibility_probe(
    session_state: MutableMapping[str, Any],
    *,
    route: str = "dashboard",
    canary_token: str = "",
) -> None:
    """Mount parent-document visibility probe after Dashboard Python render."""

    enabled = diagnostics_enabled()
    if not enabled:
        log_python_render_milestone(
            session_state,
            "dashboard_python_render_complete",
            once=True,
            detail={"probe_enabled": False},
        )
        return

    session_id, run_number = _session_ids(session_state)
    already_acked = bool(session_state.get(BROWSER_VISIBILITY_ACK_KEY))

    log_python_render_milestone(
        session_state,
        "dashboard_python_render_complete",
        once=True,
        detail={
            "probe_enabled": True,
            "already_acked": already_acked,
        },
    )
    try:
        result = DASHBOARD_VISIBILITY_PROBE(
            key="fgl_dashboard_visibility_probe",
            data={
                "enabled": True,
                "allow_ack": not already_acked,
                "already_acked": already_acked,
                "safe_visibility_mode": False,
                "startup_session_id": session_id[:16],
                "startup_run_number": run_number,
                "route": str(route or "dashboard")[:32],
                "canary_token": str(canary_token or "")[:48],
            },
            width=1,
            height=1,
        )
    except ValueError as exc:
        if "is not registered" not in str(exc):
            raise
        return
    except Exception:
        return

    ack = getattr(result, "visibility_ack", None)
    if isinstance(ack, dict) and ack:
        _log_browser_ack(session_state, ack)

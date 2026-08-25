"""Browser presentation-stability probe — Python→DOM gap measurement.

Passive console diagnostics only. Does not write back to Python, does not
rerun, and does not change football truth. Enabled with DYNASTYGM_STARTUP=1
(same gate as other founder traces).
"""

from __future__ import annotations

import os
from collections.abc import MutableMapping
from typing import Any

import streamlit as st


ENV_KEY = "DYNASTYGM_STARTUP"

PRESENTATION_STABILITY_PROBE = st.components.v2.component(
    "presentation_stability_probe",
    html=(
        '<div id="fgl-presentation-stability-probe" '
        'data-fgl-presentation-probe="1" aria-hidden="true"></div>'
    ),
    js="""
    export default function(component) {
      const { data } = component
      if (!data || !data.enabled) return

      const host = (window.parent && window.parent !== window) ? window.parent : window
      const doc = host.document || document
      const route = String((data && data.route) || '')
      const scriptSeq = Number((data && data.script_seq) || 0)

      const emit = (payload) => {
        try {
          host.console.info('DYNASTYGM_STARTUP ' + JSON.stringify(payload))
        } catch (error) {
          try { console.info('DYNASTYGM_STARTUP ' + JSON.stringify(payload)) } catch (e2) {}
        }
      }

      const stateKey = '__fglPresentationStability'
      if (!host[stateKey]) {
        host[stateKey] = {
          commits: 0,
          maxShiftPx: 0,
          lastHeight: 0,
          routeReplacements: 0,
          lateSections: 0,
          firstRouteRootMs: 0,
          probeStartMs: host.performance && host.performance.now ? host.performance.now() : 0,
          lastChangeMs: host.performance && host.performance.now ? host.performance.now() : 0,
          emittedSeq: 0,
        }
      }
      const bag = host[stateKey]
      const nowMs = () => (host.performance && host.performance.now) ? host.performance.now() : 0

      const observeRoot = () => {
        if (host.__fglPresentationObserverInstalled) return
        host.__fglPresentationObserverInstalled = true
        const target = doc.querySelector('[data-testid="stAppViewContainer"]')
          || doc.querySelector('.main')
          || doc.body
        if (!target || typeof host.ResizeObserver !== 'function') return
        const ro = new host.ResizeObserver((entries) => {
          bag.commits += 1
          bag.lastChangeMs = nowMs()
          for (const entry of entries) {
            const height = entry.contentRect && entry.contentRect.height
            if (typeof height !== 'number') continue
            if (bag.lastHeight) {
              const delta = Math.abs(height - bag.lastHeight)
              if (delta > bag.maxShiftPx) bag.maxShiftPx = delta
            }
            bag.lastHeight = height
          }
        })
        try { ro.observe(target) } catch (error) {}
        const mo = new host.MutationObserver((mutations) => {
          bag.lastChangeMs = nowMs()
          for (const mutation of mutations) {
            const nodes = []
            mutation.addedNodes && mutation.addedNodes.forEach((node) => nodes.push(node))
            for (const node of nodes) {
              if (!node || node.nodeType !== 1) continue
              const el = node
              const hasRoute = (el.matches && el.matches('[data-fgl-route-root]'))
                || (el.querySelector && el.querySelector('[data-fgl-route-root]'))
              if (hasRoute) {
                bag.routeReplacements += 1
                if (!bag.firstRouteRootMs) bag.firstRouteRootMs = nowMs()
              }
              const late = (el.matches && (
                el.matches('[data-testid="stExpander"]')
                || el.matches('.st-key-dashboard_context_pair')
                || el.matches('[data-fgl-surface-pending]')
              ))
              if (late) bag.lateSections += 1
            }
          }
        })
        try {
          mo.observe(target, { childList: true, subtree: true })
        } catch (error) {}
      }

      observeRoot()
      bag.lastChangeMs = nowMs()

      const emitStable = () => {
        if (bag.emittedSeq === scriptSeq) return
        bag.emittedSeq = scriptSeq
        const probeStart = bag.probeStartMs || 0
        const stableMs = nowMs()
        emit({
          kind: 'presentation_stable',
          route: route,
          script_seq: scriptSeq,
          layout_commits: bag.commits,
          largest_vertical_shift_px: Math.round(bag.maxShiftPx),
          route_root_replacements: bag.routeReplacements,
          late_section_mounts: bag.lateSections,
          probe_to_stable_ms: Math.round((stableMs - probeStart) * 10) / 10,
          first_route_root_ms: Math.round((bag.firstRouteRootMs || 0) * 10) / 10,
          python_wall_ms: Number((data && data.python_wall_ms) || 0),
          python_unaccounted_ms: Number((data && data.python_unaccounted_ms) || 0),
          python_complete: Boolean(data && data.python_complete),
        })
      }

      if (host.__fglPresentationStableTimer) {
        try { host.clearInterval(host.__fglPresentationStableTimer) } catch (error) {}
      }
      host.__fglPresentationStableTimer = host.setInterval(() => {
        const quiet = nowMs() - bag.lastChangeMs
        if (quiet >= 180) {
          emitStable()
          try { host.clearInterval(host.__fglPresentationStableTimer) } catch (error) {}
        }
      }, 80)
    }
    """,
)


def enabled(*, environ: dict | None = None) -> bool:
    env = environ if environ is not None else os.environ
    flag = str(env.get(ENV_KEY, "")).strip().casefold()
    return flag in {"1", "true", "yes", "on"}


def mount_presentation_stability_probe(
    session_state: MutableMapping[str, Any] | None = None,
    *,
    route: str = "",
    python_complete: bool = False,
    python_wall_ms: float = 0.0,
    python_unaccounted_ms: float = 0.0,
) -> None:
    """Mount or refresh the passive presentation observer. Never triggers a rerun."""

    if not enabled():
        return
    state = session_state if session_state is not None else {}
    script_seq = int(state.get("_hot_path_script_seq") or 0)
    try:
        PRESENTATION_STABILITY_PROBE(
            key="fgl_presentation_stability_probe",
            data={
                "enabled": True,
                "route": str(route or "")[:32],
                "script_seq": script_seq,
                "python_complete": bool(python_complete),
                "python_wall_ms": round(float(python_wall_ms or 0.0), 1),
                "python_unaccounted_ms": round(float(python_unaccounted_ms or 0.0), 1),
            },
            width=1,
            height=1,
        )
    except ValueError as exc:
        if "is not registered" not in str(exc):
            raise
    except Exception:
        return

"""GM destination sheet dismiss bridge — outside click + Escape → Streamlit state.

Presentation/interaction only. Authoritative open flag remains
``st.session_state["_mobile_destination_sheet_open"]`` in app.py; this module
only reports dismiss intents so Python can clear that flag. No fullscreen
click-catching overlay (avoids trapping Dashboard input after dismiss).
"""

from __future__ import annotations

from typing import Any

import streamlit as st

GM_SHEET_DISMISS_COMPONENT = st.components.v2.component(
    "gm_sheet_dismiss",
    html="""
    <div id="gm-sheet-dismiss-root" aria-hidden="true" style="display:none;width:0;height:0;overflow:hidden"></div>
    """,
    js="""
    export default function(component) {
      const { setTriggerValue } = component
      const win = (window.parent && window.parent !== window) ? window.parent : window
      const doc = win.document

      const PANEL_SEL =
        'div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker)'
      const ORB_SEL = 'div[class*="st-key-mobile_gm_sheet_trigger_"]'

      const inside = (target, sel) => {
        try {
          return !!(target && target.closest && target.closest(sel))
        } catch (err) {
          return false
        }
      }

      if (win.__dgGmSheetDismissCleanup) {
        try { win.__dgGmSheetDismissCleanup() } catch (err) {}
        win.__dgGmSheetDismissCleanup = null
      }

      const dismiss = (reason) => {
        setTriggerValue("dismiss", { reason: String(reason || "unknown"), ts: Date.now() })
      }

      const onPointerDown = (event) => {
        if (!doc.querySelector(PANEL_SEL)) return
        const t = event.target
        if (inside(t, PANEL_SEL)) return
        // Orb owns toggle via Streamlit on_click — do not also dismiss here.
        if (inside(t, ORB_SEL)) return
        dismiss("outside")
      }

      const onKeyDown = (event) => {
        if (event.key !== "Escape" && event.code !== "Escape") return
        if (!doc.querySelector(PANEL_SEL)) return
        dismiss("escape")
      }

      doc.addEventListener("pointerdown", onPointerDown, true)
      doc.addEventListener("keydown", onKeyDown, true)
      win.__dgGmSheetDismissCleanup = () => {
        doc.removeEventListener("pointerdown", onPointerDown, true)
        doc.removeEventListener("keydown", onKeyDown, true)
      }
    }
    """,
    isolate_styles=False,
)

_DISMISS_TS_KEY = "_mobile_gm_sheet_dismiss_ts"


def consume_gm_sheet_dismiss(*, key: str = "gm_sheet_dismiss") -> bool:
    """Mount the dismiss bridge. Return True when a new dismiss was reported."""

    try:
        result = GM_SHEET_DISMISS_COMPONENT(
            key=key,
            data={"open": True},
            width=1,
            height=1,
            on_dismiss_change=lambda: None,
        )
    except ValueError as exc:
        # Local AppTest / unregistered component — ignore; buttons still close.
        if "is not registered" not in str(exc):
            raise
        return False

    payload: Any = getattr(result, "dismiss", None)
    if not isinstance(payload, dict):
        return False
    try:
        ts = int(payload.get("ts") or 0)
    except Exception:
        return False
    if ts <= 0:
        return False
    if st.session_state.get(_DISMISS_TS_KEY) == ts:
        return False
    st.session_state[_DISMISS_TS_KEY] = ts
    return True

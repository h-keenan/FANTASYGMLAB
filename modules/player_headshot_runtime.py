"""Delegated image lifecycle for React-rendered canonical player headshots."""

import streamlit as st

from modules.html_rendering import inject_global_styles

HEADSHOT_RUNTIME_JS = """
export default function(component) {
  const win = window.parent || window
  const doc = win.document
  const selector = '.dg-player-headshot-image, .dg-modal-list-avatar-image'
  const settle = (img) => {
    if (img.naturalWidth > 0) img.classList.add('is-loaded')
    else img.remove()
  }
  if (!win.__dgHeadshotsBound) {
    win.__dgHeadshotsBound = true
    doc.addEventListener('load', (event) => {
      if (event.target.matches?.(selector)) settle(event.target)
    }, true)
    doc.addEventListener('error', (event) => {
      if (event.target.matches?.(selector)) event.target.remove()
    }, true)
  }
  doc.querySelectorAll(selector).forEach(img => {
    if (img.complete) settle(img)
  })
}
"""


def render_player_headshot_runtime() -> None:
    """Bind before route images; cached images are handled on initial mount."""
    inject_global_styles("""
    [class*="st-key-dg_headshot_runtime"] {
      position:fixed!important;left:-10px!important;top:-10px!important;
      width:1px!important;min-width:1px!important;max-width:1px!important;
      height:1px!important;min-height:1px!important;max-height:1px!important;
      opacity:0!important;pointer-events:none!important;overflow:hidden!important;
    }
    """)
    bridge = st.components.v2.component(
        "player_headshot_runtime", html="<span aria-hidden='true'></span>",
        js=HEADSHOT_RUNTIME_JS, isolate_styles=False,
    )
    bridge(key="dg_headshot_runtime", width=1, height=1)

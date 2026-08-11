"""P0 binary render canaries — diagnostic build only.

Ugly, visible native Streamlit primitives. Not HTML, not components, not CSS-styled.
Safe-render CSS disables custom hiding/overlays that can cover main Streamlit content.
"""

from __future__ import annotations

import os

import streamlit as st

from modules.html_rendering import inject_global_styles

# Diagnostic build: safe-render ON by default so production can see native output.
# Set FGL_P0_SAFE_RENDER=0 to leave custom CSS alone.
SAFE_RENDER_ENV = "FGL_P0_SAFE_RENDER"

# Unconditional when injected (no :has / data-attr dependency for the force-visible rules).
SAFE_RENDER_CSS = """
/* === FGL P0 SAFE RENDER (diagnostic) === */
.dg-startup-shell,
.dg-startup-shell * {
  display: none !important;
  visibility: hidden !important;
  opacity: 0 !important;
  pointer-events: none !important;
  z-index: -1 !important;
  position: static !important;
  inset: auto !important;
  width: 0 !important;
  height: 0 !important;
  overflow: hidden !important;
}
body:has(.dg-startup-shell) .app-hero {
  display: block !important;
}
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
section[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
.main,
.block-container,
[data-testid="stVerticalBlock"],
[data-testid="stElementContainer"],
.element-container,
[data-testid="stMarkdownContainer"],
[data-testid="stText"],
[data-testid="stButton"] {
  opacity: 1 !important;
  visibility: visible !important;
  transform: none !important;
  filter: none !important;
  clip: auto !important;
  clip-path: none !important;
  pointer-events: auto !important;
  overflow: visible !important;
  max-height: none !important;
  height: auto !important;
}
"""


def safe_render_enabled() -> bool:
    raw = str(os.environ.get(SAFE_RENDER_ENV, "1")).strip().casefold()
    return raw not in {"0", "false", "no", "off"}


def inject_safe_render_css() -> None:
    if not safe_render_enabled():
        return
    inject_global_styles(SAFE_RENDER_CSS)


def emit(label: str) -> None:
    """Emit one unmistakable native Streamlit text canary."""

    st.write(str(label))

"""P0 native Streamlit render bypass (diagnostic / isolation).

FGL_P0_NATIVE_RENDER=1 → earliest production-path stop: native title/button only.
No APP_CSS, startup shell, auth, GM orb, dashboard, components, or JS.
"""

from __future__ import annotations

import os

import streamlit as st

NATIVE_RENDER_ENV = "FGL_P0_NATIVE_RENDER"


def native_render_enabled() -> bool:
    raw = str(os.environ.get(NATIVE_RENDER_ENV, "")).strip().casefold()
    return raw in {"1", "true", "yes", "on"}


def maybe_run_native_only_bypass() -> bool:
    """If enabled, emit native Streamlit primitives and st.stop(). Return True."""

    if not native_render_enabled():
        return False
    st.set_page_config(page_title="FGL P0", layout="centered")
    st.title("FGL NATIVE RENDER TEST")
    st.write("If you can read this, native Streamlit rendering works.")
    st.button("Native test button")
    st.stop()
    return True

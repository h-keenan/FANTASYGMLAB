"""Shared helpers for Streamlit HTML/CSS injection."""

from __future__ import annotations

import streamlit as st


def normalized_style_block(css_or_style: str) -> str:
    """Return one valid HTML style block for app CSS injection."""
    text = str(css_or_style or "").strip()
    if text.lower().startswith("style>"):
        text = "<" + text

    lower = text.lower()
    if not lower.startswith("<style"):
        text = f"<style>\n{text}\n</style>"
    elif not lower.endswith("</style>"):
        text = f"{text}\n</style>"

    return text


def render_html_fragment(html: str) -> None:
    """Render trusted app-owned HTML without showing the source as text."""
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


def inject_global_styles(css_or_style: str) -> None:
    """Inject global app styles as a valid hidden style block."""
    render_html_fragment(normalized_style_block(css_or_style))

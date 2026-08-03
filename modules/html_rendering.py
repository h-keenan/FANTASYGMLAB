"""Shared helpers for Streamlit HTML/CSS injection."""

from __future__ import annotations

import streamlit as st


def normalized_style_block(css_or_style: str) -> str:
    """Return one valid HTML style block for app CSS injection."""
    text = str(css_or_style or "").strip()
    if not text:
        raise ValueError("Global CSS is empty.")
    if text.lower().startswith("style>"):
        text = "<" + text

    lower = text.lower()
    if lower.startswith("<style") and "</style>" in lower and not lower.endswith("</style>"):
        raise ValueError("Global CSS style block has trailing markup after </style>.")
    if lower.startswith("<") and not lower.startswith("<style"):
        raise ValueError("Global CSS must be plain CSS or a <style> block.")

    if not lower.startswith("<style"):
        text = f"<style>\n{text}\n</style>"
    else:
        lower = text.lower()
        if "</style>" not in lower:
            text = f"{text}\n</style>"

    return text


def render_html_fragment(html: str) -> None:
    """Render trusted app-owned HTML without showing the source as text."""
    st.markdown(str(html or ""), unsafe_allow_html=True)


def inject_global_styles(css_or_style: str) -> None:
    """Inject global app styles as a valid hidden style block."""
    # Streamlit's public HTML API treats a style-only body as non-layout
    # content, unlike markdown containers which leave an empty flex-grid row.
    st.html(normalized_style_block(css_or_style))

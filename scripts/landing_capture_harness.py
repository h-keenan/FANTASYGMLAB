#!/usr/bin/env python3
"""Minimal Streamlit harness that renders only the public marketing landing."""

from __future__ import annotations

import streamlit as st

from modules.marketing_landing import render_marketing_landing


def main() -> None:
    st.set_page_config(
        page_title="FantasyGM Lab landing capture",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    render_marketing_landing()


if __name__ == "__main__":
    main()

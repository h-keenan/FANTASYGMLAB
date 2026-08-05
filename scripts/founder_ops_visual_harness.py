"""Deterministic Founder Ops visual harness (flag-gated, synthetic only)."""

from __future__ import annotations

import os

import streamlit as st

os.environ["DYNASTYGM_FOUNDER_OPS"] = "1"

from modules import brand_identity
from modules import founder_ops_ui
from modules.html_rendering import inject_global_styles
from modules.app_styles import APP_CSS


st.set_page_config(page_title="Founder Ops Harness", layout="wide")
inject_global_styles(APP_CSS)
st.markdown(
    f"<div data-testid='founder-ops-harness'>"
    f"<strong>{brand_identity.PRODUCT_NAME}</strong> · Founder Ops harness"
    f"</div>",
    unsafe_allow_html=True,
)
founder_ops_ui.render_founder_ops_dashboard(secrets={})

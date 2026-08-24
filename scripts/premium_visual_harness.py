"""Synthetic Premium-page browser harness; no auth, billing, or provider calls."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import streamlit as st

from modules import app_styles
from modules import premium
from modules import premium_page
from modules import stripe_billing


# AppTest and the standalone browser server use separate component registries.
premium_page = importlib.reload(premium_page)


st.set_page_config(page_title="Premium UX fixture", layout="wide")
st.markdown(app_styles.APP_CSS, unsafe_allow_html=True)
st.session_state.setdefault("auth_session", {"user_id": "fixture-user"})
st.session_state.setdefault("auth_email", "fixture@example.invalid")

mode = st.sidebar.radio("Account state", ("Free", "Premium"), index=0)
config = stripe_billing.StripeBillingConfig(
    secret_key="sk_test_fixture",
    price_monthly="price_monthly_fixture",
    price_annual="price_annual_fixture",
)


def _fixture_checkout_session(**kwargs):
    interval = str(kwargs.get("interval") or "")
    st.session_state["fixture_checkout_interval"] = interval
    return SimpleNamespace(url=f"https://example.com/fgl-checkout-fixture/{interval}")


_original_load_config = premium_page.stripe_billing.load_stripe_config
_original_checkout = premium_page.stripe_billing.create_checkout_session
try:
    premium_page.stripe_billing.load_stripe_config = lambda **_kwargs: config
    premium_page.stripe_billing.create_checkout_session = _fixture_checkout_session
    premium_page.render_premium_page(
        entitlement=premium.PREMIUM if mode == "Premium" else premium.FREE
    )
finally:
    premium_page.stripe_billing.load_stripe_config = _original_load_config
    premium_page.stripe_billing.create_checkout_session = _original_checkout
st.caption("Synthetic Premium fixture only — no customer data or provider calls.")

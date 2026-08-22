from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, patch

from modules import account_ui, premium, premium_page, stripe_billing


def test_new_authenticated_account_needs_sleeper_connection():
    assert account_ui.needs_sleeper_connection_onboarding(
        user_id="user-1", username="", selected_league_id="", saved_leagues=[]
    )


def test_returning_and_connected_accounts_bypass_connection_onboarding():
    assert not account_ui.needs_sleeper_connection_onboarding(
        user_id="user-1", saved_leagues=[{"league_id": "league-1"}]
    )
    assert not account_ui.needs_sleeper_connection_onboarding(
        user_id="user-1", username="sleeper-user", saved_leagues=[]
    )
    assert not account_ui.needs_sleeper_connection_onboarding(
        user_id="user-1", selected_league_id="league-1", saved_leagues=[]
    )


def test_signed_out_user_never_enters_authenticated_onboarding():
    assert not account_ui.needs_sleeper_connection_onboarding(
        user_id="", username="", selected_league_id="", saved_leagues=[]
    )


def test_confirmed_account_connect_cta_routes_to_existing_import_flow():
    state = {
        "auth_session": {"user_id": "user-1", "access_token": "token"},
        "auth_email": "founder@example.com",
        "account_saved_leagues_cache": [],
    }
    rendered: list[str] = []

    def button(label, **_kwargs):
        return label == "Connect Sleeper Account"

    with (
        patch.object(account_ui.st, "session_state", state),
        patch.object(account_ui.st, "markdown", side_effect=lambda value, **_: rendered.append(value)),
        patch.object(account_ui.st, "success"),
        patch.object(account_ui.st, "caption"),
        patch.object(account_ui.st, "info"),
        patch.object(account_ui.st, "button", side_effect=button),
        patch.object(account_ui.account_store, "default_saved_league", return_value=None),
    ):
        actions = account_ui.render_mobile_auth_entry(
            config={
                "enabled": True,
                "url": "https://example.supabase.co",
                "anon_key": "anon-key",
            }
        )

    assert actions["logged_in"] is True
    assert actions["continue_guest"] is True
    assert "Connect Sleeper Account" in "".join(rendered)


def test_plan_cards_show_launch_prices_and_obvious_selection():
    monthly = premium_page._plan_option_html(stripe_billing.MONTHLY, selected=True)
    annual = premium_page._plan_option_html(stripe_billing.ANNUAL, selected=False)
    assert "$3.99" in monthly and "per month" in monthly
    assert "premium-checkout-option-selected" in monthly and "Selected" in monthly
    assert "$19.99" in annual and "per year" in annual
    assert "premium-checkout-option-selected" not in annual


def test_plan_selection_normalization_preserves_existing_interval_contract():
    assert premium_page.normalize_checkout_interval("monthly") == stripe_billing.MONTHLY
    assert premium_page.normalize_checkout_interval("annual") == stripe_billing.ANNUAL
    assert premium_page.normalize_checkout_interval("invalid") == stripe_billing.MONTHLY


def test_annual_card_and_single_checkout_cta_preserve_stripe_interval_mapping():
    state = {
        "auth_session": {"user_id": "user-1"},
        "auth_email": "founder@example.com",
    }
    config = stripe_billing.StripeBillingConfig(
        secret_key="sk_test_example",
        price_monthly="price_monthly",
        price_annual="price_annual",
    )
    checkout = Mock(return_value=SimpleNamespace(url="https://checkout.example/session"))

    def button(_label, *, key=None, on_click=None, **_kwargs):
        clicked = key in {"premium_choose_annual", "premium_create_test_checkout"}
        if clicked and key == "premium_choose_annual":
            state["premium_test_checkout_interval"] = stripe_billing.ANNUAL
        if clicked and on_click:
            on_click()
        return clicked

    with (
        patch.object(premium_page.st, "session_state", state),
        patch.object(premium_page.st, "secrets", {}),
        patch.object(premium_page.st, "query_params", {}),
        patch.object(premium_page.st, "markdown"),
        patch.object(premium_page.st, "caption"),
        patch.object(premium_page.st, "columns", return_value=[nullcontext(), nullcontext()]),
        patch.object(premium_page.st, "button", side_effect=button),
        patch.object(premium_page.st, "link_button"),
        patch.object(premium_page.stripe_billing, "load_stripe_config", return_value=config),
        patch.object(premium_page.stripe_billing, "create_checkout_session", checkout),
        patch("modules.premium_conversion.peek_checkout_intent", return_value={}),
        patch("modules.premium_conversion.capture_checkout_intent"),
        patch("modules.premium_conversion.track_premium_event"),
    ):
        premium_page.render_premium_page(entitlement=premium.FREE)

    assert checkout.call_count == 1
    assert checkout.call_args.kwargs["interval"] == stripe_billing.ANNUAL


def test_premium_page_keeps_streamlit_as_the_only_scroll_owner():
    source = premium_page.__file__
    styles = open(source.replace("premium_page.py", "app_styles.py"), encoding="utf-8").read()
    premium_rule = styles.split(".premium-page {", 1)[1].split("}", 1)[0]
    assert "height:" not in premium_rule
    assert "overflow:" not in premium_rule
    assert "padding-bottom: var(--space-md)" in premium_rule
    assert "premium-route-end" in styles

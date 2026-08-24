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
    def component(*, data, **_kwargs):
        selection = (
            {"interval": stripe_billing.ANNUAL, "action_id": "annual-action"}
            if data["interval"] == stripe_billing.ANNUAL
            else None
        )
        return SimpleNamespace(selection=selection, redirect_ack=None)

    with (
        patch.object(premium_page.st, "session_state", state),
        patch.object(premium_page.st, "secrets", {}),
        patch.object(premium_page.st, "query_params", {}),
        patch.object(premium_page.st, "markdown"),
        patch.object(premium_page.st, "caption"),
        patch.object(premium_page.st, "columns", return_value=[nullcontext(), nullcontext()]),
        patch.object(premium_page.st, "rerun"),
        patch.object(premium_page.stripe_billing, "load_stripe_config", return_value=config),
        patch.object(premium_page.stripe_billing, "create_checkout_session", checkout),
        patch.object(premium_page, "PREMIUM_PLAN_CTA_COMPONENT", side_effect=component),
        patch("modules.premium_conversion.peek_checkout_intent", return_value={}),
        patch("modules.premium_conversion.capture_checkout_intent"),
        patch("modules.premium_conversion.track_premium_event"),
    ):
        premium_page.render_premium_page(entitlement=premium.FREE)

    assert checkout.call_count == 1
    assert checkout.call_args.kwargs["interval"] == stripe_billing.ANNUAL
    assert state[premium_page.CHECKOUT_REDIRECT_KEY] == {
        "interval": "annual",
        "redirect_id": "annual-action",
        "url": "https://checkout.example/session",
    }


def test_monthly_plan_cta_is_the_single_checkout_action():
    state = {
        "auth_session": {"user_id": "user-1"},
        "auth_email": "founder@example.com",
    }
    config = stripe_billing.StripeBillingConfig(
        secret_key="sk_test_example",
        price_monthly="price_monthly",
        price_annual="price_annual",
    )
    checkout = Mock(return_value=SimpleNamespace(url="https://checkout.example/monthly"))
    def component(*, data, **_kwargs):
        selection = (
            {"interval": stripe_billing.MONTHLY, "action_id": "monthly-action"}
            if data["interval"] == stripe_billing.MONTHLY
            else None
        )
        return SimpleNamespace(selection=selection, redirect_ack=None)

    with (
        patch.object(premium_page.st, "session_state", state),
        patch.object(premium_page.st, "secrets", {}),
        patch.object(premium_page.st, "query_params", {}),
        patch.object(premium_page.st, "markdown"),
        patch.object(premium_page.st, "caption"),
        patch.object(premium_page.st, "columns", return_value=[nullcontext(), nullcontext()]),
        patch.object(premium_page.st, "rerun"),
        patch.object(premium_page.stripe_billing, "load_stripe_config", return_value=config),
        patch.object(premium_page.stripe_billing, "create_checkout_session", checkout),
        patch.object(premium_page, "PREMIUM_PLAN_CTA_COMPONENT", side_effect=component),
        patch("modules.premium_conversion.peek_checkout_intent", return_value={}),
        patch("modules.premium_conversion.capture_checkout_intent"),
        patch("modules.premium_conversion.track_premium_event"),
    ):
        premium_page.render_premium_page(entitlement=premium.FREE)

    assert checkout.call_count == 1
    assert checkout.call_args.kwargs["interval"] == stripe_billing.MONTHLY
    assert state[premium_page.CHECKOUT_REDIRECT_KEY]["url"] == "https://checkout.example/monthly"


def test_premium_page_orders_pricing_before_comparison_and_roadmap():
    source = open(premium_page.__file__, encoding="utf-8").read()
    renderer = source[source.index("def render_premium_page"):]
    assert renderer.index("premium-checkout-heading") < renderer.rindex("premium_details_html(")
    assert "Possible future features" in premium_page.premium_details_html()
    assert "not guaranteed deliverables or billing terms" in premium_page.premium_details_html()


def test_checkout_component_preserves_user_activation_and_one_fallback_owner():
    source = open(premium_page.__file__, encoding="utf-8").read()
    assert 'window.open("about:blank", popupName)' in source
    assert 'popup.location.replace(redirectUrl)' in source
    assert 'setTriggerValue("selection"' in source
    assert 'setTriggerValue("redirect_ack"' in source
    assert source.count("Open secure checkout") == 1


def test_checkout_failure_remains_honest_and_does_not_render_navigation():
    state = {"auth_session": {"user_id": "user-1"}, "auth_email": "fixture@example.com"}
    config = stripe_billing.StripeBillingConfig(
        secret_key="sk_test_example",
        price_monthly="price_monthly",
        price_annual="price_annual",
    )
    warnings: list[str] = []
    def component(*, data, **_kwargs):
        selection = (
            {"interval": stripe_billing.MONTHLY, "action_id": "failed-action"}
            if data["interval"] == stripe_billing.MONTHLY
            else None
        )
        return SimpleNamespace(selection=selection, redirect_ack=None)

    with (
        patch.object(premium_page.st, "session_state", state),
        patch.object(premium_page.st, "secrets", {}),
        patch.object(premium_page.st, "query_params", {}),
        patch.object(premium_page.st, "markdown"),
        patch.object(premium_page.st, "caption"),
        patch.object(premium_page.st, "columns", return_value=[nullcontext(), nullcontext()]),
        patch.object(premium_page.st, "container", return_value=nullcontext()),
        patch.object(premium_page.st, "rerun"),
        patch.object(premium_page.st, "warning", side_effect=warnings.append),
        patch.object(premium_page.stripe_billing, "load_stripe_config", return_value=config),
        patch.object(
            premium_page.stripe_billing,
            "create_checkout_session",
            side_effect=RuntimeError("fixture failure"),
        ),
        patch.object(premium_page, "PREMIUM_PLAN_CTA_COMPONENT", side_effect=component),
        patch("modules.premium_conversion.peek_checkout_intent", return_value={}),
        patch("modules.premium_conversion.capture_checkout_intent"),
        patch("modules.premium_conversion.track_premium_event"),
    ):
        premium_page.render_premium_page(entitlement=premium.FREE)

    assert warnings == [
        "Checkout is not available right now. Check billing configuration and try again."
    ]
    assert premium_page.CHECKOUT_REDIRECT_KEY not in state


def test_same_component_action_is_idempotent_and_redirect_ack_clears_handoff():
    state = {
        "auth_session": {"user_id": "user-1"},
        "auth_email": "fixture@example.com",
        premium_page.CHECKOUT_ACTION_KEY: "same-action",
        premium_page.CHECKOUT_REDIRECT_KEY: {
            "interval": "monthly",
            "redirect_id": "same-action",
            "url": "https://checkout.example/monthly",
        },
    }
    config = stripe_billing.StripeBillingConfig(
        secret_key="sk_test_example",
        price_monthly="price_monthly",
        price_annual="price_annual",
    )
    checkout = Mock()

    def component(*, data, **_kwargs):
        if data["interval"] == "monthly":
            return SimpleNamespace(
                selection={"interval": "monthly", "action_id": "same-action"},
                redirect_ack={"redirect_id": "same-action"},
            )
        return SimpleNamespace(selection=None, redirect_ack=None)

    with (
        patch.object(premium_page.st, "session_state", state),
        patch.object(premium_page.st, "secrets", {}),
        patch.object(premium_page.st, "query_params", {}),
        patch.object(premium_page.st, "markdown"),
        patch.object(premium_page.st, "caption"),
        patch.object(premium_page.st, "columns", return_value=[nullcontext(), nullcontext()]),
        patch.object(premium_page.st, "container", return_value=nullcontext()),
        patch.object(premium_page.stripe_billing, "load_stripe_config", return_value=config),
        patch.object(premium_page.stripe_billing, "create_checkout_session", checkout),
        patch.object(premium_page, "PREMIUM_PLAN_CTA_COMPONENT", side_effect=component),
        patch("modules.premium_conversion.peek_checkout_intent", return_value={}),
    ):
        premium_page.render_premium_page(entitlement=premium.FREE)

    checkout.assert_not_called()
    assert premium_page.CHECKOUT_REDIRECT_KEY not in state


def test_premium_page_keeps_streamlit_as_the_only_scroll_owner():
    source = premium_page.__file__
    styles = open(source.replace("premium_page.py", "app_styles.py"), encoding="utf-8").read()
    premium_rule = styles.split(".premium-page {", 1)[1].split("}", 1)[0]
    assert "height:" not in premium_rule
    assert "overflow:" not in premium_rule
    assert "padding-bottom: var(--space-md)" in premium_rule
    assert "premium-route-end" in styles

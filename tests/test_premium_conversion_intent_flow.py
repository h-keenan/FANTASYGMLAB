"""Premium conversion audit + intent-based upgrade contracts (#225)."""

from __future__ import annotations

from pathlib import Path

from modules import guest_conversion, launch_analytics, premium, premium_conversion, premium_page


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "premium-conversion-intent-flow.md"


def test_premium_conversion_doc_exists():
    text = DOC.read_text(encoding="utf-8")
    assert "Go deeper on the decisions that matter" in text
    assert "Upgrade to Premium" in text
    assert "premium_gate_seen" in text
    assert "Experimental" in text
    assert "de7b0dd" in text
    assert "Rollback boundary" in text


def test_canonical_cta_and_value_prop():
    assert premium_conversion.PRIMARY_CTA == "Upgrade to Premium"
    assert premium_conversion.SECONDARY_CTA == "See what Premium includes"
    assert premium_conversion.CHECKOUT_CTA == "Start Founder Premium checkout"
    assert "Go deeper" in premium_conversion.VALUE_PROP_HEADLINE
    assert "Game Plan" in premium_conversion.VALUE_PROP_BODY


def test_included_now_lists_graduated_premium_depth():
    titles = {title for title, _ in premium_page.PREMIUM_INCLUDED_NOW}
    assert "More next moves" in titles
    assert "Full Trade Hub" in titles
    assert "Decision Memory" in titles
    assert "GM Targets (full board)" in titles
    assert "Share Recommendation" not in titles
    assert premium_page.PREMIUM_EXPERIMENTAL_WHEN_ENABLED == ()
    free = {title for title, _ in premium_page.FREE_INCLUDES}
    assert "Share Recommendation" in free
    assert "GM Targets (limited)" in free


def test_premium_lock_uses_upgrade_cta_and_included_line():
    html = premium.premium_lock_html(
        "Full trade board",
        "More ideas.",
        feature="Premium Trade Hub",
    )
    assert "Upgrade to Premium" in html
    assert "Included with Premium" in html
    assert "Unlock with Premium" not in html


def test_checkout_intent_capture_and_attribution():
    state: dict = {"selected_league_id": "L1", "platform_nav_page": "trade_hub"}
    payload = premium_conversion.capture_checkout_intent(
        state,
        feature="Premium Trade Hub",
        surface="premium_lock",
        route="trade_hub",
    )
    assert payload["feature"] == "trade_depth"
    assert payload["league_id"] == "L1"
    assert premium_conversion.peek_checkout_intent(state)["surface"] == "premium_lock"
    premium_conversion.clear_checkout_intent(state)
    assert premium_conversion.peek_checkout_intent(state) == {}


def test_guest_auth_marks_premium_checkout_resume():
    state: dict = {}
    premium_conversion.capture_checkout_intent(
        state,
        feature="deep_analysis",
        surface="premium_checkout",
        return_route="premium",
    )
    # Simulate post-auth resume marker without full Streamlit session.
    premium_conversion.mark_resume_checkout_after_auth(state)
    assert state.get(premium_conversion.RESUME_CHECKOUT_FLAG) is True
    assert state.get("_pending_platform_route") == "premium"


def test_finish_auth_from_guest_resumes_premium_checkout():
    from unittest.mock import patch

    class _State(dict):
        pass

    session = _State()
    premium_conversion.capture_checkout_intent(
        session,
        feature="general",
        surface="premium_checkout",
    )
    with (
        patch.object(guest_conversion, "st") as st_mod,
        patch.object(
            guest_conversion.auth_supabase,
            "current_auth_session",
            return_value={"access_token": "tok", "user_id": "u1", "email": "a@b.c"},
        ),
        patch("modules.account_store.fetch_saved_leagues", return_value=([], "")),
        patch("modules.startup_coordinator.reset_startup_coordinator"),
        patch.object(guest_conversion, "peek_guest_resume", return_value={}),
        patch.object(guest_conversion, "clear_guest_resume"),
        patch.object(guest_conversion, "_track"),
        patch.object(premium_conversion, "st") as premium_st,
    ):
        st_mod.session_state = session
        premium_st.session_state = session
        guest_conversion.finish_auth_from_guest(
            config={},
            mode="signup",
            surface="premium_checkout",
        )
    assert session.get(premium_conversion.RESUME_CHECKOUT_FLAG) is True
    assert session.get("_pending_platform_route") == "premium"


def test_billing_return_clears_memo_and_emits_cancel_event(monkeypatch):
    state: dict = {
        "_startup_entitlement_memo": "free",
        "_startup_entitlement_memo_user": "u1",
        "_effective_entitlement": "free",
        premium_conversion.CHECKOUT_INTENT_KEY: {"feature": "trade_depth"},
    }
    events: list[str] = []

    def _track(event, **_kwargs):
        events.append(event)

    monkeypatch.setattr(premium_conversion, "track_premium_event", _track)
    premium_conversion.handle_billing_return_success(state)
    assert "_startup_entitlement_memo" not in state
    assert premium_conversion.CHECKOUT_INTENT_KEY not in state
    assert "premium_checkout_completed" in events

    events.clear()
    premium_conversion.handle_billing_return_cancel(state)
    assert "premium_checkout_cancelled" in events


def test_analytics_allowlist_covers_premium_funnel():
    for event in (
        "premium_gate_seen",
        "premium_cta_clicked",
        "checkout_started",
        "checkout_completed",
        "premium_checkout_cancelled",
        "premium_entitlement_activated",
    ):
        assert event in launch_analytics.TRACKED_EVENTS
    assert launch_analytics.normalize_event_name("premium_checkout_started") == "checkout_started"
    assert "prompt_surface" in launch_analytics.ALLOWED_PROP_KEYS
    assert "item_kind" in launch_analytics.ALLOWED_PROP_KEYS
    for blocked in ("email", "username", "player_name"):
        assert blocked in launch_analytics.BLOCKED_PROP_KEYS


def test_app_wires_intent_checkout_and_no_upsell_for_premium():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    conversion = (ROOT / "modules" / "premium_conversion.py").read_text(encoding="utf-8")
    assert "premium_conversion.begin_upgrade_flow" in app
    assert "clear_entitlement_presentation_memo" in app
    assert "maybe_emit_entitlement_activated" in app
    assert "premium_conversion.PRIMARY_CTA" in app
    assert '"Unlock with Premium"' not in app
    assert "Manage Premium" in app
    assert "Free shows up to 2 approved ideas" in app
    assert "premium_cta_clicked" in conversion
    assert '_commit_platform_destination("premium", source="premium_lock")' in app


def test_decision_memory_discovery_uses_injectable_lock():
    ui = (ROOT / "modules" / "decision_change_history_ui.py").read_text(encoding="utf-8")
    assert "render_premium_lock: Callable" in ui
    assert "render_premium_lock(discovery_title" in ui


def test_stripe_session_only_on_checkout_button():
    page = (ROOT / "modules" / "premium_page.py").read_text(encoding="utf-8")
    assert "create_checkout_session" in page
    # Session creation sits behind the explicit founder-checkout run flag.
    assert "_premium_run_founder_checkout" in page
    assert "on_click=_on_founder_checkout" in page
    assert "open_auth_dialog" in page
    assert "st.rerun()" not in page
    button_idx = page.index("premium_create_test_checkout")
    session_idx = page.index("create_checkout_session")
    assert button_idx < session_idx

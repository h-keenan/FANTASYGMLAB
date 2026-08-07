"""Regression tests for production state-transition integrity."""

from __future__ import annotations

from modules import auth_supabase
from modules import session_integrity
from modules import trade_detail_navigation
from modules import workflow_continuity
from modules import canonical_recommendation_narrative as crn


def _seed_workspace(state: dict) -> None:
    state.update(
        {
            auth_supabase.AUTH_SESSION_KEY: {
                "access_token": "tok",
                "user_id": "user-1",
                "user": {"id": "user-1", "email": "a@example.com"},
            },
            auth_supabase.AUTH_USER_KEY: {"id": "user-1", "email": "a@example.com"},
            auth_supabase.AUTH_EMAIL_KEY: "a@example.com",
            auth_supabase.ACCOUNT_MODE_KEY: "account",
            "selected_league_id": "league-a",
            "selected_league_name": "League A",
            "username": "sleeper_user",
            "active_league_context": {"selected_league_id": "league-a"},
            "account_profile": {"entitlement": "premium"},
            "_effective_entitlement": "premium",
            "_identity_established": True,
            "leagues_for_user": [{"league_id": "league-a"}],
            "leagues_for_user_username": "sleeper_user",
            "player_quick_view_player_id": "4046",
            "player_quick_view_source_label": "Dashboard",
            "canonical_recommendation_narrative": {
                "recommendation_id": "rec-1",
                "league_id": "league-a",
                "player_id": "4046",
            },
            "executive_workflow_return": {
                "origin_page": "dashboard",
                "origin_label": "Dashboard",
                "league_id": "league-a",
            },
            "dg_trade_detail_active": "trade-1",
            "dg_trade_detail_view": "trade",
            "trade_send_assets": [{"player_id": "4046"}],
            "trade_receive_assets": [{"player_id": "123"}],
            "trade_asset_score_field": "same-fingerprint",
            "trade_hub_focus_player_id_league-a": "4046",
            "trade_hub_mode_league-a": "find",
            "_mobile_destination_sheet_open": True,
            "_pending_platform_route": "trade_hub",
            "role_map": {"4046": "hold"},
        }
    )
    trade_detail_navigation.open_trade(state, "trade-1")


def test_logout_clears_overlays_identity_and_packages():
    state = {}
    _seed_workspace(state)
    auth_supabase.clear_auth_session(state)

    assert state[auth_supabase.ACCOUNT_MODE_KEY] == "guest"
    assert auth_supabase.current_user_id(state) == ""
    for key in (
        "selected_league_id",
        "active_league_context",
        "username",
        "account_profile",
        "_identity_established",
        "_effective_entitlement",
        "player_quick_view_player_id",
        "canonical_recommendation_narrative",
        "executive_workflow_return",
        "dg_trade_detail_active",
        "trade_send_assets",
        "trade_receive_assets",
        "trade_hub_focus_player_id_league-a",
        "leagues_for_user",
        "_pending_platform_route",
    ):
        assert key not in state, key
    assert state.get("_mobile_destination_sheet_open") in (None, False) or (
        "_mobile_destination_sheet_open" not in state
    )


def test_account_switch_clears_prior_workspace_on_apply():
    state = {}
    _seed_workspace(state)
    auth_supabase.apply_auth_payload(
        state,
        {
            "access_token": "tok-2",
            "refresh_token": "ref-2",
            "expires_at": 9999999999,
            "user": {"id": "user-2", "email": "b@example.com"},
        },
    )
    assert auth_supabase.current_user_id(state) == "user-2"
    assert "selected_league_id" not in state
    assert "player_quick_view_player_id" not in state
    assert "canonical_recommendation_narrative" not in state
    assert "trade_send_assets" not in state
    assert "_identity_established" not in state


def test_same_user_restore_preserves_workspace():
    state = {}
    _seed_workspace(state)
    auth_supabase.apply_auth_payload(
        state,
        {
            "access_token": "tok-refreshed",
            "refresh_token": "ref",
            "expires_at": 9999999999,
            "user_id": "user-1",
            "user": {"id": "user-1", "email": "a@example.com"},
        },
    )
    assert state.get("selected_league_id") == "league-a"
    assert state.get("player_quick_view_player_id") == "4046"
    assert state.get("_identity_established") is True


def test_league_switch_clears_trade_analyzer_package():
    import app

    class _State(dict):
        def __getattr__(self, name):
            try:
                return self[name]
            except KeyError as exc:
                raise AttributeError(name) from exc

        def __setattr__(self, name, value):
            self[name] = value

    state = _State()
    state["trade_send_assets"] = [{"player_id": "1"}]
    state["trade_receive_assets"] = [{"player_id": "2"}]
    state["trade_asset_score_field"] = "fingerprint"
    state["trade_receive_notice"] = "note"
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "streamlit.session_state", state
    ):
        app._clear_league_switch_transient_state(previous_league_id="league-a")
    assert "trade_send_assets" not in state
    assert "trade_receive_assets" not in state
    assert "trade_asset_score_field" not in state


def test_workflow_return_pops_on_league_mismatch():
    state = {}
    workflow_continuity.push_return_context(
        state, "dashboard", league_id="league-a", recommendation_id="rec-1"
    )
    assert workflow_continuity.current_return_context(state, league_id="league-b") is None
    assert workflow_continuity.WORKFLOW_RETURN_KEY not in state


def test_guest_session_after_logout_has_no_premium_cache():
    state = {"_effective_entitlement": "premium", "account_profile": {"entitlement": "premium"}}
    auth_supabase.clear_auth_session(state)
    assert "_effective_entitlement" not in state
    assert "account_profile" not in state


def test_session_integrity_inventory_covers_owned_keys():
    assert "canonical_recommendation_narrative" in session_integrity.ACCOUNT_BOUND_TRANSIENT_KEYS
    assert "executive_workflow_return" in session_integrity.ACCOUNT_BOUND_TRANSIENT_KEYS
    assert "trade_send_assets" in session_integrity.TRADE_ANALYZER_PACKAGE_KEYS
    assert crn.NARRATIVE_SESSION_KEY == "canonical_recommendation_narrative"


def test_logout_clears_pqv_source_metadata():
    state = {
        "player_quick_view_player_id": "x",
        "player_quick_view_source_label": "Trade Hub",
        "player_quick_view_source_note": "note",
        "player_quick_view_status_label": "status",
    }
    session_integrity.clear_account_bound_transient_state(state)
    assert "player_quick_view_player_id" not in state
    assert "player_quick_view_source_label" not in state

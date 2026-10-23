"""Regression tests for production state-transition integrity."""

from __future__ import annotations

from modules import auth_supabase
from modules import session_integrity
from modules import canonical_recommendation_narrative as crn


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

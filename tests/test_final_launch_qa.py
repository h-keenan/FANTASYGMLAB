"""Final launch QA contracts (#227) — launch blockers and isolation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from modules import auth_supabase, launch_analytics, premium_conversion
from modules import session_integrity
from modules.ui_architecture import (
    ARCHIVED_DESTINATION_KEYS,
    current_platform_destinations,
)
from modules import decision_memory, gm_targets, share_recommendation_cards


ROOT = Path(__file__).resolve().parents[1]
QA_DOC = ROOT / "docs" / "final-launch-qa.md"
GO_DOC = ROOT / "docs" / "launch-go-no-go.md"


def test_final_launch_docs_exist():
    assert QA_DOC.is_file()
    assert GO_DOC.is_file()
    qa = QA_DOC.read_text(encoding="utf-8")
    go = GO_DOC.read_text(encoding="utf-8")
    assert "e4454eb" in qa
    assert "Launch-default visibility" in qa
    assert "GO" in go or "CONDITIONAL GO" in go or "NO-GO" in go
    assert "Rollback" in go


def test_experiment_defaults_on_and_archived_hidden():
    assert decision_memory.experiment_enabled(environ={}) is True
    assert gm_targets.experiment_enabled(environ={}) is True
    assert share_recommendation_cards.experiment_enabled(environ={}) is True
    keys = {page.key for page in current_platform_destinations(False)}
    for archived in ARCHIVED_DESTINATION_KEYS:
        assert archived not in keys
    assert "live_draft" not in keys
    assert "gm_targets" not in keys
    assert "players" in keys
    conditional = {
        page.key
        for page in current_platform_destinations(
            False, enabled_experimental=("live_draft", "gm_targets")
        )
    }
    assert "live_draft" in conditional
    assert "gm_targets" in conditional


def test_logout_clears_premium_checkout_intent():
    state = {
        premium_conversion.CHECKOUT_INTENT_KEY: {
            "feature": "trade_depth",
            "surface": "premium_lock",
        },
        premium_conversion.RESUME_CHECKOUT_FLAG: True,
        "_premium_run_founder_checkout": True,
        "auth_session": {"user_id": "u1"},
        "selected_league_id": "L1",
        "username": "old_user",
    }
    auth_supabase.clear_auth_session(state)
    assert premium_conversion.CHECKOUT_INTENT_KEY not in state
    assert premium_conversion.RESUME_CHECKOUT_FLAG not in state
    assert "_premium_run_founder_checkout" not in state
    assert "auth_session" not in state
    assert "selected_league_id" not in state


def test_account_bound_keys_include_premium_intent():
    assert "_premium_checkout_intent" in session_integrity.ACCOUNT_BOUND_TRANSIENT_KEYS
    assert "_premium_resume_checkout" in session_integrity.ACCOUNT_BOUND_TRANSIENT_KEYS


def test_analytics_blocks_pii_and_strips_unknown_stripe_props():
    for key in ("email", "username", "player_name", "access_token", "password"):
        assert key in launch_analytics.BLOCKED_PROP_KEYS
    cleaned = launch_analytics._safe_props(
        {
            "email": "a@b.c",
            "username": "sleeper_user",
            "stripe_customer_id": "cus_123",
            "checkout_session_id": "cs_test_123",
            "route": "premium",
            "item_kind": "trade_depth",
        }
    )
    assert "email" not in cleaned
    assert "username" not in cleaned
    assert "stripe_customer_id" not in cleaned
    assert "checkout_session_id" not in cleaned
    assert cleaned.get("route") == "premium"
    assert cleaned.get("item_kind") == "trade_depth"

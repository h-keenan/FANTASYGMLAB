"""Final launch QA contracts (#227) — launch blockers and isolation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from modules import auth_supabase, guest_conversion, launch_analytics, premium_conversion
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


def test_startup_and_espn_quick_actions_exclude_dead_routes():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '("News", "news")' not in app
    assert '("Players", "players")' not in app
    # Startup draft path uses launch-safe CORE destinations.
    startup_block = app[
        app.index("Run Startup Draft Center") : app.index("ESPN limited review mode")
    ]
    assert '("Startup Draft Center", "startup_draft_center")' in startup_block
    assert '("Dashboard", "dashboard")' in startup_block
    assert '("League Overview", "rankings")' in startup_block
    espn_block = app[
        app.index("ESPN limited review mode") : app.index(
            "if not username or not selected_league_id:"
        )
    ]
    assert '("Dashboard", "dashboard")' in espn_block
    assert '("Premium", "premium")' in espn_block


def test_open_player_detail_handoff_and_canonical_cta():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    start = app.index("def open_player_detail(")
    end = app.index("\ndef ", start + 1)
    body = app[start:end]
    assert "open_player_quick_view(" in body
    assert '_queue_platform_route("player_detail")' not in body
    assert '"Unlock with Premium"' not in app
    assert "Upgrade to Premium" in (ROOT / "modules" / "premium_conversion.py").read_text(
        encoding="utf-8"
    )


def test_track_premium_event_normalizes_aliases(monkeypatch):
    seen: list[str] = []

    def _track(event, **_kwargs):
        seen.append(event)
        return True

    monkeypatch.setattr(launch_analytics, "track_event", _track)
    monkeypatch.setattr(
        launch_analytics,
        "build_context_props",
        lambda *_a, **_k: {"route": "premium"},
    )
    with patch.object(premium_conversion, "st") as st_mod:
        st_mod.session_state = {}
        premium_conversion.track_premium_event("premium_checkout_started")
        premium_conversion.track_premium_event("premium_checkout_completed")
    assert seen == ["checkout_started", "checkout_completed"]


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


def test_create_checkout_session_only_after_explicit_run_flag():
    page = (ROOT / "modules" / "premium_page.py").read_text(encoding="utf-8")
    assert "_premium_run_founder_checkout" in page
    assert "on_click=_on_founder_checkout" in page
    assert page.index("premium_create_test_checkout") < page.index("create_checkout_session")
    assert "st.rerun()" not in page


def test_waivers_faab_sort_guards_missing_score_column():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "if score_field in faab_pool.columns:" in app
    assert "faab_pool.sort_values(score_field" in app


def test_guest_soft_prompt_surfaces_and_free_language():
    assert set(guest_conversion.SURFACE_REASONS) >= {
        "dashboard",
        "my_team",
        "trade_hub",
        "waivers",
        "pqv",
    }
    blob = " ".join(guest_conversion.FREE_ACCOUNT_BENEFITS).casefold()
    assert "premium" not in blob


def test_no_concept_chip_in_styles_or_my_team():
    styles = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    my_team = (ROOT / "modules" / "my_team_ui.py").read_text(encoding="utf-8")
    assert ".concept-chip" not in styles
    assert "concept-chip" not in my_team


def test_premium_included_now_includes_graduated_premium_depth():
    page = (ROOT / "modules" / "premium_page.py").read_text(encoding="utf-8")
    included = page[
        page.index("PREMIUM_INCLUDED_NOW") : page.index("PREMIUM_EXPERIMENTAL_WHEN_ENABLED")
    ]
    assert "Decision Memory" in included
    assert "GM Targets (full board)" in included
    assert "Share Recommendation" not in included

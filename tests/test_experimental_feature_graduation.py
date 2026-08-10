"""Experimental feature graduation contracts (#226) — superseded by #232 for defaults."""

from __future__ import annotations

from pathlib import Path

from modules import decision_memory, gm_targets, share_recommendation_cards
from modules.ui_architecture import (
    ARCHIVED_DESTINATION_KEYS,
    PLATFORM_DESTINATIONS,
    current_platform_destinations,
)


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "experimental-feature-graduation.md"


def test_graduation_doc_exists_with_matrix_and_defaults():
    text = DOC.read_text(encoding="utf-8")
    assert "GRADUATE TO LAUNCH" in text
    assert "KEEP EXPERIMENTAL" in text
    assert "DEFER / HIDE" in text
    assert "REMOVE" in text
    assert "be6bfa6" in text
    assert "Production launch defaults" in text
    assert "Live Draft" in text
    assert "Decision Memory" in text
    assert "GM Targets" in text
    assert "Share Recommendation" in text
    assert "Rollback boundary" in text


def test_live_draft_graduated_conditional():
    by_key = {page.key: page for page in PLATFORM_DESTINATIONS}
    assert by_key["live_draft"].category == "CONDITIONAL"
    visible = {
        page.key
        for page in current_platform_destinations(
            False, enabled_experimental=("live_draft",)
        )
    }
    assert "live_draft" in visible
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '("[EXPERIMENTAL]", "warning")' not in app
    assert '("Active draft", "strategy")' in app


def test_archived_routes_never_in_nav():
    expected = {
        "player_detail",
        "news",
        "archetypes",
        "teams",
        "weekly_report",
        "trade_analyzer",
        "manager_tendencies",
    }
    assert set(ARCHIVED_DESTINATION_KEYS) == expected
    for show in (False, True):
        keys = {
            page.key
            for page in current_platform_destinations(False, show_experimental=show)
        }
        for archived in ARCHIVED_DESTINATION_KEYS:
            assert archived not in keys


def test_premium_kill_switches_default_on_after_reincorporation():
    # #232 graduated defaults; #226 doc remains historical.
    assert decision_memory.experiment_enabled(environ={}) is True
    assert gm_targets.experiment_enabled(environ={}) is True
    assert share_recommendation_cards.experiment_enabled(environ={}) is True
    assert decision_memory.experiment_enabled(
        environ={"DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY": "0"}
    ) is False


def test_open_player_detail_routes_to_quick_view():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    start = app.index("def open_player_detail(")
    end = app.index("\ndef ", start + 1)
    body = app[start:end]
    assert "open_player_quick_view(" in body
    assert '_queue_platform_route("player_detail")' not in body


def test_prospect_shortlist_deferred_from_launch():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Static 2027 shortlist is deferred from launch" in app
    assert 'if destination_visibility.get("show_experimental"):' in app
    assert "render_prospect_watchlist(draft_watch_needs)" in app


def test_premium_marketing_includes_graduated_features():
    page = (ROOT / "modules" / "premium_page.py").read_text(encoding="utf-8")
    included = page[
        page.index("PREMIUM_INCLUDED_NOW") : page.index("PREMIUM_EXPERIMENTAL_WHEN_ENABLED")
    ]
    assert "Decision Memory" in included
    assert "GM Targets (full board)" in included
    assert "Share Recommendation" not in included


def test_roi_audit_route_comment_matches_registry_experimental_set():
    from scripts.audit_experimental_features import documented_routes, experimental_routes

    registry = (ROOT / "modules" / "ui_architecture.py").read_text(encoding="utf-8")
    audit = (
        ROOT / "docs" / "experimental-feature-inventory-and-roi-audit.md"
    ).read_text(encoding="utf-8")
    assert documented_routes(audit) == experimental_routes(registry)

"""Regression contracts for canonical context synchronization."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import scripts.audit_context_integrity as audit_context_integrity


ROOT = Path(__file__).resolve().parents[1]


def _load_app(session_state: dict):
    import app

    app.st.session_state = session_state
    return app


def test_context_integrity_audit_script_passes():
    report = audit_context_integrity.audit()
    assert report["valid"] is True
    assert report["checks"]["league_switch_clears_transient_via_canonical_owner"]
    assert report["checks"]["notification_routes_clear_overlays"]
    assert report["checks"]["home_command_route_uses_session_league"]


def test_set_selected_league_clears_stale_overlays_roles_and_overrides():
    session = {
        "selected_league_id": "league-a",
        "selected_league_name": "League A",
        "leagues_for_user": [
            {"league_id": "league-a", "name": "League A", "season": "2026"},
            {"league_id": "league-b", "name": "League B", "season": "2026"},
        ],
        "active_league_context": {"selected_league_id": "league-a", "my_roster_id": "1"},
        "player_detail_player_id": "p1",
        "player_detail_return_page": "trade_hub",
        "player_quick_view_player_id": "p2",
        "selected_team_roster_id": "9",
        "selected_team_name": "Other",
        "role_map": {"p1": "Core"},
        "trade_hub_player_id": "p3",
        "trade_hub_focus_player_id_league-a": "p3",
        "trade_hub_focus_mode_league-a": "target_player",
        "dg_trade_detail_active": "trade-key",
        "dg_trade_detail_view": "trade",
        "league_format_override": "Dynasty",
        "league_starters_override": "10",
        "_mobile_destination_sheet_open": True,
        "username": "fixture",
    }
    app = _load_app(session)
    with (
        patch.object(app, "_persist_active_account_context"),
        patch.object(app, "_persist_supabase_account_context"),
        patch.object(app, "get_user_roster_id", return_value="2"),
    ):
        app.set_selected_league("league-b", "League B")

    assert session["selected_league_id"] == "league-b"
    assert "active_league_context" not in session
    assert "player_detail_player_id" not in session
    assert "player_quick_view_player_id" not in session
    assert "selected_team_roster_id" not in session
    assert "role_map" not in session
    assert "trade_hub_player_id" not in session
    assert "trade_hub_focus_player_id_league-a" not in session
    assert "dg_trade_detail_active" not in session
    assert session["league_format_override"] == "Auto"
    assert session["league_starters_override"] == "Auto"
    assert session["_mobile_destination_sheet_open"] is False


def test_open_home_command_route_writes_league_scoped_trade_focus():
    session = {"selected_league_id": "league-z"}
    app = _load_app(session)
    with patch.object(app, "_queue_platform_route") as queue:
        app._open_home_command_route(
            "trade_hub",
            player_id="42",
            focus_mode="target_player",
            source_label="Dashboard",
            source_note="Need",
        )
    assert session["trade_hub_focus_player_id_league-z"] == "42"
    assert session["trade_hub_focus_mode_league-z"] == "target_player"
    assert session["trade_hub_home_source_label_league-z"] == "Dashboard"
    queue.assert_called_once()


def test_notification_destination_clears_overlays_before_routing():
    session = {
        "player_quick_view_player_id": "p1",
        "dg_trade_detail_active": "trade-key",
        "_mobile_destination_sheet_open": True,
    }
    app = _load_app(session)
    with patch.object(app, "_queue_platform_route") as queue:
        app._open_notification_destination("waivers")
    assert "player_quick_view_player_id" not in session
    assert "dg_trade_detail_active" not in session
    assert session["_mobile_destination_sheet_open"] is False
    queue.assert_called_once_with("waivers", source="notification_center")


def test_recommendation_feedback_prefers_canonical_roster_over_browsed_team(monkeypatch):
    session = {
        "username": "fixture",
        "selected_league_id": "league-a",
        "selected_league_name": "League A",
        "selected_team_roster_id": "browsed",
        "active_league_context": {
            "username": "fixture",
            "selected_league_id": "league-a",
            "selected_league_name": "League A",
            "my_roster_id": "mine",
        },
    }
    app = _load_app(session)
    captured = {}

    def fake_form(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(app.feedback_ui, "render_feedback_form", fake_form)
    app.render_recommendation_feedback(
        page="dashboard",
        surface="card",
        recommendation_type="trade",
        key_prefix="fixture",
    )
    assert captured["roster_id"] == "mine"


def test_trade_hub_migrates_legacy_player_handoff_into_scoped_focus():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    trade = source[source.index('if current_page == "trade_hub"') :]
    assert 'st.session_state.pop("trade_hub_player_id"' in trade
    assert "legacy_trade_hub_player_id" in trade
    assert "trade_hub_focus_player_id_" in trade


def test_player_quick_view_uses_shared_player_id_not_route_models():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    opener = source[
        source.index("def open_player_quick_view(") : source.index(
            "def _player_on_active_roster("
        )
    ]
    assert "player_quick_view_player_id" in opener
    assert "resolve_active_league_context" in opener


def test_docs_cover_dependency_map_and_risks():
    docs = (ROOT / "docs" / "canonical-context-synchronization-audit.md").read_text(
        encoding="utf-8"
    )
    assert "Context dependency diagram" in docs
    assert "State ownership table" in docs
    assert "Navigation flow diagram" in docs
    assert "role_map" in docs
    assert "Remaining architectural risks" in docs
    assert "No football logic" in docs or "No football logic" in docs

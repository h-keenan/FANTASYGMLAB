"""League-switch widget reset + waiver Priority Adds relevance."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from modules import waivers_ui


ROOT = Path(__file__).resolve().parents[1]


def _load_app(session: dict):
    import app as app_module

    app_module.st.session_state = session
    return app_module


def test_league_switch_schedules_override_reset_instead_of_mutating_widget_keys():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    reset = source[
        source.index("def _reset_league_settings_overrides(") : source.index(
            "def _apply_pending_league_settings_override_reset("
        )
    ]
    apply = source[
        source.index("def _apply_pending_league_settings_override_reset(") : source.index(
            "def _clear_league_switch_transient_state("
        )
    ]
    assert "PENDING_LEAGUE_SETTINGS_OVERRIDE_RESET_KEY" in reset
    assert 'st.session_state[key] = "Auto"' not in reset
    assert 'st.session_state[key] = "Auto"' in apply
    assert "_apply_pending_league_settings_override_reset()" in source
    sidebar = source[source.index("# SIDEBAR") : source.index('st.header("Sleeper Setup")')]
    assert "_apply_pending_league_settings_override_reset()" in sidebar


def test_widget_then_league_switch_does_not_assign_instantiated_override_keys():
    """Mirrors production: override widgets exist → switch must not assign keys."""

    session = {
        "selected_league_id": "league-a",
        "selected_league_name": "League A",
        "leagues_for_user": [
            {"league_id": "league-a", "name": "League A", "season": "2026"},
            {"league_id": "league-b", "name": "League B", "season": "2026"},
        ],
        "league_format_override": "Dynasty",
        "league_scoring_override": "PPR",
        "username": "fixture",
        # Simulate Streamlit widget ownership after sidebar instantiation.
        "_widget_instantiated_keys": {
            "league_format_override",
            "league_scoring_override",
        },
    }
    app = _load_app(session)

    class GuardedState(dict):
        def __setitem__(self, key, value):
            if key in self.get("_widget_instantiated_keys", set()) and key in app.LEAGUE_SETTINGS_OVERRIDE_KEYS:
                raise RuntimeError(
                    f"st.session_state.{key} cannot be modified after the widget "
                    f"with key {key} is instantiated."
                )
            return super().__setitem__(key, value)

    guarded = GuardedState(session)
    app.st.session_state = guarded
    with (
        patch.object(app, "_persist_active_account_context"),
        patch.object(app, "_persist_supabase_account_context"),
        patch.object(app, "get_user_roster_id", return_value="2"),
    ):
        app.set_selected_league("league-b", "League B")

    assert guarded["selected_league_id"] == "league-b"
    assert guarded.get(app.PENDING_LEAGUE_SETTINGS_OVERRIDE_RESET_KEY) is True
    # Widget-owned values unchanged until apply runs before next construction.
    assert guarded["league_format_override"] == "Dynasty"
    # Apply happens before widgets on the next run.
    del guarded["_widget_instantiated_keys"]
    app._apply_pending_league_settings_override_reset()
    assert guarded["league_format_override"] == "Auto"
    assert guarded["league_scoring_override"] == "Auto"
    assert app.PENDING_LEAGUE_SETTINGS_OVERRIDE_RESET_KEY not in guarded


def test_priority_adds_not_qb_dominated_for_covered_1qb_roster():
    free_agents = pd.DataFrame(
        [
            {"player_id": "qb1", "name": "QB A", "position": "QB", "dynasty_score": 95, "stale_free_agent": False},
            {"player_id": "qb2", "name": "QB B", "position": "QB", "dynasty_score": 90, "stale_free_agent": False},
            {"player_id": "qb3", "name": "QB C", "position": "QB", "dynasty_score": 88, "stale_free_agent": False},
            {"player_id": "qb4", "name": "QB D", "position": "QB", "dynasty_score": 85, "stale_free_agent": False},
            {"player_id": "te1", "name": "TE A", "position": "TE", "dynasty_score": 80, "stale_free_agent": False},
            {"player_id": "k1", "name": "K A", "position": "K", "dynasty_score": 70, "stale_free_agent": False},
            {"player_id": "rb1", "name": "RB A", "position": "RB", "dynasty_score": 65, "stale_free_agent": False},
            {"player_id": "wr1", "name": "WR A", "position": "WR", "dynasty_score": 60, "stale_free_agent": False},
        ]
    )
    ranked = waivers_ui.rank_priority_add_candidates(
        free_agents,
        score_field="dynasty_score",
        needed_positions=["RB"],
        league_settings={"qb_format": "1QB", "k_count": 1, "superflex_count": 0},
        roster_df=pd.DataFrame(
            [
                {"position": "QB", "team": "DAL", "status": "Active"},
                {"position": "QB", "team": "KC", "status": "Active"},
                {"position": "QB", "team": "BUF", "status": "Active"},
                {"position": "K", "team": "DAL", "status": "Active"},
                {"position": "RB", "team": "DAL", "status": "Active"},
            ]
        ),
        max_items=6,
    )
    positions = ranked["position"].astype(str).str.upper().tolist()
    assert positions.count("QB") <= 1
    assert "K" not in positions
    assert "RB" in positions
    assert ranked.iloc[0]["player_id"] == "rb1"


def test_priority_adds_allows_qb_when_superflex_needs_qb():
    free_agents = pd.DataFrame(
        [
            {"player_id": "qb1", "name": "QB A", "position": "QB", "dynasty_score": 92, "stale_free_agent": False},
            {"player_id": "qb2", "name": "QB B", "position": "QB", "dynasty_score": 88, "stale_free_agent": False},
            {"player_id": "rb1", "name": "RB A", "position": "RB", "dynasty_score": 70, "stale_free_agent": False},
        ]
    )
    ranked = waivers_ui.rank_priority_add_candidates(
        free_agents,
        score_field="dynasty_score",
        needed_positions=["QB"],
        league_settings={"qb_format": "Superflex", "superflex_count": 1, "k_count": 0},
        roster_df=pd.DataFrame(
            [
                {"position": "QB", "team": "DAL", "status": "Active"},
                {"position": "QB", "team": "KC", "status": "Active"},
            ]
        ),
        max_items=6,
    )
    assert ranked.iloc[0]["position"] == "QB"
    assert bool(ranked.iloc[0]["priority_need_fit"]) is True


def test_priority_adds_keeps_exceptional_non_need_value():
    free_agents = pd.DataFrame(
        [
            {"player_id": "wr1", "name": "Elite WR", "position": "WR", "dynasty_score": 99, "stale_free_agent": False},
            {"player_id": "rb1", "name": "Need RB", "position": "RB", "dynasty_score": 55, "stale_free_agent": False},
            {"player_id": "wr2", "name": "Other WR", "position": "WR", "dynasty_score": 50, "stale_free_agent": False},
        ]
    )
    ranked = waivers_ui.rank_priority_add_candidates(
        free_agents,
        score_field="dynasty_score",
        needed_positions=["RB"],
        league_settings={"qb_format": "1QB", "k_count": 0},
        roster_df=pd.DataFrame([{"position": "RB", "team": "DAL"}]),
        max_items=6,
    )
    ids = ranked["player_id"].tolist()
    assert "rb1" in ids
    assert "wr1" in ids
    assert ranked.loc[ranked["player_id"] == "wr1", "priority_value_opportunity"].iloc[0]


def test_wire_rank_label_is_explicit_in_cards():
    source = (ROOT / "modules" / "waivers_ui.py").read_text(encoding="utf-8")
    assert "Wire {position} #{position_rank}" in source or 'Wire {escape(position)} #{position_rank}' in source
    assert "rank_priority_add_candidates(" in (ROOT / "app.py").read_text(encoding="utf-8")


def test_priority_adds_empty_when_balanced_and_no_exceptional_value():
    free_agents = pd.DataFrame(
        [
            {"player_id": "qb1", "name": "Backup QB", "position": "QB", "dynasty_score": 40, "stale_free_agent": False},
            {"player_id": "qb2", "name": "Backup QB2", "position": "QB", "dynasty_score": 38, "stale_free_agent": False},
            {"player_id": "te1", "name": "Depth TE", "position": "TE", "dynasty_score": 35, "stale_free_agent": False},
            {"player_id": "k1", "name": "K A", "position": "K", "dynasty_score": 20, "stale_free_agent": False},
        ]
    )
    ranked = waivers_ui.rank_priority_add_candidates(
        free_agents,
        score_field="dynasty_score",
        needed_positions=[],
        league_settings={"qb_format": "1QB", "k_count": 1, "superflex_count": 0},
        roster_df=pd.DataFrame(
            [
                {"position": "QB", "team": "DAL", "status": "Active"},
                {"position": "QB", "team": "KC", "status": "Active"},
                {"position": "RB", "team": "SF", "status": "Active"},
                {"position": "WR", "team": "MIA", "status": "Active"},
                {"position": "TE", "team": "BAL", "status": "Active"},
                {"position": "K", "team": "DAL", "status": "Active"},
            ]
        ),
        max_items=6,
    )
    assert ranked.empty


def test_priority_adds_includes_kicker_only_when_required_and_missing():
    free_agents = pd.DataFrame(
        [
            {"player_id": "k1", "name": "K A", "position": "K", "dynasty_score": 25, "stale_free_agent": False},
            {"player_id": "rb1", "name": "RB A", "position": "RB", "dynasty_score": 55, "stale_free_agent": False},
        ]
    )
    ranked = waivers_ui.rank_priority_add_candidates(
        free_agents,
        score_field="dynasty_score",
        needed_positions=["RB"],
        league_settings={"qb_format": "1QB", "k_count": 1},
        roster_df=pd.DataFrame([{"position": "RB", "team": "DAL", "status": "Active"}]),
        max_items=6,
    )
    assert "K" in ranked["position"].astype(str).str.upper().tolist()
    assert "rb1" in ranked["player_id"].tolist()


def test_dashboard_waiver_picker_uses_priority_ranker():
    source = (ROOT / "modules" / "waivers_ui.py").read_text(encoding="utf-8")
    picker = source[
        source.index("def select_top_waiver_opportunity(") : source.index(
            "def _roster_has_viable_kicker("
        )
    ]
    assert "rank_priority_add_candidates(" in picker


def test_rapid_league_switch_final_league_wins_and_pending_reset_stays_idempotent():
    session = {
        "selected_league_id": "league-a",
        "selected_league_name": "League A",
        "leagues_for_user": [
            {"league_id": "league-a", "name": "League A", "season": "2026"},
            {"league_id": "league-b", "name": "League B", "season": "2026"},
            {"league_id": "league-c", "name": "League C With A Very Long Name", "season": "2026"},
        ],
        "league_format_override": "Dynasty",
        "username": "fixture",
    }
    app = _load_app(session)
    with (
        patch.object(app, "_persist_active_account_context"),
        patch.object(app, "_persist_supabase_account_context"),
        patch.object(app, "get_user_roster_id", return_value="2"),
    ):
        app.set_selected_league("league-b", "League B")
        app.set_selected_league("league-c", "League C With A Very Long Name")
        app.set_selected_league("league-a", "League A")
    assert session["selected_league_id"] == "league-a"
    assert session.get(app.PENDING_LEAGUE_SETTINGS_OVERRIDE_RESET_KEY) is True
    app._apply_pending_league_settings_override_reset()
    assert session["league_format_override"] == "Auto"
    app._apply_pending_league_settings_override_reset()
    assert session["league_format_override"] == "Auto"

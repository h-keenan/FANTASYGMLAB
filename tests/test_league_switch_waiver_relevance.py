"""League-switch widget reset + waiver Priority Adds relevance."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from modules import waivers_logic


ROOT = Path(__file__).resolve().parents[1]


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
    ranked = waivers_logic.rank_priority_add_candidates(
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
    ranked = waivers_logic.rank_priority_add_candidates(
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
    ranked = waivers_logic.rank_priority_add_candidates(
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


def test_priority_adds_empty_when_balanced_and_no_exceptional_value():
    free_agents = pd.DataFrame(
        [
            {"player_id": "qb1", "name": "Backup QB", "position": "QB", "dynasty_score": 40, "stale_free_agent": False},
            {"player_id": "qb2", "name": "Backup QB2", "position": "QB", "dynasty_score": 38, "stale_free_agent": False},
            {"player_id": "te1", "name": "Depth TE", "position": "TE", "dynasty_score": 35, "stale_free_agent": False},
            {"player_id": "k1", "name": "K A", "position": "K", "dynasty_score": 20, "stale_free_agent": False},
        ]
    )
    ranked = waivers_logic.rank_priority_add_candidates(
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
    ranked = waivers_logic.rank_priority_add_candidates(
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
    source = (ROOT / "modules" / "waivers_logic.py").read_text(encoding="utf-8")
    picker = source[
        source.index("def select_top_waiver_opportunity(") : source.index(
            "def _roster_has_viable_kicker("
        )
    ]
    assert "rank_priority_add_candidates(" in picker

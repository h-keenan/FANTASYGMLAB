from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd

from modules import player_state_authority, waivers_ui


def _player(player_id: str, **overrides) -> dict:
    row = {
        "player_id": player_id,
        "name": player_id,
        "position": "WR",
        "fantasy_positions": ["WR"],
        "sport": "nfl",
        "active": True,
        "status": "Active",
        "team": "NYG",
        "age": 26,
        "years_exp": 3,
        "fantasycalc_value": 100,
        "dynasty_score": 2500,
        "value_score": 2500,
        "opportunity_label": "Starter",
        "projected_starter": True,
        "news_updated": int(datetime.now(timezone.utc).timestamp() * 1000),
    }
    row.update(overrides)
    return row


def test_waiver_actionability_separates_nfl_attachment_from_fantasy_availability():
    players = pd.DataFrame(
        [
            _player("valid", dynasty_score=1800),
            _player("unsigned", team=None, dynasty_score=9000),
            _player("retired", active=False, status="Retired", team=None),
            _player("practice", status="Practice Squad"),
            _player("opponent"),
            _player("mine"),
        ]
    )
    pool = player_state_authority.waiver_actionable_player_pool(
        players,
        {"mine-roster": ["mine"], "opponent-roster": ["opponent"]},
    )
    assert pool["player_id"].tolist() == ["valid"]


def test_bryce_class_record_is_not_actionable_and_cannot_keep_starter_label():
    bryce = _player(
        "9499",
        name="Bryce Ford-Wheaton",
        team=None,
        active=True,
        status="Active",
        dynasty_score=2493,
        value_score=2493,
        search_rank=44,
        opportunity_label="Starter",
        projected_starter=True,
    )
    decision = player_state_authority.waiver_actionability(bryce)
    assert decision == {"actionable": False, "reason": "no_current_nfl_team"}

    ranked = waivers_ui.rank_priority_add_candidates(
        pd.DataFrame([bryce, _player("next", dynasty_score=1700)]),
        score_field="dynasty_score",
        needed_positions=["WR"],
        league_settings={"qb_format": "1QB"},
        roster_df=pd.DataFrame(),
        max_items=1,
    )
    assert ranked["player_id"].tolist() == ["next"]
    assert "9499" not in ranked["player_id"].astype(str).tolist()


def test_top_waiver_uses_next_valid_candidate_and_pool_is_cache_stable():
    frame = pd.DataFrame(
        [
            _player("no-team", team="", dynasty_score=9000),
            _player("valid", position="RB", fantasy_positions=["RB"], dynasty_score=1600),
        ]
    )
    first = player_state_authority.waiver_actionable_player_pool(frame, {})
    second = player_state_authority.waiver_actionable_player_pool(frame.copy(), {})
    pd.testing.assert_frame_equal(first.reset_index(drop=True), second.reset_index(drop=True))
    selected = waivers_ui.select_top_waiver_opportunity(
        first,
        pd.DataFrame(),
        {"qb_format": "1QB"},
        "dynasty_score",
        needed_positions=["RB"],
    )
    assert selected["player_id"] == "valid"


def test_league_ownership_is_recomputed_without_provider_calls():
    frame = pd.DataFrame([_player("a"), _player("b")])
    with patch("requests.sessions.Session.request", side_effect=AssertionError("network call")):
        league_a = player_state_authority.waiver_actionable_player_pool(frame, {"r": ["a"]})
        league_b = player_state_authority.waiver_actionable_player_pool(frame, {"r": ["b"]})
    assert league_a["player_id"].tolist() == ["b"]
    assert league_b["player_id"].tolist() == ["a"]

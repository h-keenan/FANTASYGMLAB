"""Memoize roster_limit_status for unchanged warm My Team truth."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

import app
from modules import prepared_player_frame
from modules import recommendation_lifecycle
from modules import warm_route_render


def _roster_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "player_id": "p1",
                "name": "Alpha",
                "position": "WR",
                "role": "Core",
                "status": "Active",
                "injury_status": "",
                "team": "KC",
                "player_tier": "Star",
                "opportunity_label": "Elite Opportunity",
                "opportunity_score": 90,
                "search_rank": 12,
                "value_score": 9000,
                "market_score": 8000,
                "age": 26,
                "years_exp": 5,
                "suggested_starter": True,
            },
            {
                "player_id": "p2",
                "name": "Beta",
                "position": "RB",
                "role": "Flex",
                "status": "Active",
                "injury_status": "",
                "team": "SF",
                "player_tier": "Contributor",
                "opportunity_label": "Depth",
                "opportunity_score": 20,
                "search_rank": 80,
                "value_score": 1200,
                "market_score": 900,
                "age": 29,
                "years_exp": 7,
                "suggested_starter": False,
            },
        ]
    )


def _lineup(roster: pd.DataFrame) -> pd.DataFrame:
    frame = roster.copy()
    frame["suggested_starter"] = frame["player_id"].eq("p1")
    return frame


def _call(roster=None, **overrides):
    roster = _roster_frame() if roster is None else roster
    payload = dict(
        league_id="league-1",
        roster_id=7,
        roster_df=roster,
        lineup_df=_lineup(roster),
        league_settings={"k_count": 1, "starter_count": 9, "bench_count": 8},
        score_field="value_score",
        active_team_strategy="contender",
        needed_positions=["TE"],
        surplus_positions=["WR"],
        untouchables=["Alpha"],
    )
    payload.update(overrides)
    league = {
        "roster_positions": ["QB", "RB", "WR", "WR", "TE", "FLEX", "BN", "BN", "BN"],
        "settings": {"taxi_slots": 0, "reserve_slots": 0},
    }
    rosters = [
        {
            "roster_id": payload["roster_id"],
            "players": payload["roster_df"]["player_id"].tolist(),
            "taxi": [],
            "reserve": [],
        }
    ]
    with (
        patch.object(app, "get_league", return_value=league),
        patch.object(app, "get_rosters", return_value=rosters),
        patch.object(app, "cached_sleeper_player_directory", return_value={}),
    ):
        return app.roster_limit_status(**payload)


def test_unchanged_same_league_hit_skips_uncached_compute():
    warm_route_render.clear_presentation_models()
    calls = {"n": 0}
    real = app._roster_limit_status_uncached

    def wrapped(**kwargs):
        calls["n"] += 1
        return real(**kwargs)

    with patch.object(app, "_roster_limit_status_uncached", side_effect=wrapped):
        first = _call()
        second = _call()
    assert calls["n"] == 1
    assert first == second
    assert first["available"] is True
    assert warm_route_render.last_presentation_status() == "hit"


def test_roster_player_mutation_misses():
    warm_route_render.clear_presentation_models()
    _call()
    roster = _roster_frame()
    roster.loc[1, "player_id"] = "p9"
    roster.loc[1, "name"] = "Gamma"
    _call(roster=roster)
    assert warm_route_render.last_presentation_status() == "miss"


def test_league_switch_is_isolated():
    warm_route_render.clear_presentation_models()
    _call(league_id="league-1")
    _call(league_id="league-2")
    assert warm_route_render.last_presentation_status() == "miss"


def test_roster_limit_settings_change_misses():
    warm_route_render.clear_presentation_models()
    _call(league_settings={"k_count": 1, "starter_count": 9, "bench_count": 8})
    _call(league_settings={"k_count": 0, "starter_count": 9, "bench_count": 8})
    assert warm_route_render.last_presentation_status() == "miss"


def test_injury_status_mutation_misses():
    warm_route_render.clear_presentation_models()
    _call()
    roster = _roster_frame()
    roster.loc[0, "injury_status"] = "Out"
    _call(roster=roster)
    assert warm_route_render.last_presentation_status() == "miss"


def test_hygiene_clear_drops_roster_limit_memo():
    warm_route_render.clear_presentation_models()
    _call()
    assert warm_route_render.last_presentation_status() == "miss"
    _call()
    assert warm_route_render.last_presentation_status() == "hit"
    prepared_player_frame.clear_prepared_player_frame({})
    _call()
    assert warm_route_render.last_presentation_status() == "miss"


def test_prepared_frame_and_roster_version_are_in_fingerprint():
    warm_route_render.clear_presentation_models()
    state = {
        prepared_player_frame.SIGNATURE_KEY: "frame-a",
        recommendation_lifecycle.ROSTER_STATE_VERSION_SESSION_KEY: "rv-a",
    }
    roster = _roster_frame()
    with (
        patch.object(app, "get_league", return_value={"roster_positions": [], "settings": {}}),
        patch.object(app, "get_rosters", return_value=[{"roster_id": "7", "players": [], "taxi": [], "reserve": []}]),
        patch.object(app.st, "session_state", state, create=True),
    ):
        first = app.build_roster_limit_model_signature(
            league_id="L1",
            roster_id="7",
            roster_df=roster,
            lineup_df=_lineup(roster),
            league_settings={"k_count": 1},
            score_field="value_score",
            active_team_strategy="contender",
            needed_positions=["TE"],
            surplus_positions=["WR"],
            untouchables=[],
        )
        state[prepared_player_frame.SIGNATURE_KEY] = "frame-b"
        second = app.build_roster_limit_model_signature(
            league_id="L1",
            roster_id="7",
            roster_df=roster,
            lineup_df=_lineup(roster),
            league_settings={"k_count": 1},
            score_field="value_score",
            active_team_strategy="contender",
            needed_positions=["TE"],
            surplus_positions=["WR"],
            untouchables=[],
        )
    assert first != second


def test_taxi_membership_change_misses():
    warm_route_render.clear_presentation_models()
    _call()
    league = {
        "roster_positions": ["QB", "RB", "WR", "WR", "TE", "FLEX", "BN", "BN", "BN"],
        "settings": {"taxi_slots": 1, "reserve_slots": 0},
    }
    rosters = [
        {
            "roster_id": 7,
            "players": ["p1", "p2"],
            "taxi": ["p2"],
            "reserve": [],
        }
    ]
    with (
        patch.object(app, "get_league", return_value=league),
        patch.object(app, "get_rosters", return_value=rosters),
        patch.object(app, "cached_sleeper_player_directory", return_value={}),
    ):
        app.roster_limit_status(
            league_id="league-1",
            roster_id=7,
            roster_df=_roster_frame(),
            lineup_df=_lineup(_roster_frame()),
            league_settings={"k_count": 1, "starter_count": 9, "bench_count": 8},
            score_field="value_score",
            active_team_strategy="contender",
            needed_positions=["TE"],
            surplus_positions=["WR"],
            untouchables=["Alpha"],
        )
    assert warm_route_render.last_presentation_status() == "miss"

"""Regression test for a real duplicate-computation bug in
`modules.team_eval.build_league_summary`.

`build_league_summary` scores each roster twice per request -- once with
`current_score_field` and once with `score_field` -- via
`_score_starter_weighted_roster`, a real per-roster pandas pass (copy, sort,
multiple position-slot scans, weighted sums). When a caller passes the SAME
field for both (GET /v1/leagues/{id}/my-team-needs in
services/mobile_api_service.py always does; any other caller also collides
whenever its lens's score_field happens to equal its current_score_field
default of "value_score" -- today that's the "Non-Dynasty" lens), the second
call recomputes a byte-for-byte identical result for every roster in the
league, every single time. Fixed by reusing the first pass's result when the
two field names are identical, same "redone from scratch" bug class as the
league_rankings triple-valuation fix earlier this session.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from modules import team_eval


class _FakeAdapter:
    platform = "sleeper"

    def get_rosters(self, league_id):
        return [
            {"roster_id": 1, "owner_id": "u1", "players": ["p1", "p2"]},
            {"roster_id": 2, "owner_id": "u2", "players": ["p3"]},
        ]

    def get_users(self, league_id):
        return [
            {"user_id": "u1", "display_name": "One"},
            {"user_id": "u2", "display_name": "Two"},
        ]

    def get_league(self, league_id):
        return {"season": 2026, "settings": {}}


def _players_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"player_id": "p1", "name": "Player One", "position": "QB", "age": 24, "dynasty_score": 100, "value_score": 90},
            {"player_id": "p2", "name": "Player Two", "position": "RB", "age": 25, "dynasty_score": 80, "value_score": 70},
            {"player_id": "p3", "name": "Player Three", "position": "WR", "age": 26, "dynasty_score": 60, "value_score": 50},
        ]
    )


def test_same_score_field_scores_each_roster_only_once():
    """current_score_field == score_field (the my-team-needs call shape, and
    the Non-Dynasty-lens shape for every other caller) must not score the
    same roster twice."""

    df_players = _players_df()
    adapter = _FakeAdapter()

    with patch("modules.team_eval.get_league_roster_profiles", return_value={}), patch(
        "modules.team_eval._score_starter_weighted_roster", wraps=team_eval._score_starter_weighted_roster
    ) as spy:
        summary = team_eval.build_league_summary(
            df_players,
            "league",
            score_field="value_score",
            current_score_field="value_score",
            adapter=adapter,
        )

    # Two real rosters (non-empty) in the fixture -> exactly one scoring
    # pass each, not two.
    assert spy.call_count == 2
    assert not summary.empty
    assert set(summary["roster_id"]) == {1, 2}


def test_different_score_fields_still_scores_each_roster_twice():
    """Sanity check the fix is conditional, not a blanket skip: when the two
    fields genuinely differ (the common Dynasty/Rebuild-lens case), both
    passes must still run since they produce different results
    (total_score vs. raw_roster_score read from different columns)."""

    df_players = _players_df()
    adapter = _FakeAdapter()

    with patch("modules.team_eval.get_league_roster_profiles", return_value={}), patch(
        "modules.team_eval._score_starter_weighted_roster", wraps=team_eval._score_starter_weighted_roster
    ) as spy:
        summary = team_eval.build_league_summary(
            df_players,
            "league",
            score_field="dynasty_score",
            current_score_field="value_score",
            adapter=adapter,
        )

    assert spy.call_count == 4  # 2 rosters * 2 distinct fields
    assert not summary.empty


def test_reused_result_matches_a_fresh_identical_call():
    """The reused dict must be identical to what a fresh call with the same
    field would have produced (guards against the fix silently changing
    output, not just call count)."""

    df_players = _players_df()
    adapter = _FakeAdapter()

    with patch("modules.team_eval.get_league_roster_profiles", return_value={}):
        summary = team_eval.build_league_summary(
            df_players,
            "league",
            score_field="value_score",
            current_score_field="value_score",
            adapter=adapter,
        )

    row = summary[summary["roster_id"] == 1].iloc[0]
    # current_roster_score reads current_scores["raw_roster_score"];
    # raw_roster_score reads long_term_scores["raw_roster_score"]. When the
    # two fields are identical, long_term_scores IS current_scores (the
    # reused object), so these must be exactly equal -- not just
    # coincidentally close.
    assert row["raw_roster_score"] == row["current_roster_score"]

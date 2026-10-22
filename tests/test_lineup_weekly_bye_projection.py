"""Regression (logic audit 2026-10-21): suggested lineups for a given week.

My Team / Matchup ranked starters by season dynasty value only, so a
player on bye (or ruled Out/IR) was suggested as a starter. Weekly mode of
modules.team_eval.suggest_optimal_lineup must:

- never start a player on bye or ruled out; his slot stays open instead;
- rank by this week's projected points where a projection exists, and fall
  back to season value only for players without one;
- keep the #1330 slot rules (WRRB_FLEX counted once, narrowest flex first).
"""

from __future__ import annotations

import pandas as pd

from modules import league_value_settings
from modules.team_eval import lineup_open_slots, suggest_optimal_lineup

_SETTINGS = {"qb_count": 1, "rb_count": 2, "wr_count": 2, "te_count": 1, "regular_flex_count": 1, "k_count": 0}


def _frame(rows):
    return pd.DataFrame(
        [
            {
                "player_id": pid,
                "name": pid,
                "position": pos,
                "team": team,
                "value_score": score,
                "status": status,
                "injury_status": injury,
            }
            for pid, pos, score, team, status, injury in rows
        ]
    )


def _roster():
    return _frame(
        [
            ("qb1", "QB", 8000, "KC", "Active", ""),
            ("qb2", "QB", 2000, "NYJ", "Active", ""),
            ("rb1", "RB", 9000, "ATL", "Active", ""),
            ("rb2", "RB", 7000, "DET", "Active", ""),
            ("rb3", "RB", 3000, "CHI", "Active", ""),
            ("wr1", "WR", 8500, "CIN", "Active", ""),
            ("wr2", "WR", 6000, "MIN", "Active", ""),
            ("wr3", "WR", 2500, "SEA", "Active", ""),
            ("te1", "TE", 5000, "LV", "Active", ""),
            ("te2", "TE", 1500, "TB", "Active", ""),
        ]
    )


def _by_id(frame):
    return {row["player_id"]: row for _, row in frame.iterrows()}


def test_player_on_bye_never_starts_even_with_top_value():
    lineup = _by_id(suggest_optimal_lineup(_roster(), _SETTINGS, score_field="value_score", bye_player_ids={"rb1"}))

    assert lineup["rb1"]["slot"] == "BENCH"
    assert lineup["rb1"]["start_ineligible_reason"] == "Bye"
    assert bool(lineup["rb1"]["on_bye"]) is True
    assert bool(lineup["rb1"]["displaced_by_bye"]) is True
    # The next RB up takes the slot.
    assert lineup["rb3"]["suggested_starter"]


def test_bye_qb_leaves_slot_open_rather_than_starting_him():
    frame = _frame(
        [
            ("qb1", "QB", 8000, "KC", "Active", ""),
            ("rb1", "RB", 9000, "ATL", "Active", ""),
            ("rb2", "RB", 7000, "DET", "Active", ""),
        ]
    )
    settings = {"qb_count": 1, "rb_count": 2, "wr_count": 0, "te_count": 0, "regular_flex_count": 0}
    lineup_df = suggest_optimal_lineup(frame, settings, score_field="value_score", bye_player_ids={"qb1"})
    lineup = _by_id(lineup_df)

    assert lineup["qb1"]["slot"] == "BENCH"
    assert lineup_open_slots(lineup_df, settings) == ["QB"]


def test_out_and_ir_players_are_ineligible_in_weekly_mode():
    frame = _roster()
    frame.loc[frame["player_id"] == "wr1", "injury_status"] = "Out"
    frame.loc[frame["player_id"] == "te1", "injury_status"] = "IR"
    frame.loc[frame["player_id"] == "rb2", "injury_status"] = "Questionable"
    lineup = _by_id(suggest_optimal_lineup(frame, _SETTINGS, score_field="value_score", weekly_points={}))

    assert lineup["wr1"]["slot"] == "BENCH"
    assert lineup["wr1"]["start_ineligible_reason"] == "Out"
    assert bool(lineup["wr1"]["displaced_by_injury"]) is True
    assert lineup["te1"]["slot"] == "BENCH"
    assert lineup["te1"]["start_ineligible_reason"] == "IR"
    # Questionable is a GM judgement call and stays startable.
    assert lineup["rb2"]["suggested_starter"]
    assert pd.isna(lineup["rb2"]["start_ineligible_reason"])


def test_ruled_out_only_option_leaves_slot_open_in_weekly_mode():
    frame = _frame(
        [
            ("qb1", "QB", 8000, "KC", "Active", "Out"),
            ("rb1", "RB", 9000, "ATL", "Active", ""),
        ]
    )
    settings = {"qb_count": 1, "rb_count": 1, "wr_count": 0, "te_count": 0, "regular_flex_count": 0}
    lineup_df = suggest_optimal_lineup(frame, settings, score_field="value_score", weekly_points={})

    assert _by_id(lineup_df)["qb1"]["slot"] == "BENCH"
    assert lineup_open_slots(lineup_df, settings) == ["QB"]


def test_season_mode_is_unchanged_for_structural_callers():
    frame = _frame(
        [
            ("qb1", "QB", 8000, "KC", "Active", "Out"),
            ("rb1", "RB", 9000, "ATL", "Active", ""),
        ]
    )
    settings = {"qb_count": 1, "rb_count": 1, "wr_count": 0, "te_count": 0, "regular_flex_count": 0}
    lineup_df = suggest_optimal_lineup(frame, settings, score_field="value_score")

    # Season mode still fills a slot nothing else can (flagged ruled_out),
    # and adds no weekly columns.
    assert _by_id(lineup_df)["qb1"]["slot"] == "QB"
    assert "start_ineligible_reason" not in lineup_df.columns


def test_weekly_projections_outrank_season_value():
    points = {
        "qb1": 22.0,
        "qb2": 12.0,
        "rb1": 9.0,  # high dynasty value, low projection this week
        "rb2": 16.0,
        "rb3": 14.0,
        "wr1": 18.0,
        "wr2": 11.0,
        "wr3": 13.0,
        "te1": 8.0,
        "te2": 10.0,
    }
    lineup = _by_id(suggest_optimal_lineup(_roster(), _SETTINGS, score_field="value_score", weekly_points=points))

    assert lineup["rb2"]["slot"] == "RB"
    assert lineup["rb3"]["slot"] == "RB"
    assert lineup["wr1"]["slot"] == "WR"
    assert lineup["wr3"]["slot"] == "WR"
    assert lineup["te2"]["slot"] == "TE"
    # FLEX goes to the best remaining projection (wr2 11.0 vs rb1 9.0, te1 8.0).
    assert lineup["wr2"]["slot"] == "FLEX"
    assert lineup["rb1"]["slot"] == "BENCH"
    assert lineup["rb2"]["lineup_points_basis"] == "projection"
    assert lineup["rb2"]["lineup_points"] == 16.0


def test_unprojected_low_value_backup_is_scaled_down_not_promoted():
    # rb3 (value 3000) has no projection: a deep backup with no recent
    # production. Every projected RB out-values him, so he gets the least
    # valuable one's projection (rb2, 7000 → 16.0) scaled by value ratio,
    # and can't jump a projected starter on a guess.
    points = {"qb1": 20.0, "rb1": 10.0, "rb2": 16.0, "wr1": 15.0, "wr2": 12.0, "wr3": 4.0, "te1": 9.0, "te2": 3.0}
    lineup = _by_id(suggest_optimal_lineup(_roster(), _SETTINGS, score_field="value_score", weekly_points=points))

    assert lineup["rb3"]["lineup_points_basis"] == "value_estimate"
    assert lineup["rb3"]["lineup_points"] == 16.0 * 3000 / 7000
    # Both projected RBs keep the RB slots; his scaled estimate (6.9) only
    # beats the weak projected leftovers (wr3 4.0, te2 3.0) for FLEX.
    assert lineup["rb1"]["slot"] == "RB"
    assert lineup["rb2"]["slot"] == "RB"
    assert lineup["rb3"]["slot"] == "FLEX"
    assert lineup["qb2"]["lineup_points_basis"] == "value_estimate"
    assert lineup["qb2"]["lineup_points"] == 5.0  # 20.0 * 2000 / 8000


def test_unprojected_high_value_player_matches_the_projected_peer_just_below_him():
    # rb1 (value 9000) is back from injury with no recent games: he's
    # matched to the projected RB just below him in value (rb2, 16.0).
    points = {"qb1": 20.0, "rb2": 16.0, "rb3": 14.0, "wr1": 15.0, "wr2": 12.0, "wr3": 4.0, "te1": 9.0, "te2": 3.0}
    lineup = _by_id(suggest_optimal_lineup(_roster(), _SETTINGS, score_field="value_score", weekly_points=points))

    assert lineup["rb1"]["lineup_points"] == 16.0
    assert lineup["rb1"]["suggested_starter"]


def test_no_projections_at_all_falls_back_to_value_order_but_keeps_bye_gate():
    lineup = _by_id(
        suggest_optimal_lineup(_roster(), _SETTINGS, score_field="value_score", weekly_points={}, bye_player_ids={"wr1"})
    )

    assert lineup["wr1"]["slot"] == "BENCH"
    assert lineup["rb1"]["slot"] == "RB"
    assert lineup["rb2"]["slot"] == "RB"
    assert lineup["rb1"]["lineup_points_basis"] == "value"


def test_weekly_mode_respects_1330_slot_rules():
    positions = ["QB", "RB", "RB", "WR", "WR", "TE", "WRRB_FLEX", "FLEX"]
    settings = league_value_settings.detect_league_value_settings_from_payload(
        {"roster_positions": positions + ["BN"] * 6}
    )
    points = {
        "qb1": 20.0,
        "rb1": 18.0,
        "rb2": 17.0,
        "rb3": 10.0,
        "wr1": 16.0,
        "wr2": 15.0,
        "wr3": 9.0,
        "te1": 12.0,
        "te2": 11.0,
    }
    lineup_df = suggest_optimal_lineup(_roster(), settings, score_field="value_score", weekly_points=points)
    lineup = _by_id(lineup_df)
    starters = lineup_df[lineup_df["suggested_starter"]]

    assert len(starters) == len(positions)
    # WR/RB filled first with the best remaining RB/WR (rb3 10.0); FLEX
    # then takes te2 (11.0) over wr3 (9.0).
    assert lineup["rb3"]["slot"] == "WR/RB"
    assert lineup["te2"]["slot"] == "FLEX"
    assert lineup_open_slots(lineup_df, settings) == []

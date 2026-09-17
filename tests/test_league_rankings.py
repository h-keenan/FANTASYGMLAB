"""Direct unit tests for modules/league_rankings.py — the pure-pandas
port of app.py's Power Rank / Franchise Rank / Draft Capital Rank chain.
Exercised here without the Sleeper/adapter mocking test_mobile_api_service.py
needs for the full endpoint, since these functions take plain DataFrames.
"""

from __future__ import annotations

import pandas as pd

from modules import league_rankings


def test_safe_pick_value_uses_score_when_present():
    assert league_rankings.safe_pick_value({"score": 5000}) == 5000


def test_safe_pick_value_computes_from_base_score_and_multipliers():
    pick = {
        "base_score": 4000,
        "future_discount": 0.8,
        "team_modifier": 1.0,
        "format_multiplier": 1.0,
        "class_strength_multiplier": 1.0,
        "prospect_strength_multiplier": 1.0,
    }
    assert league_rankings.safe_pick_value(pick) == round(4000 * 0.8)


def test_safe_pick_value_falls_back_to_round_defaults():
    assert league_rankings.safe_pick_value({"round": 1}) == 6500
    assert league_rankings.safe_pick_value({"round": 2}) == 3200
    # round 5: max(150, 650 - (5-4)*150) = 500
    assert league_rankings.safe_pick_value({"round": 5}) == 500


def test_build_draft_capital_summary_sums_per_roster_and_ranks_descending():
    df_summary = pd.DataFrame(
        [
            {"roster_id": 1, "team_name": "Alpha", "owner_name": "A", "avatar_url": "", "mode": "contend"},
            {"roster_id": 2, "team_name": "Beta", "owner_name": "B", "avatar_url": "", "mode": "rebuild"},
        ]
    )
    draft_picks = [
        {"owner_roster_id": 1, "round": 1, "season": 2027, "score": 6500},
        {"owner_roster_id": 1, "round": 2, "season": 2027, "score": 3200},
        {"owner_roster_id": 2, "round": 4, "season": 2027, "score": 650},
    ]
    result = league_rankings.build_draft_capital_summary(df_summary, draft_picks)
    by_roster = {int(row["roster_id"]): row for _, row in result.iterrows()}
    assert by_roster[1]["draft_capital"] == 6500 + 3200
    assert by_roster[1]["pick_count"] == 2
    assert by_roster[1]["first_rounders"] == 1
    assert by_roster[2]["draft_capital"] == 650
    # Roster 1 clearly holds more draft capital, so it ranks first (dense
    # rank, descending).
    assert by_roster[1]["draft_capital_rank"] == 1
    assert by_roster[2]["draft_capital_rank"] == 2


def test_build_draft_capital_summary_handles_no_picks():
    df_summary = pd.DataFrame(
        [{"roster_id": 1, "team_name": "Alpha", "owner_name": "A", "avatar_url": "", "mode": "contend"}]
    )
    result = league_rankings.build_draft_capital_summary(df_summary, [])
    assert result.iloc[0]["draft_capital"] == 0
    assert result.iloc[0]["draft_capital_rank"] == 1


def test_build_league_display_frame_computes_power_and_franchise_rank():
    df_summary = pd.DataFrame(
        [
            {
                "roster_id": 1,
                "team_name": "Alpha",
                "total_score": 9000,
                "raw_roster_score": 9000,
                "starter_score": 6000,
                "bench_score": 3000,
                "mode": "contend",
            },
            {
                "roster_id": 2,
                "team_name": "Beta",
                "total_score": 3000,
                "raw_roster_score": 3000,
                "starter_score": 2000,
                "bench_score": 1000,
                "mode": "rebuild",
            },
        ]
    )
    draft_capital_summary = pd.DataFrame(
        [
            {"roster_id": 1, "draft_capital": 1000, "pick_count": 1, "first_rounders": 0, "second_rounders": 1, "third_rounders": 0, "draft_capital_rank": 2},
            {"roster_id": 2, "draft_capital": 5000, "pick_count": 3, "first_rounders": 2, "second_rounders": 0, "third_rounders": 0, "draft_capital_rank": 1},
        ]
    )
    result = league_rankings.build_league_display_frame(df_summary, draft_capital_summary, include_picks=True)
    by_roster = {int(row["roster_id"]): row for _, row in result.iterrows()}
    # Power rank follows total_score alone — roster 1 wins on raw power.
    assert by_roster[1]["power_rank"] == 1
    assert by_roster[2]["power_rank"] == 2
    # Franchise rank folds in draft capital (raw_roster_score + draft_capital):
    # roster 1 = 9000 + 1000 = 10000, roster 2 = 3000 + 5000 = 8000 — roster 1
    # still wins here too, but by a much smaller margin, proving draft
    # capital actually got added rather than ignored.
    assert by_roster[1]["franchise_score"] == 10000
    assert by_roster[2]["franchise_score"] == 8000
    assert by_roster[1]["franchise_rank"] == 1
    # include_picks=True means overall_rank aliases to franchise_rank.
    assert by_roster[1]["overall_rank"] == by_roster[1]["franchise_rank"]


def test_add_league_detail_ranks_computes_starter_bench_age_ranks():
    # current_roster_score has to be a real column, even if unused by these
    # assertions — add_league_detail_ranks does ranked.get("current_roster_
    # score"), and DataFrame.get on a genuinely missing column returns a bare
    # None/scalar NaN rather than a Series, which .fillna() can't handle.
    # build_league_summary's real output always includes this column; only a
    # synthetic test fixture would ever omit it.
    df_display = pd.DataFrame(
        [
            {"roster_id": 1, "raw_roster_score": 9000, "current_roster_score": 9000, "starter_score": 6000, "bench_score": 3000, "avg_age": 24.0},
            {"roster_id": 2, "raw_roster_score": 3000, "current_roster_score": 3000, "starter_score": 2000, "bench_score": 1000, "avg_age": 29.0},
        ]
    )
    result = league_rankings.add_league_detail_ranks(df_display)
    by_roster = {int(row["roster_id"]): row for _, row in result.iterrows()}
    assert by_roster[1]["starter_rank"] == 1
    assert by_roster[2]["starter_rank"] == 2
    assert by_roster[1]["bench_rank"] == 1
    # Younger average age ranks first (ascending).
    assert by_roster[1]["age_rank"] == 1
    assert by_roster[2]["age_rank"] == 2


def test_add_league_detail_ranks_on_empty_frame_is_a_no_op():
    empty = pd.DataFrame()
    result = league_rankings.add_league_detail_ranks(empty)
    assert result.empty

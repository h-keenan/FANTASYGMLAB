"""Direct unit tests for modules/league_rankings.py — the pure-pandas
port of app.py's Power Rank / Franchise Rank / Draft Capital Rank chain.
Exercised here without the Sleeper/adapter mocking test_mobile_api_service.py
needs for the full endpoint, since these functions take plain DataFrames.
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from modules import league_rankings, league_value_settings, player_eligibility, rankings, sleeper, team_eval


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


def test_draft_year_columns_sorts_by_year_ignoring_other_columns():
    df = pd.DataFrame(
        columns=["roster_id", "pick_value_2027", "pick_value_2025", "pick_value_2026", "team_name"]
    )
    assert league_rankings.draft_year_columns(df) == [
        "pick_value_2025",
        "pick_value_2026",
        "pick_value_2027",
    ]


def test_build_draft_workspace_frame_on_empty_summary_is_a_no_op():
    result = league_rankings.build_draft_workspace_frame(pd.DataFrame(), None)
    assert result.empty


def test_build_draft_workspace_frame_computes_future_capital_without_intel():
    draft_capital_summary = pd.DataFrame(
        [
            {
                "roster_id": 1,
                "team_name": "Alpha",
                "mode": "rebuild",
                "draft_capital_rank": 1,
                "draft_capital": 6000,
                "pick_count": 2,
                "first_rounders": 1,
                "pick_value_2026": 2000,
                "pick_value_2027": 4000,
            },
            {
                "roster_id": 2,
                "team_name": "Beta",
                "mode": "contender",
                "draft_capital_rank": 2,
                "draft_capital": 1000,
                "pick_count": 1,
                "first_rounders": 0,
                "pick_value_2026": 1000,
                "pick_value_2027": 0,
            },
        ]
    )
    result = league_rankings.build_draft_workspace_frame(draft_capital_summary, None, draft_year=2026)
    by_roster = {int(row["roster_id"]): row for _, row in result.iterrows()}

    # future_draft_capital only sums pick_value_<year> columns for years
    # AFTER draft_year (2026 itself is the current rookie draft, not future).
    assert by_roster[1]["future_draft_capital"] == 4000
    assert by_roster[2]["future_draft_capital"] == 0
    assert by_roster[1]["future_draft_capital_rank"] == 1
    assert by_roster[2]["future_draft_capital_rank"] == 2

    # No df_intel supplied: power_rank/franchise_rank/age_rank default to
    # len(summary) (the graceful-degradation fallback), and strategy_display
    # falls back to team_strategy_label(mode) rather than staying blank.
    assert by_roster[1]["power_rank"] == 2
    assert by_roster[1]["franchise_rank"] == 2
    assert by_roster[1]["strategy_display"] == "Rebuild"
    assert by_roster[2]["strategy_display"] == "Contender"
    assert by_roster[1]["strategy_key"] == "rebuild"


def test_build_draft_workspace_frame_merges_real_intel_when_provided():
    draft_capital_summary = pd.DataFrame(
        [
            {
                "roster_id": 1,
                "team_name": "Alpha",
                "mode": "rebuild",
                "draft_capital_rank": 1,
                "draft_capital": 6000,
                "pick_count": 2,
                "first_rounders": 1,
            },
        ]
    )
    df_intel = pd.DataFrame(
        [
            {
                "roster_id": 1,
                "power_rank": 5,
                "franchise_rank": 4,
                "age_rank": 3,
                "avg_age": 26.5,
                "strategy_display": "Aggressive Rebuild",
            },
        ]
    )
    result = league_rankings.build_draft_workspace_frame(draft_capital_summary, df_intel)
    row = result.iloc[0]
    # Real intel values win over the graceful-degradation defaults.
    assert row["power_rank"] == 5
    assert row["franchise_rank"] == 4
    assert row["age_rank"] == 3
    assert row["avg_age"] == 26.5
    assert row["strategy_display"] == "Aggressive Rebuild"


# --- add_rank_tie_metadata --------------------------------------------------
#
# The rank VALUES here are never touched — they already come from
# Series.rank(method="dense", ...), which already makes tied entities share
# one identical integer rank. add_rank_tie_metadata only adds the display
# metadata (`<col>_tied` / `<col>_tie_count`) so a UI can render "T4" for a
# shared rank instead of an equally-precise-looking bare "#4".


def test_add_rank_tie_metadata_no_ties_are_all_plain():
    df = pd.DataFrame({"power_rank": [1, 2, 3, 4]})
    result = league_rankings.add_rank_tie_metadata(df, ["power_rank"])
    assert list(result["power_rank_tied"]) == [False, False, False, False]
    assert list(result["power_rank_tie_count"]) == [1, 1, 1, 1]


def test_add_rank_tie_metadata_two_way_tie():
    # Two rosters dense-ranked #2 (a genuine tie); #1 and #4 remain unique.
    df = pd.DataFrame({"power_rank": [1, 2, 2, 3]})
    result = league_rankings.add_rank_tie_metadata(df, ["power_rank"])
    assert list(result["power_rank_tied"]) == [False, True, True, False]
    assert list(result["power_rank_tie_count"]) == [1, 2, 2, 1]


def test_add_rank_tie_metadata_three_plus_way_tie():
    # Three rosters share dense rank #1; the rest are unique.
    df = pd.DataFrame({"power_rank": [1, 1, 1, 2, 3]})
    result = league_rankings.add_rank_tie_metadata(df, ["power_rank"])
    assert list(result["power_rank_tied"]) == [True, True, True, False, False]
    assert list(result["power_rank_tie_count"]) == [3, 3, 3, 1, 1]


def test_add_rank_tie_metadata_every_team_tied_does_not_break():
    # Edge case: every roster dense-ranked #1 (e.g. every score identical).
    # Still must render tied for all, not crash or silently drop the column.
    df = pd.DataFrame({"power_rank": [1, 1, 1, 1]})
    result = league_rankings.add_rank_tie_metadata(df, ["power_rank"])
    assert list(result["power_rank_tied"]) == [True, True, True, True]
    assert list(result["power_rank_tie_count"]) == [4, 4, 4, 4]


def test_add_rank_tie_metadata_handles_multiple_columns_independently():
    df = pd.DataFrame(
        {
            "power_rank": [1, 1, 2],
            "franchise_rank": [1, 2, 3],
        }
    )
    result = league_rankings.add_rank_tie_metadata(df, ["power_rank", "franchise_rank"])
    assert list(result["power_rank_tied"]) == [True, True, False]
    assert list(result["franchise_rank_tied"]) == [False, False, False]


def test_add_rank_tie_metadata_missing_column_is_skipped_not_errored():
    df = pd.DataFrame({"power_rank": [1, 2]})
    result = league_rankings.add_rank_tie_metadata(df, ["power_rank", "nonexistent_rank"])
    assert "power_rank_tied" in result.columns
    assert "nonexistent_rank_tied" not in result.columns


def test_add_rank_tie_metadata_on_empty_frame_is_a_no_op():
    empty = pd.DataFrame()
    result = league_rankings.add_rank_tie_metadata(empty, ["power_rank"])
    assert result.empty


def test_build_draft_capital_summary_exposes_tie_metadata_for_a_two_way_tie():
    df_summary = pd.DataFrame(
        [
            {"roster_id": 1, "team_name": "Alpha", "owner_name": "A", "avatar_url": "", "mode": "contend"},
            {"roster_id": 2, "team_name": "Beta", "owner_name": "B", "avatar_url": "", "mode": "rebuild"},
            {"roster_id": 3, "team_name": "Gamma", "owner_name": "C", "avatar_url": "", "mode": "retool"},
        ]
    )
    draft_picks = [
        {"owner_roster_id": 1, "round": 1, "season": 2027, "score": 6500},
        {"owner_roster_id": 2, "round": 1, "season": 2027, "score": 6500},
        {"owner_roster_id": 3, "round": 4, "season": 2027, "score": 650},
    ]
    result = league_rankings.build_draft_capital_summary(df_summary, draft_picks)
    by_roster = {int(row["roster_id"]): row for _, row in result.iterrows()}
    # Rosters 1 and 2 both hold 6500 draft capital -> tied for rank 1.
    assert by_roster[1]["draft_capital_rank"] == 1
    assert by_roster[2]["draft_capital_rank"] == 1
    assert by_roster[1]["draft_capital_rank_tied"] is True
    assert by_roster[2]["draft_capital_rank_tied"] is True
    assert by_roster[1]["draft_capital_rank_tie_count"] == 2
    assert by_roster[3]["draft_capital_rank_tied"] is False
    assert by_roster[3]["draft_capital_rank_tie_count"] == 1


def test_build_league_display_frame_exposes_tie_metadata_for_power_and_franchise_rank():
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
                "total_score": 9000,
                "raw_roster_score": 9000,
                "starter_score": 6000,
                "bench_score": 3000,
                "mode": "contend",
            },
            {
                "roster_id": 3,
                "team_name": "Gamma",
                "total_score": 3000,
                "raw_roster_score": 3000,
                "starter_score": 2000,
                "bench_score": 1000,
                "mode": "rebuild",
            },
        ]
    )
    result = league_rankings.build_league_display_frame(df_summary, None, include_picks=False)
    by_roster = {int(row["roster_id"]): row for _, row in result.iterrows()}
    # Rosters 1 and 2 have identical total_score -> tied power_rank #1.
    assert by_roster[1]["power_rank"] == by_roster[2]["power_rank"] == 1
    assert by_roster[1]["power_rank_tied"] is True
    assert by_roster[2]["power_rank_tied"] is True
    assert by_roster[1]["power_rank_tie_count"] == 2
    assert by_roster[3]["power_rank_tied"] is False
    # include_picks=False means overall_rank aliases power_rank, tie info included.
    assert by_roster[1]["overall_rank_tied"] is True
    assert by_roster[3]["overall_rank_tied"] is False


def test_add_league_detail_ranks_exposes_tie_metadata_for_a_three_way_tie():
    df_display = pd.DataFrame(
        [
            {"roster_id": 1, "raw_roster_score": 5000, "current_roster_score": 5000, "starter_score": 3000, "bench_score": 2000, "avg_age": 25.0},
            {"roster_id": 2, "raw_roster_score": 5000, "current_roster_score": 5000, "starter_score": 3000, "bench_score": 2000, "avg_age": 25.0},
            {"roster_id": 3, "raw_roster_score": 5000, "current_roster_score": 5000, "starter_score": 3000, "bench_score": 2000, "avg_age": 25.0},
            {"roster_id": 4, "raw_roster_score": 1000, "current_roster_score": 1000, "starter_score": 500, "bench_score": 500, "avg_age": 30.0},
        ]
    )
    result = league_rankings.add_league_detail_ranks(df_display)
    by_roster = {int(row["roster_id"]): row for _, row in result.iterrows()}
    for roster_id in (1, 2, 3):
        assert by_roster[roster_id]["starter_rank_tied"] is True
        assert by_roster[roster_id]["starter_rank_tie_count"] == 3
        assert by_roster[roster_id]["age_rank_tied"] is True
    assert by_roster[4]["starter_rank_tied"] is False
    assert by_roster[4]["age_rank_tied"] is False


def test_build_draft_workspace_frame_exposes_future_draft_capital_rank_tie_metadata():
    draft_capital_summary = pd.DataFrame(
        [
            {"roster_id": 1, "team_name": "Alpha", "mode": "rebuild", "draft_capital_rank": 1, "draft_capital": 6000, "pick_count": 2, "first_rounders": 1, "pick_value_2027": 4000},
            {"roster_id": 2, "team_name": "Beta", "mode": "rebuild", "draft_capital_rank": 2, "draft_capital": 4000, "pick_count": 1, "first_rounders": 0, "pick_value_2027": 4000},
        ]
    )
    result = league_rankings.build_draft_workspace_frame(draft_capital_summary, None, draft_year=2026)
    by_roster = {int(row["roster_id"]): row for _, row in result.iterrows()}
    # Both rosters hold identical 2027 (future) draft capital -> tied.
    assert by_roster[1]["future_draft_capital_rank"] == by_roster[2]["future_draft_capital_rank"] == 1
    assert by_roster[1]["future_draft_capital_rank_tied"] is True
    assert by_roster[2]["future_draft_capital_rank_tied"] is True
    assert by_roster[1]["future_draft_capital_rank_tie_count"] == 2


def _patch_cache_ingredients(monkeypatch):
    monkeypatch.setattr(sleeper, "get_league", lambda _league_id: {"league_id": "x", "settings": {}})
    monkeypatch.setattr(
        rankings, "load_players", lambda _db_path: pd.DataFrame([{"player_id": "p1", "name": "P1"}])
    )
    monkeypatch.setattr(
        player_eligibility, "filter_current_fantasy_players", lambda df, **_kwargs: df
    )
    monkeypatch.setattr(league_value_settings, "apply_valuation_lens", lambda df, *_args, **_kwargs: df)
    monkeypatch.setattr(league_value_settings, "valuation_score_field", lambda _lens: "value_score")


def test_build_league_rankings_frame_cached_concurrent_misses_single_flight(monkeypatch):
    """Two concurrent cache misses for the same (league, lens, ...) key must
    run the expensive league-wide ranking pass exactly once, not once per
    caller.

    This is now enforced by a Redis-backed distributed lock
    (modules.redis_cache.redis_single_flight_cache), not a per-process
    functools.lru_cache + threading.Lock pair — the old in-process pair
    only protected one uvicorn worker; under docker-compose.yml's multiple
    mobile-api workers each would get its own separate lock/cache, so the
    same pass could still run once per worker. tests/conftest.py's autouse
    fakeredis fixture backs build_league_rankings_frame_cached with a real
    (fake) Redis here, so this test exercises the actual code path."""

    _patch_cache_ingredients(monkeypatch)

    call_count = 0
    call_count_lock = threading.Lock()

    def _slow_stub(_valued, league_id, **_kwargs):
        nonlocal call_count
        with call_count_lock:
            call_count += 1
        time.sleep(0.2)
        return pd.DataFrame([{"league_id": league_id, "ok": True}])

    monkeypatch.setattr(league_rankings, "build_league_rankings_frame", _slow_stub)

    league_id = "test-single-flight-league"
    results: list[pd.DataFrame] = []
    results_lock = threading.Lock()

    def _call():
        result = league_rankings.build_league_rankings_frame_cached(
            league_id=league_id, lens="Dynasty", players_db_path="unused.db"
        )
        with results_lock:
            results.append(result)

    threads = [threading.Thread(target=_call) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert call_count == 1, "concurrent misses for the same key must single-flight to one real computation"
    assert len(results) == 8
    assert all(r.iloc[0]["league_id"] == league_id for r in results)


def test_build_league_summary_and_draft_capital_cached_concurrent_misses_single_flight(monkeypatch):
    """Same single-flight guarantee as the rankings-frame cache above (now
    Redis-backed — see that test's docstring), for
    build_league_summary_and_draft_capital_cached (Draft Center/Draft
    Picks' shared cache)."""

    _patch_cache_ingredients(monkeypatch)

    call_count = 0
    call_count_lock = threading.Lock()

    def _slow_stub(_valued, league_id, **_kwargs):
        nonlocal call_count
        with call_count_lock:
            call_count += 1
        time.sleep(0.2)
        return (
            pd.DataFrame([{"league_id": league_id, "ok": True}]),
            pd.DataFrame([{"league_id": league_id, "ok": True}]),
        )

    monkeypatch.setattr(league_rankings, "build_league_summary_and_draft_capital", _slow_stub)

    league_id = "test-single-flight-league-2"
    results: list[tuple[pd.DataFrame, pd.DataFrame]] = []
    results_lock = threading.Lock()

    def _call():
        result = league_rankings.build_league_summary_and_draft_capital_cached(
            league_id=league_id, lens="Dynasty", players_db_path="unused.db"
        )
        with results_lock:
            results.append(result)

    threads = [threading.Thread(target=_call) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert call_count == 1, "concurrent misses for the same key must single-flight to one real computation"
    assert len(results) == 8
    assert all(summary.iloc[0]["league_id"] == league_id for summary, _ in results)


# --- Mobile/web archetype parity -------------------------------------------
#
# Regression for the gap a prior audit found: services/mobile_api_service.py's
# get_league_team_rankings used to run modules.team_eval.refine_team_directions
# directly on the cheap build_league_rankings_frame_cached frame, which has no
# injury_burden/top_heavy_ratio/impact_tier_starters/elite_tier_count columns
# at all (health/balance inputs silently defaulted to neutral), while app.py's
# web dashboard ran the same classifier on cached_league_intelligence_frame,
# which merges real per-roster injury data via the per-roster loop now
# extracted into build_roster_health_metrics_frame. The same team could get a
# different auto-computed archetype label on mobile vs. web. Both callers now
# merge build_roster_health_metrics_frame's output before classifying -- this
# proves that merge produces identical results regardless of which caller's
# base frame it's merged onto, and that it actually changes the outcome
# relative to the old no-health-data behavior (otherwise this would be a
# vacuous test).


def _injury_parity_players() -> pd.DataFrame:
    rows = [
        # Roster 1 ("Powerhouse"): a loaded roster whose top two backs are on
        # IR -- real injury weight (injury_burden >= 4, 2 injured starters)
        # that modules.team_eval._assign_team_archetype's Juggernaut gate and
        # refine_team_directions's health_strength input both react to.
        {"player_id": "h1", "name": "QB1", "position": "QB", "age": 28, "team": "AAA", "dynasty_score": 90, "value_score": 90, "player_tier": "Elite", "status": "", "injury_status": ""},
        {"player_id": "h2", "name": "RB1", "position": "RB", "age": 24, "team": "AAA", "dynasty_score": 95, "value_score": 95, "player_tier": "Elite", "status": "IR", "injury_status": "Injured Reserve"},
        {"player_id": "h3", "name": "RB2", "position": "RB", "age": 25, "team": "AAA", "dynasty_score": 93, "value_score": 93, "player_tier": "Elite", "status": "IR", "injury_status": "Injured Reserve"},
        {"player_id": "h4", "name": "RB3", "position": "RB", "age": 23, "team": "AAA", "dynasty_score": 60, "value_score": 60, "player_tier": "Star", "status": "", "injury_status": ""},
        {"player_id": "h5", "name": "RB4", "position": "RB", "age": 26, "team": "AAA", "dynasty_score": 55, "value_score": 55, "player_tier": "Starter", "status": "", "injury_status": ""},
        {"player_id": "h6", "name": "WR1", "position": "WR", "age": 24, "team": "AAA", "dynasty_score": 80, "value_score": 80, "player_tier": "Elite", "status": "", "injury_status": ""},
        {"player_id": "h7", "name": "WR2", "position": "WR", "age": 25, "team": "AAA", "dynasty_score": 75, "value_score": 75, "player_tier": "Star", "status": "", "injury_status": ""},
        {"player_id": "h8", "name": "WR3", "position": "WR", "age": 23, "team": "AAA", "dynasty_score": 70, "value_score": 70, "player_tier": "Core Starter", "status": "", "injury_status": ""},
        {"player_id": "h9", "name": "WR4", "position": "WR", "age": 26, "team": "AAA", "dynasty_score": 50, "value_score": 50, "player_tier": "Depth", "status": "", "injury_status": ""},
        {"player_id": "h10", "name": "TE1", "position": "TE", "age": 27, "team": "AAA", "dynasty_score": 40, "value_score": 40, "player_tier": "Depth", "status": "", "injury_status": ""},
    ]
    # Roster 2 ("Rebuilder"): healthy, much weaker/younger -- a contrasting
    # roster so power/franchise/starter/bench ranks aren't degenerate ties.
    positions = ["QB", "RB", "RB", "RB", "RB", "WR", "WR", "WR", "WR", "TE"]
    for i in range(1, 11):
        rows.append(
            {
                "player_id": f"r{i}",
                "name": f"Weak{i}",
                "position": positions[i - 1],
                "age": 22,
                "team": "BBB",
                "dynasty_score": 10,
                "value_score": 10,
                "player_tier": "Depth",
                "status": "",
                "injury_status": "",
            }
        )
    return pd.DataFrame(rows)


def _injury_parity_rosters() -> list[dict]:
    return [
        {"roster_id": 1, "owner_id": "u1", "players": [f"h{i}" for i in range(1, 11)], "settings": {"wins": 0, "losses": 0, "ties": 0}},
        {"roster_id": 2, "owner_id": "u2", "players": [f"r{i}" for i in range(1, 11)], "settings": {"wins": 0, "losses": 0, "ties": 0}},
    ]


def _injury_parity_adapter(rosters: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(
        get_rosters=lambda _league: rosters,
        get_users=lambda _league: [
            {"user_id": "u1", "display_name": "Powerhouse"},
            {"user_id": "u2", "display_name": "Rebuilder"},
        ],
        get_league=lambda _league: {"season": 2026, "settings": {"draft_rounds": 4, "leg": 0, "playoff_week_start": 15}},
        get_traded_picks=lambda _league: [],
    )


def _merge_roster_health(frame: pd.DataFrame, health_metrics: pd.DataFrame) -> pd.DataFrame:
    """Same shape of merge both services/mobile_api_service.py's
    get_league_team_rankings and app.py's cached_league_intelligence_frame
    now do: drop any pre-existing (neutral-default) health columns, then
    left-merge the real per-roster health frame on roster_id."""

    merge_cols = [column for column in health_metrics.columns if column != "roster_id"]
    merged = frame.drop(columns=[column for column in merge_cols if column in frame.columns], errors="ignore").copy()
    merged["__roster_id_key__"] = pd.to_numeric(merged["roster_id"], errors="coerce")
    health = health_metrics.copy()
    health["__roster_id_key__"] = pd.to_numeric(health["roster_id"], errors="coerce")
    merged = merged.merge(
        health.drop(columns=["roster_id"]), on="__roster_id_key__", how="left"
    ).drop(columns="__roster_id_key__")
    return merged


def test_mobile_and_web_archetypes_match_on_real_injury_inputs_and_differ_from_the_old_neutral_default():
    players = _injury_parity_players()
    rosters = _injury_parity_rosters()
    adapter = _injury_parity_adapter(rosters)

    # Real per-roster health pass (modules.league_rankings.
    # build_roster_health_metrics_frame) -- the exact function both
    # services/mobile_api_service.py and app.py now call.
    with patch("modules.sleeper.get_rosters", return_value=rosters):
        health_metrics = league_rankings.build_roster_health_metrics_frame(
            players, "league-parity", score_field="dynasty_score"
        )
    assert not health_metrics.empty
    powerhouse_health = health_metrics.set_index("roster_id").loc[1]
    # The two IR starters must register as real injury weight, not a
    # neutral default -- this is exactly what _assign_team_archetype's
    # Juggernaut gate (injury_burden < 4) and refine_team_directions's
    # health_strength input read.
    assert powerhouse_health["injury_burden"] >= 4
    assert powerhouse_health["injured_starters"] == 2
    assert powerhouse_health["impact_tier_starters"] >= 3

    # Mobile's base frame: the cheap, health-free rankings frame
    # build_league_rankings_frame_cached wraps.
    mobile_base = league_rankings.build_league_rankings_frame(
        players, "league-parity", score_field="dynasty_score", adapter=adapter
    )

    # Web's base frame: build_league_summary_and_draft_capital +
    # build_league_display_frame(include_picks=True) + add_league_detail_ranks
    # -- the exact chain app.py's cached_league_core_context runs to produce
    # the frame it feeds into cached_league_intelligence_frame as df_display.
    with patch("modules.team_eval.get_league_roster_profiles", return_value={}):
        df_summary, draft_capital_summary = league_rankings.build_league_summary_and_draft_capital(
            players, "league-parity", score_field="dynasty_score", adapter=adapter
        )
    web_base = league_rankings.add_league_detail_ranks(
        league_rankings.build_league_display_frame(df_summary, draft_capital_summary, include_picks=True)
    )

    mobile_frame = team_eval.refine_team_directions(_merge_roster_health(mobile_base, health_metrics))
    web_frame = team_eval.refine_team_directions(_merge_roster_health(web_base, health_metrics))

    mobile_by_roster = mobile_frame.set_index("roster_id")
    web_by_roster = web_frame.set_index("roster_id")
    for roster_id in (1, 2):
        assert mobile_by_roster.loc[roster_id, "strategy"] == web_by_roster.loc[roster_id, "strategy"]
        assert mobile_by_roster.loc[roster_id, "archetype_label"] == web_by_roster.loc[roster_id, "archetype_label"]
        assert (
            mobile_by_roster.loc[roster_id, "archetype_explanation"]
            == web_by_roster.loc[roster_id, "archetype_explanation"]
        )

    # And the fix must actually matter: classifying the same roster WITHOUT
    # the real health merge (the old mobile behavior, running
    # refine_team_directions straight on the cheap frame) lands on a
    # different archetype for the injured powerhouse roster -- otherwise
    # this would just be confirming two paths agree on a label the injury
    # data never affected.
    old_mobile_behavior = team_eval.refine_team_directions(mobile_base.copy())
    assert (
        old_mobile_behavior.set_index("roster_id").loc[1, "archetype_label"]
        != mobile_by_roster.loc[1, "archetype_label"]
    )

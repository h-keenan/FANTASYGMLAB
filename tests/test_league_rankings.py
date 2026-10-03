"""Direct unit tests for modules/league_rankings.py — the pure-pandas
port of app.py's Power Rank / Franchise Rank / Draft Capital Rank chain.
Exercised here without the Sleeper/adapter mocking test_mobile_api_service.py
needs for the full endpoint, since these functions take plain DataFrames.
"""

from __future__ import annotations

import threading
import time

import pandas as pd

from modules import league_rankings, league_value_settings, player_eligibility, rankings, sleeper


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

    functools.lru_cache alone does not guarantee this: its internal lock
    only protects the cache dict during lookup/insert, not the wrapped
    call itself, so N threads that all miss before any of them finishes
    would otherwise each independently redo the real (here: stubbed, slow)
    build_league_rankings_frame pass. build_league_rankings_frame_cached's
    per-key lock (_league_rankings_lock_for) is what actually prevents
    that."""

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
    league_rankings._build_league_rankings_frame_cached.cache_clear()

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
    """Same single-flight guarantee as the rankings-frame cache above, for
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
    league_rankings._build_league_summary_and_draft_capital_cached.cache_clear()

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

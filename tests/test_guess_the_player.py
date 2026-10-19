"""modules.guess_the_player — "surprising" week selection, stat-line
formatting, and distractor plausibility. Pure-logic tests; no FastAPI,
Supabase, or network involved (see tests/test_mobile_api_service.py for the
endpoint-level contract)."""

from __future__ import annotations

import pandas as pd

from modules import guess_the_player as gtp


def _weeks(values: list[float], *, rush_attempts: float | None = 10.0) -> list[dict]:
    rows = []
    for index, value in enumerate(values):
        row = {"week": index + 1, "games_played": 1, "fantasy_points_ppr": value}
        if rush_attempts is not None:
            row["rush_attempts"] = rush_attempts
        rows.append(row)
    return rows


def _players_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"player_id": "1", "name": "Bench Runner", "position": "RB", "team": "KC", "player_tier": "depth"},
            {"player_id": "2", "name": "Other Back", "position": "RB", "team": "NYJ", "player_tier": "depth"},
            {"player_id": "3", "name": "Third Back", "position": "RB", "team": "DAL", "player_tier": "contributor"},
            {"player_id": "4", "name": "Star RB", "position": "RB", "team": "SF", "player_tier": "elite"},
            {"player_id": "5", "name": "Fourth Back", "position": "RB", "team": "ATL", "player_tier": "depth"},
        ]
    )


def _season_stats() -> dict[str, dict]:
    return {
        # A real breakout week (30 vs a ~3.2 baseline) from a depth-tier
        # player — the headline "surprising" case.
        "1": {
            "stats_season": 2025,
            "ppg": 4.0,
            "fantasy_points_ppr": 24.0,
            "games_played": 6,
            "weekly": _weeks([3, 4, 3, 2, 30, 4]),
        },
        # Flat, unremarkable production — never a candidate.
        "2": {
            "stats_season": 2025,
            "ppg": 3.5,
            "fantasy_points_ppr": 21.0,
            "games_played": 6,
            "weekly": _weeks([3, 4, 3, 4, 3, 4]),
        },
        "3": {
            "stats_season": 2025,
            "ppg": 4.5,
            "fantasy_points_ppr": 27.0,
            "games_played": 6,
            "weekly": _weeks([4, 5, 4, 5, 4, 5]),
        },
        # Elite tier, consistently great — must NEVER be selected even
        # though 22 is its own high point; it isn't "low-profile."
        "4": {
            "stats_season": 2025,
            "ppg": 20.0,
            "fantasy_points_ppr": 120.0,
            "games_played": 6,
            "weekly": _weeks([18, 22, 20, 19, 21, 20]),
        },
        "5": {
            "stats_season": 2025,
            "ppg": 3.0,
            "fantasy_points_ppr": 18.0,
            "games_played": 6,
            "weekly": _weeks([3, 3, 3, 3, 3, 3]),
        },
    }


def test_find_surprise_candidates_flags_the_real_breakout_week():
    players_by_id = {row["player_id"]: row for row in _players_frame().to_dict("records")}
    candidates = gtp.find_surprise_candidates(_season_stats(), players_by_id)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["player_id"] == "1"
    assert candidate["week"] == 5
    assert candidate["actual_fantasy_points_ppr"] == 30.0
    assert candidate["surprise_ratio"] > gtp.MIN_SURPRISE_RATIO


def test_find_surprise_candidates_excludes_elite_tier_even_with_a_good_week():
    players_by_id = {row["player_id"]: row for row in _players_frame().to_dict("records")}
    candidates = gtp.find_surprise_candidates(_season_stats(), players_by_id)

    assert all(candidate["player_id"] != "4" for candidate in candidates)


def test_find_surprise_candidates_requires_minimum_usable_weeks():
    players_by_id = {row["player_id"]: row for row in _players_frame().to_dict("records")}
    thin_stats = {
        "1": {
            "stats_season": 2025,
            "weekly": _weeks([3, 30]),  # only 2 usable weeks, below MIN_USABLE_WEEKS
        }
    }
    assert gtp.find_surprise_candidates(thin_stats, players_by_id) == []


def test_stat_line_for_week_never_fabricates_yards_or_tds():
    week = {"week": 5, "targets": 11.0, "receptions": 9.0, "fantasy_points_ppr": 30.0, "snap_share": 0.8}
    line = gtp.stat_line_for_week(week)
    labels = {item["label"] for item in line}

    assert labels == {"Targets", "Receptions"}
    # The weekly cache genuinely never retains yards/TDs (see module
    # docstring) — this must never silently invent them.
    assert "Receiving Yards" not in labels
    assert "Touchdowns" not in labels
    assert {item["value"] for item in line} == {11, 9}


def test_stat_line_for_week_omits_zero_and_missing_fields():
    week = {"week": 1, "pass_attempts": 0, "rush_attempts": None, "targets": 4.0}
    line = gtp.stat_line_for_week(week)
    assert line == [{"label": "Targets", "value": 4}]


def test_build_distractor_options_excludes_the_real_answer():
    players_df = _players_frame()
    options = gtp.build_distractor_options(
        players_df,
        exclude_player_id="1",
        position="RB",
        season_stats=_season_stats(),
        target_ppg=4.0,
        seed="2026-10-19",
    )
    ids = [option["player_id"] for option in options]
    assert "1" not in ids
    assert len(ids) == gtp.DISTRACTOR_COUNT
    assert len(set(ids)) == len(ids)


def test_build_distractor_options_prefers_similar_production_level():
    players_df = _players_frame()
    # Only ask for 1 option among {2 (ppg 3.5), 3 (ppg 4.5), 4 (ppg 20.0), 5 (ppg 3.0)}
    # against a target of 4.0 — the closest real player (not the far-off
    # elite outlier) should win.
    options = gtp.build_distractor_options(
        players_df,
        exclude_player_id="1",
        position="RB",
        season_stats=_season_stats(),
        target_ppg=4.0,
        count=1,
        seed="fixed-seed",
    )
    assert len(options) == 1
    assert options[0]["player_id"] != "4"


def test_build_distractor_options_scopes_to_same_position():
    players_df = pd.concat(
        [
            _players_frame(),
            pd.DataFrame([{"player_id": "9", "name": "Some WR", "position": "WR", "team": "MIA", "player_tier": "depth"}]),
        ],
        ignore_index=True,
    )
    options = gtp.build_distractor_options(
        players_df,
        exclude_player_id="1",
        position="RB",
        season_stats=_season_stats(),
        target_ppg=4.0,
        seed="2026-10-19",
    )
    assert all(option["player_id"] != "9" for option in options)


def test_compute_pick_id_is_stable_and_identity_scoped():
    first = gtp.compute_pick_id(2025, "1", 5)
    same = gtp.compute_pick_id(2025, "1", 5)
    different_week = gtp.compute_pick_id(2025, "1", 6)
    assert first == same
    assert first != different_week


def test_select_daily_candidate_is_deterministic_for_the_same_seed():
    candidates = gtp.find_surprise_candidates(
        _season_stats(), {row["player_id"]: row for row in _players_frame().to_dict("records")}
    )
    first = gtp.select_daily_candidate(candidates, seed="2026-10-19")
    second = gtp.select_daily_candidate(candidates, seed="2026-10-19")
    assert first == second


def test_select_daily_candidate_returns_none_when_no_candidates():
    assert gtp.select_daily_candidate([], seed="2026-10-19") is None


def test_build_daily_pick_hides_nothing_fabricated_and_includes_real_answer():
    pick = gtp.build_daily_pick(_players_frame(), _season_stats(), seed="2026-10-19")

    assert pick is not None
    assert pick["player_id"] == "1"
    assert pick["name"] == "Bench Runner"
    assert pick["team"] == "KC"
    assert pick["tier"] == "depth"
    assert pick["stat_line"]  # a real, non-empty stat line
    option_ids = {option["player_id"] for option in pick["options"]}
    assert pick["player_id"] in option_ids
    assert len(pick["options"]) == gtp.DISTRACTOR_COUNT + 1
    assert len(option_ids) == len(pick["options"])  # no duplicate options


def test_build_daily_pick_returns_none_when_no_surprise_exists():
    flat_stats = {
        "1": {
            "stats_season": 2025,
            "weekly": _weeks([3, 4, 3, 4, 3, 4]),
        }
    }
    assert gtp.build_daily_pick(_players_frame(), flat_stats, seed="2026-10-19") is None


def test_build_daily_pick_returns_none_on_empty_inputs():
    assert gtp.build_daily_pick(pd.DataFrame(), {}, seed="2026-10-19") is None
    assert gtp.build_daily_pick(_players_frame(), {}, seed="2026-10-19") is None

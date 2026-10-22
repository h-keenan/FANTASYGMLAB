"""A game a player PLAYED and scored 0 in is a real 0, not a missing week.

Sleeper omits every zero-valued stat key from its weekly payload, including
``pts_ppr``. The participation signal that tells a played 0 apart from a
did-not-play week is Sleeper's ``gp`` (kept as ``games_played``); see
``modules.sleeper.week_row_played`` for why it was chosen over snaps.

The raw rows below are trimmed real Sleeper 2024 week 5 lines: Christian
McCaffrey (on IR, no ``gp``) and a played, zero-point receiver line.

Pure logic, no network, no real data/ cache reads or writes.
"""

from __future__ import annotations

import json

import pytest

from modules import player_projections, rankings, sleeper

# Christian McCaffrey, 2024 week 5 (on IR): no gp, no snaps, no points.
DNP_RAW = {"gms_active": 1.0, "pos_rank_ppr": 999.0}
# Inactive on a team that played: team snaps only, no gp.
INACTIVE_RAW = {"gms_active": 1.0, "tm_off_snp": 62.0}
# Played 41 offensive snaps, no target, no points: Sleeper sends no pts_ppr.
PLAYED_ZERO_RAW = {"gms_active": 1.0, "gp": 1.0, "off_snp": 41.0, "tm_off_snp": 66.0}
SCORED_RAW = {"gp": 1.0, "rec_tgt": 9.0, "rec": 7.0, "off_snp": 60.0, "tm_off_snp": 66.0,
              "pts_ppr": 18.4, "pts_half_ppr": 14.9, "pts_std": 11.4}


def test_participation_signal_is_games_played():
    assert sleeper.week_row_played({"week": 1, "games_played": 1})
    assert not sleeper.week_row_played({"week": 1, "snap_share": 0.0})
    assert not sleeper.week_row_played({"week": 1})
    assert not sleeper.week_row_played(None)


def test_points_reader_separates_played_zero_from_dnp():
    assert sleeper.week_row_fantasy_points_ppr({"week": 1, "fantasy_points_ppr": 12.5}) == 12.5
    assert sleeper.week_row_fantasy_points_ppr({"week": 1, "fantasy_points_ppr": -0.7}) == -0.7
    assert sleeper.week_row_fantasy_points_ppr({"week": 1, "games_played": 1, "snap_share": 0.6}) == 0.0
    assert sleeper.week_row_fantasy_points_ppr({"week": 1, "snap_share": 0.0}) is None


def test_extraction_writes_a_real_zero_for_a_played_week_only():
    played = sleeper._extract_week_observation(5, PLAYED_ZERO_RAW)
    assert played["games_played"] == 1
    assert played["fantasy_points_ppr"] == 0.0
    assert played["fantasy_points_half_ppr"] == 0.0
    assert played["fantasy_points_standard"] == 0.0

    inactive = sleeper._extract_week_observation(5, INACTIVE_RAW)
    assert inactive is not None and "fantasy_points_ppr" not in inactive
    assert sleeper._extract_week_observation(5, DNP_RAW) is None

    scored = sleeper._extract_week_observation(5, SCORED_RAW)
    assert scored["fantasy_points_ppr"] == 18.4


def test_season_aggregate_keeps_the_zero_week_and_ppg_unchanged():
    aggregated = sleeper._aggregate_player_week_stats(
        [(4, {"p": SCORED_RAW}), (5, {"p": PLAYED_ZERO_RAW}), (6, {"p": DNP_RAW})], 2024
    )
    record = aggregated["p"]
    assert [row["week"] for row in record["weekly"]] == [4, 5]
    assert [row["fantasy_points_ppr"] for row in record["weekly"]] == [18.4, 0.0]
    # Season totals already divided by gp; the zero game was always counted there.
    assert record["games_played"] == 2
    assert record["ppg"] == pytest.approx(9.2)


def _old_cache(*, with_box_scores: bool) -> dict:
    played = {"week": 5, "games_played": 1, "snap_share": 0.62}
    other = {"week": 4, "games_played": 1, "fantasy_points_ppr": 18.4}
    if with_box_scores:
        other["fantasy_points_half_ppr"] = 14.9
    dnp = {"week": 6, "snap_share": 0.0}
    return {"p": {"stats_season": 2024, "weekly": [other, played, dnp]}}


def test_load_backfills_an_old_cache_without_faking_box_scores(tmp_path, monkeypatch):
    template = str(tmp_path / "sleeper_player_stats_{season}.json")
    monkeypatch.setattr(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", template)
    (tmp_path / "sleeper_player_stats_2024.json").write_text(json.dumps(_old_cache(with_box_scores=False)))

    rows = sleeper.cached_season_player_weekly("p", 2024)
    by_week = {row["week"]: row for row in rows}
    assert by_week[5]["fantasy_points_ppr"] == 0.0
    assert "fantasy_points_ppr" not in by_week[6]
    # A pre-box-score cache must still read as one.
    assert "fantasy_points_half_ppr" not in by_week[5]

    loaded = sleeper.backfill_played_zero_points(_old_cache(with_box_scores=False))
    assert not sleeper.season_stats_cache_has_box_scores(loaded)


def test_load_backfills_box_score_points_on_a_box_score_cache():
    loaded = sleeper.backfill_played_zero_points(_old_cache(with_box_scores=True))
    played = loaded["p"]["weekly"][1]
    assert played["fantasy_points_ppr"] == 0.0
    assert played["fantasy_points_half_ppr"] == 0.0
    assert played["fantasy_points_standard"] == 0.0
    assert "fantasy_points_ppr" not in loaded["p"]["weekly"][2]


def _rows(*points_or_dnp):
    rows = []
    for week, value in enumerate(points_or_dnp, start=1):
        if value == "DNP":
            rows.append({"week": week, "snap_share": 0.0})
        elif value is None:
            rows.append({"week": week, "games_played": 1, "snap_share": 0.5})
        else:
            rows.append({"week": week, "games_played": 1, "fantasy_points_ppr": float(value)})
    return rows


def test_recent_trend_counts_a_played_zero_and_skips_a_dnp():
    rows = _rows(12.0, None, 12.0, "DNP")
    trend = player_projections._player_recent_trend(rows, upto_week=4)
    assert trend["games_played"] == 3
    assert trend["weeks_used"] == [1, 2, 3]
    assert trend["simple_avg_ppr"] == pytest.approx(8.0)


def test_most_recent_played_week_includes_a_zero_point_game():
    rows = _rows(12.0, 9.0, None, "DNP")
    assert player_projections._most_recent_played_week(rows, before_week=6) == 3


def test_weekly_usage_rate_is_zero_for_a_played_week_with_no_touches():
    played_no_targets = {"week": 3, "games_played": 1, "snap_share": 0.4}
    assert rankings.weekly_usage_rate("WR", played_no_targets) == 0.0
    assert rankings.weekly_usage_rate("RB", played_no_targets) == 0.0
    assert rankings.weekly_usage_rate("QB", played_no_targets) == 0.0
    # Not a played week at all: still no usage reading.
    assert rankings.weekly_usage_rate("WR", {"week": 3, "snap_share": 0.0}) is None


def test_a_real_role_collapse_now_reads_as_cooling():
    # Eight targets a game for five weeks, then three games played with no
    # target at all (Sleeper omits rec_tgt) — a real role collapse.
    weekly = [{"week": w, "games_played": 1, "targets": 8, "fantasy_points_ppr": 12.0} for w in range(1, 6)]
    weekly += [{"week": w, "games_played": 1, "snap_share": 0.2} for w in range(6, 9)]
    features = rankings.compute_recency_features("WR", weekly)
    assert features["recency_trend"] < -0.12
    assert features["recency_confidence"] > 0


def test_week_result_stat_line_reports_a_played_zero_as_zero_points():
    from modules import weekly_box_scores

    row = {"week": 5, "games_played": 1, "snap_share": 0.62}
    line = weekly_box_scores._stat_line(row, has_box_scores=True)
    assert line["fantasy_points_ppr"] == 0.0
    assert line["fantasy_points_half_ppr"] == 0.0
    assert line["fantasy_points_standard"] == 0.0
    # Box-score counts keep the documented "null when Sleeper reported nothing".
    assert line["box_score"]["receptions"] is None

    old_cache_line = weekly_box_scores._stat_line(row, has_box_scores=False)
    assert old_cache_line["fantasy_points_ppr"] == 0.0
    assert old_cache_line["fantasy_points_half_ppr"] is None

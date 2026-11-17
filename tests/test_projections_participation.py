"""v3.3 participation prior, future-game durability and calibrated game-time probabilities
(docs/audits/2026-11-projections-backtest.md)."""

import numpy as np
import pandas as pd
import pytest

from modules import injury_status, nfl_schedule
from modules import player_projections as pp


def _games(played_through: int, weeks: int = 12) -> pd.DataFrame:
    rows = []
    for week in range(1, weeks + 1):
        done = week <= played_through
        home, away = ("AAA", "BBB") if week % 2 else ("BBB", "AAA")
        rows.append({
            "season": 2099, "game_type": "REG", "week": week, "home_team": home, "away_team": away,
            "home_score": 20.0 if done else np.nan, "away_score": 17.0 if done else np.nan,
        })
    return pd.DataFrame(rows)


def _rows(weeks, points=12.0):
    return [{"week": w, "games_played": 1, "fantasy_points_ppr": points, "targets": 8} for w in weeks]


def _project(monkeypatch, *, played_through, week, weeks_played, stats_through, designation="", position="WR"):
    games = _games(played_through)
    monkeypatch.setattr(nfl_schedule, "load_games", lambda **_: games)
    players = {"p": {"position": position, "team": "AAA", "status": "Active", "injury_status": designation}}
    return pp.project_player_week(
        "p", week, 2099, players=players, player_weekly_rows=_rows(weeks_played), defense_strength={},
        team_qb_quality={}, weekly_stats={}, prior_weekly_rows=[], stats_through_week=stats_through,
    )


def test_regular_is_untouched(monkeypatch):
    out = _project(monkeypatch, played_through=8, week=9, weeks_played=range(1, 9), stats_through=8)
    assert out["basis"]["participation"] == {"multiplier": 1.0, "applied": False, "missed": 0, "window": 4}


def test_missed_all_recent_games_is_discounted_and_range_opens_to_zero(monkeypatch):
    regular = _project(monkeypatch, played_through=8, week=9, weeks_played=range(1, 9), stats_through=8)
    # played weeks 1-4 then missed 5-8 (no designation): the share missed is 1.0
    gone = _project(monkeypatch, played_through=8, week=9, weeks_played=range(1, 5), stats_through=8)
    part = gone["basis"]["participation"]
    assert part["applied"] and part["missed"] == 4 and part["multiplier"] == pytest.approx(0.331)
    assert gone["point_estimate"] < 0.45 * regular["point_estimate"]
    assert gone["low"] == 0.0 and gone["confidence"] == "low"


def test_partial_miss_uses_the_bucket(monkeypatch):
    out = _project(monkeypatch, played_through=8, week=9, weeks_played=[1, 2, 3, 4, 5, 6, 8], stats_through=8)
    assert out["basis"]["participation"]["missed"] == 1
    assert out["basis"]["participation"]["multiplier"] == pytest.approx(0.89)  # 1 of 4 = 0.25 <= 1/3


def test_unverified_stats_never_read_as_missed_games(monkeypatch):
    # The weekly stats for weeks 7-8 are not loaded yet: no evidence, so no discount (a stale cache must not
    # make every player look like he missed last week).
    stale = _project(monkeypatch, played_through=8, week=9, weeks_played=range(1, 7), stats_through=6)
    assert stale["basis"]["participation"]["applied"] is False
    unknown = _project(monkeypatch, played_through=8, week=9, weeks_played=range(1, 5), stats_through=None)
    assert unknown["basis"]["participation"]["applied"] is False


def test_injury_designation_keeps_the_availability_layer_only(monkeypatch):
    out = _project(monkeypatch, played_through=8, week=9, weeks_played=range(1, 5), stats_through=8, designation="Questionable")
    assert out["basis"]["participation"]["applied"] is False
    assert out["basis"]["availability"]["applied"] is True


def test_kickers_are_not_adjusted(monkeypatch):
    out = _project(monkeypatch, played_through=8, week=9, weeks_played=range(1, 5), stats_through=8, position="K")
    assert out["basis"]["participation"]["applied"] is False


def test_future_games_carry_a_durability_discount_but_the_next_game_does_not(monkeypatch):
    # Games 1-4 played; projecting weeks 5 (next), 7 and 11 (two and six games after the next).
    kwargs = dict(played_through=4, weeks_played=range(1, 5), stats_through=4)
    nxt = _project(monkeypatch, week=5, **kwargs)
    mid = _project(monkeypatch, week=7, **kwargs)
    far = _project(monkeypatch, week=11, **kwargs)
    assert nxt["basis"]["future_game_durability"] == 1.0
    assert mid["basis"]["future_game_durability"] == pytest.approx(0.9 + 0.0, abs=0.06)
    assert far["basis"]["future_game_durability"] < mid["basis"]["future_game_durability"] < 1.0
    assert far["point_estimate"] < mid["point_estimate"] < nxt["point_estimate"]
    assert far["low"] <= far["point_estimate"] <= far["high"]


def test_durability_curve_is_monotone_and_position_specific():
    for position in ("QB", "RB", "WR", "TE"):
        values = [pp._durability_multiplier(position, k) for k in range(0, 17)]
        assert values[0] == 1.0 and values == sorted(values, reverse=True)
        assert values[-1] > 0.65
    assert pp._durability_multiplier("QB", 12) < pp._durability_multiplier("WR", 12)
    assert pp._durability_multiplier("K", 6) < 1.0  # v3.4: kickers get cut (round 2)


def test_game_time_probabilities_are_calibrated():
    q = injury_status.classify("Active", "Questionable")
    d = injury_status.classify("Active", "Doubtful")
    assert q.p_play == pytest.approx(0.70) and q.row.calibrated
    assert d.p_play == pytest.approx(0.02) and d.row.calibrated
    # labels with no measured history keep their old prior
    assert injury_status.classify("Active", "Day-to-day").p_play == pytest.approx(0.85)
    assert pp._V2_QUESTIONABLE_PLAYS_FACTOR == pytest.approx(0.95)


def test_complete_stats_through_week_reads_the_manifest(tmp_path, monkeypatch):
    import json

    from modules import sleeper

    template = str(tmp_path / "stats_{season}.json")
    monkeypatch.setattr(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", template)
    sleeper._COMPLETE_THROUGH_CACHE.clear()
    assert sleeper.complete_stats_through_week(2099) is None  # no manifest: cannot verify
    counts = {"1": 300, "2": 310, "3": 40, "4": 0}
    manifest = {"schema": sleeper.STATS_MANIFEST_SCHEMA, "season": 2099, "built_at": 1.0, "weeks_ok": [1, 2, 3, 4], "weeks_failed": [], "week_played_counts": counts}
    (tmp_path / "stats_2099.weeks.json").write_text(json.dumps(manifest))
    assert sleeper.complete_stats_through_week(2099) == 2  # week 3 is truncated, week 4 unplayed
    assert sleeper.stats_built_at(2099) == 1.0
    manifest["weeks_ok"] = [1, 3]
    manifest["week_played_counts"] = {"1": 300, "3": 300}
    (tmp_path / "stats_2099.weeks.json").write_text(json.dumps(manifest))
    sleeper._COMPLETE_THROUGH_CACHE.clear()
    assert sleeper.complete_stats_through_week(2099) == 1  # week 2 never obtained


def test_games_that_finished_after_the_stats_build_are_not_evidence():
    # Four completed games; the stats cache was built after games 1-2 but before games 3-4 finished: the player's
    # missing rows for 3-4 prove nothing, so only games 1-2 count (he played both -> no discount).
    sched = [{"week": w, "played": True, "bye": False, "kickoff_at": f"2099-10-{w:02d}T17:00:00Z"} for w in range(1, 5)]
    built = pd.Timestamp("2099-10-02T23:00:00Z").timestamp()  # after game 2 ended (17:00 + 4h), before game 3
    rows = _rows([1, 2])
    player = {"status": "Active", "injury_status": ""}
    out = pp._participation_adjustment(player, "WR", sched, rows, 5, 0, 4, built)
    assert out["window"] == 2 and out["missed"] == 0 and not out["applied"]
    # built after everything: games 3-4 are real misses
    late = pd.Timestamp("2099-10-09T00:00:00Z").timestamp()
    out = pp._participation_adjustment(player, "WR", sched, rows, 5, 0, 4, late)
    assert out["window"] == 4 and out["missed"] == 2 and out["multiplier"] == pytest.approx(0.758)
    # an unknown build time cannot rule anything out
    assert pp._participation_adjustment(player, "WR", sched, rows, 5, 0, 4, None)["missed"] == 2

"""Round 2 (P1 fixes) of the projections audit (docs/audits/2026-11-projections-backtest.md): mean-calibrated estimate,
new-team prior, kicker durability, high-end trim, confirmed-scratch fallback, draft-capital fallback anchors, stadium-wind
cells."""

import numpy as np
import pandas as pd
import pytest

from modules import draft_capital, game_weather as gw, nfl_schedule, nflverse_contracts
from modules import matchup_win_probability as mwp
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


def _project(monkeypatch, *, played_through=4, week=5, weeks_played=range(1, 5), stats_through=4, position="WR", depth=None,
             team_history=None, inactive_weeks=None, designation=""):
    games = _games(played_through)
    monkeypatch.setattr(nfl_schedule, "load_games", lambda **_: games)
    player = {"position": position, "team": "AAA", "status": "Active", "injury_status": designation}
    if depth is not None:
        player["depth_chart_order"] = depth
    return pp.project_player_week(
        "p", week, 2099, players={"p": player}, player_weekly_rows=_rows(weeks_played), defense_strength={}, team_qb_quality={},
        weekly_stats={}, prior_weekly_rows=[], stats_through_week=stats_through, team_history=team_history, inactive_weeks=inactive_weeks,
    )


# --- mean-calibrated estimate ---------------------------------------------------------------------------------


def test_mean_estimate_is_point_times_position_lift(monkeypatch):
    for position, lift in (("WR", 1.07), ("RB", 1.05), ("TE", 1.15), ("QB", 1.02)):
        out = _project(monkeypatch, position=position)
        assert out["basis"]["mean_lift"] == pytest.approx(lift)
        assert out["mean_estimate"] == pytest.approx(out["point_estimate"] * lift, abs=0.11)
        assert out["mean_estimate"] >= out["point_estimate"]
    assert pp.MEAN_LIFT["K"] == 1.0


def test_baseline_weekly_points_exposes_mean_ppg_without_changing_ppg():
    rows = {"p": _rows(range(1, 7), points=10.0)}
    out = pp.baseline_weekly_points([{"player_id": "p", "position": "TE"}], season=2099, weekly_by_player=rows, as_of_week=7, prior_weekly_by_player={})
    assert out["p"]["mean_ppg"] == pytest.approx(out["p"]["ppg"] * 1.15, abs=0.01)


# --- new-team prior --------------------------------------------------------------------------------------------


def test_new_team_prior_cut_follows_role_clarity_and_decays_over_games(monkeypatch):
    moved = ["ZZZ"] * 8
    base = _project(monkeypatch, team_history=None, depth=2)
    starter = _project(monkeypatch, team_history=moved, depth=1)["basis"]["new_team"]
    backup = _project(monkeypatch, team_history=moved, depth=2)["basis"]["new_team"]
    unknown = _project(monkeypatch, team_history=moved)["basis"]["new_team"]
    assert starter["multiplier"] == pytest.approx(0.92) and starter["games_with_team"] == 0
    assert backup["multiplier"] == pytest.approx(0.64)
    assert starter["multiplier"] > unknown["multiplier"] > backup["multiplier"]
    after_one = _project(monkeypatch, team_history=moved + ["AAA"], depth=2)["basis"]["new_team"]
    after_two = _project(monkeypatch, team_history=moved + ["AAA", "AAA"], depth=2)["basis"]["new_team"]
    assert after_one["multiplier"] == pytest.approx(1 - 0.36 * 0.3) and after_one["games_with_team"] == 1
    assert after_two["applied"] is False and after_two["multiplier"] == pytest.approx(1.0)
    cut = _project(monkeypatch, team_history=moved, depth=2)
    assert cut["point_estimate"] == pytest.approx(0.64 * base["point_estimate"], abs=0.06)
    assert cut["low"] == 0.0 and cut["confidence"] == "low"  # a moved backup may not play at all


def test_new_team_prior_is_off_without_history_for_qbs_and_non_movers(monkeypatch):
    assert _project(monkeypatch, team_history=None)["basis"]["new_team"]["applied"] is False
    assert _project(monkeypatch, team_history=[])["basis"]["new_team"]["applied"] is False
    assert _project(monkeypatch, team_history=["AAA"] * 6)["basis"]["new_team"]["applied"] is False
    assert _project(monkeypatch, team_history=[None, None])["basis"]["new_team"]["applied"] is False
    assert _project(monkeypatch, team_history=["ZZZ"] * 8, position="QB", depth=2)["basis"]["new_team"]["applied"] is False
    assert _project(monkeypatch, team_history=["ZZZ"] * 8, position="K")["basis"]["new_team"]["applied"] is False


def test_new_team_prior_does_not_stack_with_the_participation_prior(monkeypatch):
    # missed all of the team's last 4 games AND moved: the stronger of the two applies, not their product
    both = _project(monkeypatch, played_through=8, week=9, weeks_played=range(1, 5), stats_through=8, team_history=["ZZZ"] * 4, depth=2)
    part_only = _project(monkeypatch, played_through=8, week=9, weeks_played=range(1, 5), stats_through=8, depth=2)
    assert part_only["basis"]["participation"]["multiplier"] == pytest.approx(0.331)
    assert both["point_estimate"] == pytest.approx(part_only["point_estimate"])


def test_future_games_count_toward_games_with_the_new_team(monkeypatch):
    nxt = _project(monkeypatch, week=5, team_history=["ZZZ"] * 4, depth=2)["basis"]["new_team"]["multiplier"]
    third = _project(monkeypatch, week=7, team_history=["ZZZ"] * 4, depth=2)["basis"]["new_team"]["multiplier"]
    assert nxt == pytest.approx(0.64) and third == pytest.approx(1.0)  # two games later he has played for the new team


def test_team_history_for_player_reads_the_advanced_stats_files(monkeypatch):
    from modules import nflverse_advanced_stats as nas

    def weekly(sid, season, **_):
        rows = {2098: {1: {"team": "ZZZ"}, 2: {"team": "ZZZ"}}, 2099: {1: {"team": "AAA"}}}
        return {"available": True, "weeks": rows[season]} if season in rows else {"available": False}

    monkeypatch.setattr(nas, "weekly_for_sleeper_id", weekly)
    assert pp.team_history_for_player("p", 2099) == ["ZZZ", "ZZZ", "AAA"]
    monkeypatch.setattr(nas, "weekly_for_sleeper_id", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert pp.team_history_for_player("p", 2099) == []


# --- confirmed-scratch fallback (participation, secondary) ---------------------------------------------------------


def test_inactive_weeks_are_a_secondary_signal_only_when_stats_coverage_is_unknown(monkeypatch):
    kwargs = dict(played_through=8, week=9, weeks_played=range(1, 7), stats_through=None)  # weeks 7-8 missing, coverage unknown
    silent = _project(monkeypatch, **kwargs)
    assert silent["basis"]["participation"]["applied"] is False  # a stale cache is never read as "he missed games"
    listed = _project(monkeypatch, inactive_weeks=[7, 8], **kwargs)["basis"]["participation"]
    assert listed["applied"] and listed["missed"] == 2 and listed["window"] == 4 and listed["source"] == "sleeper_inactive_weeks"
    assert listed["multiplier"] == pytest.approx(0.758)
    one = _project(monkeypatch, inactive_weeks=[8], **kwargs)["basis"]["participation"]
    assert one["missed"] == 1 and one["multiplier"] == pytest.approx(0.89)
    # coverage known: the schedule rule is primary and the listed weeks add nothing (no double counting)
    primary = _project(monkeypatch, played_through=8, week=9, weeks_played=range(1, 7), stats_through=8, inactive_weeks=[7, 8])["basis"]["participation"]
    assert primary["missed"] == 2 and "source" not in primary
    # an injury designation keeps the availability layer only
    assert _project(monkeypatch, inactive_weeks=[7, 8], designation="Questionable", **kwargs)["basis"]["participation"]["applied"] is False


# --- kicker durability and high-end trim ---------------------------------------------------------------------------


def test_kickers_carry_a_durability_discount_for_future_games():
    values = [pp._durability_multiplier("K", k) for k in range(0, 17)]
    assert values[0] == 1.0 and values == sorted(values, reverse=True)
    assert 0.80 < values[-1] < 0.90
    assert pp._durability_multiplier("K", 12) > pp._durability_multiplier("QB", 12)  # kickers are cut, not hurt


def test_high_end_trim_only_narrows_low_estimates():
    assert pp._high_scale("WR", 0.4) == pytest.approx(0.30)
    assert pp._high_scale("QB", 1.0) == pytest.approx(0.25)
    assert pp._high_scale("WR", 12.0) == 1.0 and pp._high_scale("RB", 20.0) == 1.0 and pp._high_scale("K", 0.5) == 1.0
    assert all(pp._high_scale("RB", x / 2) <= 1.0 for x in range(0, 40))


def test_trimmed_band_keeps_the_point_estimate_inside(monkeypatch):
    out = _project(monkeypatch, weeks_played=[1, 2], position="RB", stats_through=4)
    assert out["low"] <= out["point_estimate"] <= out["high"]
    assert out["basis"]["model_version"].startswith("v3.4")


# --- win probability: mean basis and draft-capital anchors -------------------------------------------------------


def _starter(point, mean, position="WR", **extra):
    return {"position": position, "actual_points": None, "projection": {"status": "ok", "point_estimate": point, "mean_estimate": mean, "low": point - 4, "high": point + 4},
            **extra}


def test_win_probability_sums_the_mean_estimate_but_single_player_points_stay_point():
    team = [_starter(10.0, 11.0), _starter(8.0, 9.0)]
    result = mwp.compute_live_win_probability(team, [_starter(10.0, 10.0), _starter(8.0, 8.0)])
    assert result["my_projected_total"] == pytest.approx(20.0) and result["opponent_projected_total"] == pytest.approx(18.0)
    assert mwp.starter_expected_points(team[0]) == pytest.approx(10.0)  # start/sit number: the median-like estimate
    assert mwp.starter_expected_points(team[0], basis="mean") == pytest.approx(11.0)
    no_mean = {"position": "WR", "projection": {"status": "ok", "point_estimate": 7.0, "low": 3.0, "high": 11.0}}
    assert mwp.starter_expected_points(no_mean, basis="mean") == pytest.approx(7.0)  # older payloads fall back


def test_fallback_anchor_follows_draft_round_and_defaults_by_position():
    def anchor(position, **extra):
        mean, variance = mwp._fallback_distribution({"position": position, **extra})
        return mean, variance

    assert anchor("QB")[0] == 8.0  # was 12.0: no-history QBs scored 4.5-8 when they played
    assert anchor("RB")[0] == 4.5 and anchor("WR")[0] == 5.0 and anchor("TE")[0] == 3.5 and anchor("K")[0] == 7.0
    assert anchor("RB", draft_round=1)[0] == pytest.approx(11.5)
    assert anchor("WR", draft_round=1)[0] == pytest.approx(8.0)
    assert anchor("TE", draft_round=1)[0] == pytest.approx(8.0)
    assert anchor("RB", draft_round=2)[0] > anchor("RB", draft_round=5)[0] > anchor("RB", draft_round=0)[0]
    assert anchor("RB", draft_round=7) == anchor("RB", draft_round=4)  # rounds 4-7 share a row
    assert anchor("WR", draft_round=None)[0] == 5.0 and anchor("WR", draft_round="x")[0] == 5.0 and anchor("WR", draft_round=True)[0] == 5.0
    assert anchor("K", draft_round=1)[0] == 7.0  # no table for kickers
    assert mwp._fallback_distribution({"position": "DEF"}) is None
    assert mwp._fallback_distribution({"position": "RB", "projection": {"status": "bye_week"}}) is None


# --- draft capital lookup (disk cache only) -------------------------------------------------------------------------


def test_draft_round_lookup_is_cache_only_and_honest_about_ambiguity(tmp_path, monkeypatch):
    path = tmp_path / "contracts.csv"
    pd.DataFrame(
        [
            {"player": "Caleb Rookie", "position": "QB", "draft_round": 1.0},
            {"player": "Caleb Rookie", "position": "QB", "draft_round": 1.0},  # a second contract row, same player
            {"player": "Walk On", "position": "WR", "draft_round": np.nan},
            {"player": "Twin Name", "position": "RB", "draft_round": 2.0},
            {"player": "Twin Name", "position": "RB", "draft_round": 5.0},
        ]
    ).to_csv(path, index=False)
    monkeypatch.setattr(nflverse_contracts, "CONTRACTS_CACHE_PATH", str(path))
    draft_capital.clear_cache()
    assert draft_capital.draft_round_for("Caleb Rookie", "QB") == 1
    assert draft_capital.draft_round_for("Walk On", "wr") == 0  # a contracts row without a draft round: undrafted
    assert draft_capital.draft_round_for("Twin Name", "RB") is None  # two different rounds: ambiguous
    assert draft_capital.draft_round_for("Nobody Here", "QB") is None
    assert draft_capital.draft_round_for("Caleb Rookie", "WR") is None  # position must match
    assert draft_capital.draft_round_for("", "QB") is None
    monkeypatch.setattr(nflverse_contracts, "CONTRACTS_CACHE_PATH", str(tmp_path / "missing.csv"))
    draft_capital.clear_cache()
    assert draft_capital.draft_round_for("Caleb Rookie", "QB") is None  # never fetches


# --- stadium wind -------------------------------------------------------------------------------------------------


def _fc(wind):
    return {"wind_mph": wind, "precip_mm": 0.0, "temp_f": 60, "precip_prob_pct": 0}


def test_wind_cells_are_modest_and_rb_is_untouched():
    for pos in ("QB", "WR", "TE", "K"):
        assert gw.weather_adjustment(pos, _fc(17))["multiplier"] < 1.0
        assert gw.weather_adjustment(pos, _fc(10))["multiplier"] == 1.0
    assert gw.weather_adjustment("RB", _fc(30))["multiplier"] == 1.0
    # shrunk toward the previous table and capped: no wind cell moves a position by more than the total cap
    assert gw.weather_adjustment("QB", _fc(17))["multiplier"] == pytest.approx(0.985)
    assert gw.weather_adjustment("WR", _fc(22))["multiplier"] == pytest.approx(0.97)
    assert gw.weather_adjustment("TE", _fc(22))["multiplier"] == pytest.approx(1.0 - gw.MAX_TOTAL_REDUCTION)
    assert all(-gw.MAX_TOTAL_REDUCTION * 2 < v < 0 for table in gw.WEATHER_EFFECTS.values() for v in table.values())


def test_apply_weather_scales_the_mean_estimate_with_the_point_estimate(monkeypatch):
    from datetime import datetime, timezone
    from unittest.mock import MagicMock, patch

    monkeypatch.delenv("FANTASYDESK_WEATHER_DISABLED", raising=False)
    gw.clear_cache()
    now = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
    kickoff = datetime(2026, 11, 2, 18, 0, tzinfo=timezone.utc)
    hourly = {"time": [(now.replace(hour=0) + pd.Timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(24 * 8)]}
    n = len(hourly["time"])
    hourly.update({"temperature_2m": [60.0] * n, "wind_speed_10m": [25.0] * n, "wind_gusts_10m": [30.0] * n, "precipitation": [0.0] * n,
                   "precipitation_probability": [0] * n})
    response = MagicMock()
    response.json.return_value = {"hourly": hourly}
    response.raise_for_status.return_value = None
    summary = {"status": "ok", "point_estimate": 10.0, "mean_estimate": 10.7, "low": 4.0, "high": 18.0}
    with patch.object(gw.requests, "get", return_value=response):
        gw.prefetch_stadium_ids(["BUF00"])
        gw.wait_for_refreshes()
        out = gw.apply_weather(summary, position="WR", stadium_id="BUF00", kickoff_at=kickoff.isoformat(), now=now)
    assert out["weather"]["applied"] and out["weather"]["multiplier"] == pytest.approx(0.97)
    assert out["point_estimate"] == pytest.approx(9.7) and out["mean_estimate"] == pytest.approx(10.4)

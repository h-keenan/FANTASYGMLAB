"""The one team-need / surplus model, end to end on a synthetic 12-team league.

Regression for the scale bug: the retired ``roster_needs.classify_roster_rooms``
compared player values to thresholds written for a 0-100 scale (18 / 20 / 24 /
55) while the valued frame runs 0-11,000, so every player was "playable cover",
every young player a "core young asset", and a dynasty roster could not have a
need. These tests build league-wide universes whose values are the same
ranking at two different scales and require identical answers, and require the
rosters that are weak to be reported as weak.
"""

from __future__ import annotations

import pandas as pd
import pytest

from modules import model_status, nfl_schedule, roster_needs
from modules import roster_value_model as rvm
from modules.trade_analyzer_fit import build_team_needs_assessment, get_needed_positions, surplus_player_ids

SETTINGS = {
    "league_format": "Dynasty",
    "qb_format": "1QB",
    "qb_count": 1,
    "rb_count": 2,
    "wr_count": 3,
    "te_count": 1,
    "k_count": 0,
    "def_count": 0,
    "flex_count": 1,
    "regular_flex_count": 1,
    "superflex_count": 0,
    "starter_count": 7,
    "current_week": 8,
}
TEAMS = 12
# position -> (players in the universe, ppg of the best, ppg of the worst)
UNIVERSE = {"QB": (24, 25, 12), "RB": (60, 24, 3), "WR": (84, 22, 3), "TE": (30, 14, 2)}


@pytest.fixture(autouse=True)
def _byes(monkeypatch):
    monkeypatch.setattr(nfl_schedule, "team_bye_week", lambda team, season, **kw: 99)


def _row(pid, pos, value, ppg, *, age=26, status="Active", injury=""):
    return {
        "player_id": pid, "name": pid, "position": pos, "team": "T", "status": status, "injury_status": injury,
        "age": age, "years_exp": max(0, int(age) - 21), "value_score": value, "dynasty_score": value, "score": value,
        "ppg": ppg, "games_played": 7, "receptions": 0,
    }


def _priced(pid, pos, ppg, **kw):
    """A player priced exactly where the universe prices that PPG (value and
    points agree, the way a real valued frame does)."""

    n, top, bottom = UNIVERSE[pos]
    i = (top - ppg) * (n - 1) / (top - bottom)
    return _row(pid, pos, 9000 * (1 - i / n) + 200, ppg, **kw)


def _league(*, value_scale=1.0, mutate=None):
    """Twelve rosters drawn from one ranked universe: team ``t`` owns the
    ``t``-th best player of each tier, so team 0 is strongest everywhere and
    team 11 weakest. ``mutate(rosters, rows)`` edits the league before it is built."""

    rows: dict[str, dict] = {}
    by_pos: dict[str, list[str]] = {}
    for pos, (n, top, bottom) in UNIVERSE.items():
        by_pos[pos] = []
        for i in range(n):
            pid = f"{pos}{i}"
            rows[pid] = _row(pid, pos, (9000 * (1 - i / n) + 200) * value_scale, top - (top - bottom) * i / (n - 1))
            by_pos[pos].append(pid)
    take = {"QB": 2, "RB": 4, "WR": 5, "TE": 2}
    rosters = []
    for team in range(TEAMS):
        ids = [by_pos[pos][k * TEAMS + team] for pos, count in take.items() for k in range(count)]
        rosters.append({"roster_id": team + 1, "players": ids, "reserve": [], "taxi": []})
    if mutate:
        mutate(rosters, rows)
    owned = {pid for r in rosters for pid in r["players"]}
    # The rest of the universe is the free-agent pool; only rostered players matter here.
    frame = pd.DataFrame([row for pid, row in rows.items() if pid in owned])
    return frame, rosters


def _needs(frame, rosters):
    return rvm.league_needs(
        valued=frame, rosters=rosters, league={"total_rosters": TEAMS}, settings=SETTINGS, score_field="dynasty_score"
    )


def _tiers(result):
    return {p["position"]: p["tier"] for p in result["positions"]}


def test_weak_rosters_have_needs_and_the_strongest_does_not_on_a_0_to_11000_frame():
    frame, rosters = _league()
    assert frame["dynasty_score"].max() > 8000  # the real scale, not 0-100
    league = _needs(frame, rosters)

    best = build_team_needs_assessment(league.for_roster(1))
    worst = build_team_needs_assessment(league.for_roster(12))
    assert best.true_needs == ()
    assert set(worst.true_needs) >= {"RB", "WR"}
    # The retired policy answered "covered" for all twelve of these.
    with_need = [rid for rid in range(1, TEAMS + 1) if build_team_needs_assessment(league.for_roster(rid)).true_needs]
    assert len(with_need) >= 3


def test_needs_do_not_depend_on_the_value_scale():
    """The same league priced on a 0-100 scale and on the production 0-11,000 scale."""

    big = _needs(*_league(value_scale=1.0))
    small = _needs(*_league(value_scale=0.01))
    for roster_id in range(1, TEAMS + 1):
        assert _tiers(big.for_roster(roster_id)) == _tiers(small.for_roster(roster_id)), roster_id
        assert big.for_roster(roster_id)["needed_positions"] == small.for_roster(roster_id)["needed_positions"]


def test_a_roster_with_no_playable_qb_needs_a_qb_even_with_a_huge_young_asset_elsewhere():
    def mutate(rosters, rows):
        mine = rosters[3]
        mine["players"] = [p for p in mine["players"] if not p.startswith("QB")]
        rows["YOUNG"] = _row("YOUNG", "WR", 11000, 22, age=21)  # a 21-year-old worth 11,000
        mine["players"].append("YOUNG")

    league = _needs(*_league(mutate=mutate))
    assert "QB" in build_team_needs_assessment(league.for_roster(4)).true_needs


def test_surplus_players_are_beyond_starters_and_cover_and_good_enough_to_start_elsewhere():
    def mutate(rosters, rows):
        mine = rosters[5]  # a middle team stacked at WR
        for i, ppg in enumerate((17.4, 17.2, 17.0, 16.8)):
            rows[f"SPARE{i}"] = _priced(f"SPARE{i}", "WR", ppg)
            mine["players"].append(f"SPARE{i}")

    league = _needs(*_league(mutate=mutate))
    surplus = surplus_player_ids(league.for_roster(6))
    # Four WR starters (three plus the flex) and one cover are the top five by
    # points. Of the rest, the 16.8, 15.4 and 12.6 PPG receivers would still
    # start for a typical team's WR4 (12.5 PPG here); the 9.9 PPG WR is depth.
    assert set(surplus["WR"]) == {"SPARE3", "WR29", "WR41"}
    assert "WR53" not in surplus["WR"]
    # The weakest roster holds nothing beyond its starters and cover.
    assert surplus_player_ids(league.for_roster(12)) == {}


def test_a_taxi_stash_does_not_cover_a_starting_slot():
    def mutate(rosters, rows):
        mine = rosters[0]
        keep = [p for p in mine["players"] if not p.startswith("RB")]
        rows["TAXIRB1"] = _row("TAXIRB1", "RB", 5000, 20, age=22)
        rows["TAXIRB2"] = _row("TAXIRB2", "RB", 4900, 19, age=22)
        mine["players"] = keep + ["TAXIRB1", "TAXIRB2"]
        mine["taxi"] = ["TAXIRB1", "TAXIRB2"]

    league = _needs(*_league(mutate=mutate))
    rb = next(p for p in league.for_roster(1)["positions"] if p["position"] == "RB")
    assert rb["healthy_count"] == 0
    assert rb["tier"] == "primary"
    assert "RB" in build_team_needs_assessment(league.for_roster(1)).true_needs


def test_a_missing_result_is_reported_not_read_as_covered():
    frame, rosters = _league()
    league = _needs(frame, rosters)
    assert league.for_roster(999) is None
    assessment = build_team_needs_assessment(league.for_roster(999))
    assert assessment.true_needs == ()
    assert assessment.model_status["degraded"] is True
    assert model_status.codes(assessment.model_status) == ["need_model_unavailable"]
    assert all(p.data_quality == "missing" for p in assessment.positions)


def test_the_headline_names_the_weakest_room_instead_of_none():
    frame, rosters = _league()
    league = _needs(frame, rosters)
    worst = roster_needs.select_need_headline(build_team_needs_assessment(league.for_roster(12)))
    assert worst["category"] == "true_need"
    assert worst["value"] in {"QB", "RB", "WR", "TE"}
    best = roster_needs.select_need_headline(build_team_needs_assessment(league.for_roster(1)))
    assert best["category"] in {"balanced", "future_risk", "upgrade"}  # not a need


def test_get_needed_positions_is_true_needs_first_then_the_softer_signals():
    frame, rosters = _league()
    league = _needs(frame, rosters)
    assessment = build_team_needs_assessment(league.for_roster(12))
    strict = get_needed_positions(assessment, include_fallback=False)
    assert strict == list(assessment.true_needs)
    assert get_needed_positions(assessment)[: len(strict)] == strict


def test_league_needs_is_built_once_per_frame_and_rosters():
    frame, rosters = _league()
    assert _needs(frame, rosters) is _needs(frame, rosters)

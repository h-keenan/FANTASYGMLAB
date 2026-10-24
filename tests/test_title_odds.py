"""Season Simulator title (championship) odds: bracket logic, format gating."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modules import playoff_simulator as ps


def test_bracket_slots_follow_standard_seeding():
    assert ps._bracket_slots(2) == [1, 2]
    assert ps._bracket_slots(4) == [1, 4, 2, 3]
    assert ps._bracket_slots(8) == [1, 8, 4, 5, 2, 7, 3, 6]


def test_format_supported_and_reseed_flag():
    assert ps.playoff_bracket_format({}, 6) == {"available": True, "reason": "", "reseed": False}
    assert ps.playoff_bracket_format({"playoff_seed_type": 1}, 6)["reseed"] is True


@pytest.mark.parametrize(
    "settings,teams,started,reason",
    [
        ({"playoff_round_type": 1}, 6, False, "unsupported_playoff_format"),
        ({"playoff_type": 1}, 6, False, "unsupported_playoff_format"),
        ({"playoff_seed_type": 7}, 6, False, "unsupported_playoff_format"),
        ({}, 0, False, "no_playoff_format"),
        ({}, 6, True, "playoffs_underway"),
    ],
)
def test_format_unavailable_reasons(settings, teams, started, reason):
    out = ps.playoff_bracket_format(settings, teams, playoffs_started=started)
    assert out["available"] is False and out["reason"] == reason


def _fixed_seeds(n_trials: int, n: int) -> np.ndarray:
    return np.tile(np.arange(n), (n_trials, 1))


@pytest.mark.parametrize("field,reseed", [(2, False), (4, False), (6, False), (6, True), (7, False), (8, True)])
def test_title_odds_sum_to_100_and_only_field_wins(field, reseed):
    n = 10
    z = np.linspace(1.5, -1.5, n)
    odds = ps.simulate_title_odds(
        seed_order=_fixed_seeds(2000, n), z=z, slope=1.0, playoff_teams=field, reseed=reseed,
        rng=np.random.default_rng(1),
    )
    assert odds.sum() == pytest.approx(100.0)
    assert odds[field:].sum() == 0.0


def test_title_odds_favor_top_seed_with_bye_and_strength():
    n = 6
    z = np.linspace(1.5, -1.5, n)
    odds = ps.simulate_title_odds(
        seed_order=_fixed_seeds(4000, n), z=z, slope=1.0, playoff_teams=6, reseed=False, rng=np.random.default_rng(3)
    )
    assert odds[0] == odds.max()
    assert odds[0] > odds[5]


def test_equal_teams_equal_title_odds():
    n = 4
    odds = ps.simulate_title_odds(
        seed_order=_fixed_seeds(8000, n), z=np.zeros(n), slope=1.0, playoff_teams=4, reseed=False,
        rng=np.random.default_rng(5),
    )
    assert all(abs(o - 25.0) < 2.5 for o in odds)


def _sim(**extra):
    n = 6
    return ps.simulate_playoff_odds(
        roster_ids=[str(i) for i in range(1, n + 1)],
        power_scores=[100.0 - 10 * i for i in range(n)],
        current_wins=[3, 2, 2, 1, 1, 0],
        current_losses=[0, 1, 1, 2, 2, 3],
        current_ties=[0] * n,
        points_for=[300, 280, 270, 250, 240, 200],
        points_against=[200] * n,
        team_names=[f"T{i}" for i in range(n)],
        completed_games=[],
        remaining_games=[("1", "6"), ("2", "5"), ("3", "4")],
        playoff_teams=4,
        n_trials=2000,
        rng=np.random.default_rng(9),
        **extra,
    )


def test_simulation_includes_title_odds_only_when_format_available():
    without = _sim()
    assert all("title_probability" not in t for t in without["teams"].values())
    with_odds = _sim(title_bracket={"available": True, "reason": "", "reseed": False})
    total = sum(t["title_probability"] for t in with_odds["teams"].values())
    assert total == pytest.approx(100.0)
    off = _sim(title_bracket={"available": False, "reason": "unsupported_playoff_format", "reseed": False})
    assert all("title_probability" not in t for t in off["teams"].values())


def test_title_odds_do_not_shift_playoff_odds():
    a = _sim()
    b = _sim(title_bracket={"available": True, "reason": "", "reseed": False})
    for rid, row in a["teams"].items():
        assert row["playoff_probability"] == b["teams"][rid]["playoff_probability"]


def _patch_league(monkeypatch, settings):
    frame = pd.DataFrame(
        [
            {"roster_id": rid, "team_name": f"T{rid}", "owner_name": "o", "avatar_url": "", "record_label": "0-0",
             "wins": 0, "losses": 0, "ties": 0, "points_for": 0, "points_against": 0, "division_id": None,
             "power_score": 100.0 - rid}
            for rid in range(1, 5)
        ]
    )
    monkeypatch.setattr(ps.sleeper, "get_league", lambda _id: {"settings": settings})
    monkeypatch.setattr(ps.sleeper, "get_rosters", lambda _id: [])
    monkeypatch.setattr(ps.sleeper, "get_league_roster_profiles", lambda _id: {})
    monkeypatch.setattr(ps.league_rankings, "build_league_rankings_frame_cached", lambda **_k: frame)
    monkeypatch.setattr(
        ps.league_standings,
        "build_league_standings_bundle",
        lambda **_k: {"available": True, "playoff_teams": 2, "frame": frame, "season": "2026"},
    )
    monkeypatch.setattr(
        ps.sleeper,
        "get_matchups",
        lambda _l, _w: [
            {"matchup_id": 1, "roster_id": 1, "points": 0},
            {"matchup_id": 1, "roster_id": 4, "points": 0},
            {"matchup_id": 2, "roster_id": 2, "points": 0},
            {"matchup_id": 2, "roster_id": 3, "points": 0},
        ],
    )


def test_assembly_reports_title_odds_for_supported_league(monkeypatch):
    _patch_league(monkeypatch, {"leg": 1, "playoff_week_start": 5})
    out = ps.build_league_playoff_odds("L", players_db_path="x", n_trials=1000, rng=np.random.default_rng(2))
    assert out["title_odds"] == {"available": True, "reason": ""}
    assert sum(t["title_probability"] for t in out["teams"]) == pytest.approx(100.0, abs=0.5)


def test_assembly_reports_unavailable_with_reason_not_a_number(monkeypatch):
    _patch_league(monkeypatch, {"leg": 1, "playoff_week_start": 5, "playoff_round_type": 1})
    out = ps.build_league_playoff_odds("L", players_db_path="x", n_trials=500, rng=np.random.default_rng(2))
    assert out["title_odds"] == {"available": False, "reason": "unsupported_playoff_format"}
    assert all(t["title_probability"] is None for t in out["teams"])

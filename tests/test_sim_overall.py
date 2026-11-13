"""Sim Overall (1-99) is the real app's OVR definition: value percentile within position, same curve."""

from __future__ import annotations

from types import SimpleNamespace

from modules import player_quick_view as real
from modules.sim import game_view as view


def _snap(values_by_pos):
    players, pids = {}, []
    for pos, values in values_by_pos.items():
        for i, v in enumerate(values):
            pid = f"{pos}{i}"
            players[pid] = SimpleNamespace(pos=pos, value=v)
            pids.append(pid)
    return SimpleNamespace(players=players, pids=pids)


def test_curve_matches_the_real_overall_curve():
    assert view.OVERALL_CURVE == real._OVERALL_RATING_CURVE
    assert view.OVERALL_MAX == real.OVERALL_RATING_MAX
    assert view.OVERALL_MIN_POOL == real.PERCENTILE_MIN_POOL
    for pct in (0.0, 0.1, 0.5, 0.8, 0.93, 0.97, 0.995, 1.0):
        assert view.overall_from_percentile(pct) == real._overall_rating_from_percentile(pct)


def test_overall_is_the_percentile_within_position():
    snap = _snap({"RB": list(range(1, 21)), "QB": [5.0] * 3})
    ovr = view.overall_ratings(snap)
    assert ovr["RB19"] == 99 and ovr["RB0"] < ovr["RB10"] < ovr["RB19"]
    assert ovr["RB0"] == view.overall_from_percentile(1 / 20)
    # a position pool thinner than the floor has no rating rather than a made-up one
    assert "QB0" not in ovr


def test_ties_share_the_average_rank():
    snap = _snap({"WR": [1.0] * 5 + [9.0] * 5})
    ovr = view.overall_ratings(snap)
    assert len({ovr[f"WR{i}"] for i in range(5)}) == 1
    assert ovr["WR0"] < ovr["WR9"]

"""Questionable conditional-on-playing factor (docs/projections-v3-signals.md)."""

import pytest

from modules import player_projections as pp
from tests.test_player_projections import extended_schedule  # noqa: F401  (fixture)
from tests.test_projections_v2 import _rows


@pytest.mark.parametrize(
    "status,injury,ahead,applied",
    [
        ("Active", "Questionable", 0, True),
        ("Active", "Questionable", 2, False),  # not the next game
        ("Active", "Doubtful", 0, False),  # Doubtful players who played scored ~1.0x in the walk-forward
        ("Active", "Out", 0, False),
        ("Active", "", 0, False),
    ],
)
def test_questionable_plays_factor_only_for_next_game_questionable(status, injury, ahead, applied):
    out = pp._questionable_plays_adjustment({"status": status, "injury_status": injury}, ahead)
    assert out["applied"] is applied
    assert out["multiplier"] == (pp._V2_QUESTIONABLE_PLAYS_FACTOR if applied else 1.0)


def test_questionable_projection_is_playprob_times_plays_factor_times_baseline(extended_schedule):  # noqa: F811
    healthy = {"wr_a1": {"position": "WR", "team": "AAA"}}
    hurt = {"wr_a1": {"position": "WR", "team": "AAA", "status": "Active", "injury_status": "Questionable"}}
    kwargs = dict(week=5, season=2099, player_weekly_rows=_rows([12, 14, 11]), defense_strength={}, team_qb_quality={}, weekly_stats={})
    base = pp.project_player_week("wr_a1", players=healthy, **kwargs)
    q = pp.project_player_week("wr_a1", players=hurt, **kwargs)
    expected = base["point_estimate"] * pp._V2_QUESTIONABLE_MULTIPLIER * pp._V2_QUESTIONABLE_PLAYS_FACTOR
    assert q["point_estimate"] == pytest.approx(expected, abs=0.15)  # both sides are rounded to 0.1
    assert q["basis"]["questionable_plays"]["applied"] is True
    assert base["basis"]["questionable_plays"]["applied"] is False
    # the availability layer is unchanged: still the one table's p_play, not multiplied twice
    assert q["basis"]["availability"]["multiplier"] == pp._V2_QUESTIONABLE_MULTIPLIER

"""Realism P1 (2026-11 audit 2): a handcuff's role and projection rise when the starter is out
or Doubtful, generalizing the backup-QB-behind-a-Doubtful-starter layer."""

import pytest

from modules import injury_status
from modules import player_projections as pp
from tests.test_player_projections import extended_schedule  # noqa: F401  (fixture)


def _rb(order, **extra):
    return {"position": "RB", "team": "AAA", "depth_chart_order": order, "status": "Active", **extra}


def _rows(points, start=1):
    return [{"week": start + i, "games_played": 1, "fantasy_points_ppr": p, "carries": 15, "targets": 3}
            for i, p in enumerate(points)]


def test_handcuff_behind_a_healthy_starter_is_unchanged():
    players = {"rb1": _rb(1), "rb2": _rb(2)}
    assert pp._role_adjustment(players["rb2"], players)["applied"] is False
    assert pp._role_adjustment(players["rb1"], players)["applied"] is False


@pytest.mark.parametrize("injury", ["Out", "IR", "Doubtful"])
def test_handcuff_role_is_flagged_when_the_starter_is_out_or_doubtful(injury):
    players = {"rb1": _rb(1, injury_status=injury), "rb2": _rb(2)}
    role = pp._role_adjustment(players["rb2"], players)
    assert role["applied"] and role["reason"] == "handcuff_starter_out" and role["starter_player_id"] == "rb1"
    assert role["uncalibrated"] is True
    if injury == "Doubtful":
        assert role["starter_p_miss"] == pytest.approx(1.0 - injury_status.classify("Active", "Doubtful").p_play, abs=0.001)
    else:
        assert role["starter_p_miss"] == 1.0
    # the starter himself and an unrelated position are not handcuffs
    assert pp._role_adjustment(players["rb1"], players)["applied"] is False
    wr = {"position": "WR", "team": "AAA", "depth_chart_order": 2, "status": "Active"}
    assert pp._role_adjustment(wr, {**players, "wr": wr})["applied"] is False


def test_handcuff_follows_the_teammate_directly_ahead():
    players = {"rb1": _rb(1, injury_status="Out"), "rb2": _rb(2), "rb3": _rb(3)}
    assert pp._role_adjustment(players["rb3"], players)["applied"] is False  # rb2 is healthy, rb3 stays buried
    assert pp._role_adjustment(players["rb2"], players)["starter_player_id"] == "rb1"


def test_projection_rises_when_the_starter_is_out(extended_schedule):  # noqa: F811
    own = _rows([4, 5, 4, 5])
    starter_rows = _rows([18, 20, 17, 19])
    weekly_stats = {"rb1": {"weekly": starter_rows}}
    kwargs = dict(week=6, season=2099, player_weekly_rows=own, defense_strength={}, team_qb_quality={},
                  weekly_stats=weekly_stats)
    healthy = {"rb1": _rb(1), "rb2": _rb(2)}
    out = {"rb1": _rb(1, injury_status="Out"), "rb2": _rb(2)}
    doubtful = {"rb1": _rb(1, injury_status="Doubtful"), "rb2": _rb(2)}
    base = pp.project_player_week("rb2", players=healthy, **kwargs)
    lifted_out = pp.project_player_week("rb2", players=out, **kwargs)
    lifted_doubtful = pp.project_player_week("rb2", players=doubtful, **kwargs)
    assert lifted_out["point_estimate"] > base["point_estimate"] * 1.3
    assert base["point_estimate"] < lifted_doubtful["point_estimate"] <= lifted_out["point_estimate"]
    role = lifted_out["basis"]["role"]
    assert role["reason"] == "handcuff_starter_out"
    assert role["inherited_ppr"] == pytest.approx(pp.HANDCUFF_INHERIT_SHARE["RB"] * role["starter_baseline_ppr"], abs=0.02)
    assert lifted_out["confidence"] == "low"  # the inherited role is an uncalibrated prior
    assert lifted_out["high"] > base["high"]
    assert base["basis"]["role"]["applied"] is False


def test_handcuff_never_projects_below_his_usual_output_and_degrades_without_starter_history(extended_schedule):  # noqa: F811
    own = _rows([9, 10, 9, 10])
    weak_starter = {"rb1": {"weekly": _rows([2, 2, 2, 2])}}
    players = {"rb1": _rb(1, injury_status="Out"), "rb2": _rb(2)}
    base = pp.project_player_week("rb2", week=6, season=2099, players={"rb1": _rb(1), "rb2": _rb(2)},
                                  player_weekly_rows=own, defense_strength={}, team_qb_quality={}, weekly_stats=weak_starter)
    lifted = pp.project_player_week("rb2", week=6, season=2099, players=players, player_weekly_rows=own,
                                    defense_strength={}, team_qb_quality={}, weekly_stats=weak_starter)
    assert lifted["point_estimate"] >= base["point_estimate"]
    # no history for the starter: nothing to inherit, the estimate stays at his usual baseline
    no_hist = pp.project_player_week("rb2", week=6, season=2099, players=players, player_weekly_rows=own,
                                     defense_strength={}, team_qb_quality={}, weekly_stats={"rb1": {"weekly": []}})
    assert no_hist["point_estimate"] == base["point_estimate"]
    assert no_hist["basis"]["role"]["starter_baseline_ppr"] is None

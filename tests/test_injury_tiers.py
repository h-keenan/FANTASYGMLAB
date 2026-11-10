"""Injury tiers are scored against the lineup the injuries actually cost.

Regression for coridian_'s report that "every single team is listed as being in
an injury crisis": production valuation scores are 0..10,000 but the injury
math capped them at 100, so every real starter read as a flat 100 and any
roster with a few tagged players summed to crisis; the health tier also tallied
every tagged player on the whole roster (taxi, IR slot, depth).
"""

import pandas as pd

from modules import league_rankings, rankings
from modules.team_eval import suggest_optimal_lineup

SETTINGS = {"qb_count": 1, "rb_count": 2, "wr_count": 2, "te_count": 1, "flex_count": 1}


def _player(pid, position, score, *, status="Active", injury=""):
    return {
        "player_id": pid,
        "name": pid,
        "position": position,
        "status": status,
        "injury_status": injury,
        "market_score": score,
        "value_score": score,
    }


def _healthy_core(scale=100):
    return [
        _player("qb", "QB", 80 * scale),
        _player("rb1", "RB", 75 * scale),
        _player("rb2", "RB", 70 * scale),
        _player("wr1", "WR", 78 * scale),
        _player("wr2", "WR", 72 * scale),
        _player("te", "TE", 60 * scale),
        _player("flex", "WR", 65 * scale),
    ]


def _summarize(rows, **kwargs):
    roster = pd.DataFrame(rows)
    lineup = suggest_optimal_lineup(roster, SETTINGS, score_field="value_score")
    return rankings.summarize_team_injuries(roster, lineup, **kwargs)


def test_production_scale_scores_are_not_flattened_to_100():
    # 3 real starters tagged on a 0..10,000 scale used to be 3 x "100" = crisis.
    rows = _healthy_core(scale=100)
    rows[1] = _player("rb1", "RB", 7500, status="Active", injury="Questionable")
    rows[3] = _player("wr1", "WR", 7800, status="Active", injury="Questionable")
    rows[5] = _player("te", "TE", 6000, status="Active", injury="Questionable")
    summary = _summarize(rows)
    assert summary["injured_starters"] == 3
    assert summary["health_flag"] != "Injury Crisis"
    assert summary["injury_impact_flag"] != "Injury Crisis"
    assert summary["lineup_injury_loss_pct"] < 15


def test_bench_cover_and_parked_players_do_not_make_a_crisis():
    rows = _healthy_core()
    rows[1] = _player("rb1", "RB", 7500, status="Inactive", injury="IR")
    rows[3] = _player("wr1", "WR", 7800, status="Inactive", injury="IR")
    rows += [
        _player("rb-bench", "RB", 6800),
        _player("wr-bench", "WR", 7000),
        # Taxi / IR-slot bodies with injuries never count against the lineup.
        _player("taxi-wr", "WR", 3000, injury="Out"),
        _player("ir-te", "TE", 5000, status="Inactive", injury="IR"),
    ]
    summary = _summarize(rows, taxi_player_ids=["taxi-wr"], reserve_player_ids=["ir-te"])
    assert summary["lineup_players_out"] == 2
    assert summary["health_flag"] in {"Stable", "Health Watch", "Injury Hit"}
    assert summary["health_flag"] != "Injury Crisis"


def test_multiple_stars_out_without_cover_is_a_crisis():
    rows = _healthy_core()
    for index, pid in ((0, "qb"), (1, "rb1"), (3, "wr1")):
        rows[index] = _player(pid, rows[index]["position"], rows[index]["market_score"], status="Inactive", injury="IR")
    summary = _summarize(rows)
    assert summary["lineup_players_out"] >= 2
    assert summary["lineup_injury_loss_pct"] >= rankings.INJURY_CRISIS_LOSS_PCT
    assert summary["health_flag"] == "Injury Crisis"
    assert summary["injury_impact_flag"] == "Injury Crisis"


def test_one_star_out_is_never_a_crisis_by_himself():
    rows = _healthy_core()
    rows[0] = _player("qb", "QB", 8000, status="Inactive", injury="IR")
    summary = _summarize(rows)
    assert summary["lineup_players_out"] == 1
    assert summary["health_flag"] != "Injury Crisis"


def test_crisis_is_league_relative():
    def team(roster_id, pct):
        return {
            "roster_id": roster_id,
            "health_flag": "Injury Crisis",
            "injury_impact_flag": "Injury Crisis",
            "lineup_injury_loss_pct": pct,
        }

    # Everyone is "in crisis" in absolute terms (a bad injury week): only the
    # worst-hit fifth of a 10-team league keeps the label.
    frame = pd.DataFrame([team(i, 30 + i) for i in range(10)])
    result = league_rankings.apply_league_relative_injury_tiers(frame)
    crisis = result.loc[result["health_flag"] == "Injury Crisis", "roster_id"].tolist()
    assert sorted(crisis) == [8, 9]
    assert (result.loc[result["health_flag"] != "Injury Crisis", "health_flag"] == "Injury Hit").all()
    assert result.loc[result["roster_id"] == 9, "injury_league_rank"].iloc[0] == 1

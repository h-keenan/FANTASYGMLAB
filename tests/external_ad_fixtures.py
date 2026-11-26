"""Fixture data for the adaptive advertising API tests and the docs example generator
(scripts/generate_external_ad_examples.py). Synthetic players, fixed dates."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

NOW = datetime(2026, 12, 8, 15, 0, tzinfo=timezone.utc)
BOARD_AS_OF = "2026-12-08T09:00:00+00:00"


def _p(pid, name, pos, team, rank, score, *, inj="", yexp=4, age=26.0):
    return {
        "player_id": pid, "name": name, "position": pos, "team": team, "age": age, "years_exp": yexp,
        "status": "Active", "injury_status": inj or None, "score": score, "trade_score": score,
        "overall_rank": rank, "position_rank": rank, "tier": "Starter", "overall_rating": 80, "trend": None,
    }


BOARD = [
    _p("100", "Alex Hurt", "WR", "AAA", 12, 7000, inj="Out"),
    _p("101", "Bo Backup", "WR", "AAA", 44, 2100),
    _p("102", "Cy Stream", "WR", "CCC", 50, 1900),
    _p("103", "Dee Flex", "RB", "AAA", 20, 4200),
    _p("104", "Eli Flex", "RB", "BBB", 22, 4000),
    _p("105", "Fox Rookie", "RB", "CCC", 30, 3000, yexp=0, age=21.5),
    _p("106", "Gus Rookie", "WR", "BBB", 60, 1500, yexp=0, age=22.0),
]

TRENDING = [{"player_id": "101", "count": 5400}, {"player_id": "102", "count": 3100}, {"player_id": "103", "count": 900}]
ROSTER_PCT = {"101": {"current": 12.0}, "102": {"current": 31.5}}


def games() -> pd.DataFrame:
    rows = []
    # weeks 1-3 completed, weeks 14-17 schedule
    for wk, (h, a) in {1: ("AAA", "BBB"), 2: ("CCC", "AAA"), 3: ("BBB", "CCC"), 14: ("AAA", "BBB"), 15: ("AAA", "CCC"), 16: ("BBB", "AAA"), 17: ("CCC", "BBB")}.items():
        rows.append({"season": 2026, "week": wk, "game_type": "REG", "game_id": f"2026_{wk:02d}_{a}_{h}", "home_team": h, "away_team": a})
    return pd.DataFrame(rows)


def _d(avg, rank, tier, low=False):
    return {"weighted_points_allowed_per_game": avg, "simple_points_allowed_per_game": avg, "games_sampled": 10, "low_sample": low, "rank": rank, "tier": tier}


# AAA is tough (low points allowed), BBB is weak, CCC average.
DEFENSE = {
    "AAA": {p: _d(a, 1, "tough") for p, a in (("QB", 15.0), ("RB", 18.0), ("WR", 22.0), ("TE", 8.0))},
    "BBB": {p: _d(a, 3, "weak") for p, a in (("QB", 22.0), ("RB", 30.0), ("WR", 36.0), ("TE", 13.0))},
    "CCC": {p: _d(a, 2, "average") for p, a in (("QB", 18.0), ("RB", 24.0), ("WR", 29.0), ("TE", 10.0))},
}

LATEST_RATINGS = {"100": 90, "101": 70, "102": 60, "103": 75, "104": 66, "105": 71}
BASELINE_RATINGS = {"100": 90, "101": 62, "102": 61, "103": 80, "104": 66, "105": 70}

ROOKIE_ADP = {"as_of": "2026-12-07", "players": {"105": {"adp": 4.5, "drafts": 40}}}
SLEEPER_PLAYERS = {"105": {"depth_chart_order": 2}, "106": {"depth_chart_order": 3}}
DEPTH_SNAPSHOTS = {"2026-W48": {"103": 2, "104": 1}, "2026-W49": {"103": 1, "104": 1}}

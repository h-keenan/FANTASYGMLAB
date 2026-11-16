from __future__ import annotations

import pandas as pd

from modules import team_sheet as ts


def test_streak_label_signs():
    assert ts.streak_label(12) == "W12"
    assert ts.streak_label(-3) == "L3"
    assert ts.streak_label(0) == "" and ts.streak_label(None) == ""


def test_levels_come_from_the_need_model_tag_not_rank():
    rooms = [
        {"position": "QB", "rank": 1, "of": 12, "tag": "surplus"},
        {"position": "RB", "rank": 2, "of": 12, "tag": None},
        {"position": "TE", "rank": 12, "of": 12, "tag": "need"},
    ]
    cards, strengths, needs = ts.position_cards(rooms, {"QB": 3, "RB": 5})
    assert [c["level"] for c in cards] == ["strength", "solid", "need"]
    assert strengths == ["QB"] and needs == ["TE"]
    assert cards[0]["depth"] == 3 and cards[2]["depth"] == 0


def _frame():
    return pd.DataFrame(
        [
            {"player_id": "1", "name": "A", "position": "WR", "team": "KC", "age": 25, "injury_status": "Questionable", "dynasty_score": 50},
            {"player_id": "2", "name": "B", "position": "QB", "team": "BUF", "age": 28, "injury_status": None, "dynasty_score": 70},
            {"player_id": "3", "name": "C", "position": "WR", "team": "KC", "age": 22, "injury_status": "IR", "dynasty_score": 80},
            {"player_id": "9", "name": "Other", "position": "RB", "team": "KC", "age": 22, "injury_status": None, "dynasty_score": 99},
        ]
    )


def test_roster_rows_injuries_and_depth():
    roster = {"players": ["1", "2", "3"], "starters": ["2"], "reserve": ["3"]}
    rows = ts.roster_rows(_frame(), roster, "dynasty_score")
    assert [r["player_id"] for r in rows] == ["2", "3", "1"]
    assert {r["player_id"]: r["slot"] for r in rows} == {"2": "starter", "3": "ir", "1": "bench"}
    assert [r["player_id"] for r in ts.injuries(rows)] == ["3", "1"]
    assert ts.depth_by_position(rows) == {"QB": 1, "WR": 1}


def test_season_result_places_by_wins_then_points():
    def r(i, owner, w, fpts):
        return {"roster_id": i, "owner_id": owner, "settings": {"wins": w, "losses": 14 - w, "fpts": fpts}}

    rosters = [r(1, "a", 10, 1500), r(2, "b", 10, 1600), r(3, "c", 4, 1000)]
    out = ts.season_result(rosters, "a", "2024", "L24")
    assert out["place"] == 2 and out["of"] == 3 and out["wins"] == 10
    assert ts.season_result(rosters, "zzz", "2024", "L24") is None
    assert ts.season_result([{"roster_id": 1, "owner_id": "a", "settings": {}}], "a", "2024", "L24") is None

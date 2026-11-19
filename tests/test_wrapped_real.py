from modules.wrapped_real import build_real_wrapped


def _week(a, b, c, d, bench=True):
    def row(rid, mid, pts):
        r = {"roster_id": rid, "matchup_id": mid, "points": pts, "starters": ["11", "12"] if rid == 1 else [], "players_points": None}
        if rid == 1 and bench:
            r["players_points"] = {"11": pts * 0.6, "12": pts * 0.4, "13": 22.0}
        return r

    return [row(1, 1, a), row(2, 1, b), row(3, 2, c), row(4, 2, d)]


LOOKUP = {"11": {"name": "Jalen Pruitt", "position": "WR", "team": "CIN"}, "13": {"name": "Eli Vasquez", "position": "WR", "team": "NYJ"}}
PROFILES = {"2": {"team_name": "Harbor Hawks"}, "3": {"team_name": "Summit Wolves"}}


def _deck(weeks, partial=False):
    return build_real_wrapped(weeks, 1, season="2026", team_name="Lake City Comets", profiles=PROFILES, lookup=LOOKUP, partial=partial)


def test_real_deck_cards_and_nothing_invented():
    deck = _deck([_week(100, 90, 80, 70), _week(60, 90, 80, 70), _week(120, 90, 80, 70), _week(0, 0, 0, 0)])
    ids = [c["id"] for c in deck["cards"]]
    assert ids == ["intro", "mvp", "weeks", "close", "luck", "journey"]
    assert deck["kind"] == "real" and not any(c["locked"] or c["pro"] for c in deck["cards"])
    intro = deck["cards"][0]["data"]
    assert intro["record"] == "2-1" and intro["weeks"] == 3
    mvp = deck["cards"][1]["data"]
    assert mvp["player"]["name"] == "Jalen Pruitt" and mvp["over_proj"] is None
    assert deck["cards"][2]["data"]["worst"]["opponent"] == "Harbor Hawks"


def test_partial_flag_and_too_early():
    assert _deck([_week(100, 90, 80, 70), _week(60, 90, 80, 70)], partial=True)["partial"] is True
    assert _deck([_week(100, 90, 80, 70)])["cards"] == []


def test_no_per_player_points_drops_close_and_mvp():
    ids = [c["id"] for c in _deck([_week(100, 90, 80, 70, bench=False), _week(60, 90, 80, 70, bench=False)])["cards"]]
    assert "mvp" not in ids and "close" not in ids and "luck" in ids

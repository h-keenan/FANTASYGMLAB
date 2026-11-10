"""Three-team (N-team) historical trades: grading, recap story, tendencies, integrity.

The fixture is a real-shaped Sleeper trade transaction: assets flow
roster 1 -> 2 -> 3 -> 1, a pick goes 2 -> 3 and FAAB goes 1 -> 2.
"""

from __future__ import annotations

from modules import league_history as history
from modules import league_integrity as li
from modules import league_recaps
from modules import manager_tendencies
from modules import transaction_grades as grades
from modules.trade_ideas import canonical_pick_identity_value

PROFILES = {
    str(i): {"team_name": f"Team {name}", "username": name.lower(), "owner_name": f"{name} Owner"}
    for i, name in ((1, "Alpha"), (2, "Bravo"), (3, "Charlie"))
}
PLAYERS = {
    "p1": {"name": "Star One", "position": "WR", "team": "CIN"},
    "p2": {"name": "Mid Two", "position": "RB", "team": "NYJ"},
    "p3": {"name": "Cheap Three", "position": "TE", "team": "ARI"},
}
LOOKUP = {
    "p1": {"current_value": 5000},
    "p2": {"current_value": 3000},
    "p3": {"current_value": 1000},
}


def three_team_raw():
    return {
        "transaction_id": "tx3",
        "type": "trade",
        "status": "complete",
        "roster_ids": [1, 2, 3],
        "creator": "u1",
        "consenter_ids": [1, 2, 3],
        "adds": {"p1": 2, "p2": 3, "p3": 1},
        "drops": {"p1": 1, "p2": 2, "p3": 3},
        "draft_picks": [
            {"season": "2027", "round": 1, "roster_id": 2, "previous_owner_id": 2, "owner_id": 3}
        ],
        "waiver_budget": [{"sender": 1, "receiver": 2, "amount": 10}],
        "status_updated": 1_700_000_000_000,
    }


def two_team_raw():
    return {
        "transaction_id": "tx2",
        "type": "trade",
        "status": "complete",
        "roster_ids": [1, 2],
        "adds": {"p1": 2, "p3": 1},
        "drops": {"p1": 1, "p3": 2},
        "draft_picks": [],
        "status_updated": 1_700_000_000_000,
    }


def normalize(raw, week=4):
    return history.normalize_transaction(
        raw, league_id="L", season="2026", week=week, profiles=PROFILES, player_lookup=PLAYERS
    )


def test_normalized_three_team_trade_has_all_edges():
    tx = normalize(three_team_raw())
    assert tx["roster_ids"] == [1, 2, 3]
    assert len(tx["sides"]) == 3
    by_rid = {s["roster_id"]: s for s in tx["sides"]}
    assert [a["player_id"] for a in by_rid["1"]["drops"]] == ["p1"]
    assert {a["name"] for a in by_rid["3"]["receives"]} >= {"Mid Two"}


def test_three_team_trade_grades_every_team_on_what_it_sent_and_received():
    tx = normalize(three_team_raw())
    graded = grades.grade_trade(tx, player_lookup=LOOKUP, current_week=12)
    assert [s["team"] for s in graded["sides"]] == ["Team Alpha", "Team Bravo", "Team Charlie"]
    pick = canonical_pick_identity_value({"round": 1})
    ratios = [s["ratio"] for s in graded["sides"]]
    # Alpha got p3 (1000) for p1 (5000); Bravo got p1 (5000) for p2 (3000) + pick;
    # Charlie got p2 (3000) + pick for p3 (1000).
    assert ratios[0] == round(1000 / 5000, 3)
    assert ratios[1] == round(5000 / (3000 + pick), 3)
    assert ratios[2] == round((3000 + pick) / 1000, 3)
    assert [s["total_assets_sent"] for s in graded["sides"]] == [1, 2, 1]
    assert graded["sides"][0]["letter"].startswith(("D", "F"))
    assert graded["sides"][2]["letter"].startswith("A")
    assert not graded["pending"]


def test_two_team_grading_is_unchanged_swap():
    tx = normalize(two_team_raw())
    graded = grades.grade_trade(tx, player_lookup=LOOKUP, current_week=12)
    assert [s["ratio"] for s in graded["sides"]] == [round(1000 / 5000, 3), round(5000 / 1000, 3)]


def test_explicit_sent_list_is_honoured_for_n_teams():
    sides = [
        {"team_name": "A", "roster_id": 1, "receives": [{"player_id": "p3", "kind": "player"}],
         "sent": [{"player_id": "p1", "kind": "player"}]},
        {"team_name": "B", "roster_id": 2, "receives": [{"player_id": "p1", "kind": "player"}],
         "sent": [{"player_id": "p2", "kind": "player"}]},
        {"team_name": "C", "roster_id": 3, "receives": [{"player_id": "p2", "kind": "player"}],
         "sent": [{"player_id": "p3", "kind": "player"}]},
    ]
    graded = grades.grade_trade({"type": "trade", "week": 1, "sides": sides}, player_lookup=LOOKUP, current_week=12)
    assert [s["ratio"] for s in graded["sides"]] == [0.2, round(5000 / 3000, 3), 3.0]


def test_recap_trade_story_includes_every_team():
    tx = normalize(three_team_raw())
    story = league_recaps._trade_story([tx], week=4, fingerprint="f")
    assert story["summary"].startswith("3-team trade")
    for name in ("Team Alpha", "Team Bravo", "Team Charlie"):
        assert name in story["summary"]
    assert story["team_count"] == 3
    assert [s["team_name"] for s in story["sides"]] == ["Team Alpha", "Team Bravo", "Team Charlie"]
    assert story["left_assets"] and story["right_assets"]


def test_recap_trade_story_two_team_unchanged():
    story = league_recaps._trade_story([normalize(two_team_raw())], week=4, fingerprint="f")
    assert story["summary"] == "Team Alpha received Cheap Three; Team Bravo received Star One."
    assert story["primary_roster_id"] == ""
    assert story["team_count"] == 2 and len(story["sides"]) == 2


def test_manager_tendencies_grades_every_side_of_a_three_team_trade():
    season = {
        "season": "2026",
        "league_id": "L",
        "teams": {i: {"team_name": f"Team {n}"} for i, n in ((1, "A"), (2, "B"), (3, "C"))},
        "previous_league_id": "L0",
        "draft_rounds": 4,
    }
    raw = three_team_raw() | {"timestamp": 1}
    sides = manager_tendencies._trade_sides(raw, season, {})
    for s in sides.values():
        for a in s["received"] + s["sent"]:
            if a["kind"] == "player":
                a["current_value"] = LOOKUP[a["player_id"]]["current_value"]
    tx = {
        "week": 4,
        "sides": [
            {"roster_id": rid, "team_name": f"Team {rid}", "received": s["received"], "sent": s["sent"]}
            for rid, s in sides.items()
        ],
    }
    results = {rid: manager_tendencies._grade_for_side(tx, rid, {}, 12) for rid in sides}
    assert all(results.values())
    assert results[3]["ratio"] > results[2]["ratio"] > results[1]["ratio"]


def test_integrity_scores_three_team_trade_per_team_but_never_as_a_pair():
    tx = normalize(three_team_raw())
    values = {"p1": {"value_score": 5000}, "p2": {"value_score": 3000}, "p3": {"value_score": 1000}}
    legs = li.trade_legs([tx], values)
    assert legs[0]["valued"] is True
    assert legs[0]["legs"][1]["sent"] == 5000 and legs[0]["legs"][1]["received"] == 1000
    assert legs[0]["legs"][2]["sent"] == 3000 + canonical_pick_identity_value({"round": 1})
    # Pair logic ignores N-team trades.
    assert li.lopsided_wins_between(legs, 1, 3) == {"1": 0, "3": 0}
    losers = li._lopsided_losers(legs)
    assert losers and all(len(t["roster_ids"]) == 3 for *_, t in losers)
    assert li.collusion_pairs(legs, {}) == []

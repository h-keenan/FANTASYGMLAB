"""GM Plan Team Outlook (handshake item 7): the shared team profile read as plan items."""

from __future__ import annotations

from modules import gm_plan, gm_plan_outlook

LOOKUP = {
    "1": {"name": "Aaron Cook", "position": "RB", "team": "DET", "age": 30},
    "2": {"name": "Amon Brown", "position": "WR", "team": "DET", "age": 28},
    "3": {"name": "Tee Hawk", "position": "TE", "team": "KC", "age": 25},
    "4": {"name": "Wes Deep", "position": "WR", "team": "SEA", "age": 24},
}


def team(rid, name, *, posture="retool", core=27.0, cliff=(), needs=(), surplus=None, firsts=1, capital=3000, tier="middle", lean=""):
    return {
        "roster_id": rid,
        "team_name": name,
        "posture": {"key": posture, "label": posture.title()},
        "age": {
            "avg": core,
            "core_avg": core,
            "cliff_ids": list(cliff),
            "rising_ids": [],
            "phase_counts": {"prime": 8},
            "by_position": {"RB": {"prime_years_left_avg": 0.5}},
        },
        "needs": {"needs": list(needs), "surplus_ids": surplus or {}},
        "picks": {
            "count": 4,
            "firsts": firsts,
            "capital": capital,
            "tier": tier,
            "assets": [{"season": "2027", "round": 1, "slot": "1.04", "slot_number": 4, "value": 3000}],
            "flow": {"picks_acquired": 1, "picks_sent": 0},
        },
        "tendency": {"lean": lean, "buy_count": 2, "sell_count": 3 if lean == "seller" else 0},
    }


def profile():
    return {
        "teams": {
            "1": team("1", "Me", posture="retool", core=28.4, cliff=["1"], needs=["TE"], surplus={"WR": ["2"]}, firsts=3, capital=9000, tier="high"),
            "2": team("2", "Gridiron Ghosts", posture="contender", core=26.0, needs=["WR"], surplus={"TE": ["3"]}, firsts=0, capital=1000, tier="low"),
            "3": team("3", "Rebuild Rovers", posture="rebuild", core=25.0, needs=["QB"], surplus={"WR": ["4"]}, firsts=2, capital=5000, lean="seller"),
            "4": team("4", "Quiet Qs", posture="retool", core=26.5, needs=["K"], surplus={}),
        }
    }


def test_outlook_reads_age_needs_picks_and_callers():
    items = gm_plan_outlook.build_outlook(my_roster_id=1, profile=profile(), players_by_id=LOOKUP, declared_stance="rebuilding")
    topics = [i["outlook_topic"] for i in items]
    assert topics[:3] == ["age", "needs", "picks"]
    assert "call" in topics
    age = items[0]
    assert "A. Cook" in age["headline"] and "near the cliff" in age["headline"]
    assert any("older" in w for w in age["why"]), "core age vs league is a reason"
    assert any("declared rebuild" in w for w in age["why"]), "the declared stance is a reason"
    assert [p["player_id"] for p in age["players"]] == ["1"]
    needs = items[1]
    assert needs["headline"] == "Need TE · deep at WR"
    assert any("A. Brown" in w for w in needs["why"])
    picks = items[2]
    assert "3 firsts" in picks["headline"] and "1st of 4" in picks["headline"]
    assert any("1.04" in w for w in picks["why"])


def test_who_to_call_needs_two_reasons_and_uses_surname_format():
    items = gm_plan_outlook.call_items("1", profile()["teams"], LOOKUP, "retool")
    names = [i["headline"].split(":")[0] for i in items]
    assert names == ["Gridiron Ghosts"], "only the team that fits both ways has two reasons"
    only = items[0]
    assert any("deep at TE" in w and "short at WR" in w for w in only["why"])
    assert only["players"][0]["name"] == "Tee Hawk"


def test_rebuilder_calls_the_contender_and_firsts_holder_with_supporting_reasons():
    teams = profile()["teams"]
    teams["3"]["needs"]["needs"] = ["WR"]
    teams["3"]["needs"]["surplus_ids"] = {"TE": ["3"]}
    items = gm_plan_outlook.call_items("1", teams, LOOKUP, "rebuild", idea_partners=["Gridiron Ghosts"])
    first = items[0]["headline"]
    assert first.startswith("Gridiron Ghosts")
    text = " ".join(" ".join(i["why"]) for i in items)
    assert "pay for veterans" in text and "holds 2 firsts" in text and "live trade idea" in text


def test_waivers_and_byes_only_in_season():
    adds = [{"player_id": "3", "name": "Tee Hawk", "position": "TE", "team": "KC", "age": 25}]
    tile = {"value": "Your WR1 (Amon Brown) is on bye in Week 9", "note": "Look at waivers.", "route_player_id": "2", "route_player_name": "Amon Brown", "route_player_position": "WR", "route_player_team": "DET"}
    off = gm_plan_outlook.build_outlook(my_roster_id=1, profile=profile(), players_by_id=LOOKUP, waiver_adds=adds, bye_tile=tile, in_season=False)
    on = gm_plan_outlook.build_outlook(my_roster_id=1, profile=profile(), players_by_id=LOOKUP, waiver_adds=adds, bye_tile=tile, in_season=True)
    assert not {"waivers", "byes"} & {i["outlook_topic"] for i in off}
    waiver = next(i for i in on if i["outlook_topic"] == "waivers")
    assert waiver["headline"] == "Add T. Hawk (TE)" and any("true TE need" in w for w in waiver["why"])
    assert any(i["outlook_topic"] == "byes" for i in on)


def test_missing_profile_yields_no_items():
    assert gm_plan_outlook.build_outlook(my_roster_id=1, profile=None, players_by_id={}) == []
    assert gm_plan_outlook.build_outlook(my_roster_id=9, profile=profile(), players_by_id=LOOKUP) == []


def test_build_gm_plan_adds_area_only_when_enabled(monkeypatch):
    items = gm_plan_outlook.build_outlook(my_roster_id=1, profile=profile(), players_by_id=LOOKUP)
    base = gm_plan.build_gm_plan(season_phase="offseason_adjacent")
    monkeypatch.delenv(gm_plan_outlook.OUTLOOK_ENV_KEY, raising=False)
    on = gm_plan.build_gm_plan(season_phase="offseason_adjacent", outlook_items=items)
    assert [a["key"] for a in on["focus_areas"]][-1] == "team_outlook"
    assert on["focus_areas"][:3] == base["focus_areas"]
    monkeypatch.setenv(gm_plan_outlook.OUTLOOK_ENV_KEY, "0")
    off = gm_plan.build_gm_plan(season_phase="offseason_adjacent", outlook_items=items)
    assert off == base, "flag off restores today's exact output"


def _flag(key):
    return {"flags": [{"key": key}]}


def test_roles_item_reads_rising_and_shrinking_roles():
    flags = {"1": _flag("role_shrinking"), "4": _flag("role_expanding"), "2": _flag("positive_regression")}
    built = gm_plan_outlook.roles_item(["1", "2", "4"], LOOKUP, flags, "rebuild")
    assert built["outlook_topic"] == "roles"
    assert built["headline"] == "1 rising · 1 shrinking"
    assert len(built["why"]) >= 2
    assert {p["player_id"] for p in built["players"]} == {"1", "4"}
    assert any("sell" in w for w in built["why"])


def test_roles_item_silent_without_a_corroborated_flag():
    assert gm_plan_outlook.roles_item(["1"], LOOKUP, {}, "contend") is None
    assert gm_plan_outlook.roles_item(["1"], LOOKUP, {"1": _flag("unsustainable")}, "contend") is None


def test_roles_item_only_in_season():
    kwargs = dict(my_roster_id=1, profile=profile(), players_by_id=LOOKUP, usage_flags={"1": _flag("role_shrinking")}, my_player_ids=["1"])
    off = [i["outlook_topic"] for i in gm_plan_outlook.build_outlook(**kwargs)]
    on = [i["outlook_topic"] for i in gm_plan_outlook.build_outlook(in_season=True, **kwargs)]
    assert "roles" not in off and "roles" in on

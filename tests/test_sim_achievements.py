"""Season and career achievements: derived at view time, nothing stored (digests and old saves untouched)."""

from __future__ import annotations

import copy
import json

import pytest

from modules.sim import game_achievements as ga
from modules.sim.game_notifications import derive
from tests.test_sim_dynasty import Run, _complete

N = 12


def wk(week, res, pts=100.0, opp=90.0, kind="regular", rnd=None, opp_seed=None):
    if res == "bye":
        return {"week": week, "kind": "playoff", "round": 1, "res": "bye", "pts": None, "opp_pts": None, "opp": None, "opp_name": None, "opp_seed": None}
    return {"week": week, "kind": kind, "round": rnd, "res": res, "pts": pts, "opp_pts": opp, "opp": "9", "opp_name": "Foes", "opp_seed": opp_seed}


def ledger(no=1, results="w" * 14, result=None, champion=None, rank=None, seed=None, playoff=(), tops=None, **kw):
    weeks = [wk(i + 1, r, 100 + i, 90 + i * 0.5) for i, r in enumerate(results)]
    weeks += list(playoff)
    w, l, t = (results.count(c) for c in "wlt")
    done = len(results) >= 14
    base = {
        "season_no": no, "year": 2025 + no, "teams": N, "regular_weeks": 14, "playoff_teams": 6, "playoff_weeks": 3,
        "reg_done": done, "complete": champion is not None, "champion": champion, "weeks": weeks,
        "league_top": tops if tops is not None else [[i + 1, 140.0, "5"] for i in range(len(results))], "bench_left": {},
        "w": w, "l": l, "t": t, "pf": 1400.0, "pa": 1300.0, "rank": rank or (1 if l == 0 else 6), "seed": seed, "made_playoffs": seed is not None,
        "result": result, "standings": [{"tid": "1", "w": w, "l": l, "t": t, "pf": 1400.0, "rank": 1}], "dynasty": True, "trades": [], "waivers": [],
    }
    base.update(kw)
    return base


def keys(ledgers):
    return {i["key"] for i in ga.evaluate(ledgers) if i["unlocked"]}


def title_run(extra_loss=False):
    po = [wk(15, "bye"), wk(16, "w", kind="playoff", rnd=2), wk(17, "l" if extra_loss else "w", kind="playoff", rnd=3)]
    return po


def test_perfect_season_needs_the_title_and_no_playoff_loss():
    led = ledger(results="w" * 14, result="champion", champion="me", seed=1, playoff=title_run())
    assert {"perfect_season", "champion"} <= keys([led])
    assert "undefeated_regular" not in keys([led])
    # undefeated but eliminated: only the regular-season badge
    out = ledger(results="w" * 14, result="semifinal", champion="5", seed=1, playoff=[wk(15, "bye"), wk(16, "l", kind="playoff", rnd=2)])
    assert "undefeated_regular" in keys([out]) and "perfect_season" not in keys([out])
    # a playoff loss on the way to a title is impossible, but a loss anywhere kills "perfect"
    assert "perfect_season" not in keys([ledger(results="w" * 13 + "l", result="champion", champion="me", seed=1, playoff=title_run())])


def test_ties_are_not_undefeated_but_are_unbeaten():
    led = ledger(results="w" * 13 + "t", seed=1)
    k = keys([led])
    assert "unbeaten_regular" in k and "undefeated_regular" not in k and "perfect_season" not in k


def test_undefeated_is_not_awarded_before_the_regular_season_ends():
    led = ledger(results="w" * 10)
    assert not keys([led]) & {"undefeated_regular", "perfect_season"}
    prog = [i for i in ga.evaluate([led]) if i["key"] == "perfect_season"][0]
    assert not prog["unlocked"] and prog["progress"]["text"] == "10-0, 4 games left"


def test_winless_and_tank_commander():
    led = ledger(results="l" * 14, rank=12, top_pick={"is_you": True, "n": 1}, champion="5", result="missed")
    items = {i["key"]: i for i in ga.evaluate([led]) if i["unlocked"]}
    assert "winless" in items and "The #1 pick is yours" in items["winless"]["detail"] and "tank_commander" in items
    assert items["winless"]["tone"] == "bad"
    # winless without the top pick: no tank commander
    plain = ledger(results="l" * 14, rank=12, top_pick={"is_you": False, "n": 1}, champion="5", result="missed")
    assert "winless" in keys([plain]) and "tank_commander" not in keys([plain])


def test_worst_to_first_and_first_to_worst_need_a_comparable_previous_season():
    last = ledger(1, "l" * 10 + "w" * 4, rank=12, champion="5", result="missed")
    best = ledger(2, "w" * 14, rank=1, champion="5", result="missed")
    assert "worst_to_first" in keys([last, best])
    assert "first_to_worst" in keys([best, ledger(3, "l" * 12 + "w" * 2, rank=12, champion="5", result="missed")])
    assert "worst_to_first" not in keys([ledger(1, "w" * 14, rank=2, champion="5", result="missed"), best])


def test_back_to_back_and_three_peat_and_dynasty():
    def champ(no):
        return ledger(no, "w" * 10 + "l" * 4, result="champion", champion="me", seed=2, rank=2, playoff=title_run())
    assert "back_to_back" not in keys([champ(1)])
    assert "back_to_back" in keys([champ(1), champ(2)]) and "three_peat" not in keys([champ(1), champ(2)])
    three = keys([champ(1), champ(2), champ(3)])
    assert "three_peat" in three and "back_to_back" in three  # the second title earned its own badge on the way
    ids = {i["id"] for i in ga.evaluate([champ(1), champ(2), champ(3)]) if i["unlocked"]}
    assert "back_to_back:2" in ids and "three_peat:3" in ids and "back_to_back:3" not in ids
    items = {i["id"]: i for i in ga.evaluate([champ(i) for i in range(1, 4)]) if i["unlocked"]}
    assert "dynasty_3" in items and items["dynasty_3"]["rarity"] == "epic" and items["dynasty_3"]["season_no"] == 3
    # a title, a miss, then a title is not back-to-back
    assert "back_to_back" not in keys([champ(1), ledger(2, "w" * 7 + "l" * 7, result="missed", champion="5"), champ(3)])


def test_comeback_year_and_free_fall():
    a = ledger(1, "w" * 4 + "l" * 10, champion="5", result="missed")
    assert "comeback_year" in keys([a, ledger(2, "w" * 9 + "l" * 5, champion="5", result="missed")])
    assert "comeback_year" not in keys([a, ledger(2, "w" * 7 + "l" * 7, champion="5", result="missed")])
    assert "free_fall" in keys([ledger(1, "w" * 11 + "l" * 3, champion="5", result="missed"), ledger(2, "w" * 5 + "l" * 9, champion="5", result="missed")])


def test_streak_tiers_count_regular_season_only_and_stop_at_a_loss():
    k = {i["key"]: i for i in ga.evaluate([ledger(results="w" * 5 + "l" + "w" * 8)]) if i["unlocked"]}
    assert k["win_streak"]["rarity"] == "rare" and k["win_streak"]["detail"].startswith("8 wins")  # the 5-run before the loss is not the best
    five = {i["key"]: i for i in ga.evaluate([ledger(results="w" * 5 + "l" * 2 + "w" * 2 + "l" * 5)]) if i["unlocked"]}
    assert five["win_streak"]["rarity"] == "common" and five["loss_streak"]["rarity"] == "common"
    ten = {i["key"]: i for i in ga.evaluate([ledger(results="l" + "w" * 10 + "l" * 3)]) if i["unlocked"]}
    assert ten["win_streak"]["rarity"] == "epic" and ten["win_streak"]["week"] == 11
    assert "loss_streak" not in ten  # 3 losses is nothing
    # a tie breaks a streak
    assert "win_streak" not in keys([ledger(results="wwwwtwwww" + "l" * 5)])


def test_blowout_closest_win_and_ties_in_margin():
    weeks = "wwww"
    led = ledger(results=weeks)
    led["weeks"][0] = wk(1, "w", 150.0, 70.0)
    led["weeks"][1] = wk(2, "w", 100.05, 100.0)
    k = {i["key"]: i for i in ga.evaluate([led]) if i["unlocked"]}
    assert k["blowout"]["rarity"] == "epic" and k["closest_win"]["rarity"] == "epic"
    # a loss is never a nail-biter win
    lost = ledger(results="l")
    lost["weeks"][0] = wk(1, "l", 99.9, 100.0)
    assert "closest_win" not in keys([lost])


def test_underdog_needs_the_lowest_seed_and_the_title():
    led = ledger(results="w" * 8 + "l" * 6, result="champion", champion="me", seed=6, rank=6, playoff=[wk(15, "w", kind="playoff", rnd=1), wk(16, "w", kind="playoff", rnd=2), wk(17, "w", kind="playoff", rnd=3)])
    assert "underdog" in keys([led])
    led["seed"] = 5
    assert "underdog" not in keys([led])


def test_heartbreaker_is_a_lost_title_game_by_under_three():
    po = [wk(15, "bye"), wk(16, "w", kind="playoff", rnd=2), wk(17, "l", 120.0, 121.5, kind="playoff", rnd=3)]
    led = ledger(results="w" * 11 + "l" * 3, result="runner_up", champion="5", seed=1, playoff=po)
    items = {i["key"]: i for i in ga.evaluate([led]) if i["unlocked"]}
    assert "heartbreaker" in items and items["heartbreaker"]["tone"] == "bad" and items["heartbreaker"]["week"] == 17
    po[2] = wk(17, "l", 120.0, 123.5, kind="playoff", rnd=3)
    assert "heartbreaker" not in keys([ledger(results="w" * 11 + "l" * 3, result="runner_up", champion="5", seed=1, playoff=po)])


def test_byes_never_count_as_games_or_streak_breaks():
    led = ledger(results="w" * 14, result="champion", champion="me", seed=1, playoff=title_run())
    assert [w["res"] for w in led["weeks"]][14] == "bye"
    assert ga.evaluate([led])  # the bye row has no points and must not crash any rule
    assert sum(1 for w in led["weeks"] if w["res"] == "w") == 16


def test_record_week_requires_history_and_beating_every_team():
    led = ledger(results="w" * 14, tops=[[i + 1, 130.0, "5"] for i in range(14)])
    led["weeks"][9] = wk(10, "w", 175.0, 100.0)
    led["league_top"][9] = [10, 175.0, "me"]
    assert "record_week" in keys([led])
    led["weeks"][9] = wk(10, "w", 129.0, 100.0)
    for i, w in enumerate(led["weeks"]):
        w["pts"] = min(w["pts"], 129.0)
    assert "record_week" not in keys([led])
    early = ledger(results="www", tops=[[1, 100.0, "me"], [2, 101.0, "me"], [3, 102.0, "me"]])
    assert "record_week" not in keys([early])  # nothing to beat yet
    prior = ledger(1, "w" * 14, champion="5", result="missed", tops=[[i + 1, 160.0, "5"] for i in range(14)])
    this = ledger(2, "w" * 3, tops=[[1, 150.0, "me"]] + [[i + 2, 100.0, "5"] for i in range(2)])
    this["weeks"][0] = wk(1, "w", 200.0, 90.0)
    assert "record_week" in keys([prior, this])


def test_perfect_lineup_counts_weeks_and_ignores_missing_data():
    led = ledger(results="w" * 14)
    led["bench_left"] = {"2": 0.0, "5": 0.04, "7": 3.0}
    item = [i for i in ga.evaluate([led]) if i["key"] == "perfect_lineup"][0]
    assert item["rarity"] == "common" and item["week"] == 2
    led["bench_left"] = {str(i): 0.0 for i in range(1, 6)}
    assert [i for i in ga.evaluate([led]) if i["key"] == "perfect_lineup"][0]["rarity"] == "epic"
    led["bench_left"] = {}
    assert "perfect_lineup" not in keys([led])


def test_mvp_roy_trade_shark_and_waiver_wizard():
    led = ledger(results="w" * 14, champion="5", result="missed")
    led["mvp"] = {"pid": "p1", "name": "Star", "pos": "WR", "pts": 280.0, "is_you": True}
    led["roy"] = {"pid": "p2", "name": "Rook", "pos": "RB", "pts": 150.0, "is_you": True}
    led["trades"] = [{"week": 4, "got_pts": 220.0, "sent_pts": 100.0, "net": 120.0, "pid": "p3", "name": "Got", "pos": "QB", "reach": [6, 9, None]}]
    led["waivers"] = [{"week": 3, "pts": 110.0, "pid": "p4", "name": "Wire", "pos": "TE", "reach": [5, 8, None]}]
    k = {i["key"]: i for i in ga.evaluate([led]) if i["unlocked"]}
    assert k["mvp_season"]["player"]["id"] == "p1" and k["roy"]["player"]["id"] == "p2"
    assert k["trade_shark"]["rarity"] == "rare" and k["trade_shark"]["week"] == 9  # dated to the week it reached the tier
    assert k["waiver_wizard"]["rarity"] == "rare" and k["waiver_wizard"]["week"] == 8
    led["mvp"]["is_you"] = led["roy"]["is_you"] = False
    led["trades"][0]["net"] = 39.0
    led["waivers"][0]["pts"] = 20.0
    assert not keys([led]) & {"mvp_season", "roy", "trade_shark", "waiver_wizard"}


def test_career_ladders_date_each_milestone_and_show_progress():
    seasons = [ledger(n, "w" * 10 + "l" * 4, champion="5", result="missed", seed=2) for n in range(1, 4)]
    items = {i["id"]: i for i in ga.evaluate(seasons)}
    assert items["career_wins_10"]["unlocked"] and items["career_wins_10"]["season_no"] == 1 and items["career_wins_10"]["week"] == 10
    assert items["career_wins_25"]["unlocked"] and items["career_wins_25"]["season_no"] == 3
    nxt = items["career_wins_50"]
    assert not nxt["unlocked"] and nxt["progress"] == {"current": 30, "target": 50, "text": "30 of 50 wins"}
    assert items["career_seasons_3"]["unlocked"] and items["playoff_streak_3"]["unlocked"]
    assert items["playoff_streak_5"]["progress"]["current"] == 3


def test_week_view_banners_and_new_unlocks():
    led = ledger(results="w" * 10)
    view = ga.week_view([led], ga.evaluate([led]), 10)
    assert view["milestones"][0]["headline"] == "WIN #10, still perfect" and "10-0" in view["milestones"][0]["sub"] + view["milestones"][0]["headline"]
    assert {i["id"] for i in view["new"]} == {"career_wins_10", "win_streak:1"}
    losing = ledger(results="w" * 4 + "l" + "w" * 6)
    banner = ga.week_view([losing], ga.evaluate([losing]), 11)["milestones"]
    assert [(b["kind"], b["headline"], b["sub"]) for b in banner] == [("win_number", "WIN #10", "Now 10-1.")]
    assert ga.week_view([losing], ga.evaluate([losing]), 5)["milestones"] == []  # a loss week with wins on the board is quiet
    tank = ledger(results="l" * 5)
    assert ga.week_view([tank], ga.evaluate([tank]), 5)["milestones"][0]["kind"] == "winless_watch"
    done = ledger(results="w" * 14, result="champion", champion="me", seed=1, playoff=title_run())
    final = ga.week_view([done], ga.evaluate([done]), 17)
    assert "perfect_season" in {i["key"] for i in final["new"]}
    assert ga.week_view([], [], 1) == {"new": [], "milestones": []}


def test_no_unlock_has_a_missing_date_and_every_item_is_json_safe():
    items = ga.evaluate([ledger(1, "w" * 14, result="champion", champion="me", seed=1, playoff=title_run()), ledger(2, "l" * 14, rank=12, champion="5", result="missed")])
    json.dumps(items, allow_nan=False)
    for i in items:
        assert {"id", "key", "rarity", "tone", "icon", "name", "detail", "unlocked", "season_label"} <= set(i)
        assert i["rarity"] in ("common", "rare", "epic")
        if i["unlocked"]:
            assert i["at"] is not None and i["week"] is not None
        else:
            assert i["progress"]


def test_season_label_uses_the_shared_form():
    items = ga.evaluate([ledger(3, "w" * 14, result="champion", champion="me", seed=1, playoff=title_run())])
    assert any(i["season_label"] == "S3 2028" for i in items if i["unlocked"])


# ---------------------------------------------------------------- real games


@pytest.fixture(scope="module")
def run():
    return _complete(Run())


def test_derivation_is_read_only_and_digest_neutral(run):
    before, seq = run.state.digest(), run.state.seq
    events = copy.deepcopy(run.em.events)
    a, _ = ga.fold_ledgers(run.root, run.em.events)
    b, _ = ga.fold_ledgers(run.root, run.em.events)
    assert a == b and run.state.digest() == before and run.state.seq == seq and events == run.em.events
    assert "achievements" not in run.state.to_dict()


def test_fold_matches_the_state_for_the_open_season_and_covers_every_season(run):
    ledgers, moves = ga.fold_ledgers(run.root, run.em.events)
    assert [l["season_no"] for l in ledgers] == [1, 2, 3]
    cur = ga.ledger_from_state(run.root, run.state, moves)
    assert cur == ledgers[-1]
    me = run.state.seasons[0]["you"]
    assert (ledgers[0]["w"], ledgers[0]["l"], ledgers[0]["rank"]) == (me["wins"], me["losses"], me["rank"])
    assert all(l["complete"] for l in ledgers)
    json.dumps(ledgers, allow_nan=False)


def test_old_save_without_any_new_fields_derives_the_same(run):
    """An old save has only events: strip every display-only field from the stored recaps and the answer is unchanged."""
    events = copy.deepcopy(run.em.events)
    for ev in events:
        if ev["type"] == "week_advanced":
            for row in ev["payload"]["recap"].get("standings") or []:
                row.pop("rank_prev", None), row.pop("rank_delta", None)
            g = ev["payload"]["recap"].get("your_game") or {}
            g.pop("proj", None)
    assert ga.fold_ledgers(run.root, events)[0] == ga.fold_ledgers(run.root, run.em.events)[0]
    assert ga.build(run.root, ga.fold_ledgers(run.root, events)[0]) == ga.build(run.root, ga.fold_ledgers(run.root, run.em.events)[0])


def test_resume_prefix_is_a_prefix_of_the_full_derivation(run):
    """Folding only the first season's events yields the same first ledger (what a mid-dynasty view sees)."""
    cut = next(i for i, e in enumerate(run.em.events) if e["type"] == "season_started")
    partial, _ = ga.fold_ledgers(run.root, run.em.events[:cut])
    full, _ = ga.fold_ledgers(run.root, run.em.events)
    assert partial[0]["w"] == full[0]["w"] and partial[0]["weeks"] == full[0]["weeks"] and partial[0]["complete"]


def test_a_season_in_progress_never_awards_season_end_badges(run):
    first_week = next(i for i, e in enumerate(run.em.events) if e["type"] == "week_advanced" and e["payload"]["week"] == 3)
    ledgers, _ = ga.fold_ledgers(run.root, run.em.events[: first_week + 1])
    items = ga.evaluate(ledgers)
    assert not any(i["unlocked"] and i["key"] in ("perfect_season", "winless", "mvp_season", "champion", "worst_to_first") for i in items)


def test_notifications_carry_unlocks_of_the_current_season(run):
    ledgers, _ = ga.fold_ledgers(run.root, run.em.events)
    items = ga.build(run.root, ledgers)["items"]
    out = derive(run.snap, run.state, run.em.events[-400:], 0, achievements=items)
    mine = [i for i in out["items"] if i["kind"] == "achievement"]
    again = derive(run.snap, run.state, run.em.events[-400:], 0, achievements=items)
    assert mine == [i for i in again["items"] if i["kind"] == "achievement"]  # ids are stable
    assert all(i["headline"].startswith("Achievement unlocked: ") and i["target"]["screen"] == "achievements" for i in mine)
    assert derive(run.snap, run.state, run.em.events[-400:], 0)["items"] == [i for i in out["items"] if i["kind"] != "achievement"]


# ----------------------------------------------------------------------- API


def _api_game():
    from tests.test_sim_game_api import advance, finish_draft, hdr, make_app, new_game

    client, backend, _ = make_app()
    gid = new_game(client)["game"]["id"]
    finish_draft(client, gid)
    return client, backend, gid, advance, hdr


def _cold(backend, gid):
    from modules.sim.game_store import GameStore

    store = GameStore(backend)
    snap, _state = store.load_game("pro", gid, store.get_game("pro", gid))
    return ga.build(snap.root, ga.fold_ledgers(snap.root, store.load_events("pro", gid, 0))[0])


def test_every_advance_carries_a_week_view_and_the_cache_matches_a_cold_fold():
    client, backend, gid, advance, hdr = _api_game()
    for _ in range(20):
        body = advance(client, gid)
        ach = body["achievements"]
        assert {"items", "counts", "new", "milestones"} <= set(ach)
        json.dumps(ach, allow_nan=False)
        assert all(i["unlocked"] and i["season_no"] == 1 for i in ach["new"])
        assert {k: v for k, v in ach.items() if k in ("items", "counts")} == _cold(backend, gid)
        if body["game"]["status"] == "complete":
            break
        assert client.get(f"/v1/sim/games/{gid}/home", headers=hdr()).json()["achievements"]["items"] == ach["items"]
    res = client.get(f"/v1/sim/games/{gid}/result", headers=hdr()).json()
    assert res["achievements"]["items"] == ach["items"]
    assert "achievements" not in res["result"]  # presentation only: never part of the stored result
    assert "achievements" not in json.dumps(backend.tables["sim_games"][0]["result"])


def test_notifications_list_unlocks_with_stable_ids():
    client, backend, gid, advance, hdr = _api_game()
    for _ in range(20):
        if advance(client, gid)["game"]["status"] == "complete":
            break
    first = client.get(f"/v1/sim/games/{gid}/notifications", headers=hdr()).json()["items"]
    again = client.get(f"/v1/sim/games/{gid}/notifications", headers=hdr()).json()["items"]
    assert first == again
    unlocked = [i for i in _cold(backend, gid)["items"] if i["unlocked"]]
    mine = [i for i in first if i["kind"] == "achievement"]
    if unlocked:
        assert mine and all(i["target"]["screen"] == "achievements" for i in mine)


def test_replayed_week_reports_only_that_weeks_unlocks_and_undo_rebuilds_the_cache():
    client, backend, gid, advance, hdr = _api_game()
    first = advance(client, gid)
    advance(client, gid)
    advance(client, gid)
    again = advance(client, gid, week=1)
    assert again["replayed"] and again["achievements"]["new"] == [i for i in first["achievements"]["new"] if i["week"] == 1]
    assert client.post(f"/v1/sim/games/{gid}/revert-week", headers=hdr()).json()["reverted"] == 0
    nxt = advance(client, gid)
    assert {k: v for k, v in nxt["achievements"].items() if k in ("items", "counts")} == _cold(backend, gid)

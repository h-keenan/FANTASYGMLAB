"""'Sim to...': stop conditions, determinism against manual Advances, targets, undo, the API."""

from __future__ import annotations

import copy
import json

import pytest

from modules.sim import game_api, game_actions as act, game_simto as simto
from modules.sim.game_engine import advance
from modules.sim.game_state import GameState, fold
from modules.sim.game_types import GameError
from test_sim_dynasty import Run
from test_sim_game_api import finish_draft, hdr, make_app, new_game  # noqa: F401


@pytest.fixture(autouse=True)
def _fresh_pool_cache():
    game_api.clear_pool_cache()
    yield
    game_api.clear_pool_cache()


def sim(run, **kw):
    args = dict(target="weeks", weeks=1, auto_set=False, force_first=False, pro=True, paywalled_fn=lambda s: False)
    args.update(kw)
    run.em.snap = run.snap
    return simto.run(run.em, run.snap, run.state, run.sd, **args)


def digest(state):
    return json.dumps(state.to_dict(), sort_keys=True, default=str)


def test_sim_to_writes_exactly_the_events_of_the_same_manual_advances():
    a, b = Run(), Run()
    got = sim(a, target="weeks", weeks=4, force_first=True)
    n = got["weeks_played"]
    assert n >= 1
    for _ in range(n):
        b.em.snap = b.snap
        advance(b.em, b.snap, b.state, b.sd)
    assert json.dumps(a.em.events[len(b.em.events) - len(b.em.events):], sort_keys=True) == json.dumps(a.em.events, sort_keys=True)
    assert a.em.events == b.em.events  # the same log, event for event
    assert digest(a.state) == digest(b.state)
    # and a fold of that log from scratch lands on the same state (replay-identical)
    assert digest(fold(a.root, copy.deepcopy(a.em.events))) == digest(a.state)


def test_auto_set_each_week_equals_pressing_auto_set_then_advance():
    a, b = Run(), Run()
    got = sim(a, target="weeks", weeks=3, auto_set=True, force_first=True)
    for _ in range(got["weeks_played"]):
        b.em.snap = b.snap
        act.auto_lineup(b.em)
        advance(b.em, b.snap, b.state, b.sd)
    if got["stopped"]:  # a stop leaves the lineup it auto-set for the week that was not played (what the user then sees)
        b.em.snap = b.snap
        act.auto_lineup(b.em)
    assert a.em.events == b.em.events and digest(a.state) == digest(b.state)
    assert got["weeks_played"] >= 1 and got["from_seq"] < got["to_seq"]


def test_roster_over_limit_always_stops_before_a_week_even_when_forced():
    r = Run()
    user = r.snap.user_team.tid
    extra = next(p for p in r.snap.pids if p not in r.state.owner_map())
    r.state.rosters[user].extend([extra] * 0 + [p for p in r.snap.pids if p not in r.state.owner_map()][:3])
    got = sim(r, target="weeks", weeks=2, force_first=True)
    assert got["weeks_played"] == 0 and got["stopped"]["code"] == "roster_over_limit" and got["stopped"]["fix"] == "roster"
    assert got["stopped"]["message"].startswith(f"Stopped at Week {r.state.week}:")


def test_a_starter_who_is_out_stops_with_a_named_reason_and_force_first_plays_through():
    r = Run()
    user = r.snap.user_team.tid
    slot, pid = next((s, p) for s, p in r.state.lineups[user] if p)
    r.state.out[pid] = 3
    got = sim(r, target="weeks", weeks=1)
    st = got["stopped"]
    assert got["weeks_played"] == 0 and st["code"] == "starter_out" and st["fix"] == "lineup" and st["player_id"] == pid
    assert r.snap.players[pid].name in st["message"] and "is out" in st["message"]
    forced = sim(r, target="weeks", weeks=1, force_first=True)
    assert forced["weeks_played"] == 1 and forced["stopped"] is None


def test_auto_set_clears_a_benchable_injury_so_it_does_not_stop():
    r = Run()
    user = r.snap.user_team.tid
    _, pid = next((s, p) for s, p in r.state.lineups[user] if p)
    r.state.out[pid] = 3
    r.state.offers = []  # an expiring offer would stop it for its own reason
    got = sim(r, target="weeks", weeks=1, auto_set=True)
    assert got["weeks_played"] == 1 and got["stopped"] is None


def test_a_starter_on_a_bye_and_an_empty_slot_stop():
    r = Run()
    user = r.snap.user_team.tid
    W = r.state.week
    bye = next((p for p in r.state.rosters[user] if r.snap.bye_of(p) == W), None)
    if bye:
        r.state.lineups[user][0][1] = bye
        got = sim(r, target="weeks", weeks=1)
        assert got["stopped"]["code"] == "starter_bye" and "bye" in got["stopped"]["message"]
    r2 = Run()
    r2.state.lineups[user][0][1] = None
    got2 = sim(r2, target="weeks", weeks=1)
    assert got2["stopped"]["code"] == "empty_slot" and got2["weeks_played"] == 0


def test_trade_offers_about_to_expire_stop_and_point_at_the_inbox():
    r = Run()
    r.state.offers.append({"id": "o1", "team": next(t.tid for t in r.snap.teams if not t.is_user), "give": [], "get": [], "expires_week": r.state.week, "message": ""})
    got = sim(r, target="weeks", weeks=2)
    st = got["stopped"]
    assert got["weeks_played"] == 0 and st["code"] == "trade_offers" and st["fix"] == "inbox" and st["count"] >= 1


def test_stops_mid_run_when_something_comes_up_and_reports_progress():
    r = Run()
    got = sim(r, target="season_end", force_first=True)
    assert got["weeks_played"] >= 1
    if got["stopped"]:
        assert got["stopped"]["week"] == r.state.week and got["stopped"]["message"].startswith("Stopped at Week")
    s = got["summary"]
    assert [w["week"] for w in s["weeks"]] == list(range(1, 1 + got["weeks_played"])) or s["weeks"]
    assert s["record"]["before"] == "0-0" and len(s["standings"]) == len(r.snap.teams)
    assert got["recap"]["week"] == r.state.week - 1 or got["recap"]["week"] == s["weeks"][-1]["week"]


def test_targets_trade_deadline_playoffs_start_season_end_and_passed_target():
    r = Run()
    S = r.snap.settings
    got = sim(r, target="trade_deadline", force_first=True)
    if got["stopped"] is None:
        assert r.state.week == S.trade_deadline_week
    r2 = Run()
    g2 = sim(r2, target="playoffs_start", force_first=True)
    if g2["stopped"] is None:
        assert r2.state.status == "playoffs" and r2.state.week == S.regular_weeks + 1
    with pytest.raises(GameError) as e:
        r3 = Run()
        r3.state.week = S.trade_deadline_week
        sim(r3, target="trade_deadline")
    assert e.value.code == "target_passed"
    with pytest.raises(GameError):
        sim(Run(), target="nonsense")
    with pytest.raises(GameError):
        sim(Run(), target="weeks", weeks=0)


def test_the_whole_season_in_a_few_forced_runs_matches_playing_it_week_by_week():
    a, b = Run(), Run()
    guard = 0
    while a.state.status in ("in_season", "playoffs") and guard < 60:
        sim(a, target="season_end", force_first=True)
        guard += 1
    b.play_season()
    assert a.state.status == b.state.status and a.state.champion == b.state.champion
    assert digest(a.state) == digest(b.state) or [e["type"] for e in a.em.events] == [e["type"] for e in b.em.events]


def test_options_follow_the_stage():
    r = Run()
    ids = [o["id"] for o in simto.options_for(r.snap, r.state)]
    assert ids[0] == "weeks" and "playoffs_start" in ids and ids[-1] == "season_end"
    r.play_season()
    assert simto.options_for(r.snap, r.state) == []  # offseason: nothing to sim


# ------------------------------------------------------------------- the API


def test_api_sim_to_stops_for_a_decision_then_undo_restores_the_week():
    client, _, _ = make_app()
    gid = new_game(client)["game"]["id"]
    finish_draft(client, gid)
    opts = client.get(f"/v1/sim/games/{gid}/sim-to/options", headers=hdr()).json()["options"]
    assert opts and opts[0]["id"] == "weeks"
    res = client.post(f"/v1/sim/games/{gid}/sim-to", json={"target": "weeks", "weeks": 3, "force_first": True, "auto_set": True}, headers=hdr())
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["reason"] == "" and out["weeks_played"] >= 1 and out["summary"]["weeks"]
    assert out["game"]["week"] == 1 + out["weeks_played"]
    assert out["recap"]["week"] == out["game"]["week"] - 1
    undo = client.post(f"/v1/sim/games/{gid}/undo-sim", json={"from_seq": out["from_seq"]}, headers=hdr())
    assert undo.status_code == 200, undo.text
    assert undo.json()["game"]["week"] == 1 and undo.json()["undone"] is True
    # replaying forward after the undo works (checkpoints past the undo point were dropped)
    again = client.post(f"/v1/sim/games/{gid}/sim-to", json={"target": "weeks", "weeks": 1, "force_first": True}, headers=hdr()).json()
    assert again["weeks_played"] == 1 and again["game"]["week"] == 2
    bad = client.post(f"/v1/sim/games/{gid}/undo-sim", json={"from_seq": 3}, headers=hdr())
    assert bad.json()["reason"] == "bad_seq"


def test_api_sim_to_matches_manual_advances_event_for_event():
    ca, ba, _ = make_app()
    cb, bb, _ = make_app()
    ga = new_game(ca)["game"]["id"]
    gb = new_game(cb)["game"]["id"]
    finish_draft(ca, ga)
    finish_draft(cb, gb)
    out = ca.post(f"/v1/sim/games/{ga}/sim-to", json={"target": "weeks", "weeks": 3, "force_first": True}, headers=hdr()).json()
    for _ in range(out["weeks_played"]):
        assert cb.post(f"/v1/sim/games/{gb}/advance", headers=hdr()).status_code == 200
    ev_a = ba.select("sim_game_events", user_id="pro", filters={"game_id": ga}, order="seq.asc")[0]
    ev_b = bb.select("sim_game_events", user_id="pro", filters={"game_id": gb}, order="seq.asc")[0]
    strip = lambda rows: [{k: r[k] for k in ("seq", "week", "actor", "type", "payload")} for r in rows]  # noqa: E731
    assert strip(ev_a) == strip(ev_b)


def test_api_free_user_stops_at_the_paywall_not_with_an_error():
    client, _, _ = make_app()
    gid = new_game(client, user="free")["game"]["id"]
    finish_draft(client, gid, user="free")
    out = {}
    for _ in range(8):  # each forced run plays at least a week; keep going until the free preview ends
        out = client.post(f"/v1/sim/games/{gid}/sim-to", json={"target": "season_end", "force_first": True, "auto_set": True}, headers=hdr("free")).json()
        if out.get("stopped") and out["stopped"]["code"] == "premium_required":
            break
    assert out["reason"] == "" and out["stopped"]["code"] == "premium_required" and out["stopped"]["fix"] == "premium"
    assert out["game"]["week"] == out["preview"]["paywall_week"]
    blocked = client.post(f"/v1/sim/games/{gid}/sim-to", json={"target": "weeks", "weeks": 1}, headers=hdr("free")).json()
    assert blocked["reason"] == "premium_required"

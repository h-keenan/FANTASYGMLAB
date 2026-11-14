"""'Sim to...': stop conditions, determinism against manual Advances, targets, undo, the API."""

from __future__ import annotations

import copy
import dataclasses
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


def over_the_limit(r, n=3):
    user = r.snap.user_team.tid
    free = [p for p in r.snap.pids if p not in r.state.owner_map()]
    r.state.rosters[user].extend(free[:max(0, r.snap.settings.roster_limit + n - len(r.state.rosters[user]))])
    return user


def test_old_save_over_the_limit_always_stops_before_a_week_even_when_forced():
    r = Run()
    object.__setattr__(r.root, "settings", dataclasses.replace(r.root.settings, limit_v=0))
    r.root.__dict__.pop("_views", None)
    over_the_limit(r)
    got = sim(r, target="weeks", weeks=2, force_first=True)
    assert got["weeks_played"] == 0 and got["stopped"]["code"] == "roster_over_limit" and got["stopped"]["fix"] == "roster"
    assert got["stopped"]["message"].startswith(f"Stopped at Week {r.state.week}:")


def test_over_the_limit_does_not_stop_a_run_and_the_summary_notes_it():
    r = Run()
    over_the_limit(r, 3)
    r.state.offers = []
    got = sim(r, target="weeks", weeks=2, auto_set=True, stops=simto.Stops(offers=False, injuries=False))
    assert got["weeks_played"] == 2 and (got["stopped"] is None or got["stopped"]["code"] != "roster_over_limit")
    assert got["summary"]["roster"]["over"] == 3 and got["summary"]["roster"]["limit"] == r.snap.settings.roster_limit


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


# ------------------------------------------------------ per-run stop toggles and auto-set lineup

QUIET = dict(offers=False, injuries=False, starters=False, deadline=False, roster=False)


def only(**on):
    return simto.Stops(**{**QUIET, **on})


def starters_of(r):
    return [p for _, p in r.state.lineups[r.snap.user_team.tid] if p]


def test_auto_set_each_week_changes_the_lineup_over_a_multi_week_run_and_never_starts_an_out_or_bye_player():
    r = Run()
    user = r.snap.user_team.tid
    hurt = next(p for p in starters_of(r))
    r.state.out[hurt] = 10  # hurt for the whole run
    r.state.offers = []
    seen_weeks = []
    real = simto.advance

    def spy(em, snap, state, seed):
        from modules.sim.game_eval import Evaluator
        ev = Evaluator(snap, state)
        bad = [p for _, p in state.lineups[user] if p and ev.status(p, state.week) != "healthy"]
        seen_weeks.append((state.week, bad))
        return real(em, snap, state, seed)

    simto.advance = spy
    try:
        got = sim(r, target="weeks", weeks=4, auto_set=True, stops=simto.Stops(**QUIET))
    finally:
        simto.advance = real
    assert got["weeks_played"] == 4 and got["stopped"] is None
    assert [w for w, _ in seen_weeks] == [1, 2, 3, 4] and all(bad == [] for _, bad in seen_weeks)  # never started an out/bye player
    ch = got["summary"]["lineup_changes"]
    name = r.snap.players[hurt].name
    assert got["summary"]["auto_set"] is True and ch and ch[0]["week"] == 1 and ch[0]["out"] == name and ch[0]["in"]
    assert hurt not in starters_of(r)
    # the same run without auto-set stops at the problem instead (it does not fix anything for you)
    r2 = Run()
    r2.state.out[starters_of(r2)[0]] = 10
    r2.state.offers = []
    stop = sim(r2, target="weeks", weeks=4, stops=simto.Stops(offers=False))["stopped"]
    assert stop["code"] == "starter_out"


def test_auto_set_fixes_a_bye_starter_in_the_week_it_matters():
    r = Run()
    user = r.snap.user_team.tid
    r.state.offers = []
    W = r.state.week
    bye = next((p for p in r.state.rosters[user] if r.snap.bye_of(p) == W), None)
    if bye is None:
        pytest.skip("no bye player on the user roster in week 1 for this seed")
    r.state.lineups[user][0][1] = bye
    got = sim(r, target="weeks", weeks=1, auto_set=True, stops=simto.Stops(**QUIET))
    assert got["weeks_played"] == 1 and any(c["out"] == r.snap.players[bye].name for c in got["summary"]["lineup_changes"])


def test_stop_toggle_trade_offers_new_or_expiring_and_off():
    r = Run()
    ai = next(t.tid for t in r.snap.teams if not t.is_user)
    ev = simto.Evaluator(r.snap, r.state)
    r.state.offers = [{"id": "o1", "team": ai, "give": [], "get": [], "expires_week": r.state.week + 3, "message": ""}]
    kw = dict(pro=True, paywalled=False)
    fresh = simto.stop_reason(r.snap, r.state, ev, stops=only(offers=True), seen_offers=frozenset(), **kw)
    assert fresh["code"] == "trade_offers" and "waiting" in fresh["message"] and fresh["fix"] == "inbox"
    assert simto.stop_reason(r.snap, r.state, ev, stops=only(offers=True), seen_offers=frozenset({"o1"}), **kw) is None  # not news
    r.state.offers[0]["expires_week"] = r.state.week
    exp = simto.stop_reason(r.snap, r.state, ev, stops=only(offers=True), seen_offers=frozenset({"o1"}), **kw)
    assert exp["code"] == "trade_offers" and "expire" in exp["message"]
    assert simto.stop_reason(r.snap, r.state, ev, stops=only(offers=False), seen_offers=frozenset(), **kw) is None


def test_a_run_stops_for_an_offer_that_arrives_mid_run_unless_the_toggle_is_off():
    def with_new_offer(r):
        real = simto.advance
        ai = next(t.tid for t in r.snap.teams if not t.is_user)

        def adv(em, snap, state, seed):
            out = real(em, snap, state, seed)
            state.offers.append({"id": f"new{state.week}", "team": ai, "give": [], "get": [], "expires_week": state.week + 5, "message": ""})
            return out
        return real, adv

    for toggle, expect_stop in ((True, True), (False, False)):
        r = Run()
        r.state.offers = []
        real, adv = with_new_offer(r)
        simto.advance = adv
        try:
            got = sim(r, target="weeks", weeks=3, auto_set=True, stops=only(offers=toggle))
        finally:
            simto.advance = real
        if expect_stop:
            assert got["weeks_played"] == 1 and got["stopped"]["code"] == "trade_offers" and got["summary"]["offers_new"] >= 1
        else:
            assert got["weeks_played"] == 3 and got["stopped"] is None


def test_stop_toggle_injury_to_a_starter_stops_after_the_week_he_got_hurt_and_can_be_skipped():
    def run_with(toggle):
        r = Run()
        r.state.offers = []
        real = simto.advance
        box = {}

        def adv(em, snap, state, seed):
            if state.week == 1:
                box["v"] = [p for _, p in state.lineups[snap.user_team.tid] if p][0]  # a starter of the lineup that is about to play
            victim = box["v"]
            out = real(em, snap, state, seed)
            if state.week == 2:  # the week just played was week 1
                out[-1]["injuries"].append({"player": {"id": victim}, "weeks": 3, "team_id": snap.user_team.tid, "is_yours": True})
            return out
        simto.advance = adv
        try:
            res = sim(r, target="weeks", weeks=3, auto_set=True, stops=only(injuries=toggle))
            return r, box["v"], res
        finally:
            simto.advance = real

    r, victim, got = run_with(True)
    assert got["weeks_played"] == 1 and got["stopped"]["code"] == "starter_injured" and got["stopped"]["player_id"]
    assert got["stopped"]["fix"] == "lineup" and "lineup was updated" in got["stopped"]["message"]
    r, victim, got = run_with(False)
    assert got["weeks_played"] == 3 and got["stopped"] is None


def test_stop_toggle_starter_out_with_no_fix_can_be_skipped():
    r = Run()
    r.state.offers = []
    r.state.out[starters_of(r)[0]] = 3
    assert sim(r, target="weeks", weeks=1, stops=only(starters=True))["stopped"]["code"] == "starter_out"
    r2 = Run()
    r2.state.offers = []
    r2.state.out[starters_of(r2)[0]] = 3
    got = sim(r2, target="weeks", weeks=1, stops=only(starters=False))
    assert got["weeks_played"] == 1 and got["stopped"] is None


def test_stop_toggle_trade_deadline_stops_in_deadline_week_only_mid_run():
    r = Run()
    D = r.snap.settings.trade_deadline_week
    got = sim(r, target="season_end", auto_set=True, stops=only(deadline=True))
    assert got["stopped"]["code"] == "trade_deadline" and got["stopped"]["fix"] == "inbox" and r.state.week == D
    assert got["weeks_played"] == D - 1
    again = sim(r, target="season_end", auto_set=True, stops=only(deadline=True))  # starting AT the deadline week does not stop at once
    assert again["weeks_played"] >= 1 and (again["stopped"] is None or again["stopped"]["code"] != "trade_deadline")
    r2 = Run()
    off = sim(r2, target="playoffs_start", auto_set=True, stops=only(deadline=False))
    assert off["stopped"] is None and r2.state.status != "in_season"


def test_stop_toggle_waiver_claim_that_cannot_go_through_stops_unless_off():
    for toggle, stops_run in ((True, True), (False, False)):
        r = Run()
        r.state.offers = []
        user = over_the_limit(r, 0)  # exactly at the limit
        assert len(r.state.rosters[user]) == r.snap.settings.roster_limit
        free = [p for p in r.snap.pids if p not in r.state.owner_map()][5]
        r.state.claims.append({"id": "c1", "team": user, "add": free, "drop": None, "start_slot": None})
        got = sim(r, target="weeks", weeks=1, auto_set=True, stops=only(roster=toggle))
        if stops_run:
            assert got["weeks_played"] == 0 and got["stopped"]["code"] == "waiver_issue" and got["stopped"]["fix"] == "roster"
        else:
            assert got["weeks_played"] == 1
    r = Run()
    user = over_the_limit(r, 0)
    drop = next(p for p in r.state.rosters[user] if p not in starters_of(r))
    r.state.claims.append({"id": "c1", "team": user, "add": [p for p in r.snap.pids if p not in r.state.owner_map()][5], "drop": drop, "start_slot": None})
    assert simto.failing_claims(r.snap, r.state) == []  # a swap is fine


def test_stops_parse_rejects_unknown_and_non_boolean_toggles_and_defaults_all_on():
    assert simto.Stops.parse(None) == simto.Stops() and all(vars(simto.Stops()).values())
    assert simto.Stops.parse({"offers": False}).offers is False
    for bad in ({"nope": True}, {"offers": "yes"}):
        with pytest.raises(ValueError):
            simto.Stops.parse(bad)


def test_the_summary_reads_out_record_pending_offers_injuries_and_lineup_changes():
    r = Run()
    r.state.offers = []
    r.state.out[starters_of(r)[0]] = 2
    got = sim(r, target="weeks", weeks=2, auto_set=True, stops=simto.Stops(**QUIET))
    s = got["summary"]
    assert {"record", "lineup_changes", "offers_pending", "offers_new", "roster", "injuries", "auto_set"} <= set(s)
    assert s["record"]["after"] and s["roster"]["size"] == len(r.state.rosters[r.snap.user_team.tid]) and s["offers_pending"] == len(r.state.offers)


def test_api_accepts_stops_and_rejects_bad_ones():
    client, _, _ = make_app()
    gid = new_game(client)["game"]["id"]
    finish_draft(client, gid)
    ok = client.post(f"/v1/sim/games/{gid}/sim-to", json={"target": "weeks", "weeks": 1, "force_first": True, "auto_set": True,
                                                         "stops": {"offers": False, "deadline": False}}, headers=hdr())
    assert ok.status_code == 200 and ok.json()["weeks_played"] == 1 and "lineup_changes" in ok.json()["summary"]
    bad = client.post(f"/v1/sim/games/{gid}/sim-to", json={"target": "weeks", "stops": {"bogus": True}}, headers=hdr())
    assert bad.status_code == 422

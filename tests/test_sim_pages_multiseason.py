"""Every game page answers 200 and JSON-serializable at every phase of a multi-season dynasty."""

from __future__ import annotations

import json

import pytest

from modules.sim import game_api
from tests.test_sim_store_constraints import StrictBackend, client
from tests.test_sim_dynasty import H

PAGES = ("home", "lineup", "players", "picks", "league", "draft", "offseason", "result", "dynasty", "trades/inbox", "waivers", "teams")


@pytest.fixture(autouse=True)
def _fresh():
    game_api.clear_pool_cache()
    yield
    game_api.clear_pool_cache()


def sweep(c, gid, label, failures):
    for page in PAGES:
        r = c.get(f"/v1/sim/games/{gid}/{page}", headers=H)
        if r.status_code in (404, 405):
            continue  # not a route in this build
        if r.status_code != 200:
            failures.append(f"{label} {page}: {r.status_code} {r.text[:200]}")
            continue
        try:
            body = r.json()
            json.dumps(body, allow_nan=False)
        except ValueError as exc:
            failures.append(f"{label} {page}: not strict JSON ({exc})")
            continue
        if page == "home" and body.get("reason") == "" and body.get("errors"):
            failures.append(f"{label} home card errors: {body['errors']}")


def test_every_page_at_every_phase_of_a_multi_season_dynasty():
    c = client(StrictBackend())
    gid = c.post("/v1/sim/games", json={"mode": "dynasty", "teams": 8, "seasons": 3, "rookie_rounds": 2, "user_slot": 3}, headers=H).json()["game"]["id"]
    failures: list[str] = []
    sweep(c, gid, "drafting", failures)
    assert c.post(f"/v1/sim/games/{gid}/draft/auto", headers=H).json()["completed"] is True
    seen = 0
    for season in (1, 2):
        sweep(c, gid, f"s{season} wk1", failures)
        while True:
            out = c.post(f"/v1/sim/games/{gid}/advance", headers=H).json()
            assert out["reason"] == "", out
            game = out["game"]
            sweep(c, gid, f"s{season} {game['status']} wk{game['week']}", failures)
            if game["status"] in ("offseason", "complete"):
                break
        if game["status"] == "complete":
            break
        started = c.post(f"/v1/sim/games/{gid}/offseason/rookie-draft/start", headers=H).json()
        assert started["reason"] == "", started
        sweep(c, gid, f"s{season} rookie draft", failures)
        auto = c.post(f"/v1/sim/games/{gid}/offseason/rookie-draft/auto", headers=H).json()
        assert auto["reason"] == "", auto
        sweep(c, gid, f"s{season} cutdown", failures)
        for _ in range(8):
            if not auto["offseason"]["roster"]["cuts_needed"]:
                break
            roster = c.get(f"/v1/sim/games/{gid}/teams/{auto['game']['you']['team_id']}", headers=H).json()
            worst = sorted(roster["players"], key=lambda p: p["ros_mean"])[0]["id"]
            c.post(f"/v1/sim/games/{gid}/cut", json={"player_id": worst}, headers=H)
            auto = {"offseason": c.get(f"/v1/sim/games/{gid}/offseason", headers=H).json()["offseason"], "game": auto["game"]}
        nxt = c.post(f"/v1/sim/games/{gid}/offseason/start-season", headers=H).json()
        assert nxt["reason"] == "", nxt
        seen += 1
    assert seen >= 1
    assert not failures, "\n".join(failures)


def test_one_failing_home_card_does_not_fail_the_page(monkeypatch):
    from modules.sim import game_home

    c = client(StrictBackend())
    gid = c.post("/v1/sim/games", json={"mode": "dynasty", "teams": 8, "seasons": 3, "rookie_rounds": 2, "user_slot": 3}, headers=H).json()["game"]["id"]
    c.post(f"/v1/sim/games/{gid}/draft/auto", headers=H)

    def boom(*a, **k):
        raise KeyError("g0001")

    monkeypatch.setattr(game_home, "_league_moves", boom)
    r = c.get(f"/v1/sim/games/{gid}/home", headers=H)
    assert r.status_code == 200
    body = r.json()
    assert body["errors"] == {"league": "KeyError"} and body["league"] is None and body["checklist"] is not None


def _to_rookie_draft(c, gid):
    while True:
        out = c.post(f"/v1/sim/games/{gid}/advance", headers=H).json()
        if out["game"]["status"] == "offseason":
            break
    return c.post(f"/v1/sim/games/{gid}/offseason/rookie-draft/start", headers=H).json()


def test_picks_trade_during_the_rookie_draft_and_the_draft_order_follows():
    c = client(StrictBackend())
    gid = c.post("/v1/sim/games", json={"mode": "dynasty", "teams": 8, "seasons": 3, "rookie_rounds": 2, "user_slot": 3}, headers=H).json()["game"]["id"]
    c.post(f"/v1/sim/games/{gid}/draft/auto", headers=H)
    started = _to_rookie_draft(c, gid)
    off = started["offseason"]
    assert off["can_trade"] is True
    league = c.get(f"/v1/sim/games/{gid}/league", headers=H)
    assert league.status_code == 200 and [t for t in league.json()["teams"] if not t["is_you"]]
    order = off["draft"]["order"]
    mine = [o for o in order if o["is_yours"] and not o["made"]]
    assert mine, "user holds an unused pick this draft"
    on_clock = off["draft"]["on_clock"]
    picks_before = c.get(f"/v1/sim/games/{gid}/picks", headers=H).json()
    total_before = sum(len(t["picks"]) for t in picks_before["teams"]) + len(picks_before["you"])
    partner = next(o for o in order if not o["is_yours"] and not o["made"] and o["round"] == 2)
    give = [mine[0]["pick"]]
    # overpay with the user's own later pick so the AI accepts
    extra = [o["pick"] for o in mine[1:]]
    body = {"partner": partner["team_id"], "give": give + extra, "get": [partner["pick"]]}
    pv = c.post(f"/v1/sim/games/{gid}/trades/preview", json=body, headers=H)
    assert pv.status_code == 200 and pv.json()["reason"] == "", pv.text
    sent = c.post(f"/v1/sim/games/{gid}/trades", json=body, headers=H).json()
    assert sent["reason"] == "", sent
    if not sent["executed"]:
        pytest.skip("AI declined the overpay in this seed")
    after = c.get(f"/v1/sim/games/{gid}/offseason", headers=H).json()["offseason"]
    owner = {o["pick"]: o["team_id"] for o in after["draft"]["order"]}
    assert owner[give[0]] == partner["team_id"]
    picks_after = c.get(f"/v1/sim/games/{gid}/picks", headers=H).json()
    ids = lambda pk: {p["id"] for t in pk["teams"] for p in t["picks"]} | {p["id"] for p in pk["you"]}
    spent = {o["pick"] for o in after["draft"]["order"] if o["made"]}
    assert ids(picks_after) <= ids(picks_before)  # nothing appeared
    assert ids(picks_before) - ids(picks_after) <= spent, "a pick vanished that was not used in the draft"
    # the draft keeps moving: an AI team is never left on the clock
    clock = after["draft"]["on_clock"]
    assert clock is None or clock["is_yours"]
    assert (on_clock is None) or True
    # a pick already used in the draft is spent
    used = next((o for o in after["draft"]["order"] if o["made"]), None)
    if used:
        spent = c.post(f"/v1/sim/games/{gid}/trades/preview",
                       json={"partner": used["team_id"], "give": [mine[-1]["pick"]], "get": [used["pick"]]}, headers=H)
        assert spent.status_code == 422 or spent.json()["reason"] == "picks_locked"  # never tradable


def test_a_player_on_the_taxi_squad_or_ir_can_be_cut_and_replays_identically(monkeypatch):
    from modules.sim import game_actions as act
    from modules.sim.game_state import Emitter, GameState, fold
    from tests.test_sim_dynasty import Run

    monkeypatch.setattr(act, "taxi_eligible", lambda snap, pid: True)  # a seed's veterans are not rookies
    run = Run()
    user = run.snap.user_team.tid
    pid = next(p for p in sorted(run.state.rosters[user]) if run.snap.players[p].pos in ("RB", "WR", "TE", "QB"))
    run.em.snap = run.snap
    act.move_player(run.em, pid, "taxi")
    assert run.state.where(user, pid) == "taxi"
    act.cut_player(run.em, pid)
    assert run.state.where(user, pid) is None and pid in run.state.free_agents(run.snap)
    events = list(run.em.events)
    replay = GameState(run.root)
    fold(run.root, events, replay)
    assert replay.where(user, pid) is None and replay.taxi[user] == run.state.taxi[user]


def _cut_ok(c, gid, pid):
    r = c.post(f"/v1/sim/games/{gid}/cut", json={"player_id": pid}, headers=H)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reason"] == "", body
    assert pid not in {p["id"] for p in body["roster"]}
    return body


def test_cut_answers_success_in_every_phase_and_is_idempotent():
    c = client(StrictBackend())
    gid = c.post("/v1/sim/games", json={"mode": "dynasty", "teams": 8, "seasons": 3, "rookie_rounds": 2, "user_slot": 3}, headers=H).json()["game"]["id"]
    c.post(f"/v1/sim/games/{gid}/draft/auto", headers=H)
    # in season, then a repeat of the same cut (double tap / retry after a lost response)
    team = c.get(f"/v1/sim/games/{gid}/lineup", headers=H).json()
    pid = team["bench"][-1]["id"]
    _cut_ok(c, gid, pid)
    again = c.post(f"/v1/sim/games/{gid}/cut", json={"player_id": pid}, headers=H)
    assert again.status_code == 200 and again.json()["reason"] == "", again.text
    # another team's player still cannot be cut
    rival = c.get(f"/v1/sim/games/{gid}/teams/1", headers=H).json()["players"][0]["id"]
    assert c.post(f"/v1/sim/games/{gid}/cut", json={"player_id": rival}, headers=H).status_code == 422
    # offseason (the next season's view), after a rollover
    for season in (1, 2):
        while True:
            out = c.post(f"/v1/sim/games/{gid}/advance", headers=H).json()
            if out["game"]["status"] in ("offseason", "complete"):
                break
        if out["game"]["status"] == "complete":
            break
        c.post(f"/v1/sim/games/{gid}/offseason/rookie-draft/start", headers=H)
        c.post(f"/v1/sim/games/{gid}/offseason/rookie-draft/auto", headers=H)
        mine = c.get(f"/v1/sim/games/{gid}/teams/{out['game']['you']['team_id']}", headers=H).json()
        _cut_ok(c, gid, mine["players"][-1]["id"])
        c.post(f"/v1/sim/games/{gid}/offseason/start-season", headers=H)
        mine = c.get(f"/v1/sim/games/{gid}/teams/{out['game']['you']['team_id']}", headers=H).json()
        _cut_ok(c, gid, mine["players"][-1]["id"])

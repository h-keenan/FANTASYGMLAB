"""Player and team history derived from the event log (pure, replay-safe, no model change)."""

from __future__ import annotations

import copy

import pytest

from modules.sim import game_api, game_history as hist
from modules.sim.game_state import GameState, fold
from test_sim_dynasty import Run
from test_sim_game_api import advance, finish_draft, hdr, make_app, new_game  # noqa: F401


@pytest.fixture(autouse=True)
def _fresh_pool_cache():
    game_api.clear_pool_cache()
    yield
    game_api.clear_pool_cache()


def played():
    run = Run()
    run.play_season()
    run.offseason()
    run.play_season()
    return run


def test_history_never_changes_state_and_is_a_pure_function_of_the_events():
    run = played()
    events = copy.deepcopy(run.em.events)
    before = GameState(run.root)
    fold(run.root, events, before)
    pid = next(iter(run.state.rosters[run.root.user_team.tid]))
    a = hist.player_history(run.root, events, pid)
    b = hist.player_history(run.root, copy.deepcopy(events), pid)
    assert a == b
    assert events == run.em.events  # the fold read, never wrote
    assert before.seq == run.state.seq


def test_a_drafted_player_knows_his_round_pick_team_and_season_lines():
    run = played()
    drafts = [e for e in run.em.events if e["type"] == "draft_pick"]
    pick = next(e for e in drafts if e["payload"]["round"] == 3)
    pid, team = pick["payload"]["pid"], pick["payload"]["team"]
    h = hist.player_history(run.root, run.em.events, pid)
    o = h["origin"]
    assert o["kind"] == "drafted" and o["draft"] == "league" and o["round"] == 3 and o["pick"] == pick["payload"]["n"] + 1
    assert o["team_id"] == team and o["season"] == 1 and o["team_name"] == run.root.team(team).name
    assert h["name"] == run.root.players[pid].name
    if h["seasons"]:
        s1 = h["seasons"][0]
        assert s1["season"] == 1 and s1["games"] > 0 and s1["points"] > 0 and s1["ppg"] == pytest.approx(s1["points"] / s1["games"], abs=0.06)
        assert sum(t["games"] for t in s1["teams"]) == s1["games"]


def test_trades_claims_and_cuts_are_recorded_in_order_with_both_sides():
    run = played()
    trades = [e for e in run.em.events if e["type"] == "trade" and e["payload"]["give"] and e["payload"]["get"]]
    assert trades, "the seeded league makes AI trades"
    ev = trades[0]
    p = ev["payload"]
    pid = next(x for x in p["give"] if not x.startswith("pick:"))
    h = hist.player_history(run.root, run.em.events, pid)
    moved = [e for e in h["entries"] if e["kind"] == "traded" and e["week"] == ev["week"]]
    assert moved, h["entries"]
    m = moved[0]
    assert m["from_team"]["team_id"] == p["team_a"] and m["to_team"]["team_id"] == p["team_b"]
    assert {a["id"] for a in m["with_assets"]} == set(p["get"])
    weeks = [(e["season"], e["week"]) for e in h["entries"] if not e["offseason"]]
    assert weeks == sorted(weeks)
    claims = [e for e in run.em.events if e["type"] == "waiver_result" and e["payload"]["ok"]]
    c = claims[0]["payload"]
    hc = hist.player_history(run.root, run.em.events, c["add"])
    assert any(e["kind"] == "claimed" and e["team_id"] == c["team"] for e in hc["entries"])
    cuts = [e for e in run.em.events if e["type"] in ("cut", "drop")]
    if cuts:
        hd = hist.player_history(run.root, run.em.events, cuts[0]["payload"]["pid"])
        assert any(e["kind"] in ("cut", "dropped") for e in hd["entries"])


def test_a_rookie_carries_class_year_round_pick_and_the_original_pick_owner():
    run = played()
    picks = [e for e in run.em.events if e["type"] == "rookie_pick"]
    assert picks
    traded = next((e for e in picks if e["payload"]["orig"] != e["payload"]["team"]), picks[0])
    p = traded["payload"]
    h = hist.player_history(run.root, run.em.events, p["pid"])
    o = h["origin"]
    assert o["kind"] == "drafted" and o["draft"] == "rookie" and o["offseason"] is True
    assert o["round"] == p["round"] and o["pick"] == p["n"] + 1 and o["team_id"] == p["team"]
    assert o["class_year"] and o["class_year"] > 2000 or run.root.settings.start_year == 0
    if p["orig"] != p["team"]:
        assert o["via"]["team_id"] == p["orig"]
    assert h["name"] == run.root.season_view(2).players[p["pid"]].name  # a rookie is only in a later pool


def test_team_history_has_draft_class_record_by_season_and_moves():
    run = played()
    tid = run.root.user_team.tid
    th = hist.team_history(run.root, run.em.events, tid)
    assert len(th["draft"]) == run.root.settings.rounds and [d["round"] for d in th["draft"]] == sorted(d["round"] for d in th["draft"])
    assert [s["season"] for s in th["seasons"]] == [1, 2]
    s1 = th["seasons"][0]
    assert s1["wins"] + s1["losses"] + s1["ties"] == run.root.settings.regular_weeks
    assert th["rookie_drafts"] and th["rookie_drafts"][0]["picks"]
    every = [hist.team_history(run.root, run.em.events, t.tid) for t in run.root.teams]
    moves = [m for t in every for m in t["moves"]]
    assert moves and all("season" in m and "week" in m for m in moves)
    assert {"trade", "claim"} & {m["kind"] for m in moves}
    assert sum(1 for t in run.root.teams if any(s["champion"] for s in hist.team_history(run.root, run.em.events, t.tid)["seasons"])) >= 1


def test_history_endpoints_read_the_stored_events():
    client, _, _ = make_app()
    gid = new_game(client)["game"]["id"]
    finish_draft(client, gid)
    mine = client.get(f"/v1/sim/games/{gid}/lineup", headers=hdr()).json()
    pid = next(s["player"]["id"] for s in mine["slots"] if s["player"])
    res = client.get(f"/v1/sim/games/{gid}/players/{pid}/history", headers=hdr())
    assert res.status_code == 200, res.text
    h = res.json()
    assert h["reason"] == "" and h["origin"]["kind"] == "drafted" and h["origin"]["round"] >= 1 and h["origin"]["team_id"]
    assert client.get(f"/v1/sim/games/{gid}/players/nope/history", headers=hdr()).status_code == 404
    team_id = h["origin"]["team_id"]
    th = client.get(f"/v1/sim/games/{gid}/teams/{team_id}/history", headers=hdr()).json()
    assert th["draft"] and th["team_name"]
    assert client.get(f"/v1/sim/games/{gid}/teams/zzz/history", headers=hdr()).status_code == 404

"""The trade block: the user's block, the AI teams' blocks, block-aware offers, the version gate."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from modules.sim import game_actions as act, game_api, game_block as blk, game_engine as engine
from modules.sim.game_ai import TradeDesk
from modules.sim.game_eval import Evaluator
from modules.sim.game_state import Emitter
from modules.sim.game_types import GameError
from modules.sim.types import is_pick_id
from test_sim_dynasty import Run
from test_sim_game_api import finish_draft, hdr, make_app, new_game  # noqa: F401


@pytest.fixture(autouse=True)
def _fresh_pool_cache():
    game_api.clear_pool_cache()
    yield
    game_api.clear_pool_cache()


def old_save(run):
    """A game from before the block: the setting is absent, so nothing about the engine may change."""
    object.__setattr__(run.root, "settings", replace(run.root.settings, block_v=0))
    run.root.__dict__.pop("_views", None)
    return run


def user_assets(run):
    user = run.snap.user_team.tid
    ev = Evaluator(run.snap, run.state)
    players = sorted((p for p in run.state.rosters[user] if run.snap.players[p].pos in ("QB", "RB", "WR", "TE")), key=lambda p: (-ev.ros_mean(p), p))
    return user, players


def play(run, weeks):
    for _ in range(weeks):
        run.em.snap = run.snap
        engine.advance(run.em, run.snap, run.state, run.sd)


# ---------------------------------------------------------------- the version gate


def test_a_game_without_a_block_plays_exactly_as_before_and_new_games_carry_the_flag():
    assert Run().root.settings.block_v == 2 and Run().root.settings.to_dict()["block_v"] == 2
    old = old_save(Run())
    assert "block_v" not in old.root.settings.to_dict()  # an old save serializes as it always did
    a, b = Run(), old_save(Run())
    play(a, 8)
    play(b, 8)
    assert json.dumps(a.em.events, sort_keys=True) == json.dumps(b.em.events, sort_keys=True)  # same events: the block changes nothing until used
    assert a.state.digest() == b.state.digest()  # the empty block stays out of the digest
    user, players = user_assets(old)
    with pytest.raises(GameError) as e:
        blk.set_block(Emitter(old.state, old.snap), players[0], True)
    assert e.value.code == "block_unavailable"
    assert blk.user_block(old.snap, old.state) == {} and blk.block_index(old.snap, old.state, Evaluator(old.snap, old.state), old.sd) == {}


def with_gates(run, *, ai_v=None, block_v=None):
    """Flip one version gate on an existing game (the three gates are independent settings)."""
    changes = {k: v for k, v in (("ai_v", ai_v), ("block_v", block_v)) if v is not None}
    object.__setattr__(run.root, "settings", replace(run.root.settings, **changes))
    run.root.__dict__.pop("_views", None)
    return run


@pytest.mark.parametrize("ai_v", [0, 1])
def test_golden_digest_a_dynasty_v3_game_with_block_v1_and_nothing_blocked_equals_the_block_free_engine(ai_v):
    """The version gates (dynasty_v, ai_v, block_v) are independent: with block_v 1 and an empty block, a dynasty_v 3 game
    plays two full seasons and an offseason event for event and digest for digest like the same game with block_v 0 (the
    engine as it was before the block), whatever ai_v is."""
    a, b = with_gates(Run(), ai_v=ai_v, block_v=1), with_gates(Run(), ai_v=ai_v, block_v=0)
    assert a.root.settings.dynasty_v == 3 and a.root.settings.block_v == 1 and b.root.settings.block_v == 0
    for run in (a, b):
        run.play_season()
        run.offseason()
        run.play_season()
    assert json.dumps(a.em.events, sort_keys=True) == json.dumps(b.em.events, sort_keys=True)
    assert a.state.digest() == b.state.digest()
    assert {t["type"] for t in a.em.events} >= {"rookie_pick", "season_started"}  # it really crossed a season boundary
    assert not any(e["type"] == "block_set" or e["payload"].get("via_block") for e in a.em.events)


def test_the_block_settings_serialize_independently_of_the_other_gates():
    r = Run()
    d = r.root.settings.to_dict()
    assert d["dynasty_v"] == 3 and d["ai_v"] == 1 and d["block_v"] == 2
    for ai_v, block_v in ((0, 0), (0, 1), (1, 0), (1, 1)):
        g = with_gates(Run(), ai_v=ai_v, block_v=block_v).root.settings
        back = type(g).from_dict(g.to_dict()) if hasattr(type(g), "from_dict") else g
        assert (back.dynasty_v, back.ai_v, back.block_v) == (3, ai_v, block_v)
        assert ("ai_v" in g.to_dict()) == bool(ai_v) and ("block_v" in g.to_dict()) == bool(block_v)


# ---------------------------------------------------------------- the user's block


def test_set_block_rules_roundtrip_and_digest():
    r = Run()
    user, players = user_assets(r)
    em = Emitter(r.state, r.snap)
    before = r.state.digest()
    blk.set_block(em, players[0], True, "RB")
    assert blk.user_block(r.snap, r.state) == {players[0]: {"looking_for": "RB", "week": r.state.week}}
    assert r.state.digest() != before
    blk.set_block(em, players[0], False)
    assert blk.user_block(r.snap, r.state) == {} and r.state.block == {}
    n = len(em.events)
    blk.set_block(em, players[0], False)  # taking off what is not there writes nothing
    assert len(em.events) == n
    other = next(p for t, ps in r.state.rosters.items() if t != user for p in ps)
    for bad, exc in ((other, ValueError), ("not-a-player", ValueError)):
        with pytest.raises(exc):
            blk.set_block(em, bad, True)
    with pytest.raises(ValueError):
        blk.set_block(em, players[0], True, "K")
    k = next((p for p in r.state.rosters[user] if r.snap.players[p].pos in ("K", "DEF")), None)
    if k:
        with pytest.raises(ValueError):
            blk.set_block(em, k, True)
    for p in players[: blk.MAX_BLOCK_ITEMS]:
        blk.set_block(em, p, True)
    extra = next(p for p in r.state.rosters[user] if p not in blk.user_block(r.snap, r.state) and r.snap.players[p].pos in ("QB", "RB", "WR", "TE"))
    with pytest.raises(GameError) as e:
        blk.set_block(em, extra, True)
    assert e.value.code == "block_full"


def test_blocked_assets_that_leave_the_team_drop_off_the_block_and_picks_can_be_blocked():
    r = Run()
    user, players = user_assets(r)
    em = Emitter(r.state, r.snap)
    blk.set_block(em, players[0], True)
    act.cut_player(em, players[0])
    assert players[0] not in blk.user_block(r.snap, r.state)  # derived from ownership: no extra event
    pick = r.state.picks_of(user)[0]
    blk.set_block(em, pick, True, "WR")
    assert pick in blk.user_block(r.snap, r.state)
    with pytest.raises(ValueError):
        blk.set_block(em, next(p for p, o in r.state.pick_owner.items() if o != user), True)


# ---------------------------------------------------------------- the AI blocks


def blocks(r, week=None):
    if week is not None:
        r.state.week = week
    ev = Evaluator(r.snap, r.state)
    return blk.league_blocks(r.snap, r.state, ev, r.sd)


def test_ai_blocks_are_deterministic_capped_realistic_and_vary_by_week():
    r = Run()
    play(r, 1)
    a, b = blocks(r), blocks(r)
    assert a == b and a  # a pure function of (state, week, seed)
    seen_stances = set()
    union = set()
    for week in range(2, 11):
        got = blocks(r, week)
        union |= {b["team_id"] for b in got}
        assert len(got) <= blk.MAX_AI_BLOCKS_PER_WEEK  # the shelf stays readable
        for b in got:
            assert b["team_id"] != r.snap.user_team.tid and 1 <= len(b["items"]) <= blk.MAX_AI_BLOCK_ITEMS
            seen_stances.add(b["stance"])
            for it in b["items"]:
                pid = it["id"]
                assert pid in r.state.holdings(b["team_id"]) or pid in r.state.picks_of(b["team_id"])
                if not is_pick_id(pid):
                    assert r.snap.players[pid].pos in ("QB", "RB", "WR", "TE")
            if b["stance"] == "rebuilding" and not any(i["why"] == "Shopping a bench piece" for i in b["items"]):
                assert all(r.snap.players[i["id"]].age >= 28 for i in b["items"])
            if b["stance"] == "contending":
                assert all(i["why"] in ("Selling depth", "Moving a pick", "Shopping a bench piece") for i in b["items"])
            assert b["looking_for"] in (None, "QB", "RB", "WR", "TE")
    assert {"contending", "rebuilding"} & seen_stances
    assert len({tuple(sorted(i["id"] for b in blocks(r, w) for i in b["items"])) for w in range(2, 8)}) > 1  # the shelves change from week to week
    r.state.week = r.snap.settings.trade_deadline_week + 1
    assert blocks(r) == []  # no shopping once trades are closed


# ---------------------------------------------------------------- offers answer the block


def run_with_block(weeks=8, **kw):
    r = Run(**kw)
    user, players = user_assets(r)
    em = Emitter(r.state, r.snap)
    for p in players[:4]:
        blk.set_block(em, p, True)
    r.em.events.extend(em.events)
    return r, user


def test_offers_answer_the_block_under_the_normal_rules_and_are_capped():
    r, user = run_with_block()
    blocked_ever, via_total, weeks_with = set(), 0, 0
    for _ in range(9):
        if r.state.status != "in_season" or r.state.week > r.snap.settings.trade_deadline_week:
            break
        play(r, 1)
        offers = r.state.offers
        assert len(offers) <= engine.MAX_OFFERS_PER_WEEK
        via = [o for o in offers if o.get("via_block")]
        assert len(via) <= blk.MAX_BLOCK_OFFERS
        assert len({o["team"] for o in offers}) == len(offers)  # one per team
        desk = TradeDesk(Evaluator(r.snap, r.state), r.sd, r.state.week)
        for o in via:
            via_total += 1
            assert set(o["via_block"]) <= set(o["get"]) and set(o["via_block"]) <= set(blk.user_block(r.snap, r.state)) | blocked_ever | set(r.state.block)
            names = [r.snap.players[p].name for p in o["via_block"] if not is_pick_id(p)]
            assert all(n in o["message"] for n in names)  # the note only says what the deal contains
            # roster legality on both sides (the counter rule): neither side ends over the limit unless it already was
            assert desk.legal_for_counter(o["team"], o["give"], o["get"]) and desk.legal_for_counter(user, o["get"], o["give"])
            assert all(p in r.state.holdings(o["team"]) or p in r.state.picks_of(o["team"]) for p in o["give"])
            blocked_ever |= set(o["via_block"])
        weeks_with += bool(via)
    assert via_total >= 1 and weeks_with >= 1


def test_the_looking_for_hint_is_only_claimed_when_the_offer_really_sends_that_position():
    r = Run()
    user, players = user_assets(r)
    em = Emitter(r.state, r.snap)
    for p in players[:4]:
        blk.set_block(em, p, True, "WR")
    r.em.events.extend(em.events)
    for _ in range(9):
        if r.state.week > r.snap.settings.trade_deadline_week:
            break
        play(r, 1)
        for o in r.state.offers:
            if not o.get("via_block"):
                continue
            sends_wr = any(not is_pick_id(p) and r.snap.players[p].pos == "WR" for p in o["give"])
            assert ("looking for" in o["message"]) == sends_wr


def test_an_accepted_block_offer_executes_a_legal_trade():
    r, user = run_with_block()
    for _ in range(9):
        play(r, 1)
        via = [o for o in r.state.offers if o.get("via_block")]
        if via:
            o = via[0]
            from modules.sim.game_ai import TradeDesk as TD  # noqa: F401
            r.em.snap = r.snap
            before = len(r.state.rosters[user])
            act.respond_offer(r.em, TradeDesk(Evaluator(r.snap, r.state), r.sd), o["id"], "accept")
            assert len(r.state.rosters[user]) <= max(before, r.snap.settings.roster_limit)
            assert all(p in r.state.holdings(user) or p in r.state.picks_of(user) for p in o["give"])
            assert all(p not in r.state.holdings(user) for p in o["get"] if not is_pick_id(p))
            return
    pytest.skip("no block offer arose in this seed")


def test_with_nothing_blocked_the_offers_are_the_original_ones():
    a, b = Run(), old_save(Run())
    play(a, 6)
    play(b, 6)
    assert a.state.offers == b.state.offers and a.state.offer_keys == b.state.offer_keys


# ---------------------------------------------------------------- the API


def test_api_block_put_get_filter_rosters_and_inbox_flag():
    client, _, _ = make_app()
    gid = new_game(client)["game"]["id"]
    finish_draft(client, gid)
    got = client.get(f"/v1/sim/games/{gid}/block", headers=hdr()).json()
    assert got["enabled"] is True and got["mine"] == [] and got["max_items"] == blk.MAX_BLOCK_ITEMS
    lineup = client.get(f"/v1/sim/games/{gid}/lineup", headers=hdr()).json()
    pid = next(s["player"]["id"] for s in lineup["slots"] if s["player"] and s["player"]["pos"] in ("RB", "WR"))
    put = client.put(f"/v1/sim/games/{gid}/block", json={"asset_id": pid, "on": True, "looking_for": "QB"}, headers=hdr()).json()
    assert put["reason"] == "" and [m["asset"]["id"] for m in put["mine"]] == [pid] and put["mine"][0]["looking_for"] == "QB"
    rows = client.get(f"/v1/sim/games/{gid}/players", params={"status": "block", "page_size": 100}, headers=hdr()).json()["items"]
    assert any(r["id"] == pid and r["block"]["mine"] for r in rows)
    ros = client.get(f"/v1/sim/games/{gid}/league/rosters", headers=hdr()).json()["teams"]
    assert all("block" in t for t in ros)
    mine = next(t for t in ros if t["is_you"])
    assert next(p for p in mine["players"] if p["id"] == pid)["block"]["looking_for"] == "QB"
    sheet = client.get(f"/v1/sim/games/{gid}/teams/{mine['team_id']}", headers=hdr()).json()
    assert next(p for p in sheet["players"] if p["id"] == pid)["block"]["mine"] is True
    bad = client.put(f"/v1/sim/games/{gid}/block", json={"asset_id": "nope", "on": True}, headers=hdr())
    assert bad.status_code in (400, 422)
    off = client.put(f"/v1/sim/games/{gid}/block", json={"asset_id": pid, "on": False}, headers=hdr()).json()
    assert off["mine"] == []
    # the league's blocks list assets with their team's stated needs
    league = client.get(f"/v1/sim/games/{gid}/block", headers=hdr()).json()["league"]
    for b in league:
        assert b["items"] and set(b["needs"]) <= {"QB", "RB", "WR", "TE", "K", "DEF"}


# ----------------------------------------------------- block_v 2: assets that leave the team leave the block for good


def _reclaim(run, user, pid):
    run.em.emit(run.state.week, "engine", "waiver_result", team=user, add=pid, drop=None, ok=True, reason="", start_slot=None, claim_id=None)


def test_a_cut_player_is_off_the_block_even_when_he_comes_back():
    run = Run()
    assert run.root.settings.block_v == 2 and run.root.settings.block_forgets
    user, players = user_assets(run)
    pid = players[-1]
    blk.set_block(run.em, pid, True, "RB")
    assert pid in blk.user_block(run.snap, run.state)
    act.cut_player(run.em, pid)
    assert pid not in run.state.block  # forgotten in the state, not just filtered from the view
    _reclaim(run, user, pid)
    assert pid in run.state.rosters[user] and pid not in blk.user_block(run.snap, run.state)


def test_a_traded_player_and_a_spent_pick_leave_the_block():
    run = Run()
    user, players = user_assets(run)
    partner = next(t for t in run.snap.tids if t != user)
    mine, theirs = players[-1], next(p for p in run.state.rosters[partner] if run.snap.players[p].pos in ("RB", "WR"))
    pick = next(p for p, o in run.state.pick_owner.items() if o == user)
    blk.set_block(run.em, mine, True)
    blk.set_block(run.em, pick, True)
    act.execute_trade(run.em, user, partner, [mine, pick], [theirs], key="", source="user")
    assert mine not in run.state.block and pick not in run.state.block
    act.execute_trade(run.em, user, partner, [theirs], [mine, pick], key="", source="user")  # and back again
    assert mine in run.state.rosters[user] and not blk.user_block(run.snap, run.state)


def test_block_v1_saves_keep_the_derived_only_behaviour():
    run = Run()
    object.__setattr__(run.root, "settings", replace(run.root.settings, block_v=1))
    run.root.__dict__.pop("_views", None)
    user, players = user_assets(run)
    pid = players[-1]
    blk.set_block(run.em, pid, True)
    act.cut_player(run.em, pid)
    assert pid not in blk.user_block(run.snap, run.state) and pid in run.state.block  # filtered from the view, kept in the state
    _reclaim(run, user, pid)
    assert pid in blk.user_block(run.snap, run.state)  # the old resurrection, unchanged for old saves


def test_sim_to_rejects_an_unknown_target_and_silly_weeks():
    client, _, _ = make_app()
    gid = new_game(client)["game"]["id"]
    finish_draft(client, gid)
    for body in ({"target": "zz"}, {"target": "weeks", "weeks": 0}, {"target": "weeks", "weeks": 31}, {"target": "weeks", "weeks": -3}):
        res = client.post(f"/v1/sim/games/{gid}/sim-to", json=body, headers=hdr())
        assert res.status_code == 422, (body, res.text)
    assert "target must be one of" in client.post(f"/v1/sim/games/{gid}/sim-to", json={"target": "zz"}, headers=hdr()).json()["detail"]
    assert client.post(f"/v1/sim/games/{gid}/sim-to", json={"target": "weeks", "weeks": 1}, headers=hdr()).status_code == 200

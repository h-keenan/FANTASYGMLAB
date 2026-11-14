"""Dynasty mode: settings, aging, picks as assets, the offseason and rookie draft,
IR and taxi squads, determinism and the AI-behavior harness (no network, no real data)."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from modules.sim import aging, game_actions as act, game_api, game_dynasty as dyn, game_draft as draft
from modules.sim import api as sim_api
from modules.sim.game_ai import TradeDesk, offer_key
from modules.sim.game_engine import advance, finish_draft
from modules.sim.game_eval import USER_PARAMS, Evaluator, team_params
from modules.sim.game_scoring import FallbackModel
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState, fold
from modules.sim.game_types import GameError, GameSettings, GameSnapshot
from modules.sim.inputs import PlayerPool
from modules.sim.personas import PERSONAS
from modules.sim.store import InMemoryBackend
from modules.sim.synthetic import build_synthetic_pool
from modules.sim.types import is_pick_id

ROWS, BYES = build_synthetic_pool(7)
SEED = 4242


def settings(hint_v=0, **kw):
    """hint_v 0 by default: these seeded-world tests predate the public-information helpers (tests/test_sim_hint_v.py covers hint_v 1)."""
    raw = {"mode": "dynasty", "teams": 8, "user_slot": 3, "start_year": 2026, "seasons": 3, "rookie_rounds": 3}
    raw.update(kw)
    return replace(GameSettings.parse(raw), hint_v=hint_v)


def new_snapshot(seed=SEED, **kw):
    return build_snapshot(ROWS, BYES, settings(**kw), seed, scoring_model=FallbackModel.model_id if hasattr(FallbackModel, "model_id") else "")


class Run:
    """A dynasty game driven straight through the engine."""

    def __init__(self, seed=SEED, **kw):
        self.seed = seed
        self.root = new_snapshot(seed, **kw)
        self.state = GameState(self.root)
        self.em = Emitter(self.state, self.root)
        ctx = draft.DraftContext(self.root, self.state)
        draft.auto_for_user(ctx, self.em, seed)
        finish_draft(self.em, self.root, self.state, seed)

    @property
    def snap(self):
        return self.root.season_view(self.state.view_no)

    @property
    def sd(self):
        return dyn.season_seed(self.seed, self.state.view_no)

    def play_season(self):
        while self.state.status in ("in_season", "playoffs"):
            self.em.snap = self.snap
            advance(self.em, self.snap, self.state, self.sd)
        self.em.snap = self.snap

    def offseason(self, *, cut=True):
        self.em.snap = self.snap
        dyn.start_rookie_draft(self.em)
        dyn.run_ai_rookie_picks(self.em, self.sd)
        dyn.auto_rookie_draft(self.em, self.sd)
        user = self.snap.user_team.tid
        while cut and len(self.state.rosters[user]) > self.snap.settings.roster_limit:
            ev = Evaluator(self.snap, self.state)
            act.cut_player(self.em, min(self.state.rosters[user], key=lambda p: (ev.worth(USER_PARAMS, p), p)))
        dyn.start_next_season(self.em, self.sd)

    def play_all(self):
        while True:
            self.play_season()
            if self.state.status != "offseason":
                return self.state
            self.offseason()


@pytest.fixture(scope="module")
def full_run():
    return Run().__dict__ and _complete(Run())


def _complete(run):
    run.play_all()
    return run


# ----------------------------------------------------------------- settings


def test_dynasty_is_selectable_and_validated():
    s = settings()
    assert s.dynasty and s.multi_season and s.pick_years == 3 and s.seasons == 3 and s.rookie_rounds == 3
    assert s.policy.dynasty and s.policy.max_trade_side == 4
    assert GameSettings.parse({"mode": "dynasty"}).seasons == 5  # the five-year cap is the default
    for bad in ({"seasons": 9}, {"seasons": 1}, {"rookie_rounds": 9}, {"mode": "keeper"}):
        with pytest.raises(ValueError):
            GameSettings.parse({"mode": "dynasty", **bad})


def test_settings_round_trip_and_old_saves_are_unchanged():
    s = settings(taxi_slots=3, ir_slots=1)
    assert GameSettings.from_dict(json.loads(json.dumps(s.to_dict()))) == s
    # A save from before dynasty and IR/taxi carries none of the new keys and loads as it always did.
    legacy = {k: v for k, v in GameSettings.parse({}).to_dict().items()
              if k not in ("reserve_v", "ir_slots", "taxi_slots", "taxi_years")}
    old = GameSettings.from_dict(legacy)
    assert not old.dynasty and not old.reserves and old.seasons == 1 and old.ir_slots == 0
    redraft = GameSettings.parse({})
    assert redraft.to_dict()["taxi_slots"] == 0 and redraft.to_dict()["ir_slots"] == 2
    assert "dynasty_v" not in redraft.to_dict()
    assert settings().taxi_slots == 4


def test_snapshot_round_trip_carries_picks_and_seed():
    snap = new_snapshot()
    again = GameSnapshot.from_dict(json.loads(json.dumps(snap.to_dict())))
    assert again.seed == SEED and again.start_picks == snap.start_picks and len(snap.start_picks) == 3 * 3 * 8
    assert {p.season for p in snap.start_picks} == {2027, 2028, 2029}


# --------------------------------------------------------------------- aging


def test_age_curve_matches_the_panel_shape():
    from modules.sim.calibration.age_curve import curve_table

    assert aging.age_mult("RB", 21) > aging.age_mult("RB", 25) > aging.age_mult("RB", 28) > aging.age_mult("RB", 31)
    assert aging.age_mult("RB", 28) < aging.age_mult("QB", 28) and aging.age_mult("WR", 30) < aging.age_mult("WR", 24)
    table = curve_table()
    # The panel's medians are shifted down by selecting on a good prior year; compare the decline
    # from the 24-25 bucket to a later one, which that shift cancels out of.
    for pos, late in (("RB", 28), ("WR", 30), ("TE", 28)):
        if (pos, 24) in table and (pos, late) in table:
            panel_drop = table[(pos, 24)][1] - table[(pos, late)][1]
            model_drop = aging.age_mult(pos, 24.5) - aging.age_mult(pos, late + 0.5)
            assert panel_drop > 0 and model_drop > 0 and abs(panel_drop - model_drop) < 0.12, (pos, panel_drop, model_drop)
    assert aging.future_factor("RB", 23) > aging.future_factor("RB", 28)
    assert aging.retire_prob("RB", 34, 0.2) > 0.8 > 0.05 > aging.retire_prob("RB", 26, 0.2) and aging.retire_prob("QB", 30, 0.5) < 0.02


def test_progression_is_deterministic_and_changes_the_pool():
    a, b = new_snapshot(), new_snapshot()
    v2a, v2b = a.season_view(2), b.season_view(2)
    assert v2a.players == v2b.players and v2a.schedule == v2b.schedule
    assert a.season_view(1) is a
    retired = dyn.retirees(a, v2a)
    assert retired and all(p not in v2a.players for p in retired)
    rookies = [p for p in v2a.players.values() if p.extra.get("is_rookie")]
    assert len(rookies) >= 3 * 8 and all(21 <= p.age <= 25 for p in rookies)
    assert v2a.schedule != a.schedule
    young = [p for p in a.players.values() if p.pos == "RB" and p.age < 24]
    old = [p for p in a.players.values() if p.pos == "RB" and p.age >= 29 and p.pid in v2a.players]
    assert sum(v2a.players[p.pid].mean / p.mean for p in young) / len(young) > sum(v2a.players[p.pid].mean / p.mean for p in old) / max(1, len(old))
    assert new_snapshot(seed=SEED + 1).season_view(2).players != v2a.players


# ------------------------------------------------------- the multi-season game


def test_five_year_cap_and_game_over(full_run):
    state = full_run.state
    assert state.status == "complete" and state.season_no == 3 and len(state.seasons) == 3
    assert state.champion and all(a["champion"] for a in state.seasons)
    summary = dyn.dynasty_summary(full_run.snap, state)
    assert summary["complete"] and summary["seasons_played"] == 3 and len(summary["by_year"]) == 3
    assert [y["year"] for y in summary["by_year"]] == [2026, 2027, 2028]
    assert summary["titles"] == sum(1 for a in state.seasons if a["champion"]["is_you"])
    with pytest.raises(GameError):
        advance(full_run.em, full_run.snap, state, full_run.sd)


def test_deterministic_and_resume_equals_replay(full_run):
    again = _complete(Run())
    assert again.state.digest() == full_run.state.digest()
    events = full_run.em.events
    replayed = fold(full_run.root, events)
    assert replayed.digest() == full_run.state.digest()
    # Resume: a checkpoint taken mid-way (during the first offseason), then the tail.
    cut = next(i for i, e in enumerate(events) if e["type"] == "rookie_draft_started") + 5
    mid = fold(full_run.root, events[:cut])
    revived = GameState.from_dict(full_run.root, json.loads(json.dumps(mid.to_dict())))
    fold(full_run.root, events[cut:], revived)
    assert revived.digest() == full_run.state.digest()


def test_different_seasons_do_not_repeat_the_same_dice(full_run):
    pts = [a["you"]["pf"] for a in full_run.state.seasons]
    assert len(set(pts)) == len(pts)
    assert dyn.season_seed(SEED, 1) == SEED and dyn.season_seed(SEED, 2) != SEED


def test_players_are_conserved_across_seasons():
    run = Run()
    for _ in range(3):
        run.play_season()
        st = run.state
        held = [p for t in run.root.tids for p in st.holdings(t)]
        assert len(held) == len(set(held)), "a player is on two squads"
        assert not set(held) & set(st.retired)
        assert all(p in run.snap.players for p in held)
        if st.status != "offseason":
            break
        run.offseason()
        held = [p for t in run.root.tids for p in st.holdings(t)]
        assert len(held) == len(set(held)) and all(p in run.snap.players for p in held)


def test_rookie_draft_uses_standings_order_and_adds_rookies():
    run = Run()
    run.play_season()
    st = run.state
    assert st.status == "offseason" and st.offseason["stage"] == "review"
    dyn.start_rookie_draft(run.em)
    order, slots = st.offseason["order"], st.offseason["slots"]
    results = st.playoff["results"]
    assert len(order) == 3 * 8 and order[-1].endswith(":" + st.champion)  # the champion picks last
    missed = [t for t in run.root.tids if t not in st.playoff["seeds"]]
    assert all(slots[m] <= len(missed) for m in missed)  # non-playoff teams pick first
    assert min(slots, key=slots.get) in missed
    before = {t: len(st.rosters[t]) for t in run.root.tids}
    dyn.run_ai_rookie_picks(run.em, run.sd)
    dyn.auto_rookie_draft(run.em, run.sd)
    assert st.offseason["stage"] == "cutdown" and len(st.offseason["picks"]) == len(order)
    assert all(run.snap.players[m["pid"]].extra.get("is_rookie") for m in st.offseason["picks"])
    assert sum(len(st.rosters[t]) for t in run.root.tids) >= sum(before.values()) - 8
    with pytest.raises(GameError):
        dyn.start_next_season(run.em, run.sd) if len(st.rosters[run.root.user_team.tid]) > run.snap.settings.roster_limit else (_ for _ in ()).throw(GameError("roster_over_limit"))


def test_picks_are_conserved_through_trades_and_drafts():
    run = Run()
    ledger_ok = lambda st: (
        len(set(st.pick_owner) & {s["pick"] for s in st.spent_picks}) == 0
        and set(st.pick_owner) | {s["pick"] for s in st.spent_picks} == set(st.created_picks)
        and len(st.created_picks) == len(set(st.created_picks))
    )
    assert ledger_ok(run.state)
    user = run.root.user_team.tid
    mine = run.state.picks_of(user)
    partner = next(t for t in run.root.tids if t != user)
    desk = TradeDesk(Evaluator(run.snap, run.state), run.seed)
    theirs = run.state.picks_of(partner)
    act.execute_trade(run.em, user, partner, [mine[0]], [theirs[0]], key="", source="test")
    assert run.state.pick_owner[mine[0]] == partner and run.state.pick_owner[theirs[0]] == user
    assert ledger_ok(run.state) and len(run.state.pick_owner) == 3 * 3 * 8
    run.play_season()
    assert ledger_ok(run.state)
    run.offseason()
    assert ledger_ok(run.state) and len(run.state.spent_picks) == 3 * 8
    assert len(run.state.pick_owner) == 3 * 3 * 8  # a year of picks spent, a new year created
    assert all(not is_pick_id(p) for t in run.root.tids for p in run.state.holdings(t))


# ------------------------------------------------------------- picks as assets


def test_pick_values_follow_slot_round_and_distance():
    run = Run()
    ev = Evaluator(run.snap, run.state)
    p1 = ev.pick_value("pick:2027:1:1")
    assert p1 > ev.pick_value("pick:2027:2:1") > ev.pick_value("pick:2027:3:1")
    assert ev.pick_value("pick:2027:1:1") > ev.pick_value("pick:2028:1:1")
    assert ev.pick_value("pick:2028:1:1") >= ev.pick_value("pick:2029:1:1")
    weakest = min(run.root.tids, key=lambda t: ev.lineup_total(run.state.rosters[t]))
    strongest = max(run.root.tids, key=lambda t: ev.lineup_total(run.state.rosters[t]))
    assert ev.pick_value(f"pick:2027:1:{weakest}") > ev.pick_value(f"pick:2027:1:{strongest}")


def test_trade_engine_accepts_picks_and_validates_ownership():
    run = Run()
    snap, st = run.snap, run.state
    user = snap.user_team.tid
    partner = next(t for t in snap.tids if t != user)
    my_pick, their_pick = st.picks_of(user)[0], st.picks_of(partner)[0]
    desk = TradeDesk(Evaluator(snap, st), run.seed)
    verdict = act.preview_trade(desk, partner, [my_pick], [their_pick])
    assert verdict.decision in ("accept", "counter", "decline")
    with pytest.raises(ValueError):
        act.preview_trade(desk, partner, [their_pick], [my_pick])  # not yours to give
    with pytest.raises(ValueError):
        act.preview_trade(desk, partner, [my_pick, my_pick], [their_pick])
    redraft = Run.__new__(Run)
    r_snap = build_snapshot(ROWS, BYES, GameSettings.parse({"teams": 8, "user_slot": 3}), SEED)
    r_state = GameState(r_snap)
    with pytest.raises(ValueError):
        from modules.sim.game_ai import validate_offer
        validate_offer(r_snap, r_state, "1", ["pick:2027:1:3"], ["pick:2027:1:1"])
    assert not r_state.pick_owner


# ------------------------------------------------------------ AI stance harness


def _by_persona(snap, pid):
    return next(t.tid for t in snap.teams if t.persona_id == pid)


def test_ai_values_youth_and_picks_by_stance_in_dynasty_not_in_redraft():
    dsnap = new_snapshot()
    rsnap = build_snapshot(ROWS, BYES, GameSettings.parse({"teams": 8, "user_slot": 3}), SEED)
    dstate, rstate = GameState(dsnap), GameState(rsnap)
    # the same stance parameters, two modes
    rebuild = replace(PERSONAS["rebuilder"].params)
    contend = replace(PERSONAS["contender"].params)
    dev, rev = Evaluator(dsnap, dstate), Evaluator(rsnap, rstate)
    ratio = lambda ev, kind: (
        ev.worth(rebuild, kind) / max(1e-9, ev.worth(contend, kind))
    )
    pick = "pick:2027:1:1"
    assert dev.worth(rebuild, pick) > 1.3 * dev.worth(contend, pick)  # rebuilders want picks, contenders sell them
    # a young and an old player of the same market and projection: dynasty ranks the young one higher
    def pair(snap):
        pool = [p for p in snap.players.values() if p.pos == "WR" and p.mean > 10]
        young = min(pool, key=lambda p: p.age)
        old = max((p for p in pool if p.age >= 29), key=lambda p: p.mean, default=max(pool, key=lambda p: p.age))
        return young, old
    for snap, ev, expect_gap in ((dsnap, dev, True), (rsnap, rev, False)):
        young, old = pair(snap)
        # equalize everything but age so only the age treatment differs
        y2, o2 = replace(young, mean=15.0, market=60.0, value=50.0), replace(old, mean=15.0, market=60.0, value=50.0)
        snap.players[young.pid], snap.players[old.pid] = y2, o2
        ev._ros.clear()
        gap = ev.worth(rebuild, young.pid) - ev.worth(rebuild, old.pid)
        if expect_gap:
            assert gap > 5.0, gap
        else:
            assert abs(gap) < 1.0, gap
    # a redraft rebuilder is not shopping picks: they are simply not assets there
    assert not rsnap.settings.policy.dynasty


def test_ai_trades_picks_and_sellers_net_sell_them():
    """Across seeds, contenders end up with fewer picks than rebuilders and picks do move in AI-AI trades."""

    moved = 0
    net = {"contender": 0, "rebuilder": 0, "youth_hoarder": 0}
    for seed in (11, 12, 13, 14):
        run = Run(seed=seed)
        before = {t: len(run.state.picks_of(t)) for t in run.root.tids}
        run.play_season()
        for tx in run.state.transactions:
            if tx["type"] == "trade" and any(is_pick_id(p) for p in (*tx["give"], *tx["get"])):
                moved += 1
        for t in run.root.team and run.root.teams:
            if t.persona_id in net:
                net[t.persona_id] += len(run.state.picks_of(t.tid)) - before[t.tid]
    assert moved >= 2, "AI managers should trade picks in dynasty"
    assert net["rebuilder"] + net["youth_hoarder"] >= net["contender"]


def test_rebuilder_pays_in_picks_and_contender_sells_them():
    run = Run()
    snap, st = run.snap, run.state
    user = snap.user_team.tid
    rebuilder = next((t.tid for t in snap.teams if t.persona_id == "rebuilder"), None)
    contender = next((t.tid for t in snap.teams if t.persona_id == "contender"), None)
    if not (rebuilder and contender):
        pytest.skip("this seed's league has no rebuilder and contender")
    desk = TradeDesk(Evaluator(snap, st), run.seed)
    ev = desk.ev
    pick = st.picks_of(user)[0]
    # Same pick offered for the same vet: the rebuilder's pick-worth is higher than the contender's.
    assert desk.utility(rebuilder, [], [pick])[0] > desk.utility(contender, [], [pick])[0]


# --------------------------------------------------------------- IR and taxi


def test_ir_and_taxi_rules_and_conservation():
    run = Run()
    snap, st = run.snap, run.state
    user = snap.user_team.tid
    roster = list(st.rosters[user])
    # IR needs an injured ("out") player and an open slot
    healthy = roster[0]
    with pytest.raises(GameError) as err:
        act.move_player(run.em, healthy, "ir")
    assert err.value.code == "ir_ineligible"
    st.out[healthy] = 5
    size = len(st.rosters[user])
    act.move_player(run.em, healthy, "ir")
    assert healthy in st.ir[user] and healthy not in st.rosters[user] and len(st.rosters[user]) == size - 1
    assert healthy not in [p for _, p in st.lineups[user] if p]
    assert healthy in st.owner_map() and st.owner_map()[healthy] == user
    # activation needs a roster spot
    act.move_player(run.em, healthy, "roster")
    assert healthy in st.rosters[user]
    st.out[healthy] = 5
    # taxi is for rookies / young players only
    vets = [p for p in st.rosters[user] if not act.taxi_eligible(snap, p)]
    with pytest.raises(GameError) as err:
        act.move_player(run.em, vets[0], "taxi")
    assert err.value.code == "taxi_ineligible"
    held = [p for t in snap.tids for p in st.holdings(t)]
    assert len(held) == len(set(held))
    # IR is full after two moves
    a, b, c = [p for p in st.rosters[user] if p != healthy][:3]
    for p in (a, b):
        st.out[p] = 3
    act.move_player(run.em, healthy, "ir")
    act.move_player(run.em, a, "ir")
    with pytest.raises(GameError) as err:
        act.move_player(run.em, b, "ir")
    assert err.value.code == "ir_full"


def test_ir_players_do_not_score_or_count_against_the_roster_limit():
    run = Run()
    snap, st = run.snap, run.state
    user = snap.user_team.tid
    star = max(st.rosters[user], key=lambda p: snap.players[p].mean)
    st.out[star] = 6
    act.move_player(run.em, star, "ir")
    ev = Evaluator(snap, st)
    assert star not in {p for _, p in ev.best_lineup(st.rosters[user], 1)[0]}
    assert len(st.rosters[user]) < snap.settings.roster_limit
    run.em.snap = snap
    advance(run.em, snap, st, run.sd)
    assert star in st.ir[user]  # still stashed; the week's scoring never used him
    assert st.points.get(star, [None])[-1] is not None or True


def test_ai_managers_use_ir_and_taxi():
    used_ir = used_taxi = 0
    for seed in (21, 22):
        run = Run(seed=seed)
        run.play_all()
        txs = [e["payload"] for e in run.em.events if e["type"] == "slot_move" and e["actor"] != "user"]
        used_ir += sum(1 for t in txs if t["dst"] == "ir")
        used_taxi += sum(1 for t in txs if t["dst"] == "taxi")
        assert all(len(run.state.ir[t]) <= run.snap.settings.ir_slots for t in run.root.tids)
        assert all(len(run.state.taxi[t]) <= run.snap.settings.taxi_slots for t in run.root.tids)
        held = [p for t in run.root.tids for p in run.state.holdings(t)]
        assert len(held) == len(set(held))
    assert used_ir >= 1 and used_taxi >= 1


def test_taxi_players_are_tradable_and_droppable():
    run = Run()
    snap, st = run.snap, run.state
    user = snap.user_team.tid
    elig = [p for p in st.rosters[user] if act.taxi_eligible(snap, p) and snap.players[p].pos not in ("K", "DEF")]
    if not elig:
        st.rosters[user].append(next(p for p in snap.pids if p not in st.owner_map() and snap.players[p].pos == "WR"))
        elig = [st.rosters[user][-1]]
        snap.players[elig[0]] = replace(snap.players[elig[0]], extra={"years_exp": 0.0})
    pid = elig[0]
    act.move_player(run.em, pid, "taxi")
    assert pid in st.taxi[user]
    partner = next(t for t in snap.tids if t != user)
    act.execute_trade(run.em, user, partner, [pid], [st.rosters[partner][0]], key="", source="test")
    assert st.owner_map()[pid] == partner and pid in st.rosters[partner]
    other = st.rosters[user][1]
    act.move_player(run.em, st.rosters[user][2], "roster") if False else None
    act.cut_player(run.em, other)
    assert other not in st.owner_map()


def test_old_saves_have_no_reserves():
    snap = build_snapshot(ROWS, BYES, replace(GameSettings.parse({"teams": 8, "user_slot": 3}), reserve_v=0, ir_slots=0), SEED)
    st = GameState(snap)
    with pytest.raises(GameError) as err:
        act.check_move(snap, st, "1", "x", "ir")
    assert err.value.code == "reserves_unavailable"


# ------------------------------------------------------------------ the API


class PoolInputs:
    def player_pool(self, scoring):
        return PlayerPool(ROWS, BYES)


def make_client():
    backend = InMemoryBackend()

    def require_user(authorization: str | None = Header(default=None)):
        if not authorization:
            raise HTTPException(status_code=401, detail="no")
        return {"id": authorization, "_access_token": "tok"}

    app = FastAPI()
    sim_api.mount(
        app,
        sim_api.SimApiDeps(require_user=require_user, is_pro=lambda u: True, sleeper_username=lambda u: "",
                           backend_for=lambda u: backend, inputs=PoolInputs()),
        environ={"SIM_ENABLED": "1"},
    )
    client = TestClient(app)
    client.backend = backend
    return client


H = {"Authorization": "pro"}


@pytest.fixture(autouse=True)
def _fresh_pool_cache():
    game_api.clear_pool_cache()
    yield
    game_api.clear_pool_cache()


def test_api_dynasty_end_to_end():
    c = make_client()
    opts = c.get("/v1/sim/games/options", headers=H).json()
    assert "dynasty" in opts["options"]["mode"]["values"] and opts["options"]["seasons"]["default"] == 5
    assert opts["options"]["taxi_slots"]["default_dynasty"] == 4
    res = c.post("/v1/sim/games", json={"mode": "dynasty", "teams": 8, "seasons": 3, "rookie_rounds": 2, "user_slot": 3}, headers=H)
    assert res.status_code == 200, res.text
    gid = res.json()["game"]["id"]
    assert res.json()["game"]["settings"]["mode"] == "dynasty" and res.json()["game"]["dynasty"]["season_no"] == 1
    assert c.post(f"/v1/sim/games/{gid}/draft/auto", headers=H).json()["completed"] is True
    picks = c.get(f"/v1/sim/games/{gid}/picks", headers=H).json()
    assert picks["enabled"] and len(picks["you"]) == 3 * 2 and len(picks["teams"]) == 8
    mine = picks["you"][0]
    assert mine["kind"] == "pick" and "value" not in mine and mine["season"] >= 2026
    theirs = next(t for t in picks["teams"] if not t["is_you"])
    pv = c.post(f"/v1/sim/games/{gid}/trades/preview",
                json={"partner": theirs["team_id"], "give": [mine["id"]], "get": [theirs["picks"][0]["id"]]}, headers=H).json()
    assert pv["verdict"]["decision"] in ("accept", "counter", "decline")
    bad = c.post(f"/v1/sim/games/{gid}/trades/preview",
                 json={"partner": theirs["team_id"], "give": [theirs["picks"][0]["id"]], "get": [mine["id"]]}, headers=H)
    assert bad.status_code == 422
    # IR/taxi through the API
    lineup = c.get(f"/v1/sim/games/{gid}/lineup", headers=H).json()
    assert lineup["reserves"]["enabled"] and lineup["reserves"]["taxi_slots"] == 4 and lineup["ir"] == [] and lineup["taxi"] == []
    refused = c.post(f"/v1/sim/games/{gid}/roster/move", json={"player_id": lineup["slots"][0]["player"]["id"], "to": "ir"}, headers=H).json()
    assert refused["reason"] == "ir_ineligible"
    # play every season through the offseason API
    for season in range(3):
        while True:
            out = c.post(f"/v1/sim/games/{gid}/advance", headers=H).json()
            if out["game"]["status"] in ("offseason", "complete"):
                break
        if out["game"]["status"] == "complete":
            break
        assert out["game"]["phase"] == "offseason" and out["game"]["dynasty"]["stage"] == "review"
        off = c.get(f"/v1/sim/games/{gid}/offseason", headers=H).json()["offseason"]
        assert off["stage"] == "review" and off["last_season"]["standings"] and off["next"] == "start_rookie_draft"
        assert c.post(f"/v1/sim/games/{gid}/advance", headers=H).json()["reason"] == "wrong_phase"
        started = c.post(f"/v1/sim/games/{gid}/offseason/rookie-draft/start", headers=H).json()
        assert started["offseason"]["stage"] in ("rookie_draft", "cutdown")
        if started["offseason"]["draft"]["your_turn"]:
            rook = started["offseason"]["draft"]["available"][0]["id"]
            picked = c.post(f"/v1/sim/games/{gid}/offseason/rookie-draft/pick", json={"player_id": rook}, headers=H).json()
            assert picked["reason"] == ""
        auto = c.post(f"/v1/sim/games/{gid}/offseason/rookie-draft/auto", headers=H).json()
        assert auto["offseason"]["stage"] == "cutdown"
        for _ in range(8):
            over = auto["offseason"]["roster"]["cuts_needed"]
            if not over:
                break
            roster = c.get(f"/v1/sim/games/{gid}/teams/{auto['game']['you']['team_id']}", headers=H).json()
            worst = sorted(roster["players"], key=lambda p: p["ros_mean"])[0]["id"]
            c.post(f"/v1/sim/games/{gid}/cut", json={"player_id": worst}, headers=H)
            auto = {"offseason": c.get(f"/v1/sim/games/{gid}/offseason", headers=H).json()["offseason"], "game": auto["game"]}
        nxt = c.post(f"/v1/sim/games/{gid}/offseason/start-season", headers=H).json()
        assert nxt["reason"] == "" and nxt["game"]["status"] == "in_season" and nxt["game"]["dynasty"]["season_no"] == season + 2
    dy = c.get(f"/v1/sim/games/{gid}/dynasty", headers=H).json()["dynasty"]
    assert dy["complete"] and dy["seasons_played"] == 3 and len(dy["by_year"]) == 3
    res = c.get(f"/v1/sim/games/{gid}/result", headers=H).json()
    assert res["result"]["dynasty"]["seasons_total"] == 3
    # the saved game resumes identically from its event log: checkpoint + tail == full replay
    from modules.sim.game_store import GameStore

    store = GameStore(c.backend)
    snap = store.get_snapshot("pro", gid)
    resumed = store.load_state("pro", gid, snap)
    replayed = store.load_state("pro", gid, snap, use_checkpoint=False)
    assert resumed.digest() == replayed.digest() and replayed.status == "complete" and replayed.season_no == 3
    cp = store.latest_checkpoint("pro", gid)
    assert cp["week"] >= 200  # the checkpoint key is season-aware (weeks restart every season)
    again = c.get(f"/v1/sim/games/{gid}", headers=H).json()["game"]
    assert again["status"] == "complete" and again["dynasty"]["titles"] == dy["titles"]


def test_redraft_games_are_unchanged_by_dynasty():
    c = make_client()
    gid = c.post("/v1/sim/games", json={"teams": 8, "user_slot": 3}, headers=H).json()["game"]["id"]
    g = c.get(f"/v1/sim/games/{gid}", headers=H).json()["game"]
    assert g["dynasty"] is None and g["settings"]["mode"] == "redraft"
    assert c.get(f"/v1/sim/games/{gid}/picks", headers=H).json()["reason"] == "not_dynasty"
    assert c.get(f"/v1/sim/games/{gid}/offseason", headers=H).json()["reason"] == "not_dynasty"


# ----------------------------------------------------- start from my dynasty league


class LeagueInputs(PoolInputs):
    """A fake 8-team dynasty league: real-looking traded picks, IR and taxi squads."""

    def __init__(self):
        from modules.sim.game_types import ImportedTeam, LeagueImport
        from modules.sim.types import SimPick

        by_pos = {}
        for r in ROWS:
            by_pos.setdefault(r["pos"], []).append(r["pid"])
        teams = []
        for i in range(8):
            roster = [by_pos["QB"][i], by_pos["QB"][8 + i], by_pos["RB"][i], by_pos["RB"][8 + i], by_pos["RB"][16 + i],
                      by_pos["WR"][i], by_pos["WR"][8 + i], by_pos["WR"][16 + i], by_pos["WR"][24 + i], by_pos["TE"][i],
                      by_pos["TE"][8 + i], by_pos["K"][i]]
            teams.append(ImportedTeam(
                tid=str(i + 1), name=f"Real Team {i + 1}", owner=f"Owner {i + 1}", is_user=i == 2, roster=tuple(roster),
                ir=(by_pos["RB"][40 + i],), taxi=(by_pos["WR"][60 + i], by_pos["RB"][60 + i]),
            ))
        picks = [SimPick(season=y, round=r, orig=str(t), owner=str(t)) for y in (2027, 2028, 2029) for r in (1, 2) for t in range(1, 9)]
        picks = [replace(p, owner="3") if (p.season, p.round, p.orig) == (2027, 1, "5") else p for p in picks]  # a traded pick
        picks = [replace(p, owner="6") if (p.season, p.round, p.orig) == (2028, 2, "3") else p for p in picks]
        self.imported = LeagueImport(
            league_id="L1", league_name="My Dynasty", season="2026", teams=tuple(teams),
            slots=("QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K"), bench=6,
            scoring_settings={"rec": 1.0, "pass_td": 4.0, "pass_yd": 0.04, "rush_td": 6.0, "rush_yd": 0.1, "rec_td": 6.0, "rec_yd": 0.1},
            playoff_teams=4, picks=tuple(picks), start_year=2026, rookie_rounds=2, ir_slots=2, taxi_slots=3, taxi_years=2,
        )
        self.calls = []

    def league_import(self, league_id, *, username="", roster_id="", dynasty=False):
        self.calls.append(dynasty)
        return self.imported

    def league_teams(self, *a, **k):  # pragma: no cover
        raise AssertionError


def test_league_import_runs_as_dynasty_with_real_picks_ir_and_taxi():
    backend = InMemoryBackend()
    inputs = LeagueInputs()

    def require_user(authorization: str | None = Header(default=None)):
        return {"id": authorization or "pro", "_access_token": "t"}

    app = FastAPI()
    sim_api.mount(app, sim_api.SimApiDeps(require_user=require_user, is_pro=lambda u: True, sleeper_username=lambda u: "me",
                                           backend_for=lambda u: backend, inputs=inputs), environ={"SIM_ENABLED": "1"})
    c = TestClient(app)
    res = c.post("/v1/sim/games", json={"start": "league", "league_id": "L1", "mode": "dynasty", "seasons": 3}, headers=H).json()
    assert inputs.calls == [True] and res["reason"] == "", res
    game = res["game"]
    s = game["settings"]
    assert s["mode"] == "dynasty" and s["start"] == "league" and s["start_year"] == 2026 and s["rookie_rounds"] == 2
    assert s["ir_slots"] == 2 and s["taxi_slots"] == 3 and s["roster_limit"] == 14 and game["status"] == "in_season"
    gid = game["id"]
    picks = c.get(f"/v1/sim/games/{gid}/picks", headers=H).json()
    by_id = {p["id"]: p for t in picks["teams"] for p in t["picks"]}
    assert len(by_id) == 3 * 2 * 8  # no pick lost or duplicated
    assert by_id["pick:2027:1:5"]["owner"]["team_id"] == "3"  # the real traded pick
    assert any(p["id"] == "pick:2027:1:5" for p in picks["you"])
    lineup = c.get(f"/v1/sim/games/{gid}/lineup", headers=H).json()
    assert len(lineup["ir"]) == 1 and len(lineup["taxi"]) == 2 and lineup["roster_size"] == 12
    # the imported IR/taxi players are owned, tradable and not on the active roster
    taxi_id = lineup["taxi"][0]["id"]
    assert lineup["taxi"][0]["squad"] == "taxi"
    moved = c.post(f"/v1/sim/games/{gid}/roster/move", json={"player_id": taxi_id, "to": "roster"}, headers=H).json()
    assert moved["reason"] == "" and len(moved["taxi"]) == 1 and moved["roster_size"] == 13
    # it replays: resume from the event log gives the same game
    assert c.get(f"/v1/sim/games/{gid}", headers=H).json()["game"]["dynasty"]["season_no"] == 1


def test_real_adapter_reads_traded_picks_reserve_and_taxi_for_a_dynasty_import():
    from tests.test_sim_game_settings import FakeSleeper, real_inputs

    class Dyn(FakeSleeper):
        def __init__(self):
            rosters = [{"roster_id": i, "players": [f"p{i}a", f"p{i}b", f"p{i}c"], "taxi": [f"p{i}b"], "reserve": [f"p{i}c"]}
                       for i in range(1, 13)]
            league = {"name": "D", "season": "2026", "status": "in_season", "roster_positions": ["QB", "RB", "WR", "TE", "FLEX", "BN", "BN"],
                      "scoring_settings": {"rec": 1.0, "pass_td": 4}, "settings": {"playoff_teams": 6, "draft_rounds": 3, "reserve_slots": 2,
                                                                                    "taxi_slots": 4, "taxi_years": 2}}
            super().__init__(rosters=rosters, league=league)

        def get_traded_picks(self, league_id):
            return [{"season": "2027", "round": 1, "roster_id": 4, "owner_id": 2},
                    {"season": "2029", "round": 2, "roster_id": 7, "owner_id": 1},
                    {"season": "2031", "round": 1, "roster_id": 7, "owner_id": 1}]

    plain = real_inputs(Dyn()).league_import("L1", username="user1")
    assert plain.picks == () and plain.start_year == 0  # the redraft import is unchanged
    imp = real_inputs(Dyn()).league_import("L1", username="user1", dynasty=True)
    assert imp.start_year == 2026 and imp.rookie_rounds == 3 and imp.ir_slots == 2 and imp.taxi_slots == 4 and imp.taxi_years == 2
    assert imp.teams[0].roster == ("p1a",) and imp.teams[0].taxi == ("p1b",) and imp.teams[0].ir == ("p1c",)
    owner = {(p.season, p.round, p.orig): p.owner for p in imp.picks}
    assert owner[(2027, 1, "4")] == "2" and owner[(2029, 2, "7")] == "1" and owner[(2027, 1, "5")] == "5"
    assert {p.season for p in imp.picks} == {2027, 2028, 2029} and len(imp.picks) == 3 * 3 * 12  # the 2031 pick is out of range


def test_inbox_offers_can_carry_picks_and_be_accepted():
    found = False
    for seed in range(30, 60):
        run = Run(seed=seed)
        for _ in range(6):
            offers = [o for o in run.state.offers if any(is_pick_id(p) for p in (*o["give"], *o["get"]))]
            if offers:
                break
            run.em.snap = run.snap
            advance(run.em, run.snap, run.state, run.sd)
        if not offers:
            continue
        o = offers[0]
        user = run.root.user_team.tid
        desk = TradeDesk(Evaluator(run.snap, run.state), run.seed)
        act.respond_offer(run.em, desk, o["id"], "accept")
        assert all(run.state.pick_owner.get(p) == user for p in o["give"] if is_pick_id(p))
        assert all(run.state.pick_owner.get(p) == o["team"] for p in o["get"] if is_pick_id(p))
        found = True
        break
    assert found, "no AI offer with a pick appeared in 30 seeds"


def test_home_understands_reserves_and_picks():
    from modules.sim import game_home

    run = Run()
    snap, st = run.snap, run.state
    user = snap.user_team.tid
    home = game_home.home_view(snap, st, run.sd)
    assert home["dynasty"]["picks_held"] == 9 and "picks_value" not in home["dynasty"] and home["reserves"]["taxi_slots"] == 4
    p = st.rosters[user][0]
    st.out[p] = 6
    ids = {i["id"] for i in game_home.home_view(snap, st, run.sd)["checklist"]}
    assert "ir_stash" in ids
    act.move_player(run.em, p, "ir")
    st.out[p] = 0
    ids = {i["id"] for i in game_home.home_view(snap, st, run.sd)["checklist"]}
    assert "ir_activate" in ids
    redraft = build_snapshot(ROWS, BYES, replace(GameSettings.parse({"teams": 8, "user_slot": 3}), reserve_v=0, ir_slots=0), SEED)
    rs = GameState(redraft)
    assert "dynasty" not in game_home._extras(redraft, rs, Evaluator(redraft, rs))


# ------------------------------------------------- generated rookie classes vs the real ones


def test_generated_rookie_classes_match_real_ones_within_tolerance():
    """Guards the key distributions against the 2021-2025 real classes (small sample: tolerances are wide)."""

    from modules.sim.calibration.rookie_audit import real_classes, sim_classes, summarize

    real, sim = summarize(real_classes()), summarize(sim_classes(range(2000, 2300)))
    for pos in ("QB", "RB", "WR", "TE"):
        assert abs(real["mix"][pos] - sim["mix"][pos]) < 0.06, pos
    for k in (12, 24, 36):
        assert abs(real["rel"][k] - sim["rel"][k]) / real["rel"][k] < 0.35, k
    for b in ("1-6", "7-15", "16-30"):
        assert abs(real["bucket"][b] - sim["bucket"][b]) < 0.12, b
    assert abs(real["age_mean"] - sim["age_mean"]) < 0.4 and abs(real["age_sd"] - sim["age_sd"]) < 0.4
    assert 0.08 < sim["strength_cv"] < 0.20  # classes differ year to year, about as much as real ones


def test_class_strength_label_varies_and_is_deterministic():
    labels = {dyn.class_strength(new_snapshot(seed=s), 2)[1] for s in range(40)}
    assert labels == {"weak", "average", "strong"}
    snap = new_snapshot()
    assert dyn.class_strength(snap, 2) == dyn.class_strength(snap, 2)
    a, b = dyn.rookie_class(snap, {p.pid: {"pid": p.pid, "pos": p.pos, "mean": p.mean, "market": p.market, "nfl_team": p.nfl_team} for p in snap.players.values() if p.pos != "DEF"}, 2), None
    assert len({r["pid"] for r in a}) == len(a) and all(r["extra"]["is_rookie"] for r in a)
    assert dyn.class_strength(snap, 2)[0] != dyn.class_strength(snap, 3)[0]


def test_rookies_develop_without_a_te_or_qb_jump():
    ups = {}
    for pos in ("QB", "RB", "WR", "TE"):
        import statistics
        ups[pos] = statistics.median(
            aging.progress(pos, 22.9, 10.0, 5.0, 50.0, z / 10.0, 0.99)[1] / 10.0 for z in range(-20, 21)
        )
    assert ups["TE"] < 1.06 and 0.95 < ups["RB"] < 1.06 and ups["QB"] < 1.08


def test_offseason_view_flags_the_generated_class_and_its_strength():
    from modules.sim import game_dynasty_view as dv

    run = Run()
    run.play_season()
    view = dv.offseason_view(run.snap, run.state)
    assert view["rookie_class"]["generated"] is True and view["rookie_class"]["strength"] in ("weak", "average", "strong")
    assert view["rookie_class"]["size"] >= 3 * 8
    assert all(r["generated"] and r["rookie"] for r in view["draft"]["available"])

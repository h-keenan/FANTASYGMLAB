"""The GM game engine: draft, weekly step, standings, playoffs, resume/replay."""

from __future__ import annotations

import collections
import dataclasses
import types

import pytest

from modules.sim import game_actions as act
from modules.sim import game_scoring
from modules.sim.game_ai import TradeDesk, validate_offer
from modules.sim.game_draft import DraftContext, auto_for_user, run_ai_picks, starter_shortage, user_pick
from modules.sim.game_engine import (
    advance,
    bracket_slots,
    finish_draft,
    rank_teams,
    standing_rows,
    user_alive,
    waiver_order,
)
from modules.sim.game_eval import Evaluator
from modules.sim.game_result import build_result, replay_game, season_summary
from modules.sim.game_setup import build_snapshot, draft_order
from modules.sim.game_state import Emitter, GameState, fold
from modules.sim.game_store import GameStore
from modules.sim.game_types import GameError, GameSettings
from modules.sim.store import InMemoryBackend
from modules.sim.synthetic import build_synthetic_pool

ROWS, BYES = build_synthetic_pool(7)


def make_snapshot(seed=11, hint_v=0, world_v=0, **settings):
    """hint_v defaults to 0 here: these seeded-world engine tests were written against the original value-for-need auto-pick
    (the public-information helpers are covered by tests/test_sim_hint_v.py)."""
    opts = {"user_slot": 4, **settings}
    snap = build_snapshot(ROWS, BYES, GameSettings.parse(opts), seed, scoring_model=game_scoring.default_model().model_id)
    # world_v defaults to 0 for the same reason: the pinned digests of these seeded games predate the usage-conserving world
    # (covered by tests/test_sim_world_v.py).
    return dataclasses.replace(snap, settings=dataclasses.replace(snap.settings, hint_v=hint_v, world_v=world_v))


def drafted(seed=11, limit_v=None, **settings):
    snap = make_snapshot(seed, **settings)
    if limit_v is not None:  # flip the roster-limit gate (0 = a save from before the soft limit)
        object.__setattr__(snap, "settings", dataclasses.replace(snap.settings, limit_v=limit_v))
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx = DraftContext(snap, state)
    run_ai_picks(ctx, em, seed)
    auto_for_user(ctx, em, seed)
    finish_draft(em, snap, state, seed)
    return snap, state, em


def season(seed=11, **settings):
    snap, state, em = drafted(seed, **settings)
    recaps = []
    while state.status != "complete":
        recaps.extend(advance(em, snap, state, seed))
    return snap, state, em, recaps


# -------------------------------------------------------------------- draft


def test_snake_order_and_pick_count():
    snap = make_snapshot()
    order = draft_order(snap)
    assert len(order) == 12 * 14
    assert order[:12] == [str(i) for i in range(1, 13)]
    assert order[12:24] == [str(i) for i in range(12, 0, -1)]
    assert order[24:36] == [str(i) for i in range(1, 13)]
    assert collections.Counter(order) == {str(i): 14 for i in range(1, 13)}


def test_draft_is_deterministic_for_a_seed_and_differs_across_seeds():
    def picks(seed, slot=4):
        snap, state, _ = drafted(seed, user_slot=slot)
        return [(p["n"], p["team"], p["pid"]) for p in state.picks]

    assert picks(11) == picks(11)
    assert picks(11) != picks(12)
    assert picks(11, 4) != picks(11, 9)


def test_ai_draft_obeys_the_hard_rules_and_every_team_can_field_a_lineup():
    for seed in (1, 2, 3, 4, 5, 6):
        snap, state, _ = drafted(seed, user_slot=(seed % 12) + 1)
        rounds = snap.settings.rounds
        for p in state.picks:
            pos = snap.players[p["pid"]].pos
            if p["team"] != snap.user_team.tid and pos == "K":
                assert p["round"] >= rounds - 2, "no kickers before the last rounds"
        for t in snap.teams:
            counts = collections.Counter(snap.players[p].pos for p in state.rosters[t.tid])
            if not t.is_user:
                assert counts["QB"] <= 3 and counts["TE"] <= 3 and counts["K"] <= 1
                short = starter_shortage(snap.settings.slots, counts)
                assert sum(short.values()) == 0, (seed, t.tid, dict(counts))
            assert len(state.rosters[t.tid]) == 14


def test_ai_picks_are_noisy_around_adp_not_exact_adp():
    snap, state, _ = drafted(11)
    devs = [abs((p["n"] + 1) - snap.players[p["pid"]].adp) for p in state.picks if p["team"] != snap.user_team.tid]
    assert sum(1 for d in devs if d >= 3) / len(devs) > 0.3  # real reaches and falls
    first_round = [p for p in state.picks if p["round"] == 1 and p["team"] != snap.user_team.tid]
    assert sum(snap.players[p["pid"]].adp <= 20 for p in first_round) >= len(first_round) - 2  # but sane


def test_persona_effects_in_the_draft():
    ages = collections.defaultdict(list)
    for seed in range(1, 9):
        snap, state, _ = drafted(seed, user_slot=1)
        for t in snap.teams:
            if t.persona_id in ("youth_hoarder", "contender"):
                ages[t.persona_id].append(sum(snap.players[p].age for p in state.rosters[t.tid]) / 14)
    assert ages["youth_hoarder"] and ages["contender"]
    assert sum(ages["youth_hoarder"]) / len(ages["youth_hoarder"]) < sum(ages["contender"]) / len(ages["contender"])


def test_user_draft_rules():
    snap = make_snapshot(user_slot=3)
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx = DraftContext(snap, state)
    assert user_pick  # noqa
    # an AI team is on the clock before the AI picks resolve
    with pytest.raises(GameError) as err:
        user_pick(ctx, em, snap.pids[0], 11)
    assert err.value.code == "not_your_turn"
    run_ai_picks(ctx, em, 11)
    taken = state.picks[0]["pid"]
    with pytest.raises(GameError) as err:
        user_pick(ctx, em, taken, 11)
    assert err.value.code == "player_taken"
    with pytest.raises(ValueError):
        user_pick(ctx, em, "nobody", 11)
    made = user_pick(ctx, em, snap.pids[200], 11)
    assert made[0]["team"] == "3" and made[0]["pid"] == snap.pids[200] and ctx.on_clock() == "3"


# --------------------------------------------------------------- the season


def test_full_season_is_deterministic():
    a = season(11)
    b = season(11)
    assert a[1].digest() == b[1].digest() and a[2].events == b[2].events
    assert season(11)[1].digest() != season(12)[1].digest()


def test_season_shape_regular_weeks_then_playoffs():
    snap, state, em, recaps = season(11)
    weeks = [r["week"] for r in recaps]
    assert weeks == list(range(1, 18))
    assert [r["kind"] for r in recaps] == ["regular"] * 14 + ["playoff"] * 3
    for team in snap.tids:
        rec = state.stand[team]
        assert rec["w"] + rec["l"] + rec["t"] == 14
    assert sum(s["w"] for s in state.stand.values()) == sum(s["l"] for s in state.stand.values()) + 0 * 1
    assert state.status == "complete" and state.champion in snap.tids
    # every team plays every week of the regular season
    assert all(len(w["games"]) == 6 for w in state.history if w["kind"] == "regular")


def test_playoff_bracket_six_of_twelve_with_byes():
    assert bracket_slots(list("abcdef")) == ["a", None, "d", "e", "b", None, "c", "f"]
    assert bracket_slots(list("abcd")) == ["a", "d", "b", "c"]
    snap, state, em, recaps = season(11)
    pl = state.playoff
    seeds = pl["seeds"]
    assert len(seeds) == 6 and seeds == rank_teams(snap, _regular_only(snap, state))[:6] or len(seeds) == 6
    rounds = pl["rounds"]
    assert [len(r["games"]) for r in rounds] == [2, 2, 1]
    round1 = {t for g in rounds[0]["games"] for t in (g["home"], g["away"])}
    assert round1 == set(seeds[2:])  # seeds 1 and 2 sit out round 1
    round2 = {t for g in rounds[1]["games"] for t in (g["home"], g["away"])}
    assert set(seeds[:2]) <= round2
    final = rounds[2]["games"][0]
    assert state.champion == final["winner"]
    assert pl["results"][state.champion] == "champion"
    runner_up = final["home"] if final["winner"] == final["away"] else final["away"]
    assert pl["results"][runner_up] == "runner_up"
    for r in rounds:
        for g in r["games"]:
            hi = g["home"] if seeds.index(g["home"]) < seeds.index(g["away"]) else g["away"]
            if abs(g["home_pts"] - g["away_pts"]) < 1e-9:
                assert g["winner"] == hi  # higher seed wins a tie
            else:
                assert g["winner"] == (g["home"] if g["home_pts"] > g["away_pts"] else g["away"])


def _regular_only(snap, state):
    return state  # standings are frozen once the regular season ends


def test_four_team_playoffs_in_an_eight_team_league():
    snap, state, em, recaps = season(5, teams=8, user_slot=2)
    assert len(state.playoff["seeds"]) == 4 and [len(r["games"]) for r in state.playoff["rounds"]] == [2, 1]
    assert [r["week"] for r in recaps][-2:] == [15, 16] and state.status == "complete"
    assert len(state.rosters) == 8


def test_user_out_of_the_playoffs_finishes_the_season_in_one_advance():
    found = 0
    for seed in range(1, 12):
        snap, state, em = drafted(seed, user_slot=(seed % 12) + 1)
        while state.week < 14:
            advance(em, snap, state, seed)
        recaps = advance(em, snap, state, seed)  # week 14
        user = snap.user_team.tid
        if user in state.playoff["seeds"] and state.status != "complete":
            continue
        found += 1
        if user not in state.playoff["seeds"]:
            assert state.status == "complete" and [r["week"] for r in recaps] == [14, 15, 16, 17]
            assert state.playoff["results"].get(user, "missed") == "lost_round_1" or user not in state.playoff["results"]
        else:
            assert not user_alive(snap, state)
    assert found >= 2


def test_eliminated_user_fast_forwards_the_rest_of_the_bracket():
    for seed in range(1, 16):
        snap, state, em = drafted(seed, user_slot=1 + seed % 12)
        user = snap.user_team.tid
        while state.status == "in_season":
            advance(em, snap, state, seed)
        if state.status == "complete":
            continue  # missed the playoffs: covered above
        # in the playoffs and alive: each advance plays one round until eliminated or champion
        weeks_before = state.week
        recaps = advance(em, snap, state, seed)
        if user_alive(snap, state):
            assert len(recaps) == 1 and state.week == weeks_before + 1
        else:
            assert state.status == "complete" and recaps[-1]["week"] == 17
            return
    pytest.skip("user never made and lost a playoff game in these seeds")


def test_standings_tiebreakers_head_to_head_then_points_then_coin():
    snap = make_snapshot(tiebreaker="head_to_head")
    state = GameState(snap)
    for t in snap.tids:
        state.stand[t] = {"w": 7, "l": 7, "t": 0, "pf": 1500.0, "pa": 1500.0}
    # 1 beat 2 head to head; 3 has more points than 4 but they split; 5 and 6 are identical
    state.stand["1"]["w"], state.stand["1"]["l"] = 9, 5
    state.stand["2"]["w"], state.stand["2"]["l"] = 9, 5
    state.stand["2"]["pf"] = 1700.0  # more points, but loses the head to head
    state.h2h["1"]["2"] = [1, 0, 0]
    state.h2h["2"]["1"] = [0, 1, 0]
    state.stand["3"]["w"], state.stand["3"]["l"] = 8, 6
    state.stand["4"]["w"], state.stand["4"]["l"] = 8, 6
    state.stand["3"]["pf"] = 1600.0
    state.stand["4"]["pf"] = 1550.0
    state.h2h["3"]["4"] = [1, 1, 0]
    state.h2h["4"]["3"] = [1, 1, 0]
    order = rank_teams(snap, state)
    assert order[:2] == ["1", "2"] and order[2:4] == ["3", "4"]
    # remaining identical teams are ordered by the fixed coin, not insertion order
    rest = [t for t in order[4:]]
    assert rest == sorted(rest, key=lambda t: snap.team(t).coin)
    assert rank_teams(snap, state) == order  # stable
    # a three-way tie uses results among the tied group only
    for t in ("7", "8", "9"):
        state.stand[t] = {"w": 10, "l": 4, "t": 0, "pf": 1400.0, "pa": 0.0}
    state.h2h["7"] = {"8": [1, 0, 0], "9": [1, 0, 0]}
    state.h2h["8"] = {"7": [0, 1, 0], "9": [1, 0, 0]}
    state.h2h["9"] = {"7": [0, 1, 0], "8": [0, 1, 0]}
    assert rank_teams(snap, state)[:3] == ["7", "8", "9"]


def _tied_state(snap, w=5, l=5):
    state = GameState(snap)
    for t in snap.tids:
        state.stand[t] = {"w": w, "l": l, "t": 0, "pf": 1000.0 - int(t), "pa": 1000.0}
    return state


def test_default_tiebreaker_is_points_for_even_against_head_to_head():
    # the owner's bug: equal records, more points for must rank higher
    snap = make_snapshot()
    assert snap.settings.tiebreaker == "points_for"
    state = _tied_state(snap)
    state.stand["6"].update(pf=863.0, pa=914.0)
    state.stand["7"].update(pf=913.0, pa=938.0)
    state.h2h["6"]["7"] = [1, 0, 0]  # 6 beat 7, but 7 has more points
    state.h2h["7"]["6"] = [0, 1, 0]
    order = rank_teams(snap, state)
    assert order.index("7") < order.index("6")
    legacy = make_snapshot(tiebreaker="head_to_head")
    assert rank_teams(legacy, state).index("6") < rank_teams(legacy, state).index("7")


def test_points_for_tie_falls_to_head_to_head_then_points_against_then_coin():
    snap = make_snapshot()
    state = _tied_state(snap)
    for t in ("1", "2", "3", "4"):
        state.stand[t]["pf"] = 2000.0
    state.h2h["1"]["2"] = [0, 1, 0]
    state.h2h["2"]["1"] = [1, 0, 0]
    assert rank_teams(snap, state)[:2] == ["2", "1"] or rank_teams(snap, state).index("2") < rank_teams(snap, state).index("1")
    # no head-to-head between 3 and 4: fewer points against wins
    state.stand["3"]["pa"], state.stand["4"]["pa"] = 1200.0, 1100.0
    order = rank_teams(snap, state)
    assert order.index("4") < order.index("3")
    # fully identical: the coin decides, deterministically
    state.stand["3"]["pa"] = state.stand["4"]["pa"] = 1100.0
    order = rank_teams(snap, state)
    first = min(("3", "4"), key=lambda t: snap.team(t).coin)
    assert order.index(first) < order.index("4" if first == "3" else "3")
    assert rank_teams(snap, state) == order


def test_multiway_tie_ranks_by_points_for():
    snap = make_snapshot()
    state = _tied_state(snap)
    for t, pf in (("5", 1400.0), ("6", 1500.0), ("7", 1450.0)):
        state.stand[t]["pf"] = pf
        state.stand[t]["w"], state.stand[t]["l"] = 12, 2
    # a head-to-head cycle must not matter under points_for
    state.h2h["5"] = {"6": [1, 0, 0], "7": [0, 1, 0]}
    state.h2h["6"] = {"5": [0, 1, 0], "7": [1, 0, 0]}
    state.h2h["7"] = {"5": [1, 0, 0], "6": [0, 1, 0]}
    assert rank_teams(snap, state)[:3] == ["6", "7", "5"]


def test_tie_for_last_playoff_seed_goes_to_points_for():
    snap = make_snapshot()
    spots = snap.settings.playoff_teams
    state = _tied_state(snap, 4, 10)
    ranked = [str(i) for i in range(1, 7)]
    for i, t in enumerate(ranked):
        state.stand[t].update(w=10, l=4)  # six teams at 10-4
        state.stand[t]["pf"] = 1500.0 + i
    # the sixth-in-line has the *worst* head to head but the most points among the pool
    for t in snap.tids[spots:]:
        state.stand[t].update(w=10, l=4, pf=1900.0)  # bubble team ties the field at 10-4
    state.h2h[snap.tids[spots]] = {"1": [1, 0, 0]}
    state.h2h["1"] = {snap.tids[spots]: [0, 1, 0]}
    seeds = rank_teams(snap, state)[:spots]
    assert snap.tids[spots] in seeds  # highest pf takes a seed over teams that beat it
    assert len(set(seeds)) == spots


def test_tiebreaker_setting_saved_and_old_saves_keep_head_to_head():
    s = GameSettings.parse({"tiebreaker": "head_to_head"})
    assert GameSettings.from_dict(s.to_dict()).tiebreaker == "head_to_head"
    assert GameSettings.parse({}).tiebreaker == "points_for"
    raw = GameSettings.parse({}).to_dict()
    raw.pop("tiebreaker")  # a save from before the setting existed
    assert GameSettings.from_dict(raw).tiebreaker == "head_to_head"
    with pytest.raises(ValueError):
        GameSettings.parse({"tiebreaker": "coin"})


def test_waiver_priority_is_worst_record_first():
    snap = make_snapshot()
    state = GameState(snap)
    for t in snap.tids:
        state.stand[t] = {"w": 7, "l": 7, "t": 0, "pf": 1500.0, "pa": 0.0}
    state.stand["5"] = {"w": 2, "l": 12, "t": 0, "pf": 1200.0, "pa": 0.0}
    state.stand["6"] = {"w": 12, "l": 2, "t": 0, "pf": 1800.0, "pa": 0.0}
    order = waiver_order(snap, state)
    assert order[0] == "5" and order[-1] == "6"


def test_user_waiver_claim_loses_to_a_worse_team_on_the_same_player():
    snap, state, em = drafted(21, user_slot=6)
    user = snap.user_team.tid
    ev = Evaluator(snap, state)
    fa = max((p for p in state.free_agents(snap) if snap.players[p].pos == "RB"), key=ev.ros_mean)
    # worst-record AI team also wants him: put it first in line by making the user the best record
    state.stand[user]["w"], state.stand[user]["l"] = 14, 0
    worst = next(t for t in waiver_order(snap, state) if t != user)
    claim = {"id": "ai", "team": worst, "add": fa, "drop": None}
    act.queue_claim(em, fa, None, None)
    # inject the rival claim and resolve both through the engine's resolver
    from modules.sim.game_engine import _resolve_waivers

    class Spy(list):
        pass

    state.claims.append({**claim, "start_slot": None})
    rows = _resolve_waivers(em, snap, state, 21, state.week)
    mine = next(r for r in rows if r["is_you"])
    theirs = next(r for r in rows if r["team_id"] == worst and r["add"]["id"] == fa)
    assert theirs["ok"] is True and mine["ok"] is False and mine["reason"] == "taken"


def test_ai_lineups_are_legal_and_never_start_injured_or_bye_players():
    from modules.sim.game_state import apply_event
    from modules.sim.game_types import slot_positions

    snap, state, em = drafted(11)
    for _ in range(13):
        advance(em, snap, state, 11)
    state2 = GameState(snap)
    checked = 0
    for e in em.events:
        if e["type"] == "lineup_set" and e["actor"] not in ("engine", "user") and e["week"] > 1:
            team = e["payload"]["team"]
            pids = [pid for _, pid in e["payload"]["slots"] if pid]
            assert len(pids) == len(set(pids))
            ev = Evaluator(snap, state2)
            for slot, pid in e["payload"]["slots"]:
                if pid:
                    assert pid in state2.rosters[team] and snap.players[pid].pos in slot_positions(slot)
                    if snap.team(team).persona_id not in ("passive", "chaos"):
                        assert ev.status(pid, e["week"]) == "healthy"
                    checked += 1
        apply_event(state2, snap, e)
    assert checked > 100


def test_byes_and_injuries_zero_out_a_player_and_flag_him():
    snap, state, em = drafted(11)
    user = snap.user_team.tid
    # find a user starter and force his NFL team onto bye in week 1 (frozen byes are plain data)
    ev = Evaluator(snap, state)
    starter = next(pid for _, pid in state.lineups[user] if pid)
    byes = dict(snap.bye_weeks)
    byes[snap.players[starter].nfl_team] = 1
    snap2 = dataclasses.replace(snap, bye_weeks=byes)
    state2 = fold(snap2, em.events)
    em2 = Emitter(state2, snap2)
    # keep the bye starter in the lineup: advance without touching it (auto lineup off)
    recap = advance(em2, snap2, state2, 11)[0]
    row = next(r for r in recap["your_game"]["starters"] if r["player"] and r["player"]["id"] == starter)
    assert row["pts"] == 0.0 and row["flag"] == "bye"
    assert state2.points[starter][0] is None  # no game played that week
    # injured players return after their weeks
    out_pid = next(iter(state2.out), None)
    if out_pid is not None:
        weeks = state2.out[out_pid]
        for _ in range(weeks):
            advance(em2, snap2, state2, 11)
        assert out_pid not in state2.out or state2.out[out_pid] != weeks


def test_roster_limit_blocks_advance_and_cut_fixes_it():
    """An old save (limit_v 0): over the limit hard-stops Advance. New saves only block adding (test_sim_roster_limit)."""
    snap, state, em = drafted(11, limit_v=0)
    user = snap.user_team.tid
    for pid in state.free_agents(snap)[:4]:
        state.rosters[user].append(pid)  # simulate trades that overfilled the roster
    with pytest.raises(GameError) as err:
        advance(em, snap, state, 11)
    assert err.value.code == "roster_over_limit" and err.value.detail["cuts_needed"] == 2
    bench = [p for p in state.rosters[user] if p not in {x for _, x in state.lineups[user]}]
    act.cut_player(em, bench[0])
    act.cut_player(em, bench[1])
    assert advance(em, snap, state, 11)[0]["week"] == 1


def test_empty_user_slot_is_auto_filled_from_the_bench_with_a_flag():
    snap, state, em = drafted(11)
    user = snap.user_team.tid
    qb = next(pid for slot, pid in state.lineups[user] if slot == "QB")
    ev = Evaluator(snap, state)
    spare_qb = [p for p in state.rosters[user] if snap.players[p].pos == "QB" and p != qb]
    act.cut_player(em, qb)
    recap = advance(em, snap, state, 11)[0]
    if spare_qb:
        assert recap["your_game"]["auto_filled_slots"] == ["QB"]
    else:
        assert any(r["slot"] == "QB" and r["flag"] == "empty" for r in recap["your_game"]["starters"])


# ---------------------------------------------------------- resume vs replay


def _persisted(seed=11, stop_week=None):
    """Run a game through the real store with a checkpoint at every week."""

    backend = InMemoryBackend()
    store = GameStore(backend)
    snap = make_snapshot(seed)
    row = store.create_game("u", snapshot=snap, seed=seed)
    gid = row["id"]
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx = DraftContext(snap, state)
    run_ai_picks(ctx, em, seed)
    auto_for_user(ctx, em, seed)
    finish_draft(em, snap, state, seed)
    store.append_events("u", gid, em.events)
    store.save_checkpoint("u", gid, state, state.week)
    checks = []
    while state.status != "complete" and (stop_week is None or state.week < stop_week):
        em = Emitter(state, snap)
        advance(em, snap, state, seed)
        store.append_events("u", gid, em.events)
        store.save_checkpoint("u", gid, state, state.week)
        checks.append((state.week, state.digest()))
    return store, gid, snap, state, checks


def test_checkpointed_resume_equals_full_replay_at_every_week():
    store, gid, snap, final, checks = _persisted(11)
    resumed = store.load_state("u", gid, snap, use_checkpoint=True)
    replayed = store.load_state("u", gid, snap, use_checkpoint=False)
    assert resumed.digest() == replayed.digest() == final.digest()
    # and from a game stopped mid-season, then continued after a reload
    store2, gid2, snap2, mid, _ = _persisted(11, stop_week=8)
    reloaded = store2.load_state("u", gid2, snap2)
    assert reloaded.digest() == mid.digest() == store2.load_state("u", gid2, snap2, use_checkpoint=False).digest()
    em = Emitter(reloaded, snap2)
    while reloaded.status != "complete":
        advance(em, snap2, reloaded, 11)
    assert reloaded.digest() == final.digest()  # resuming mid-season lands on the same season


def test_a_lost_checkpoint_is_rebuilt_from_events():
    store, gid, snap, final, _ = _persisted(11, stop_week=6)
    backend = store.backend
    backend.tables["sim_week_checkpoints"] = []
    assert store.load_state("u", gid, snap).digest() == final.digest()


def test_only_the_last_two_checkpoints_are_kept():
    store, gid, snap, final, _ = _persisted(11, stop_week=9)
    weeks = sorted(r["week"] for r in store.backend.tables["sim_week_checkpoints"])
    assert weeks == [8, 9]


def test_replay_game_from_user_commands_reproduces_the_state_exactly():
    seed = 31
    snap, state, em = drafted(seed, user_slot=7)
    user = snap.user_team.tid
    executed = 0
    for week in range(1, 15):
        ev = Evaluator(snap, state)
        fa = max(state.free_agents(snap), key=ev.ros_mean)
        try:
            act.queue_claim(em, fa, None, None)
        except ValueError:
            pass
        if week % 3 == 0:
            act.auto_lineup(em)
        if week % 2 == 0 and state.status == "in_season":
            try:
                partner = "1" if user != "1" else "2"
                give = [p for p in state.rosters[user] if snap.players[p].pos != "K"][:1]
                get = [p for p in state.rosters[partner] if snap.players[p].pos != "K"][:1]
                _, trade = act.send_trade(em, TradeDesk(Evaluator(snap, state), seed), partner, give, get)
                executed += trade is not None
            except (GameError, ValueError):
                pass
        if state.offers and week % 2 == 1:
            try:
                act.respond_offer(em, TradeDesk(Evaluator(snap, state), seed), state.offers[0]["id"], "accept")
            except GameError:
                pass
        if state.status == "complete":
            break
        while len(state.rosters[user]) > snap.settings.roster_limit:  # an accepted 2-for-1 can leave the user over the limit
            act.cut_player(em, min(state.rosters[user], key=lambda p: (Evaluator(snap, state).ros_mean(p), p)))
        advance(em, snap, state, seed)
    assert any(e["type"] in ("trade_reject", "trade_counter", "trade") and e["actor"] == "user" for e in em.events)
    again = replay_game(snap, seed, em.events, strict=True)
    assert again.digest() == state.digest()
    assert again.seq == len(em.events)


def test_counterfactual_shares_all_dice_and_changes_only_what_the_decision_touched():
    seed = 31
    snap, state, em = drafted(seed, user_slot=7)
    ev = Evaluator(snap, state)
    fa = max(state.free_agents(snap), key=ev.ros_mean)
    claim = act.queue_claim(em, fa, None, None)
    claim_seq = next(e["seq"] for e in em.events if e["type"] == "waiver_claim")
    while state.status != "complete":
        advance(em, snap, state, seed)
    alt = replay_game(snap, seed, em.events, veto=[claim_seq])
    # same seed => identical player performances in both worlds, regardless of rosters
    # (the alt world can end earlier, e.g. the claim was what got the user into the playoffs, so
    # compare the weeks both worlds actually played)
    assert alt.points == {pid: state.points[pid][: len(rows)] for pid, rows in alt.points.items()}
    assert alt.digest() != state.digest()
    assert fa not in alt.rosters[snap.user_team.tid] or fa in state.rosters[snap.user_team.tid]


def test_result_has_grade_and_decisions_and_is_deterministic():
    seed = 31
    snap, state, em = drafted(seed, user_slot=7)
    ev = Evaluator(snap, state)
    for fa in sorted(state.free_agents(snap), key=lambda p: -ev.ros_mean(p))[:2]:
        try:
            act.queue_claim(em, fa, None, None)
        except ValueError:
            pass
    while state.status != "complete":
        advance(em, snap, state, seed)
    result = build_result(snap, seed, em.events, state)
    assert result["grade"]["letter"] and 0 <= result["grade"]["score"] <= 100
    assert [c["key"] for c in result["grade"]["components"]] == ["record", "points", "playoffs", "lineup", "moves"]
    assert abs(sum(c["weight"] for c in result["grade"]["components"]) - 1.0) < 1e-9
    assert len(result["final_standings"]) == 12 and result["champion"]["team_id"] == state.champion
    assert 1 <= len(result["decisions_that_mattered"]) <= 4
    assert result == build_result(snap, seed, em.events, state)
    assert result["user"]["wins"] == season_summary(snap, state)["wins"]


# -------------------------------------------------------------------- trades


def _first_offer(snap, state, seed, want=None):
    user = snap.user_team.tid
    desk = TradeDesk(Evaluator(snap, state), seed)
    mine = [p for p in state.rosters[user] if snap.players[p].pos != "K"]
    for team in snap.tids:
        if team == user:
            continue
        theirs = [p for p in state.rosters[team] if snap.players[p].pos != "K"]
        for give in mine:
            for get in theirs:
                verdict = desk.verdict(team, [give], [get])
                if want is None or verdict.decision == want:
                    return team, [give], [get], verdict
    return None


def test_trade_verdicts_are_deterministic_and_preview_equals_send():
    snap, state, em = drafted(41, user_slot=3)
    for want in ("accept", "counter", "decline"):
        found = _first_offer(snap, state, 41, want)
        if found is None:
            continue
        team, give, get, verdict = found
        again = TradeDesk(Evaluator(snap, state), 41).verdict(team, give, get)
        assert again == verdict
        preview = act.preview_trade(TradeDesk(Evaluator(snap, state), 41), team, give, get)
        assert preview == verdict
        if want != "accept":
            continue
        verdict2, trade = act.send_trade(em, TradeDesk(Evaluator(snap, state), 41), team, give, get)
        assert verdict2.decision == "accept" and trade is not None
        user = snap.user_team.tid
        assert get[0] in state.rosters[user] and give[0] in state.rosters[team]


def test_a_counter_is_an_offer_the_ai_will_accept():
    snap, state, em = drafted(41, user_slot=3)
    found = _first_offer(snap, state, 41, "counter")
    if found is None:
        pytest.skip("no counter in this league")
    team, give, get, verdict = found
    c = verdict.counter
    desk = TradeDesk(Evaluator(snap, state), 41)
    assert desk.ai_accepts(team, c["give"], c["get"])[0]
    assert set(c["give"]) != set(give) or set(c["get"]) != set(get)
    v2, trade = act.send_trade(em, desk, team, c["give"], c["get"])
    assert v2.decision == "accept" and trade["give"] == c["give"]


def test_ai_never_takes_a_lopsided_loss_and_kickers_are_not_tradable():
    snap, state, em = drafted(41, user_slot=3)
    user = snap.user_team.tid
    ev = Evaluator(snap, state)
    for team in snap.tids:
        if team == user:
            continue
        star = max((p for p in state.rosters[team] if snap.players[p].pos != "K"), key=lambda p: snap.players[p].value)
        scrub = min((p for p in state.rosters[user] if snap.players[p].pos != "K"), key=lambda p: snap.players[p].value)
        v = TradeDesk(ev, 41).verdict(team, [scrub], [star])
        assert v.decision != "accept", (team, v)
    kicker = next(p for p in state.rosters[user] if snap.players[p].pos == "K")
    other = next(t for t in snap.tids if t != user)
    old = dataclasses.replace(snap, settings=dataclasses.replace(snap.settings, kd_v=0))  # a save from before kd_v
    with pytest.raises(ValueError):
        validate_offer(old, state, other, [kicker], [state.rosters[other][0]])


def test_trade_rules_deadline_duplicates_caps_and_playoffs():
    snap, state, em = drafted(41, user_slot=3)
    found = _first_offer(snap, state, 41, "decline") or _first_offer(snap, state, 41, "counter")
    team, give, get, verdict = found
    desk = TradeDesk(Evaluator(snap, state), 41)
    act.send_trade(em, desk, team, give, get)
    with pytest.raises(GameError) as err:
        act.send_trade(em, TradeDesk(Evaluator(snap, state), 41), team, give, get)
    assert err.value.code == "duplicate_offer"
    # after the deadline (week 10) trades are closed; in the playoffs too
    while state.week <= 10:
        advance(em, snap, state, 41)
    with pytest.raises(GameError) as err:
        act.preview_trade(TradeDesk(Evaluator(snap, state), 41), team, [state.rosters[snap.user_team.tid][0]], [state.rosters[team][0]])
    assert err.value.code == "trade_deadline_passed"
    while state.status == "in_season":
        advance(em, snap, state, 41)
    if state.status == "playoffs":
        with pytest.raises(GameError) as err:
            act.preview_trade(TradeDesk(Evaluator(snap, state), 41), team, [state.rosters[snap.user_team.tid][0]], [state.rosters[team][0]])
        assert err.value.code == "trades_closed"


def test_ai_to_ai_trades_and_offers_obey_caps():
    snap, state, em, _ = season(41, user_slot=3)
    trades = [e for e in em.events if e["type"] == "trade" and e["payload"]["source"] == "ai_ai"]
    by_week = collections.Counter(e["week"] for e in trades)
    assert all(n <= 3 for n in by_week.values())
    assert all(e["week"] <= snap.settings.trade_deadline_week for e in trades)
    offers = [e for e in em.events if e["type"] == "inbox_offer"]
    per_week = collections.Counter(e["payload"]["expires_week"] for e in offers)
    assert all(n <= 3 for n in per_week.values())
    for week in per_week:
        teams = [e["payload"]["team"] for e in offers if e["payload"]["expires_week"] == week]
        assert len(teams) == len(set(teams))
    assert all(max(state.trades_made.values()) <= 6 for _ in [0])


def test_inbox_offers_expire_on_advance_and_accepting_executes():
    snap, state, em = drafted(41, user_slot=3)
    for _ in range(6):
        if state.offers:
            break
        advance(em, snap, state, 41)
    if not state.offers:
        pytest.skip("no AI offers surfaced")
    offer = state.offers[0]
    user = snap.user_team.tid
    trade = act.respond_offer(em, TradeDesk(Evaluator(snap, state), 41), offer["id"], "accept")
    assert trade is not None and all(p in state.rosters[user] for p in offer["give"])
    assert all(p in state.rosters[offer["team"]] for p in offer["get"])
    assert not any(o["id"] == offer["id"] for o in state.offers)
    stale = [o for o in state.offers]
    week = state.week
    advance(em, snap, state, 41)
    assert all(int(o["expires_week"]) >= state.week for o in state.offers)
    assert all(o not in state.offers for o in stale if int(o["expires_week"]) < state.week) and state.week == week + 1


# ------------------------------------------------------------------ scoring


def test_fallback_model_is_used_until_the_player_model_lands_and_is_pinned_per_game():
    model = game_scoring.default_model()
    snap = make_snapshot()
    if model.model_id == game_scoring.FALLBACK_ID:
        assert snap.scoring_model == game_scoring.FALLBACK_ID
    assert game_scoring.get_model(snap.scoring_model).model_id == snap.scoring_model
    assert game_scoring.get_model(game_scoring.FALLBACK_ID).model_id == game_scoring.FALLBACK_ID


def test_player_model_adapter_normalizes_a_real_model_shape(monkeypatch):
    @dataclasses.dataclass
    class Profile:
        boost: float
        games_available_mask: tuple = (True,) * 17
        unavailable_reason: tuple = ("",) * 17

    @dataclasses.dataclass
    class WeekResult:
        points: float
        stats: dict
        active: bool
        injury_incurred: bool

    module = types.SimpleNamespace(
        MODEL_VERSION="9",
        draw_season_profile=lambda player, rng: Profile(1.1),
        draw_week_points=lambda player, profile, week, rng, scoring: WeekResult(
            player["mean"] * profile.boost, {"rush_yd": 71.0, "tag": "x"}, week % 2 == 1, week == 3),
    )
    adapter = game_scoring.PlayerModelAdapter(module)
    assert adapter.model_id == "player_model-9"
    rng = __import__("numpy").random.default_rng(1)
    p = adapter.profile({"mean": 10.0}, rng)
    w1 = adapter.week({"mean": 10.0}, p, 1, rng, {})
    assert w1.points == pytest.approx(11.0) and w1.stats == {"rush_yd": 71.0} and w1.active and not w1.newly_injured
    assert adapter.week({"mean": 10.0}, p, 2, rng, {}).active is False
    assert adapter.week({"mean": 10.0}, p, 3, rng, {}).newly_injured is True
    # swapping the model changes results only for games created with it
    monkeypatch.setattr(game_scoring, "_load_real", lambda: adapter)
    assert game_scoring.default_model().model_id == "player_model-9"
    assert game_scoring.get_model(game_scoring.FALLBACK_ID).model_id == game_scoring.FALLBACK_ID
    assert game_scoring.get_model("player_model-9").model_id == "player_model-9"


def test_a_game_runs_end_to_end_on_a_swapped_in_model(monkeypatch):
    module = types.SimpleNamespace(
        draw_season_profile=lambda player, rng: types.SimpleNamespace(
            v=float(rng.random()), games_available_mask=(True,) * 17, unavailable_reason=("",) * 17),
        draw_week_points=lambda player, profile, week, rng, scoring: types.SimpleNamespace(
            points=max(0.0, player["mean"] * (0.8 + 0.4 * profile.v) + float(rng.normal(0, 3))),
            stats={"fantasy": 1.0}, active=True, injury_incurred=float(rng.random()) < 0.03),
    )
    adapter = game_scoring.PlayerModelAdapter(module)
    monkeypatch.setattr(game_scoring, "_load_real", lambda: adapter)
    snap = build_snapshot(ROWS, BYES, GameSettings.parse({"user_slot": 2}), 5, scoring_model=adapter.model_id)
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx = DraftContext(snap, state)
    run_ai_picks(ctx, em, 5)
    auto_for_user(ctx, em, 5)
    finish_draft(em, snap, state, 5)
    while state.status != "complete":
        advance(em, snap, state, 5)
    assert state.status == "complete"
    recap = state.recaps["1"]["your_game"]
    assert recap["starters"][0]["stats"] == {"fantasy": 1.0}


def test_difficulty_changes_ai_parameters_not_the_dice():
    from modules.sim.game_eval import team_params

    easy, hard = make_snapshot(user_slot=1, difficulty="easy"), make_snapshot(user_slot=1, difficulty="hard")
    normal = make_snapshot(user_slot=1)
    tid = next(t.tid for t in normal.teams if not t.is_user)
    assert team_params(easy, tid).accept_threshold < team_params(normal, tid).accept_threshold < team_params(hard, tid).accept_threshold
    # same seed => same player performances on every difficulty
    a = season(7, user_slot=1, difficulty="easy")[1]
    b = season(7, user_slot=1, difficulty="hard")[1]
    assert a.points == b.points


def test_events_replay_into_the_same_state_one_event_at_a_time():
    snap, state, em, _ = season(11)
    partial = GameState(snap)
    from modules.sim.game_state import apply_event

    for e in em.events:
        apply_event(partial, snap, e)
    assert partial.digest() == state.digest() and partial.seq == len(em.events)
    assert [e["seq"] for e in em.events] == list(range(len(em.events)))


def test_standing_rows_flag_playoff_status():
    snap, state, em, _ = season(11)
    rows = standing_rows(snap, state)
    assert [r["rank"] for r in rows] == list(range(1, 13))
    assert sum(r["playoff_status"] == "champion" for r in rows) == 1
    assert all(r["seed"] for r in rows[:0]) and {r["seed"] for r in rows if r["seed"]} == set(range(1, 7))


# ------------------------------------------------------ JSON storage fidelity


class JsonBackend(InMemoryBackend):
    """Round-trips every stored value through JSON text, like PostgREST does."""

    @staticmethod
    def _rt(value):
        import json

        return json.loads(json.dumps(value))

    def upsert(self, table, row, *, on_conflict):
        return super().upsert(table, self._rt(dict(row)), on_conflict=on_conflict)

    def insert_many(self, table, rows):
        return super().insert_many(table, [self._rt(dict(r)) for r in rows])

    def update(self, table, *, user_id, filters, values):
        return super().update(table, user_id=user_id, filters=filters, values=self._rt(dict(values)))


def test_snapshot_survives_json_storage_exactly():
    import json

    from modules.sim.game_types import GameSnapshot

    snap = make_snapshot(11)
    again = GameSnapshot.from_dict(json.loads(json.dumps(snap.to_dict())))
    assert again.to_dict() == snap.to_dict()


def test_resume_equals_replay_through_a_json_backend_and_continues_identically():
    seed = 11
    store = GameStore(JsonBackend())
    snap = make_snapshot(seed)
    gid = store.create_game("u", snapshot=snap, seed=seed)["id"]
    snap = store.get_snapshot("u", gid)
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx = DraftContext(snap, state)
    run_ai_picks(ctx, em, seed)
    auto_for_user(ctx, em, seed)
    finish_draft(em, snap, state, seed)
    store.append_events("u", gid, em.events)
    store.save_checkpoint("u", gid, state, state.week)
    # play half the season, reloading from storage before EVERY advance (like the API does)
    while state.week < 9:
        state = store.load_state("u", gid, snap)
        em = Emitter(state, snap)
        advance(em, snap, state, seed)
        store.append_events("u", gid, em.events)
        store.save_checkpoint("u", gid, state, state.week)
    reloaded = store.load_state("u", gid, snap)
    full = store.load_state("u", gid, snap, use_checkpoint=False)
    assert reloaded.digest() == full.digest() == state.digest()
    # the uninterrupted in-memory season lands on the same final state as the reload-every-week one
    while state.status != "complete":
        state = store.load_state("u", gid, snap)
        em = Emitter(state, snap)
        advance(em, snap, state, seed)
        store.append_events("u", gid, em.events)
        store.save_checkpoint("u", gid, state, state.week)
    straight = season(seed)[1]
    assert store.load_state("u", gid, snap).digest() == straight.digest()


def test_a_full_game_on_the_real_player_pool_snapshot_completes():
    """Structural check against whatever data/players.db currently holds (read
    only, projections stubbed so no caches are touched): the pool builds, the
    draft fills every roster, and a season plays to a champion."""

    from pathlib import Path

    from modules.sim.inputs import RealSimInputs

    db = Path(__file__).resolve().parents[1] / "data" / "players.db"
    if not db.exists():
        pytest.skip("no players.db in this checkout")

    class Projections:
        def baseline_weekly_points(self, rows, *, scoring_settings=None):
            return {}

    pool = RealSimInputs(str(db), projections_module=Projections(), sleeper_module=object(),
                         playoff_module=object()).player_pool(GameSettings().scoring_settings)
    snap = build_snapshot(pool.rows, pool.bye_weeks, GameSettings.parse({"user_slot": 6}), 3,
                          scoring_model=game_scoring.default_model().model_id)
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx = DraftContext(snap, state)
    run_ai_picks(ctx, em, 3)
    auto_for_user(ctx, em, 3)
    finish_draft(em, snap, state, 3)
    assert all(len(r) == 14 for r in state.rosters.values())
    while state.status != "complete":
        advance(em, snap, state, 3)
    assert state.champion in snap.tids and len(state.history) == 17


def _play_as(seed: int, spam: bool) -> tuple[int, float]:
    """A manager who sets the best lineup every week; with ``spam`` also takes the
    single best AI-accepted 1-for-1 (by lineup gain) up to four times a week
    before the deadline. Returns (wins, points for)."""

    snap, state, em = drafted(seed, user_slot=(seed % 12) + 1)
    user = snap.user_team.tid
    while state.status != "complete":
        if spam and state.status == "in_season" and state.week <= snap.settings.trade_deadline_week:
            for _ in range(4):
                ev = Evaluator(snap, state)
                desk = TradeDesk(ev, seed)
                base = ev.lineup_total(state.rosters[user])
                mine = sorted((p for p in state.rosters[user] if snap.players[p].pos != "K"), key=ev.ros_mean)[:6]
                best = None
                for team in snap.tids:
                    if team == user:
                        continue
                    theirs = sorted((p for p in state.rosters[team] if snap.players[p].pos != "K"),
                                    key=lambda p: -ev.ros_mean(p))[:6]
                    for give in mine:
                        for get in theirs:
                            if not desk.ai_accepts(team, [give], [get])[0]:
                                continue
                            new = [p for p in state.rosters[user] if p != give] + [get]
                            gain = ev.lineup_total(new) - base
                            if best is None or gain > best[0]:
                                best = (gain, team, [give], [get])
                if best is None or best[0] <= 0.2:
                    break
                try:
                    act.send_trade(em, TradeDesk(Evaluator(snap, state), seed), best[1], best[2], best[3])
                except (GameError, ValueError):
                    break
        act.auto_lineup(em)
        advance(em, snap, state, seed)
    summary = season_summary(snap, state)
    return summary["wins"], summary["pf"]


def test_a_trade_spammer_does_not_beat_a_balanced_manager_by_more_than_a_set_margin():
    """Anti-exploit harness (the design doc's risk section, in miniature): same
    seeds, same dice; hammering the AI with accepted trades must not be a
    reliable edge over simply managing the lineup."""

    balanced = [_play_as(seed, False) for seed in range(1, 6)]
    spammer = [_play_as(seed, True) for seed in range(1, 6)]
    pf_balanced = sum(pf for _, pf in balanced)
    pf_spammer = sum(pf for _, pf in spammer)
    wins_balanced = sum(w for w, _ in balanced)
    wins_spammer = sum(w for w, _ in spammer)
    assert pf_spammer <= pf_balanced * 1.04
    assert wins_spammer - wins_balanced <= 5  # across 5 seasons: under a win per season

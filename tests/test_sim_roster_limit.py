"""Roster limit (limit_v 1): being over the limit never blocks advancing, only acquiring players. Old saves replay as before."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from modules.sim import game_actions as act, game_dynasty as dyn, game_engine as engine, game_simto as simto
from modules.sim.game_ai import TradeDesk
from modules.sim.game_eval import Evaluator
from modules.sim.game_types import GameError, GameSettings
from test_sim_dynasty import Run

# Digest of a dynasty game (seed of test_sim_dynasty.Run) with limit_v 0 after two seasons, two offseasons and five weeks,
# computed on the engine as it was before limit_v existed. An old save must keep replaying to exactly this.
GOLDEN_LEGACY_DIGEST = "dedfcfec4052ddd2e0f9401b71c40b8bb35a660933be2e5ce4c63bc3c9208a29"


def with_limit_v(run, v):
    object.__setattr__(run.root, "settings", replace(run.root.settings, limit_v=v, hint_v=0, **({"names_v": 0} if v == 0 else {})))  # a save from before limit_v also predates names_v
    run.root.__dict__.pop("_views", None)
    return run


def overfill(run, n):
    user = run.snap.user_team.tid
    free = [p for p in run.snap.pids if p not in run.state.owner_map()]
    run.state.rosters[user].extend(free[:max(0, run.snap.settings.roster_limit + n - len(run.state.rosters[user]))])
    return user


def five_weeks(run):
    for _ in range(5):
        run.em.snap = run.snap
        engine.advance(run.em, run.snap, run.state, run.sd)


def test_golden_digest_a_limit_v0_save_replays_exactly_as_before_the_soft_limit():
    r = with_limit_v(Run(), 0)
    assert "limit_v" not in r.root.settings.to_dict() and not r.root.settings.soft_limit
    r.play_season(); r.offseason(); r.play_season(); r.offseason()
    five_weeks(r)
    assert r.state.digest() == GOLDEN_LEGACY_DIGEST and r.state.season_no == 3
    # a new game (limit_v 1) that never goes over the limit is the same game event for event
    n = Run()
    assert n.root.settings.limit_v == 1 and n.root.settings.to_dict()["limit_v"] == 1
    object.__setattr__(n.root, "settings", replace(n.root.settings, names_v=0, hint_v=0))  # new rookie names (names_v 1) are the one other new-game difference
    n.root.__dict__.pop("_views", None)
    n.play_season(); n.offseason(); n.play_season(); n.offseason()
    five_weeks(n)
    assert n.state.digest() == GOLDEN_LEGACY_DIGEST


def test_settings_roundtrip_and_old_saves_default_to_the_hard_limit():
    s = GameSettings.parse({})
    assert s.limit_v == 1 and GameSettings.from_dict(s.to_dict()).limit_v == 1
    d = s.to_dict(); d.pop("limit_v")
    assert GameSettings.from_dict(d).soft_limit is False


def test_old_save_over_the_limit_still_blocks_advance_and_start_season():
    r = with_limit_v(Run(), 0)
    overfill(r, 3)
    with pytest.raises(GameError) as e:
        engine.advance(r.em, r.snap, r.state, r.sd)
    assert e.value.code == "roster_over_limit" and e.value.detail["cuts_needed"] == 3


def test_over_the_limit_never_blocks_advancing_and_the_week_scores_normally():
    r = Run()
    user = overfill(r, 5)
    over = len(r.state.rosters[user]) - r.snap.settings.roster_limit
    assert over == 5
    before_lineup = [list(x) for x in r.state.lineups[user]]
    recap = engine.advance(r.em, r.snap, r.state, r.sd)[0]
    assert recap["week"] == 1 and recap["your_game"]["your_pts"] > 0
    assert len(r.state.rosters[user]) >= r.snap.settings.roster_limit + 5 - 0  # nobody was cut for the user
    assert [s for s, _ in r.state.lineups[user]] == [s for s, _ in before_lineup]
    for t in r.snap.tids:  # AI teams stay trimmed
        if t != user:
            assert len(r.state.rosters[t]) <= r.snap.settings.roster_limit


def test_the_offseason_can_start_the_season_while_over_the_limit_and_ai_teams_still_trim():
    r = Run()
    r.play_season()
    r.em.snap = r.snap
    dyn.start_rookie_draft(r.em)
    dyn.run_ai_rookie_picks(r.em, r.sd)
    dyn.auto_rookie_draft(r.em, r.sd)
    user = overfill(r, 5)  # the draft class plus what we already carried: well over the limit at the cut-down stage
    assert r.state.offseason["stage"] == "cutdown"
    dyn.start_next_season(r.em, r.sd)
    assert r.state.status == "in_season" and r.state.week == 1 and r.state.season_no == 2
    assert len(r.state.rosters[user]) > r.snap.settings.roster_limit  # the rookie draft left us over: the season started anyway
    for t in r.snap.tids:
        if t != user:
            assert len(r.state.rosters[t]) <= r.snap.settings.roster_limit
    r.em.snap = r.snap
    assert engine.advance(r.em, r.snap, r.state, r.sd)[0]["week"] == 1  # and the first week plays


def test_acquiring_is_blocked_while_over_but_cuts_ir_and_neutral_moves_are_allowed():
    r = Run()
    user = overfill(r, 3)
    free = [p for p in r.snap.pids if p not in r.state.owner_map()]
    drop = next(p for p in r.state.rosters[user] if p not in {x for _, x in r.state.lineups[user]})
    with pytest.raises(GameError) as e:
        act.queue_claim(r.em, free[10], None, None)  # a free-agent add
    assert e.value.code == "roster_full" and "Over the limit by 3" in str(e.value)
    act.queue_claim(r.em, free[10], drop, None)  # a swap does not grow the roster
    act.cut_player(r.em, drop)
    assert act.over_by(r.snap, r.state, user) == 2
    # trades: more in than out is blocked, even or fewer is fine
    S = r.snap.settings
    partner = next(t for t in r.snap.tids if t != user)
    theirs = [p for p in r.state.rosters[partner] if r.snap.players[p].pos in ("QB", "RB", "WR", "TE")][:3]
    mine = [p for p in r.state.rosters[user] if r.snap.players[p].pos in ("QB", "RB", "WR", "TE")][:3]
    with pytest.raises(GameError) as e:
        act.check_roster_room(r.snap, r.state, user, mine[:1], theirs[:2])
    assert e.value.code == "roster_full"
    act.check_roster_room(r.snap, r.state, user, mine[:2], theirs[:2])
    act.check_roster_room(r.snap, r.state, user, mine[:2], theirs[:1])
    with pytest.raises(GameError):
        act.send_trade(r.em, TradeDesk(Evaluator(r.snap, r.state), r.sd), partner, mine[:1], theirs[:2])
    # at the limit exactly, adding is also blocked; back under, it is allowed
    while act.over_by(r.snap, r.state, user) > 0:
        act.cut_player(r.em, next(p for p in r.state.rosters[user] if p not in {x for _, x in r.state.lineups[user]} and p not in mine[:2]))
    assert len(r.state.rosters[user]) == S.roster_limit
    with pytest.raises(GameError):
        act.check_roster_room(r.snap, r.state, user, [], theirs[:1])
    act.cut_player(r.em, next(p for p in r.state.rosters[user] if p not in {x for _, x in r.state.lineups[user]} and p not in mine[:2]))
    act.check_roster_room(r.snap, r.state, user, [], theirs[:1])


def test_old_saves_are_not_gated_on_trades_or_claims():
    r = with_limit_v(Run(), 0)
    user = r.snap.user_team.tid
    partner = next(t for t in r.snap.tids if t != user)
    theirs = [p for p in r.state.rosters[partner] if r.snap.players[p].pos == "WR"][:2]
    act.check_roster_room(r.snap, r.state, user, [], theirs)  # no error: the old engine let the user go over and cut after


def test_a_waiver_swap_while_over_the_limit_resolves_but_a_plain_add_is_turned_away():
    r = Run()
    user = overfill(r, 2)
    free = [p for p in r.snap.pids if p not in r.state.owner_map()]
    bench = [p for p in r.state.rosters[user] if p not in {x for _, x in r.state.lineups[user]}]
    r.state.claims.append({"id": "c1", "team": user, "add": free[20], "drop": bench[0], "start_slot": None})
    r.state.claims.append({"id": "c2", "team": user, "add": free[21], "drop": None, "start_slot": None})
    recap = engine.advance(r.em, r.snap, r.state, r.sd)[0]
    got = {w["add"]["id"]: w for w in recap["waivers"] if w["is_you"]}
    assert got[free[20]]["ok"] and not got[free[21]]["ok"] and got[free[21]]["reason"] == "roster_full"


def test_the_trade_builder_count_matches_the_server_active_roster_only():
    """Client (simTradeFit over the active roster) and server (TradeDesk.roster_size_after) agree: IR and taxi never count."""
    r = Run()
    user = r.snap.user_team.tid
    partner = next(t for t in r.snap.tids if t != user)
    desk = TradeDesk(Evaluator(r.snap, r.state), r.sd)
    give = [p for p in r.state.rosters[user] if r.snap.players[p].pos == "WR"][:1]
    get = [p for p in r.state.rosters[partner] if r.snap.players[p].pos == "RB"][:2]
    assert desk.roster_size_after(user, give, get) == len(r.state.rosters[user]) - 1 + 2
    ir_like = list(r.state.ir[user]) + list(r.state.taxi[user])
    assert all(p not in r.state.rosters[user] for p in ir_like)
    assert desk.roster_size_after(user, ir_like, get) == len(r.state.rosters[user]) + 2  # giving a reserve frees no active spot


def test_old_save_cannot_start_the_season_while_over_the_limit():
    r = with_limit_v(Run(), 0)
    r.play_season()
    r.em.snap = r.snap
    dyn.start_rookie_draft(r.em)
    dyn.run_ai_rookie_picks(r.em, r.sd)
    dyn.auto_rookie_draft(r.em, r.sd)
    overfill(r, 4)
    with pytest.raises(GameError) as e:
        dyn.start_next_season(r.em, r.sd)
    assert e.value.code == "roster_over_limit" and e.value.detail["cuts_needed"] == 4

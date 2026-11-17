"""vorp_v 1: trades value a player over the league's starter line, so a backup QB is cheap and a counter asks for the smallest fair add.

Product report: "it's almost impossible to trade for a QB, even the worst one they counter for one of my best WRs along with everything else".
Cause: a QB was priced as points over the free-agent wire, and the wire is bare of QBs (every team stocks two), so a QB12-QB20 looked like a star;
and a counter only ever tried the AI's eight most wanted assets (the user's stars)."""

from __future__ import annotations

import pytest

from modules.sim.game_ai import TradeDesk
from modules.sim.game_draft import DraftContext, auto_for_user, run_ai_picks
from modules.sim.game_engine import advance, finish_draft
from modules.sim.game_eval import USER_PARAMS, Evaluator
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import VORP_VERSION, GameSettings
from modules.sim.synthetic import build_synthetic_pool

ROWS, BYES = build_synthetic_pool(7)
MODEL = "player_model-player-model-6"
SEEDS = (11, 12, 13, 14)


def _game(seed: int, *, vorp: bool, superflex: bool = False, week: int = 3):
    d = GameSettings.parse({"user_slot": 4, "superflex": superflex}).to_dict()
    if not vorp:
        d.pop("vorp_v", None)
    d.pop("defense_v", None)  # these price pins predate opponent defenses
    d.pop("incumbent_v", None)
    d.pop("cap_v", None)  # ... and the shared position limit (tests/test_sim_cap_v.py)
    snap = build_snapshot(ROWS, BYES, GameSettings.from_dict(d), seed, scoring_model=MODEL)
    state = GameState(snap)
    em = Emitter(state, snap)
    run_ai_picks(DraftContext(snap, state), em, seed)
    auto_for_user(DraftContext(snap, state), em, seed)
    finish_draft(em, snap, state, seed)
    for _ in range(week - 1):
        advance(em, snap, state, seed)
    return snap, state


def _qb_market(vorp: bool, superflex: bool):
    """For every AI team with a true backup QB: the neutral worth of the cheapest single user asset it accepts for him, and the counter it
    makes to a median-asset offer."""

    prices: list[float] = []
    asks: list[float] = []
    star_asks = 0
    for seed in SEEDS:
        snap, state = _game(seed, vorp=vorp, superflex=superflex)
        ev = Evaluator(snap, state)
        desk = TradeDesk(ev, seed, state.week)
        user = snap.user_team.tid
        mine = [p for p in state.rosters[user] if snap.players[p].pos in ("RB", "WR", "TE")]
        neutral = {p: ev.worth(USER_PARAMS, p) for p in mine}
        top2 = sorted(neutral.values(), reverse=True)[1]
        for ai in snap.tids:
            qbs = sorted((p for p in state.rosters.get(ai, []) if snap.players[p].pos == "QB"), key=ev.ros_mean)
            if ai == user or len(qbs) <= (2 if superflex else 1):
                continue
            backup = qbs[0]
            ok = [neutral[p] for p in sorted(mine, key=neutral.get) if desk.verdict(ai, [p], [backup]).decision == "accept"]
            prices.append(ok[0] if ok else 100.0)
            median = sorted(mine, key=neutral.get)[len(mine) // 2]
            counter = desk.verdict(ai, [median], [backup]).counter
            for pid in (counter or {}).get("give", []):
                if pid != median:
                    asks.append(ev.worth(USER_PARAMS, pid))
                    star_asks += ev.worth(USER_PARAMS, pid) >= top2
    return prices, asks, star_asks


def test_the_gate_is_on_for_new_games_and_absent_on_old_saves():
    assert GameSettings.parse({"user_slot": 4}).vorp_v == VORP_VERSION == 1
    d = GameSettings.parse({"user_slot": 4}).to_dict()
    assert d["vorp_v"] == 1
    d.pop("vorp_v")
    old = GameSettings.from_dict(d)
    assert old.vorp_v == 0 and "vorp_v" not in old.to_dict()  # an old save serializes exactly as it did


def test_old_saves_price_players_exactly_as_before():
    snap, state = _game(11, vorp=False)
    ev = Evaluator(snap, state)
    assert not snap.settings.vorp_v and ev.replacement("QB") == ev._repl["QB"]  # the free-agent wire alone
    new_snap, new_state = _game(11, vorp=True)
    new_ev = Evaluator(new_snap, new_state)
    assert new_ev.replacement("QB") == ev.replacement("QB")  # waiver and depth choices keep the wire's level
    TradeDesk(new_ev, 11)  # a trade desk prices over the starter line
    assert new_ev.replacement("QB") >= ev.replacement("QB")


@pytest.mark.parametrize("superflex", [False, True])
def test_a_bad_backup_qb_is_cheap_and_counters_do_not_ask_for_stars(superflex):
    old_prices, old_asks, old_stars = _qb_market(False, superflex)
    prices, asks, stars = _qb_market(True, superflex)
    assert prices and old_prices
    assert sum(prices) / len(prices) < 0.7 * sum(old_prices) / len(old_prices)  # a backup costs far less than it did
    assert max(prices) < 100.0  # and some modest single asset always buys him
    assert stars == 0 and stars <= old_stars  # a counter never reaches for the user's best two assets
    if asks and old_asks:
        assert sum(asks) / len(asks) < sum(old_asks) / len(old_asks)


def test_a_starting_qb_still_costs_a_fair_amount():
    checked = 0
    for seed in SEEDS:
        snap, state = _game(seed, vorp=True)
        ev = Evaluator(snap, state)
        desk = TradeDesk(ev, seed, state.week)
        user = snap.user_team.tid
        mine = [p for p in state.rosters[user] if snap.players[p].pos in ("RB", "WR", "TE")]
        junk = min(mine, key=lambda p: ev.worth(USER_PARAMS, p))
        for ai in snap.tids:
            qbs = sorted((p for p in state.rosters[ai] if snap.players[p].pos == "QB"), key=lambda p: -ev.ros_mean(p))
            if ai == user or not qbs:
                continue
            starter = qbs[0]
            if ev.worth(USER_PARAMS, starter, healthy=True) < 40:
                continue
            checked += 1
            assert desk.verdict(ai, [junk], [starter]).decision != "accept"  # a good starter is not given away for the user's worst asset
    assert checked >= 8


def test_the_starter_line_is_a_real_qb_in_a_one_qb_league_and_a_superflex_one_counts_two():
    snap, state = _game(11, vorp=True)
    ev = Evaluator(snap, state)
    assert ev.starter_count("QB") == 1.0
    qbs = sorted((ev.ros_mean(p) for p in snap.pids if snap.players[p].pos == "QB"), reverse=True)
    assert ev.starter_line("QB") == qbs[len(snap.teams)]  # the first QB no typical team starts
    sf_snap, sf_state = _game(11, vorp=True, superflex=True)
    sf_ev = Evaluator(sf_snap, sf_state)
    assert sf_ev.starter_count("QB") == 2.0 and sf_ev.starter_line("QB") < ev.starter_line("QB")

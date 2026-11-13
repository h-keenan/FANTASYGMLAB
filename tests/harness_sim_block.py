"""Trade-block harness: offers per week and acceptance, with and without a block, over several seeds.

    PYTHONPATH=. python tests/harness_sim_block.py [seeds]

Reports, per variant: offers a week (mean / max), the share that answer the block, how often the user accepting a block offer
executes a legal trade, AI teams shopping a week (mean, by stance) and how the shelves change week to week."""

from __future__ import annotations

import statistics
import sys

sys.path.insert(0, "tests")

from modules.sim import game_actions as act, game_block as blk, game_engine as engine  # noqa: E402
from modules.sim.game_ai import TradeDesk  # noqa: E402
from modules.sim.game_eval import USER_PARAMS, Evaluator  # noqa: E402
from modules.sim.game_state import Emitter  # noqa: E402
from modules.sim.types import is_pick_id  # noqa: E402
from test_sim_dynasty import Run  # noqa: E402


def run_one(seed: int, with_block: bool, hint: str | None):
    r = Run(seed=seed)
    user = r.snap.user_team.tid
    ev = Evaluator(r.snap, r.state)
    mine = sorted((p for p in r.state.rosters[user] if r.snap.players[p].pos in ("QB", "RB", "WR", "TE")), key=lambda p: (-ev.ros_mean(p), p))
    if with_block:
        em = Emitter(r.state, r.snap)
        for p in mine[:4]:
            blk.set_block(em, p, True, hint)
        r.em.events.extend(em.events)
    offers, via, accepted, legal, ai_shelves, stances = [], [], 0, 0, [], {}
    deadline = r.snap.settings.trade_deadline_week
    for _ in range(deadline):
        if r.state.status != "in_season" or r.state.week > deadline:
            break
        r.em.snap = r.snap
        engine.advance(r.em, r.snap, r.state, r.sd)
        offers.append(len(r.state.offers))
        vb = [o for o in r.state.offers if o.get("via_block")]
        via.append(len(vb))
        shelves = blk.league_blocks(r.snap, r.state, Evaluator(r.snap, r.state), r.sd)
        ai_shelves.append(len(shelves))
        for b in shelves:
            stances[b["stance"]] = stances.get(b["stance"], 0) + 1
        if vb:
            o = vb[0]
            desk = TradeDesk(Evaluator(r.snap, r.state), r.sd, r.state.week)
            ok = desk.legal_for_counter(o["team"], o["give"], o["get"]) and desk.legal_for_counter(user, o["get"], o["give"])
            legal += int(ok)
            before = len(r.state.rosters[user])
            act.respond_offer(r.em, desk, o["id"], "accept")
            accepted += int(all(p in r.state.holdings(user) or is_pick_id(p) for p in o["give"]) and len(r.state.rosters[user]) <= max(before, r.snap.settings.roster_limit))
    return offers, via, accepted, legal, ai_shelves, stances


def main(n: int) -> None:
    print(f"{'variant':<22}{'offers/wk':>10}{'max':>5}{'block share':>13}{'block offers':>14}{'accepted legal':>16}{'AI shelves/wk':>15}")
    for label, wb, hint in (("no block", False, None), ("block", True, None), ("block, looking WR", True, "WR")):
        offers, via, acc, legal, shelves, stances = [], [], 0, 0, [], {}
        for seed in range(1, n + 1):
            o, v, a, l, s, st = run_one(4000 + seed, wb, hint)
            offers += o; via += v; acc += a; legal += l; shelves += s
            for k, c in st.items():
                stances[k] = stances.get(k, 0) + c
        total = sum(offers) or 1
        print(f"{label:<22}{statistics.mean(offers):>10.2f}{max(offers):>5}{sum(via) / total:>13.0%}{sum(via):>14}{f'{acc}/{legal}':>16}{statistics.mean(shelves):>15.2f}   stances {stances}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6)

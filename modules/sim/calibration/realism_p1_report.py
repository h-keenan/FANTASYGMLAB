"""Realism P1 harness (docs/audits/2026-11-realism-advice-audit-2.md): before / after tables for ``wire_v`` (waiver contests), and the
later ``need_v`` / ``cap_v`` / ``posture_v`` tables as they are added.

    python -m modules.sim.calibration.realism_p1_report wire [--seeds 8] [--flags '{"wire_v": 0}']

Redraft games on the committed 2025 panel pool, 12 teams, the user rotating through draft slots. Never touches data/players.db.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import replace
from typing import Any

from modules.sim import game_scoring
from modules.sim.calibration import dataset, tail_report
from modules.sim.game_actions import queue_claim
from modules.sim.game_draft import DraftContext, auto_for_user, run_ai_picks
from modules.sim.game_engine import advance, finish_draft, waiver_order
from modules.sim.game_eval import USER_PARAMS, Evaluator
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GameSettings


def _pool():
    prows = dataset.load_panel()
    return tail_report.pool_from_panel(prows)


def _new_game(seed: int, flags: dict[str, int], extra: dict[str, Any] | None = None):
    pool, byes = _pool()
    raw = {"user_slot": 1 + (seed * 5) % 12, "scoring": "ppr", "teams": 12, **(extra or {})}
    settings = replace(GameSettings.parse(raw), **flags)
    model_id = game_scoring.default_model().model_id
    snap = build_snapshot(pool, byes, settings, seed, scoring_model=model_id)
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx = DraftContext(snap, state)
    run_ai_picks(ctx, em, seed)
    auto_for_user(ctx, em, seed)
    finish_draft(em, snap, state, seed)
    return snap, state


def _user_queue_best(em: Emitter, snap, state) -> int:
    """The edge the audit describes: every week the user queues the three most valuable free agents against his three least valuable players."""

    user = snap.user_team.tid
    ev = Evaluator(snap, state)
    owned = state.owner_map()
    fas = sorted((p for p in snap.pids if p not in owned and state.out.get(p, 0) == 0), key=lambda p: (-ev.worth(USER_PARAMS, p), p))
    roster = sorted(state.rosters[user], key=lambda p: (ev.worth(USER_PARAMS, p), p))
    n = 0
    for add, drop in zip(fas[:3], roster[:3]):
        try:
            queue_claim(em, add, drop, None)
            n += 1
        except (ValueError, Exception):  # noqa: BLE001 - a rejected queue is just not counted
            pass
    return n


def wire_table(seeds: int, flags: dict[str, int]) -> dict[str, Any]:
    won = lost = 0
    by_pri = {"top": [0, 0], "bottom": [0, 0]}
    ai_claims = 0
    for seed in range(1, seeds + 1):
        snap, state = _new_game(seed, flags)
        user = snap.user_team.tid
        while state.status == "in_season":
            em = Emitter(state, snap)
            if state.week <= snap.settings.regular_weeks - 1:
                _user_queue_best(em, snap, state)
            order = waiver_order(snap, state)
            half = "top" if order.index(user) < len(order) // 2 else "bottom"
            seen = len(state.transactions)
            before = len(em.events) if hasattr(em, "events") else 0
            advance(em, snap, state, seed)
            for e in (em.events[before:] if hasattr(em, "events") else []):
                if e.get("type") != "waiver_result":
                    continue
                p = e["payload"] if "payload" in e else e
                if p.get("team") == user and p.get("claim_id"):
                    ok = bool(p.get("ok"))
                    if ok:
                        won += 1
                    elif p.get("reason") == "taken":
                        lost += 1
                    else:
                        continue
                    by_pri[half][0 if ok else 1] += 1
                elif p.get("team") != user:
                    ai_claims += 1
            del seen
    total = max(1, won + lost)
    rate = lambda a: round(a[0] / max(1, a[0] + a[1]), 3)  # noqa: E731
    return {
        "user_claims_contested_or_won": won + lost, "user_win_rate": round(won / total, 3),
        "win_rate_when_priority_top_half": rate(by_pri["top"]), "win_rate_when_priority_bottom_half": rate(by_pri["bottom"]),
        "ai_claims_per_game": round(ai_claims / seeds, 1),
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("table", choices=["wire"])
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--flags", default="{}", help="JSON of GameSettings overrides, e.g. '{\"wire_v\": 0}'")
    args = ap.parse_args(argv)
    flags = {str(k): int(v) for k, v in json.loads(args.flags).items()}
    out = {"wire": wire_table}[args.table](args.seeds, flags)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

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


def need_table(seeds: int, flags: dict[str, int]) -> dict[str, Any]:
    """The Needs / Strength tags against real holes. Per format (one QB / superflex), every league-week from week 2 on:
    how many of the 12 teams carry a tag at each position, and what the tag predicts (the AI team's realized points from that position's starters
    that week against the league mean of the same position and week: a real need should score under 1.0, a strength over)."""

    from modules.sim.game_need import position_report

    out: dict[str, Any] = {}
    for fmt, extra in (("one_qb", {}), ("superflex", {"superflex": True})):
        counts: dict[str, list[int]] = {}
        str_counts: dict[str, list[int]] = {}
        realized: dict[str, dict[str, list[float]]] = {"need": {}, "ok": {}, "strength": {}}
        empty = {"need": [0, 0], "ok": [0, 0], "strength": [0, 0]}
        qb_need_sf = 0
        for seed in range(1, seeds + 1):
            snap, state = _new_game(seed, flags, extra)
            user = snap.user_team.tid
            while state.status == "in_season":
                w = state.week
                if w >= 2:
                    ev = Evaluator(snap, state)
                    rep = position_report(snap, ev)
                    for pos in {e["pos"] for e in rep[user]}:
                        counts.setdefault(pos, []).append(sum(1 for t in snap.tids if next(e for e in rep[t] if e["pos"] == pos)["level"] == "need"))
                        str_counts.setdefault(pos, []).append(sum(1 for t in snap.tids if next(e for e in rep[t] if e["pos"] == pos)["level"] == "strength"))
                    tags = {(t, e["pos"]): e["level"] for t in snap.tids for e in rep[t]}
                else:
                    tags = {}
                em = Emitter(state, snap)
                advance(em, snap, state, seed)
                if tags and state.week == w + 1:
                    byposweek: dict[str, dict[str, float]] = {}
                    for t in snap.tids:
                        if t == user:
                            continue
                        for pos in {p for (_, p) in tags}:
                            pts = 0.0
                            holes = 0
                            for slot, pid in state.lineups[t]:
                                if pid and snap.players[pid].pos == pos and slot == pos:
                                    v = state.points.get(pid, [])
                                    pts += v[w - 1] if len(v) >= w and v[w - 1] is not None else 0.0
                                elif not pid and slot == pos:
                                    holes += 1
                            byposweek.setdefault(pos, {})[t] = pts
                            empty[tags[(t, pos)]][0] += int(holes > 0)
                            empty[tags[(t, pos)]][1] += 1
                    for pos, d in byposweek.items():
                        mean = sum(d.values()) / max(1, len(d))
                        if mean <= 0:
                            continue
                        for t, v in d.items():
                            realized[tags[(t, pos)]].setdefault(pos, []).append(v / mean)
        out[fmt] = {
            "teams_tagged_need_per_league_week": {k: {"mean": round(sum(v) / len(v), 2), "min": min(v), "max": max(v)} for k, v in sorted(counts.items())},
            "teams_tagged_strength_per_league_week": {k: round(sum(v) / len(v), 2) for k, v in sorted(str_counts.items())},
            "realized_pts_vs_league_mean_by_tag": {tag: {k: round(sum(v) / len(v), 3) for k, v in sorted(d.items())} for tag, d in realized.items()},
            "empty_starting_slot_rate_by_tag": {k: round(a / max(1, b), 4) for k, (a, b) in empty.items()},
        }
    del qb_need_sf
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("table", choices=["wire", "need"])
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--flags", default="{}", help="JSON of GameSettings overrides, e.g. '{\"wire_v\": 0}'")
    args = ap.parse_args(argv)
    flags = {str(k): int(v) for k, v in json.loads(args.flags).items()}
    out = {"wire": wire_table, "need": need_table}[args.table](args.seeds, flags)
    print(json.dumps(out, indent=1, separators=(",", ": ")) if args.table == "wire" else "\n".join(f"{k}: {json.dumps(v)}" for k, v in out.items()))


if __name__ == "__main__":
    main()

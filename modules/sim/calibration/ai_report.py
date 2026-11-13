"""AI manager realism report: do AI teams plan around byes and injuries and use the wire sensibly?

Plays whole GM games (redraft on a pool built from the real 2025 panel; dynasty on the synthetic pool) and measures, over
AI teams only: how often a starting slot is empty or scores nothing (a bye or injury nobody covered), whether every position
keeps a usable backup, waiver activity and churn, roster composition (hoarding), and what the league feed shows.

    python -m modules.sim.calibration.ai_report [--games 4] [--ai-v 0|1] [--dynasty-games 2] [--json out.json]

Pure stdlib + numpy + modules.sim. Never touches data/players.db.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import replace
from typing import Any

import numpy as np

from modules.sim import game_dynasty as dyn
from modules.sim.calibration import dataset, tail_report
from modules.sim.game_draft import DraftContext, auto_for_user, run_ai_picks
from modules.sim.game_engine import advance, finish_draft
from modules.sim.game_eval import Evaluator
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GameSettings, slot_positions

POS = ("QB", "RB", "WR", "TE", "K")


class Meter:
    def __init__(self) -> None:
        self.team_weeks = 0
        self.empty_slots = 0
        self.dnp_slots = 0       # started a player who did not play (out / bye / inactive)
        self.zero_slots = 0      # played, scored exactly 0
        self.slots = 0
        self.vacant_weeks = 0    # team-weeks with at least one empty slot
        self.cover_ok = 0        # team-weeks where every starting position keeps a healthy, non-bye backup
        self.cover_den = 0
        self.bye_weeks_with_hole = 0
        self.claims_ok = Counter()
        self.add_pos = Counter()
        self.team_season_adds: list[int] = []
        self.roster_sizes: list[int] = []
        self.pos_counts: dict[str, list[int]] = defaultdict(list)
        self.hoard = 0           # team-weeks with a position group over (starters + 3), or 2+ kickers
        self.pingpong = 0        # an AI added then dropped (or dropped then re-added) the same player within 3 weeks
        self.tx = Counter()
        self.pickups_by_week: Counter = Counter()


def _starter_need(snap) -> dict[str, int]:
    need = {p: 0 for p in POS}
    for slot in snap.settings.slots:
        pos = sorted(slot_positions(slot))
        if len(pos) == 1 and pos[0] in need:
            need[pos[0]] += 1
    return need


def observe_week_start(m: Meter, snap, state) -> None:
    """Before the week is played: do AI rosters have cover for this week's lineup and the next bye/injury?"""

    ev = Evaluator(snap, state)
    w = state.week
    need = _starter_need(snap)
    flex = sum(1 for s in snap.settings.slots if len(slot_positions(s)) > 1)
    user = snap.user_team.tid
    for tid in snap.tids:
        if tid == user:
            continue
        roster = state.rosters[tid]
        m.roster_sizes.append(len(roster))
        counts = Counter(snap.players[p].pos for p in roster)
        over = False
        for pos in POS:
            m.pos_counts[pos].append(counts.get(pos, 0))
            if pos == "K":
                over |= counts.get(pos, 0) >= 3
            elif counts.get(pos, 0) > need[pos] + flex + 3:
                over = True
        m.hoard += int(over)
        ok = True
        for pos in ("QB", "RB", "WR", "TE"):
            # injury cover: someone beyond the starters who is not hurt (a bye is handled by the empty-slot measure)
            usable = [p for p in roster if snap.players[p].pos == pos and state.out.get(p, 0) <= 1]
            ok &= len(usable) > need[pos]
        m.cover_den += 1
        m.cover_ok += int(ok)


def observe_week_end(m: Meter, snap, state, week: int) -> None:
    user = snap.user_team.tid
    for tid in snap.tids:
        if tid == user:
            continue
        m.team_weeks += 1
        rows = state.lineups[tid]
        vacant = False
        for slot, pid in rows:
            m.slots += 1
            if not pid:
                m.empty_slots += 1
                vacant = True
                continue
            pts = state.points.get(pid, [])
            val = pts[week - 1] if len(pts) >= week else None
            if val is None:
                m.dnp_slots += 1
            elif val == 0.0:
                m.zero_slots += 1
        m.vacant_weeks += int(vacant)


def observe_transactions(m: Meter, snap, state, seen: int, adds_by_team: Counter, last_seen: dict) -> int:
    user = snap.user_team.tid
    for tx in state.transactions[seen:]:
        m.tx[tx["type"]] += 1
        team = tx.get("team")
        if tx["type"] == "waiver" and team != user:
            m.claims_ok[team] += 1
            adds_by_team[team] += 1
            m.add_pos[snap.players[tx["add"]].pos] += 1
            m.pickups_by_week[tx["week"]] += 1
            key = (team, tx["add"])
            if key in last_seen and tx["week"] - last_seen[key] <= 3:
                m.pingpong += 1
            if tx.get("drop"):
                last_seen[(team, tx["drop"])] = tx["week"]
            last_seen[key] = tx["week"]
    return len(state.transactions)


def play_redraft(rows, byes, model_id: str, seed: int, ai_v: int, m: Meter) -> dict[str, Any]:
    settings = replace(GameSettings.parse({"user_slot": 4, "scoring": "ppr"}), ai_v=ai_v)
    snap = build_snapshot(rows, byes, settings, seed, scoring_model=model_id)
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx = DraftContext(snap, state)
    run_ai_picks(ctx, em, seed)
    auto_for_user(ctx, em, seed)
    finish_draft(em, snap, state, seed)
    adds: Counter = Counter()
    seen, last = len(state.transactions), {}
    while state.status == "in_season":
        w = state.week
        observe_week_start(m, snap, state)
        em = Emitter(state, snap)
        advance(em, snap, state, seed)
        if state.week == w + 1:  # an Advance can chain playoff rounds; only a single-week step has a clean lineup
            observe_week_end(m, snap, state, w)
        seen = observe_transactions(m, snap, state, seen, adds, last)
    for tid in snap.tids:
        if tid != snap.user_team.tid:
            m.team_season_adds.append(adds.get(tid, 0))
    return {"snap": snap, "state": state}


def play_dynasty(model_id: str, seed: int, ai_v: int, m: Meter, seasons: int = 3) -> dict[str, Any]:
    from modules.sim.game_actions import cut_player
    from modules.sim.game_eval import USER_PARAMS
    from modules.sim.synthetic import build_synthetic_pool

    rows, byes = build_synthetic_pool(7)
    settings = replace(GameSettings.parse({"mode": "dynasty", "teams": 8, "user_slot": 3, "start_year": 2026, "seasons": seasons, "rookie_rounds": 3}), ai_v=ai_v)
    root = build_snapshot(rows, byes, settings, seed, scoring_model=model_id)
    state = GameState(root)
    em = Emitter(state, root)
    draft = DraftContext(root, state)
    auto_for_user(draft, em, seed)
    finish_draft(em, root, state, seed)
    adds: Counter = Counter()
    last: dict = {}
    seen = len(state.transactions)
    while True:
        snap = root.season_view(state.view_no)
        sd = dyn.season_seed(seed, state.view_no)
        em.snap = snap
        while state.status in ("in_season", "playoffs"):
            w = state.week
            if state.status == "in_season":
                observe_week_start(m, snap, state)
            advance(em, snap, state, sd)
            if w <= snap.settings.regular_weeks and state.week == w + 1:
                observe_week_end(m, snap, state, w)
            seen = observe_transactions(m, snap, state, seen, adds, last)
        for tid in snap.tids:
            if tid != snap.user_team.tid:
                m.team_season_adds.append(adds.get(tid, 0))
        adds = Counter()
        if state.status != "offseason":
            break
        snap = root.season_view(state.view_no)
        sd = dyn.season_seed(seed, state.view_no)
        em.snap = snap
        dyn.start_rookie_draft(em)
        dyn.run_ai_rookie_picks(em, sd)
        dyn.auto_rookie_draft(em, sd)
        user = snap.user_team.tid
        ev = Evaluator(snap, state)
        while len(state.rosters[user]) > snap.settings.roster_limit:
            ev = Evaluator(snap, state)
            cut_player(em, min(state.rosters[user], key=lambda p: (ev.worth(USER_PARAMS, p), p)))
        dyn.start_next_season(em, sd)
        seen = len(state.transactions)
        last = {}
    return {"snap": root, "state": state}


def summarize(m: Meter) -> dict[str, Any]:
    tw = max(1, m.team_weeks)
    out = {
        "team_weeks": m.team_weeks,
        "empty_slot_rate": round(m.empty_slots / max(1, m.slots), 5),
        "dnp_starter_rate": round(m.dnp_slots / max(1, m.slots), 5),
        "zero_score_starter_rate": round(m.zero_slots / max(1, m.slots), 5),
        "team_weeks_with_empty_slot": round(m.vacant_weeks / tw, 4),
        "depth_cover_rate": round(m.cover_ok / max(1, m.cover_den), 4),
        "adds_per_team_season": round(float(np.mean(m.team_season_adds)), 2) if m.team_season_adds else 0.0,
        "adds_per_team_season_p90": round(float(np.percentile(m.team_season_adds, 90)), 1) if m.team_season_adds else 0.0,
        "add_position_mix": {k: v for k, v in sorted(m.add_pos.items())},
        "roster_size_mean": round(float(np.mean(m.roster_sizes)), 2) if m.roster_sizes else 0.0,
        "roster_size_max": int(max(m.roster_sizes)) if m.roster_sizes else 0,
        "pos_count_mean": {k: round(float(np.mean(v)), 2) for k, v in m.pos_counts.items()},
        "pos_count_max": {k: int(max(v)) for k, v in m.pos_counts.items() if v},
        "hoard_team_weeks": round(m.hoard / max(1, m.cover_den), 4),
        "pingpong_adds": m.pingpong,
        "transactions": dict(m.tx),
    }
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--dynasty-games", type=int, default=2)
    ap.add_argument("--ai-v", type=int, default=None, help="0 = the AI as it was, 1 = bye/injury-aware (default: both)")
    ap.add_argument("--json", default="")
    args = ap.parse_args(argv)
    from modules.sim import game_scoring

    model_id = game_scoring.default_model().model_id
    prows = dataset.load_panel()
    pool, byes = tail_report.pool_from_panel(prows)
    versions = [args.ai_v] if args.ai_v is not None else [0, 1]
    res: dict[str, Any] = {"model": model_id}
    for v in versions:
        m = Meter()
        for seed in range(1, args.games + 1):
            play_redraft(pool, byes, model_id, seed, v, m)
        res[f"redraft_ai{v}"] = summarize(m)
        if args.dynasty_games:
            md = Meter()
            for seed in range(1, args.dynasty_games + 1):
                play_dynasty(model_id, seed, v, md)
            res[f"dynasty_ai{v}"] = summarize(md)
    text = json.dumps(res, indent=1)
    if args.json:
        open(args.json, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()

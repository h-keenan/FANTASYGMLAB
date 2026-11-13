"""Tail realism report: weekly scores in the whole GM game against real nflverse-era history.

Two layers, both compared with the real 2021-25 panel (``data/panel.json.gz``, PPR):

1. ``player``: the player model alone (``backtest.simulate_panel``): percentiles, max and the share of
   player-weeks above 30 / 40 / 50 by position and by preseason-projection tier.
2. ``game``: whole GM games on a pool built from the real panel (projection, ADP-derived depth order, real team
   codes): weekly points by position and depth slot, team lineup scores, and the shown projection against what
   the player then scored (MAE, bias, the largest projection ever shown, how many projections exceed the
   position ceiling).

    python -m modules.sim.calibration.tail_report [--games 4] [--model player_model-player-model-4] [--json out.json]

Pure stdlib + numpy + modules.sim; never touches data/players.db.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from typing import Any

import numpy as np

from modules.sim.calibration import backtest, dataset

CORE = ("QB", "RB", "WR", "TE")
SHARES = (30, 40, 50)


def tier_of(proj: float) -> str:
    return "depth(<6)" if proj < 6 else "flex(6-10)" if proj < 10 else "starter(10-16)" if proj < 16 else "elite(16+)"


def summarize(values) -> dict[str, float]:
    v = np.asarray(list(values), dtype=float)
    if v.size == 0:
        return {"n": 0}
    out = {"n": int(v.size), "mean": round(float(v.mean()), 2), "sd": round(float(v.std()), 2)}
    for q in (50, 90, 99, 99.9):
        out[f"p{q}"] = round(float(np.percentile(v, q)), 1)
    out["max"] = round(float(v.max()), 1)
    for s in SHARES:
        out[f"gt{s}"] = round(float((v > s).mean()), 5)
    return out


# ----------------------------------------------------------------------------- layer 1


def player_layer(rows: list[dict], copies: int = 3) -> dict[str, Any]:
    sims = backtest.simulate_panel(rows, copies)
    real: dict[str, list] = defaultdict(list)
    sim: dict[str, list] = defaultdict(list)
    for r, ss in zip(rows, sims):
        if r["pos"] not in CORE:
            continue
        for key in (r["pos"], tier_of(r["proj_ppg"] or 0.0)):
            real[key] += [w[1] for w in r["weeks"] if w and w[0]]
            for s in ss:
                sim[key] += s["pts"]
    return {k: {"real": summarize(real[k]), "sim": summarize(sim[k])} for k in sorted(real)}


# ----------------------------------------------------------------------------- layer 2


def pool_from_panel(rows: list[dict], season: int = 2025):
    """Adapter rows (``RealSimInputs.player_pool`` shape) from one real season: real projection, ADP-derived market
    and depth order within each (team, position), plus a flat defense per team."""

    from modules.sim.game_setup import synthetic_byes

    rs = [r for r in rows if r["season"] == season and r["team"] and r["pos"] in (*CORE, "K")]
    by: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rs:
        by[(r["team"], r["pos"])].append(r)
    out: list[dict] = []
    for (team, pos), group in by.items():
        group.sort(key=lambda r: (r["adp"] if r["adp"] is not None else 999.0, -(r["proj_ppg"] or 0.0), r["pid"]))
        for i, r in enumerate(group, 1):
            mean = max(0.5, float(r["proj_ppg"] or 0.0))
            adp = r["adp"] if r["adp"] is not None else 400.0
            out.append({
                "pid": f"{r['pid']}", "name": f"{pos}{r['pid']}", "pos": pos, "nfl_team": team, "age": float(r["age"] or 26.0),
                "market": round(100.0 * float(np.exp(-adp / 90.0)), 2), "mean": round(mean, 2), "sd": round(max(2.0, mean * 0.42), 2),
                "injury_weeks": 0, "extra": {"depth_chart_order": float(i), "ppg": mean},
            })
    teams = sorted({r["nfl_team"] for r in out})
    for t in teams:
        out.append({"pid": f"DEF-{t}", "name": f"{t} D/ST", "pos": "DEF", "nfl_team": t, "age": 26.0, "market": 20.0,
                    "mean": 7.0, "sd": 4.5, "injury_weeks": 0, "extra": {}})
    return out, synthetic_byes(teams, 14, 3)


def _run_game(rows, byes, model_id: str, seed: int, ceil_check) -> dict[str, Any]:
    from dataclasses import replace

    from modules.sim.game_draft import DraftContext, auto_for_user, run_ai_picks
    from modules.sim.game_engine import advance, finish_draft
    from modules.sim.game_eval import Evaluator
    from modules.sim.game_setup import build_snapshot
    from modules.sim.game_state import Emitter, GameState
    from modules.sim.game_types import GameSettings

    settings = replace(GameSettings.parse({"user_slot": 4, "scoring": "ppr"}), reserve_v=0, ir_slots=0)
    snap = build_snapshot(rows, byes, settings, seed, scoring_model=model_id)
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx = DraftContext(snap, state)
    run_ai_picks(ctx, em, seed)
    auto_for_user(ctx, em, seed)
    finish_draft(em, snap, state, seed)
    shown: dict[tuple[str, int], float] = {}
    while state.status == "in_season" and state.week <= settings.regular_weeks:
        w = state.week
        ev = Evaluator(snap, state)
        for pid in snap.pids:
            if ev.status(pid, w) == "healthy":
                shown[(pid, w)] = ev.proj(pid, w)
        em = Emitter(state, snap)
        advance(em, snap, state, seed)
    team_scores = []
    for rc in state.recaps.values():
        if rc.get("kind") == "regular":
            for g in rc["scores"]:
                team_scores += [g["home_pts"], g["away_pts"]]
    weekly: dict[str, list] = defaultdict(list)
    errs: list[tuple[str, float, float]] = []
    slot_rank: dict[str, int] = {}
    for p in snap.players.values():
        slot_rank[p.pid] = int(p.extra.get("depth_chart_order", 99))
    for pid, hist in state.points.items():
        pos = snap.players[pid].pos
        if pos not in CORE:
            continue
        for wk, pts in enumerate(hist, 1):
            if pts is None or wk > settings.regular_weeks:
                continue
            weekly[pos].append(pts)
            weekly[f"{pos}{min(slot_rank[pid], 3)}" + ("+" if slot_rank[pid] >= 3 else "")].append(pts)
            weekly[tier_of(snap.players[pid].mean)].append(pts)
            if (pid, wk) in shown:
                errs.append((pos, shown[(pid, wk)], pts))
    return {"weekly": weekly, "team_scores": team_scores, "errs": errs, "shown": shown, "snap": snap, "state": state}


def game_layer(rows: list[dict], model_id: str, games: int = 3, season: int = 2025) -> dict[str, Any]:
    pool, byes = pool_from_panel(rows, season)
    weekly: dict[str, list] = defaultdict(list)
    team: list[float] = []
    errs: list[tuple[str, float, float]] = []
    shown_all: list[tuple[str, float]] = []
    for seed in range(1, games + 1):
        res = _run_game(pool, byes, model_id, seed, None)
        for k, v in res["weekly"].items():
            weekly[k] += v
        team += res["team_scores"]
        errs += res["errs"]
        snap = res["snap"]
        shown_all += [(snap.players[pid].pos, v) for (pid, _w), v in res["shown"].items() if snap.players[pid].pos in CORE]
    out: dict[str, Any] = {"weekly": {k: summarize(v) for k, v in sorted(weekly.items())}, "team_scores": summarize(team)}
    e = np.array([(p, a) for _, p, a in errs], dtype=float)
    if len(e):
        out["projection_error"] = {
            "n": int(len(e)), "mae": round(float(np.abs(e[:, 1] - e[:, 0]).mean()), 2),
            "bias": round(float((e[:, 1] - e[:, 0]).mean()), 2),
            "max_shown": round(max(v for _, v in shown_all), 1),
            "shown_gt_30": sum(1 for _, v in shown_all if v > 30), "shown_gt_40": sum(1 for _, v in shown_all if v > 40),
            "shown_gt_25_non_QB": sum(1 for p, v in shown_all if v > 25 and p != "QB"),
        }
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", type=int, default=3)
    ap.add_argument("--copies", type=int, default=3)
    ap.add_argument("--model", default="")
    ap.add_argument("--skip-player", action="store_true")
    ap.add_argument("--json", default="")
    args = ap.parse_args(argv)
    from modules.sim import game_scoring

    model_id = args.model or game_scoring.default_model().model_id
    rows = dataset.load_panel()
    res: dict[str, Any] = {"model": model_id}
    if not args.skip_player:
        res["player"] = player_layer(rows, args.copies)
    res["game"] = game_layer(rows, model_id, args.games)
    text = json.dumps(res, indent=1)
    if args.json:
        open(args.json, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()

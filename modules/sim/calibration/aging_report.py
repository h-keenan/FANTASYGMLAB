"""Aging and retirement report: do 20-season dynasties retire players at realistic ages and keep realistic rosters?

Builds the season pools of whole dynasties (no games are played: the offseason is a pure function of the seed) from the real 2025 panel
and records, per position: age at retirement (quantiles), career length of drafted classes, the share retiring at each age, and the pool's
average age by season. ``--aging-v 0`` is the engine before position hazard curves, ``--aging-v 1`` after.

    python -m modules.sim.calibration.aging_report [--seeds 40] [--seasons 20] [--aging-v 1] [--json out.json]

Pure stdlib + numpy + modules.sim. Never touches data/players.db.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace

import numpy as np

from modules.sim import game_dynasty as dyn, game_scoring
from modules.sim.calibration import dataset, tail_report
from modules.sim.game_setup import build_snapshot
from modules.sim.game_types import GameSettings

POSITIONS = ("QB", "RB", "WR", "TE", "K")
# Published yardsticks (NFL history): median age at retirement by position, ages at which a starter-calibre player is still active.
REAL_MEDIAN_RETIRE_AGE = {"QB": 34.5, "RB": 28.5, "WR": 30.5, "TE": 31.5, "K": 37.0}
QS = (10, 25, 50, 75, 90)


def run_seed(seed: int, seasons: int, rows, byes, model_id: str, aging_v: int, teams: int = 12) -> dict:
    base = GameSettings.parse({"mode": "dynasty", "teams": teams, "user_slot": 3, "start_year": 2026, "seasons": 5, "rookie_rounds": 3, "scoring": "ppr"})
    settings = replace(base, seasons=seasons, aging_v=aging_v)
    root = build_snapshot(rows, byes, settings, seed, scoring_model=model_id)
    retire_ages: dict[str, list[float]] = {p: [] for p in POSITIONS}
    starter_ret: dict[str, list[float]] = {p: [] for p in POSITIONS}
    career: dict[str, list[int]] = {p: [] for p in POSITIONS}
    avg_age: dict[str, list[float]] = {p: [] for p in POSITIONS}
    gt33_k: list[int] = []
    first_seen: dict[str, int] = {}
    n_ret: list[int] = []
    prev = root.season_view(1)
    for s in (1,):
        pass
    for pid in prev.pids:
        first_seen[pid] = 0 if not prev.players[pid].extra.get("is_rookie") else 1
    sizes = []
    for s in range(1, seasons + 1):
        snap = root.season_view(s)
        for pos in POSITIONS:
            ages = [p.age for p in snap.players.values() if p.pos == pos]
            avg_age[pos].append(float(np.mean(ages)) if ages else float("nan"))
        gt33_k.append(sum(1 for p in snap.players.values() if p.pos == "K" and p.age > 33))
        sizes.append(len(snap.players))
        if s > 1:
            gone = [pid for pid in prev.pids if pid not in snap.players]
            n_ret.append(len(gone))
            order = {}
            for pos in POSITIONS:
                order[pos] = sorted((p for p in prev.players.values() if p.pos == pos), key=lambda p: (-p.mean, p.pid))
            rank = {p.pid: i for pos in POSITIONS for i, p in enumerate(order[pos])}
            for pid in gone:
                p = prev.players[pid]
                if p.pos not in retire_ages:
                    continue
                age = p.age + 1.0  # the age at which he does not come back
                retire_ages[p.pos].append(age)
                n_start = {"QB": 12, "RB": 30, "WR": 36, "TE": 12, "K": 12}[p.pos]
                if rank[pid] < n_start:
                    starter_ret[p.pos].append(age)
                if first_seen.get(pid, 0) >= 1:  # drafted into the league during the game: a full career
                    career[p.pos].append(s - first_seen[pid])
            for pid, p in snap.players.items():
                if pid not in first_seen:
                    first_seen[pid] = s
        prev = snap
    return {"retire_ages": retire_ages, "starter_ret": starter_ret, "career": career, "avg_age": avg_age, "k_gt33": gt33_k, "retirees": n_ret, "pool": sizes}


def q(vals, qs=QS):
    return [round(float(np.percentile(vals, x)), 1) for x in qs] if len(vals) else [float("nan")] * len(qs)


def summarize(games: list[dict]) -> dict:
    out: dict = {"retire_age_quantiles": {}, "starter_retire_age_quantiles": {}, "career_quantiles": {}, "n": {}, "age_by_season": {}, "share_active": {}}
    seasons = len(games[0]["avg_age"]["QB"])
    for pos in POSITIONS:
        ra = [a for g in games for a in g["retire_ages"][pos]]
        sr = [a for g in games for a in g["starter_ret"][pos]]
        cr = [a for g in games for a in g["career"][pos]]
        out["retire_age_quantiles"][pos] = q(ra) + [round(float(np.mean(ra)), 1) if ra else None, round(float(np.mean([a >= 40 for a in ra])), 3) if ra else None, round(float(np.mean([a <= 33 for a in ra])), 3) if ra else None]
        out["starter_retire_age_quantiles"][pos] = q(sr)
        out["career_quantiles"][pos] = q(cr)
        out["n"][pos] = len(ra)
        out["age_by_season"][pos] = [round(float(np.nanmean([g["avg_age"][pos][i] for g in games])), 2) for i in range(seasons)]
    out["k_over_33_mean"] = round(float(np.mean([np.mean(g["k_gt33"]) for g in games])), 2)
    out["pool_by_season"] = [round(float(np.mean([g["pool"][i] for g in games])), 1) for i in range(seasons)]
    out["retirees_per_offseason"] = round(float(np.mean([np.mean(g["retirees"]) for g in games])), 1)
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--seasons", type=int, default=20)
    ap.add_argument("--aging-v", type=int, default=1)
    ap.add_argument("--json", default="")
    args = ap.parse_args(argv)
    model_id = game_scoring.default_model().model_id
    rows, byes = tail_report.pool_from_panel(dataset.load_panel())
    games = [run_seed(s, args.seasons, rows, byes, model_id, args.aging_v) for s in range(1, args.seeds + 1)]
    res = {"model": model_id, "aging_v": args.aging_v, "seeds": args.seeds, **summarize(games)}
    text = json.dumps(res, indent=1)
    if args.json:
        open(args.json, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()

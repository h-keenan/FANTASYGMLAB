"""Single-game tail audit: the player model's one-game score distribution against real NFL weeks (2021-25 panel, PPR).

Per position: percentiles up to 99.99, the largest game, and the count of 30+/40+/50+/60+ games per 1000 player-seasons
(a player-season = a panel row with 8+ games played, real and simulated alike). Also a trace of how the largest
simulated games were built (which stat-line components).

    python -m modules.sim.calibration.single_game_tail [--model v5|v6] [--copies 20] [--json out.json]

Pure stdlib + numpy + modules.sim; reads data/panel.json.gz only, never data/players.db.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from typing import Any

import numpy as np

from modules.sim.calibration import backtest, dataset

CORE = ("QB", "RB", "WR", "TE")
PCTS = (50, 90, 99, 99.9, 99.99)
THRESH = (30, 40, 50, 60)
MIN_GAMES = 8


def _summ(games: np.ndarray, seasons: int) -> dict[str, Any]:
    out: dict[str, Any] = {"games": int(games.size), "player_seasons": seasons}
    for q in PCTS:
        out[f"p{q}"] = round(float(np.percentile(games, q)), 1) if games.size else 0.0
    out["max"] = round(float(games.max()), 1) if games.size else 0.0
    for t in THRESH:
        out[f"n{t}_per_1000"] = round(1000.0 * float((games >= t).sum()) / max(1, seasons), 2)
    return out


def real_games(rows: list[dict]) -> dict[str, tuple[np.ndarray, int]]:
    g: dict[str, list] = defaultdict(list)
    n: dict[str, int] = defaultdict(int)
    for r in rows:
        if r["pos"] not in CORE:
            continue
        pts = [w[1] for w in r["weeks"] if w and w[0]]
        if len(pts) < MIN_GAMES:
            continue
        g[r["pos"]] += pts
        n[r["pos"]] += 1
    return {p: (np.asarray(g[p], dtype=float), n[p]) for p in CORE}


def sim_games(rows: list[dict], copies: int) -> tuple[dict[str, tuple[np.ndarray, int]], list[dict]]:
    sims = backtest.simulate_panel(rows, copies)
    g: dict[str, list] = defaultdict(list)
    n: dict[str, int] = defaultdict(int)
    big: list[dict] = []
    for r, ss in zip(rows, sims):
        if r["pos"] not in CORE:
            continue
        for s in ss:
            if s["played"] < MIN_GAMES:
                continue
            g[r["pos"]] += s["pts"]
            n[r["pos"]] += 1
            top = max(s["pts"]) if s["pts"] else 0
            if top >= 45:
                big.append({"pos": r["pos"], "proj": r["proj_ppg"], "pts": top})
    return {p: (np.asarray(g[p], dtype=float), n[p]) for p in CORE}, big


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--copies", type=int, default=10)
    ap.add_argument("--model", choices=["v6", "v5"], default="v6")
    ap.add_argument("--json", default="")
    args = ap.parse_args(argv)
    if args.model == "v5":
        backtest.pm = __import__("modules.sim.player_model_v5", fromlist=["x"])  # type: ignore[attr-defined]
    rows = dataset.load_panel()
    real = real_games(rows)
    sim, big = sim_games(rows, args.copies)
    res = {"model": args.model, "real": {p: _summ(*real[p]) for p in CORE}, "sim": {p: _summ(*sim[p]) for p in CORE}}
    text = json.dumps(res, indent=1)
    if args.json:
        open(args.json, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()

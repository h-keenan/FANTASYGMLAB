"""Whole-game batch for the single-game tail audit: many seeded GM games on the real-2025 pool across difficulties,
for a chosen player model (default or a frozen one), counting the largest single-game scores by position.

    python -m modules.sim.calibration.single_game_batch --model player_model-player-model-6 --seeds 12 [--json out.json]

Never touches data/players.db (pool from data/panel.json.gz).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

import numpy as np

from modules.sim import game_types
from modules.sim.calibration import dataset, tail_report


def run(model_id: str, seeds: int, difficulties: tuple[str, ...]) -> dict:
    rows = dataset.load_panel()
    pool, byes = tail_report.pool_from_panel(rows, 2025)
    pts: dict[str, list] = defaultdict(list)
    seasons: dict[str, int] = defaultdict(int)
    team: list[float] = []
    for diff in difficulties:
        for seed in range(1, seeds + 1):
            res = tail_report._run_game(pool, byes, model_id, seed, None, diff)
            team += res["team_scores"]
            for pid, hist in res["state"].points.items():
                pos = res["snap"].players[pid].pos
                if pos not in tail_report.CORE:
                    continue
                played = [x for x in hist[:14] if x is not None]
                if len(played) >= 8:
                    pts[pos] += played
                    seasons[pos] += 1
    out: dict = {"model": model_id, "games": seeds * len(difficulties), "difficulties": list(difficulties)}
    for pos in tail_report.CORE:
        g = np.asarray(pts[pos])
        n = max(1, seasons[pos])
        out[pos] = {"player_seasons": seasons[pos], "p99": round(float(np.percentile(g, 99)), 1), "p99.9": round(float(np.percentile(g, 99.9)), 1),
                    "p99.99": round(float(np.percentile(g, 99.99)), 1), "max": round(float(g.max()), 1),
                    **{f"n{t}_per_1000": round(1000.0 * float((g >= t).sum()) / n, 2) for t in (40, 50, 60)}}
    t = np.asarray(team)
    out["team_score"] = {"mean": round(float(t.mean()), 1), "sd": round(float(t.std()), 1), "p99": round(float(np.percentile(t, 99)), 1), "max": round(float(t.max()), 1)}
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="")
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--json", default="")
    args = ap.parse_args(argv)
    from modules.sim import game_scoring

    model_id = args.model or game_scoring.default_model().model_id
    res = run(model_id, args.seeds, tuple(game_types.DIFFICULTIES))
    text = json.dumps(res, indent=1)
    if args.json:
        open(args.json, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()

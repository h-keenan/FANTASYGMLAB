"""Fit the in-season path tilt of player-model-5.

The real weekly points of a player relative to his own level are close to flat through the season (2021-25 panel, weeks 1-14: the weekly
trend is -0.1% a week for elite players, -0.2% for starters, +0.3% flex, +1.7% depth, whose usage grows as injuries open roles). The
model-4 expected weekly mean, measured on the same panel, trends -0.3% / -0.9% / -0.1% / +1.8%: its role changes are biased down at the top,
so a 12-team league's scoring fell about 13% from week 1 to week 13 (8% from the model alone). ``PATH_TILT`` is the per-week slope that closes
the gap, per preseason tier, applied as ``1 + tilt x (week - 8)``: centered, so season totals (and everything calibrated on them) do not move.

    python -m modules.sim.calibration.path_fit [--copies 3]
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from modules.sim import player_model as pm
from modules.sim.calibration import backtest, dataset

WEEKS = 14


def tier_of(pos: str, p: float) -> str:
    return pm.tier_label(pos, p)  # the model's own tiers (relative to the position's reference ppg)


def slopes(copies: int = 3) -> dict[str, dict[str, float]]:
    rows = [r for r in dataset.load_panel() if r["pos"] in ("QB", "RB", "WR", "TE") and (r["proj_ppg"] or 0) >= 1.5]
    sims = backtest.simulate_panel(rows, copies)
    out: dict[str, dict[str, float]] = {}
    for tier in ("elite", "starter", "flex", "depth"):
        real = np.zeros(WEEKS)
        rn = np.zeros(WEEKS)
        sim = np.zeros(WEEKS)
        sn = np.zeros(WEEKS)
        for r, ss in zip(rows, sims):
            if tier_of(r["pos"], r["proj_ppg"]) != tier:
                continue
            for w in range(WEEKS):
                cell = r["weeks"][w]
                if cell and cell[0]:
                    real[w] += cell[1]
                    rn[w] += 1
            for s in ss:
                for w, res in enumerate(s["weeks"][:WEEKS]):
                    if res.active:
                        sim[w] += res.points
                        sn[w] += 1
        rm, sm = real / np.maximum(rn, 1), sim / np.maximum(sn, 1)
        x = np.arange(WEEKS)
        rs = float(np.polyfit(x, rm, 1)[0] / rm.mean())
        ss_ = float(np.polyfit(x, sm, 1)[0] / sm.mean())
        out[tier] = {"real_slope": round(rs, 4), "sim_slope": round(ss_, 4), "tilt": round(rs - ss_, 4)}
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--copies", type=int, default=3)
    args = ap.parse_args(argv)
    print(json.dumps(slopes(args.copies), indent=1))


if __name__ == "__main__":
    main()

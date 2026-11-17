"""Season-level variance of the top tier, sim vs the real 2021-25 panel (``player-model-8``). Throwaway 2025 panel pool, never ``data/players.db``.

    python -m modules.sim.calibration.season_variance_report --seeds 8 --seasons 5
    python -m modules.sim.calibration.season_variance_report --seeds 8 --seasons 5 --off     # player-model-7 behaviour (star terms zeroed)

Two tables per position (QB, RB, WR, TE), the sim against the panel:

* **top-12 projected: realized / projected points per game** (8+ games): sd of the log and the 5th / 10th / 50th percentile. The top tier's low tail is the
  season-level bust draw (``bust_sd_star`` / ``pu_star``).
* **top-12 by points per game: next / this points per game** (same NFL team, 8+ games both years): p10 / p25 / p50 / p90 and the share under 0.7. Real n is
  35-40 per position, so the real p10 has a wide interval (printed): read the sim against the interval, not the point.
"""

from __future__ import annotations

import argparse
from dataclasses import replace

import numpy as np

from modules.sim import player_model
from modules.sim.calibration import dataset, dynasty_run

POS = ("QB", "RB", "WR", "TE")


def real_tables() -> dict[str, dict]:
    panel = dataset.load_panel()
    by: dict[str, dict[int, tuple]] = {}
    proj: dict[tuple[int, str], list[tuple[float, float]]] = {}
    for r in panel:
        pl = [w[1] for w in r["weeks"] if w and w[0]]
        if len(pl) >= 8 and r["pos"] in POS:
            by.setdefault(r["pid"], {})[r["season"]] = (r["pos"], float(np.mean(pl)), r["team"])
            if r.get("proj_ppg") and r["proj_ppg"] > 0:
                proj.setdefault((r["season"], r["pos"]), []).append((r["proj_ppg"], float(np.mean(pl))))
    rng = np.random.default_rng(0)
    out = {}
    for pos in POS:
        tier = [np.log(b / a) for s in range(2021, 2026) for a, b in sorted(proj.get((s, pos), []), key=lambda t: -t[0])[:12]]
        nxt = []
        for s in range(2021, 2025):
            cur = sorted(((pid, d[s]) for pid, d in by.items() if s in d and d[s][0] == pos), key=lambda x: -x[1][1])[:12]
            for pid, v in cur:
                n = by[pid].get(s + 1)
                if n and n[2] == v[2]:
                    nxt.append(n[1] / v[1])
        nxt = np.array(nxt)
        boots = [np.quantile(rng.choice(nxt, len(nxt)), 0.1) for _ in range(1000)]
        out[pos] = dict(tier=np.array(tier), nxt=nxt, ci=(float(np.quantile(boots, 0.05)), float(np.quantile(boots, 0.95))))
    return out


def sim_tables(runs: list[list[dict]]) -> dict[str, dict]:
    out = {}
    for pos in POS:
        tier, nxt = [], []
        for seasons in runs:
            for a in seasons:
                items = sorted(((pr["proj"], pid) for pid, pr in a["prof"].items() if pr["pos"] == pos and pid in a["pl"]), reverse=True)[:12]
                tier += [np.log(a["pl"][pid][1] / pj) for pj, pid in items]
            for a, b in zip(seasons, seasons[1:]):
                cur = sorted(((pid, v) for pid, v in a["pl"].items() if v[0] == pos), key=lambda x: -x[1][1])[:12]
                for pid, v in cur:
                    team = a["nfl"].get(pid)
                    if team and b["nfl"].get(pid) == team and pid in b["pl"]:
                        nxt.append(b["pl"][pid][1] / v[1])
        out[pos] = dict(tier=np.array(tier), nxt=np.array(nxt))
    return out


def fmt_tier(x: np.ndarray) -> str:
    q = np.quantile(np.exp(x), [0.05, 0.1, 0.5])
    return f"n={len(x):4d} sd {x.std():.3f}  p05/p10/p50 {q[0]:.2f}/{q[1]:.2f}/{q[2]:.2f}"


def fmt_next(x: np.ndarray) -> str:
    q = np.quantile(x, [0.1, 0.25, 0.5, 0.9])
    return f"n={len(x):4d} p10/p25/p50/p90 {q[0]:.2f}/{q[1]:.2f}/{q[2]:.2f}/{q[3]:.2f}  under 0.7: {100 * np.mean(x < 0.7):.1f}%"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--seasons", type=int, default=5)
    ap.add_argument("--seed0", type=int, default=0)
    ap.add_argument("--stability", type=int, default=None, help="stability_v for the sim games (default: the current default)")
    ap.add_argument("--off", action="store_true", help="zero the player-model-8 star terms (player-model-7 behaviour)")
    args = ap.parse_args()
    if args.off:
        player_model.SEASON = replace(player_model.SEASON, bust_sd_star=0.0, pu_star=0.0)
    runs = [dynasty_run.run(s, args.seasons, profiles=True, flags={"stability_v": args.stability} if args.stability is not None else None) for s in range(1 + args.seed0, 1 + args.seed0 + args.seeds)]
    real, sim = real_tables(), sim_tables(runs)
    print(f"== {args.seeds} seeds x {args.seasons} seasons, {'star terms OFF (model-7)' if args.off else 'player-model-8'}")
    print("mean team score per week: %.2f" % np.mean([x for s in runs for r in s for x in r["weekly"]]))
    for pos in POS:
        print(f"{pos} top-12 projected, realized/projected  REAL {fmt_tier(real[pos]['tier'])}")
        print(f"{pos}                                        SIM  {fmt_tier(sim[pos]['tier'])}")
        print(f"{pos} top-12 by ppg, next/this              REAL {fmt_next(real[pos]['nxt'])}  (p10 90% interval {real[pos]['ci'][0]:.2f}-{real[pos]['ci'][1]:.2f})")
        print(f"{pos}                                        SIM  {fmt_next(sim[pos]['nxt'])}")


if __name__ == "__main__":
    main()

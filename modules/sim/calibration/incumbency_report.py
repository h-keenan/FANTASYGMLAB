"""Depth-chart stickiness and matchup spread of headless dynasties (``incumbent_v`` / ``defense_v``). Throwaway 2025 panel pool, never ``data/players.db``.

    python -m modules.sim.calibration.incumbency_report --seeds 8 --seasons 8 --label after
    python -m modules.sim.calibration.incumbency_report --seeds 8 --seasons 8 --label before --off incumbent_v defense_v

Prints, per position, over every (season, next season) pair: of last season's top-12 by points per game (8+ games) who are still on the same NFL team,
the share who are no longer their team's top scorer at the position, and the distribution of next / this ppg for those who played 8+ games again.
The real panel (2021-25) gives QB 0 percent, RB 19, WR 33, TE 8 (see the audit doc).
"""

from __future__ import annotations

import argparse
from collections import Counter

import numpy as np

from modules.sim.calibration import dynasty_run

TOP = {"QB": 12, "RB": 12, "WR": 12, "TE": 12}


def measure(runs: list[list[dict]]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for pos, n in TOP.items():
        tot = lost = dlost = 0
        drops: list[float] = []
        for seasons in runs:
            for a, b in zip(seasons, seasons[1:]):
                cur = sorted(((pid, v) for pid, v in a["pl"].items() if v[0] == pos), key=lambda x: -x[1][1])[:n]
                for pid, v in cur:
                    if float(a["depth"].get(pid) or 1.0) > 1.0:
                        continue  # only players who held the first slot of the chart last season (not a fill-in who had a big year)
                    team = a["nfl"].get(pid)
                    if not team or b["nfl"].get(pid) != team or pid not in b["tot"]:
                        continue
                    mates = sorted((t for p, t in b["tot"].items() if t[0] == pos and b["nfl"].get(p) == team), key=lambda t: -t[1])
                    mine = b["tot"][pid]
                    tot += 1
                    dlost += int(float(b["depth"].get(pid) or 1.0) > 1.0)  # the depth chart itself: no longer first at the position
                    lost += int(mates[0] is not mine and mates[0][1] > mine[1])
                    if pid in b["pl"]:
                        drops.append(b["pl"][pid][1] / v[1])
        d = np.array(drops) if drops else np.array([0.0])
        out[pos] = {"n": tot, "lost_pct": 100.0 * lost / tot if tot else 0.0, "depth_pct": 100.0 * dlost / tot if tot else 0.0, "p10": float(np.quantile(d, 0.1)), "p50": float(np.quantile(d, 0.5)), "p90": float(np.quantile(d, 0.9)),
                    "drop30_pct": 100.0 * float(np.mean(d < 0.7))}
    return out


def depth_events(runs: list[list[dict]]) -> Counter:
    c: Counter = Counter()
    for seasons in runs:
        for e in seasons[-1]["depth_events"]:
            for ch in e["payload"]["changes"]:
                c[(e["payload"]["phase"], ch["reason"])] += 1
    return c


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--seasons", type=int, default=6)
    ap.add_argument("--label", default="run")
    ap.add_argument("--off", nargs="*", default=[], help="flags to switch off (before)")
    args = ap.parse_args()
    flags = {f: 0 for f in args.off}
    runs = [dynasty_run.run(seed, args.seasons, flags=flags) for seed in range(1, args.seeds + 1)]
    print(f"== {args.label}: {args.seeds} seeds x {args.seasons} seasons, off={args.off}")
    for pos, m in measure(runs).items():
        print(f"{pos}: n={m['n']:4d} off depth chart {m['depth_pct']:5.1f}%  not team top scorer {m['lost_pct']:5.1f}%  next/this ppg p10/p50/p90 {m['p10']:.2f}/{m['p50']:.2f}/{m['p90']:.2f}  drop>30%: {m['drop30_pct']:.1f}%")
    import statistics
    print("mean team score per week: %.2f" % statistics.mean(x for seasons in runs for r in seasons for x in r["weekly"]))
    ev = depth_events(runs)
    for k, v in sorted(ev.items()):
        print("depth_chart", k, v)


if __name__ == "__main__":
    main()

"""Whole-league dynasty tables against the real 2021-25 panel: balance by season, late-career ratios, persistence and rookie-class strength.

The measurements behind ``stability_v 2`` and ``rookie_v 1`` (docs/audits/2026-11-realism-advice-audit-2.md). Headless 12-team PPR dynasties on the committed
2025 panel pool (``dynasty_run``, a throwaway pool, never ``data/players.db``); "real" is the panel (``calibration/data/panel.json.gz``).

    python -m modules.sim.calibration.dynasty_tables --seeds 8 --seasons 10 --seed0 8
    python -m modules.sim.calibration.dynasty_tables --seeds 8 --seasons 10 --seed0 8 --flags '{"stability_v": 1, "rookie_v": 0}'     # before

Sections: ``balance`` (team points per week and the projection at ranks 12 and 24 of each position, by season: the league must stay as strong in season 10
as in season 1), ``persistence`` (correlation of a top-24 player's next projection change with last season's realized / projected result), ``late career``
(realized next / this points per game of the top-24 by points per game, same NFL team, 8+ games both years, by age cell), ``next / this top 12`` and
``rookies`` (rookies per position top 12 and top 24 after the first offseason, the best rookie against the 12th veteran, the top-12 class bust rate).
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import numpy as np

from modules.sim.calibration import dataset, dynasty_run

POS = ("QB", "RB", "WR", "TE")
SKILL = ("RB", "WR", "TE")

# Real (panel) late-career cells: (p50, p10, sd of log) of next / this ppg, top-24 by ppg, same team, 8+ games both years.
REAL_CELLS = {
    ("RB", "25-26"): (0.90, 0.63, 0.22), ("RB", "27+"): (0.71, 0.52, 0.28), ("WR", "25-26"): (0.81, 0.58, 0.25),
    ("WR", "27+"): (0.88, 0.62, 0.23), ("TE", "25-26"): (0.72, 0.50, 0.48), ("TE", "27+"): (0.97, 0.73, 0.22),
}
REAL_PERSIST = {"RB": 0.77, "WR": 0.66, "TE": 0.73}


def balance(runs: list[list[dict[str, Any]]]) -> list[str]:
    n = max(len(r) for r in runs)
    out = ["season                " + " ".join(f"{i + 1:6d}" for i in range(n))]
    out.append("team points per week  " + " ".join("%6.1f" % np.mean([x for r in runs if len(r) > i for x in r[i]["weekly"]]) for i in range(n)))
    for pos in POS:
        for k in (12, 24):
            row = []
            for i in range(n):
                v = []
                for r in runs:
                    if len(r) > i:
                        ps = sorted((pr["proj"] for pr in r[i]["prof"].values() if pr["pos"] == pos), reverse=True)
                        if len(ps) >= k:
                            v.append(ps[k - 1])
                row.append(np.mean(v))
            out.append(f"{pos}{k} projection".ljust(22) + " ".join("%6.1f" % x for x in row))
    return out


def persistence(runs: list[list[dict[str, Any]]], top: int = 24) -> list[str]:
    out = []
    for pos in SKILL:
        rows = []
        for seasons in runs:
            for a, b in zip(seasons, seasons[1:]):
                items = sorted(((pr["proj"], pid) for pid, pr in a["prof"].items() if pr["pos"] == pos and pid in a["pl"] and pid in b["pl"] and pid in b["prof"]), reverse=True)[:top]
                rows += [(np.log(a["pl"][pid][1] / pj), np.log(b["prof"][pid]["proj"] / pj)) for pj, pid in items]
        r = np.array(rows)
        out.append(f"{pos}: corr {np.corrcoef(r[:, 0], r[:, 1])[0, 1]:.2f} (real {REAL_PERSIST[pos]:.2f}), sd of the projection change {r[:, 1].std():.2f}")
    return out


def late_career(runs: list[list[dict[str, Any]]], top: int = 24) -> list[str]:
    out = []
    for pos in SKILL:
        for name, lo, hi in (("25-26", 25, 26.99), ("27+", 27, 99)):
            x = []
            for seasons in runs:
                for a, b in zip(seasons, seasons[1:]):
                    cur = sorted(((pid, v) for pid, v in a["pl"].items() if v[0] == pos), key=lambda t: -t[1][1])[:top]
                    x += [b["pl"][pid][1] / v[1] for pid, v in cur if a["nfl"].get(pid) == b["nfl"].get(pid) and pid in b["pl"] and lo <= v[2] <= hi]
            x = np.array(x)
            p50, p10, sd = REAL_CELLS[(pos, name)]
            out.append(f"{pos} {name}: p50 {np.median(x):.2f} p10 {np.quantile(x, 0.1):.2f} sd(log) {np.log(np.maximum(x, 0.02)).std():.2f}   real {p50:.2f} / {p10:.2f} / {sd:.2f}   n={len(x)}")
    return out


def next_this(runs: list[list[dict[str, Any]]]) -> list[str]:
    from modules.sim.calibration import season_variance_report as svr

    real, sim = svr.real_tables(), svr.sim_tables(runs)
    return [f"{pos}: sim {svr.fmt_next(sim[pos]['nxt'])}   real {svr.fmt_next(real[pos]['nxt'])}" for pos in POS]


def real_rookies() -> dict[str, Any]:
    panel = dataset.load_panel()
    res: dict[str, Any] = {}
    for pos in POS:
        top12, top24, best, top3 = [], [], [], []
        for s in range(2021, 2026):
            rows = [r for r in panel if r["season"] == s and r["pos"] == pos and r.get("proj_ppg") and r["proj_ppg"] > 0]
            allp = sorted((r["proj_ppg"] for r in rows), reverse=True)
            vets = sorted((r["proj_ppg"] for r in rows if not r["rookie"]), reverse=True)
            rk = sorted((r["proj_ppg"] for r in rows if r["rookie"]), reverse=True)
            top12.append(sum(1 for x in rk if x >= allp[11]))
            top24.append(sum(1 for x in rk if x >= allp[23]))
            if rk:
                best.append(rk[0] / vets[11])
            top3.append((rk + [0, 0, 0])[:3])
        res[pos] = (np.mean(top12), np.mean(top24), np.mean(best), np.mean(top3, axis=0))
    return res


def rookies(runs: list[list[dict[str, Any]]]) -> list[str]:
    real = real_rookies()
    out = []
    for pos in POS:
        t12, t24, best, top3 = [], [], [], []
        for seasons in runs:
            for a in seasons[1:]:
                allp = sorted((pr["proj"] for pr in a["prof"].values() if pr["pos"] == pos), reverse=True)
                vets = sorted((pr["proj"] for pr in a["prof"].values() if pr["pos"] == pos and not pr["rookie"]), reverse=True)
                rk = sorted((pr["proj"] for pr in a["prof"].values() if pr["pos"] == pos and pr["rookie"]), reverse=True)
                if rk and len(vets) >= 12:
                    t12.append(sum(1 for x in rk if x >= allp[11]))
                    t24.append(sum(1 for x in rk if x >= allp[23]))
                    best.append(rk[0] / vets[11])
                    top3.append((rk + [0, 0, 0])[:3])
        r = real[pos]
        m3 = np.mean(top3, axis=0)
        out.append(f"{pos}: in position top 12 {np.mean(t12):.2f} (real {r[0]:.1f}), top 24 {np.mean(t24):.2f} ({r[1]:.1f}), best rookie / 12th veteran {np.mean(best):.2f} ({r[2]:.2f}), "
                   f"top three {m3[0]:.1f} / {m3[1]:.1f} / {m3[2]:.1f} (real {r[3][0]:.1f} / {r[3][1]:.1f} / {r[3][2]:.1f})")
    bust, n = [], 0
    for seasons in runs:
        for a in seasons[1:]:
            top = sorted(((pr["proj"], pid) for pid, pr in a["prof"].items() if pr["rookie"]), reverse=True)[:12]
            bust += [a["pl"][pid][1] / pj < 0.6 for pj, pid in top if pid in a["pl"]]
    out.append(f"class rank 1-12 busts (under 0.6 of the projection): {100 * np.mean(bust):.0f}%   (real 16%, n={len(bust)})")
    return out


def main() -> None:  # pragma: no cover - a reporting tool
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--seasons", type=int, default=10)
    ap.add_argument("--seed0", type=int, default=0)
    ap.add_argument("--flags", type=str, default="", help="GameSettings overrides as JSON, e.g. '{\"stability_v\": 1}' for the before side")
    args = ap.parse_args()
    flags = json.loads(args.flags) if args.flags else None
    runs = [dynasty_run.run(s, args.seasons, profiles=True, flags=flags) for s in range(1 + args.seed0, 1 + args.seed0 + args.seeds)]
    print(f"== {args.seeds} seeds x {args.seasons} seasons (seeds {1 + args.seed0}-{args.seed0 + args.seeds}), flags {flags or 'defaults'}")
    for title, lines in (("balance", balance(runs)), ("persistence of a top-24 player's projection change vs last season's result", persistence(runs)),
                         ("late career: next / this ppg, top 24 by ppg", late_career(runs)), ("next / this ppg, top 12 by ppg", next_this(runs)), ("rookies after the first offseason", rookies(runs))):
        print(f"\n-- {title}")
        print("\n".join(lines))


if __name__ == "__main__":  # pragma: no cover
    main()

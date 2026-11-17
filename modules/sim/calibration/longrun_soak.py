"""Long-run soak: many seeds x 30 dynasty seasons, one metrics row per season, to catch slow drift in the balance or the economy.

    python -m modules.sim.calibration.longrun_soak run    --out DIR [--seeds 8] [--seasons 30] [--procs 4]      # 1QB and superflex, 12-team PPR, current flags
    python -m modules.sim.calibration.longrun_soak report --out DIR [--before DIR3]                               # drift table from the saved runs
    python scripts/sim_longrun_charts.py tables.json docs/audits/sim-longrun                                     # the charts (report --json tables.json; needs matplotlib)

Headless games on the committed 2025 panel pool (``dynasty_run``; a throwaway pool, never ``data/players.db``), every current gate on (a new game takes the
newest version of each rule). ``season_metrics`` turns one simulated season into scalars; ``BOUNDS`` is what the quick regression test
(tests/test_sim_longrun_regression.py) asserts, with the real-NFL / audit target each bound comes from.
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
from collections import Counter
from typing import Any

import numpy as np

POS = ("QB", "RB", "WR", "TE")


def season_metrics(x: dict[str, Any], prev: dict[str, Any] | None = None) -> dict[str, float]:
    """Scalars for one season dict from ``dynasty_run.run(..., profiles=True)``; ``prev`` is the season before it (for the offseason deltas)."""
    # The harness plays the user's team with no lineup or waiver management (slot 3), so every team-level metric reads the 11 AI teams only.
    w = np.asarray(x["weekly"], dtype=float)
    ai_w = np.delete(w.reshape(-1, 12), int(x["user"]) - 1, axis=1).ravel() if len(w) % 12 == 0 else w
    w = ai_w
    soak = x["soak"]
    ai = lambda d: [v for k, v in d.items() if k != x["user"]]
    m: dict[str, float] = {
        "score_mean": w.mean(), "score_sd": w.std(), "score_p1": np.percentile(w, 1), "score_p99": np.percentile(w, 99),
        "score_lt70": 100 * (w < 70).mean(), "score_lt60": 100 * (w < 60).mean(), "score_gt170": 100 * (w > 170).mean(),
    }
    for pos in POS:
        ps = sorted((v[1] for v in x["pl"].values() if v[0] == pos), reverse=True)
        m[f"{pos}12_ppg"] = ps[11] if len(ps) > 11 else float("nan")
        m[f"{pos}1_ppg"] = ps[0] if ps else float("nan")
    prof = x["prof"]
    rk = [(pr["proj"], pr["pos"]) for pr in prof.values() if pr["rookie"]]
    if rk:
        vets = {p: sorted((pr["proj"] for pr in prof.values() if pr["pos"] == p and not pr["rookie"]), reverse=True) for p in ("RB", "WR", "TE")}
        top12 = {p: sorted((pr["proj"] for pr in prof.values() if pr["pos"] == p), reverse=True)[11] for p in ("RB", "WR", "TE") if len(vets[p]) > 11}
        m["rookies_top12_skill"] = sum(1 for pj, p in rk if p in top12 and pj >= top12[p])
        ratios = [max(pj for pj, q in rk if q == p) / vets[p][11] for p in vets if len(vets[p]) > 11 and any(q == p for _, q in rk)]
        if ratios:
            m["best_rookie_vs_vet12"] = float(np.mean(ratios))
        m["rookie_class_n"] = len(rk)
    if soak["rookie_mkts"]:
        rm = soak["rookie_mkts"]
        m["pick_value_1"], m["pick_value_12"], m["pick_value_36"] = rm[0], rm[min(11, len(rm) - 1)], rm[-1]
    sa, ra = np.asarray(soak["starters_age"], dtype=float), np.asarray(soak["roster_ages"], dtype=float)
    m["starter_age"], m["starter_age_30plus"] = sa.mean(), 100 * (sa >= 30).mean()
    m["roster_age"], m["roster_age_u24"], m["roster_age_30plus"] = ra.mean(), 100 * (ra < 24).mean(), 100 * (ra >= 30).mean()
    m["pool"] = x["nplayers"]
    for pos in POS + ("K",):
        m[f"pool_{pos}"] = soak["pool_by_pos"].get(pos, 0)
    if prev is not None:
        m["retired"] = soak["retired_total"] - prev["soak"]["retired_total"]
    m["trades"] = len(soak["trades"])
    both = [(a, b) for a, b in soak["trades"] if a > 1 and b > 1]
    if both:
        m["trade_unfair"] = float(np.mean([abs(np.log(a / b)) for a, b in both]))
    m["waivers"], m["drops"], m["injuries"] = soak["n_waiver"], soak["n_drop"], soak["n_injuries"]
    qb = [c.get("QB", 0) for c in ai(x["comp"])]
    m["qb_per_team"], m["teams_3plus_qb"] = float(np.mean(qb)), 100 * float(np.mean([q >= 3 for q in qb]))
    tv = np.asarray(ai(x["team_val"]), dtype=float)
    m["team_value_mean"], m["team_value_cv"] = tv.mean(), tv.std() / tv.mean()
    m["win_sd"] = float(np.std(ai(x["wins"])))
    m["pf_cv"] = float(np.std(ai(x["pfs"])) / np.mean(ai(x["pfs"])))
    m["top_market"] = float(np.mean(x["top_market"]))
    rows = [r for r in soak.get("mm_rows", ()) if r[0] in POS and r[1] > 3 and r[2] > 3]
    if rows:  # the price curve: log market on log projection, per position, and the mean market of the pool
        m["market_mean"] = float(np.mean([r[2] for r in rows]))
        for pos in ("RB", "WR", "TE"):
            g = np.array([(np.log(r[2]), np.log(r[1])) for r in rows if r[0] == pos])
            m[f"market_slope_{pos}"] = float(np.polyfit(g[:, 1], g[:, 0], 1)[0])
    return {k: float(v) for k, v in m.items()}


def parity(runs: list[list[dict[str, Any]]]) -> dict[str, float]:
    """Champion variety and dynasties across seeds: distinct champions per 10 seasons, repeat champion share, the largest title count of any team."""
    distinct, repeats, most, n = [], 0, [], 0
    for r in runs:
        ch = [s["champ"] for s in r]
        distinct += [len(set(ch[i:i + 10])) for i in range(0, len(ch) - 9, 10)]
        repeats += sum(1 for a, b in zip(ch, ch[1:]) if a == b)
        n += len(ch) - 1
        most.append(max(Counter(ch).values()))
    return {"distinct_per_10": float(np.mean(distinct)) if distinct else float("nan"), "repeat_champ_pct": 100 * repeats / max(n, 1), "max_titles": float(np.mean(most))}


def metrics_table(runs: list[list[dict[str, Any]]]) -> dict[str, np.ndarray]:
    """{metric: array (seeds, seasons)} (NaN where a metric is not defined that season)."""
    n = max(len(r) for r in runs)
    rows = [[season_metrics(r[i], r[i - 1] if i else None) for i in range(len(r))] for r in runs]
    keys = sorted({k for r in rows for m in r for k in m})
    out = {k: np.full((len(runs), n), np.nan) for k in keys}
    for si, r in enumerate(rows):
        for i, m in enumerate(r):
            for k, v in m.items():
                out[k][si, i] = v
    if "retired" in out:
        out["retired"][:, -1] = np.nan
    return out


# Bounds the regression test holds a short run to: (low, high, where the number comes from).
BOUNDS: dict[str, tuple[float, float, str]] = {
    "score_mean": (85.0, 115.0, "season-1 level 101.7 (long-dynasty audit); the league plateaus within 10 percent"),
    "score_sd": (17.0, 30.0, "weekly team-score sd 23-26 (realism sweep)"),
    "score_lt70": (0.0, 13.0, "soak level 8-9 percent (1QB, K only, no DEF) vs real 3.6 for K+DEF (#2091): a drift guard, the level gap is in the audit"),
    "score_lt60": (0.0, 6.0, "soak level 3 percent vs real 1.2 for K+DEF (#2091)"),
    "score_gt170": (0.0, 3.0, "real 0.8 percent over 170 (#2091)"),
    "starter_age": (24.5, 29.5, "starter age 26-27 over 20 seasons (long-dynasty audit)"),
    "pool": (330.0, 560.0, "pool 383 at the start, 450-480 plateau"),
    "pool_K": (24.0, 36.0, "kickers 30, held"),
    "qb_per_team": (1.4, 2.9, "AI QB counts 1.4-2.7 (long-dynasty audit); cap_v 1"),
    "best_rookie_vs_vet12": (0.4, 1.4, "real 0.9 (rookie audit #2030)"),
    "waivers": (15.0, 160.0, "60-100 waiver adds a league-season"),
}


def windows(n: int) -> list[tuple[str, slice]]:
    mid = n // 2
    return [("s1-3", slice(0, 3)), (f"s{mid - 1}-{mid + 1}", slice(mid - 2, mid + 1)), (f"s{n - 2}-{n}", slice(n - 3, n))]


def drift_rows(t: dict[str, np.ndarray]) -> list[tuple[str, float, float, float]]:
    n = next(iter(t.values())).shape[1]
    rows = []
    for k, a in t.items():
        v = [float(np.nanmean(a[:, sl])) if not np.isnan(a[:, sl]).all() else float("nan") for _, sl in windows(n)]
        rows.append((k, *v))
    return rows


def run_all(out: str, seeds: int, seasons: int, procs: int, flags: dict | None = None) -> None:  # pragma: no cover - the long soak
    from multiprocessing import Pool

    os.makedirs(out, exist_ok=True)
    jobs = [(s, sf, seasons, out, flags) for s in range(1, seeds + 1) for sf in (False, True)]
    with Pool(procs) as p:
        for f in p.imap_unordered(_job, jobs):
            print("done", f, flush=True)


def _job(a):  # pragma: no cover
    from modules.sim.calibration import dynasty_run

    seed, sf, n, out, flags = a
    f = f"{out}/{'sf' if sf else '1qb'}_{seed}.pkl"
    if os.path.exists(f):
        return f
    r = dynasty_run.run(seed, n, profiles=True, superflex=sf, flags=flags)
    for x in r:
        for k in ("depth_events", "nfl", "depth"):
            x.pop(k, None)
    with open(f, "wb") as fh:
        pickle.dump(r, fh)
    return f


def load(out: str, mode: str) -> list[list[dict[str, Any]]]:  # pragma: no cover
    fs = sorted(f for f in os.listdir(out) if f.startswith(mode + "_") and f.endswith(".pkl"))
    return [pickle.load(open(os.path.join(out, f), "rb")) for f in fs]


def main() -> None:  # pragma: no cover
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("run", "report"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--seasons", type=int, default=30)
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--flags", default="", help='run: GameSettings overrides as JSON for a before side, e.g. \'{"stability_v": 3}\'')
    ap.add_argument("--json", default="", help="report: write every metric table (seeds x seasons) to this file for scripts/sim_longrun_charts.py")
    ap.add_argument("--before", default="", help="report: a second run directory (made with --flags stability_v 3) drawn on the charts and printed beside it")
    a = ap.parse_args()
    if a.cmd == "run":
        run_all(a.out, a.seeds, a.seasons, min(a.procs, 4), json.loads(a.flags) if a.flags else None)
        return
    tables = {}
    for mode in ("1qb", "sf"):
        runs = load(a.out, mode)
        if not runs:
            continue
        t = tables[mode] = metrics_table(runs)
        print(f"== {mode}: {len(runs)} seeds x {len(runs[0])} seasons   parity {parity(runs)}")
        for k, s13, mid, last in drift_rows(t):
            print(f"{k:<24}{s13:>10.2f}{mid:>10.2f}{last:>10.2f}")
    if a.before:
        runs = load(a.before, "1qb")
        if runs:
            tables["1qb before"] = metrics_table(runs)
            print(f"== before (1qb) {len(runs)} seeds   parity {parity(runs)}")
            for k, s13, mid, last in drift_rows(tables["1qb before"]):
                print(f"{k:<24}{s13:>10.2f}{mid:>10.2f}{last:>10.2f}")
    if a.json:
        with open(a.json, "w") as fh:
            json.dump({m: {k: v.tolist() for k, v in t.items()} for m, t in tables.items()}, fh)


if __name__ == "__main__":  # pragma: no cover
    main()

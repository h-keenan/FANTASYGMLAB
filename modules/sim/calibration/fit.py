"""Fit the player model's calibrated constants to the real panel.

Each stage fits on the TRAIN seasons only (default 2021-2023); ``backtest.py``
then scores the held-out seasons (2024-2025). Stages:

    templates   least-squares stat-line curves (stat vs PPR points) per position
    injuries    empirical episode-length pmf and hazard scale
    weekly      per-position weekly dispersion (game factor, volume, efficiency, yards, TD mixing)
    season      season-level archetype mixture (breakout / bust / solid)
    inseason    role-change rate and form scale (half-season split, lag-1)

    python -m modules.sim.calibration.fit season --train 2021 2022 2023

Each stage prints constants to paste into ``modules/sim/player_model.py``. A
(mu, lambda) evolution strategy with common random numbers does the searching;
no scipy needed. Slow stages take minutes, not hours.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from collections import defaultdict
from typing import Any

import numpy as np

from modules.sim import player_model as pm
from modules.sim.calibration import backtest as bt
from modules.sim.calibration import dataset

CORE = bt.CORE


def evolve(f, x0: np.ndarray, step: np.ndarray, gens: int, pop: int = 14, keep: int = 4, seed: int = 3, verbose: bool = True):
    """(mu, lambda) evolution strategy with shrinking step."""

    rng = np.random.default_rng(seed)
    best_x, best_f = x0.copy(), f(x0)
    mean = x0.copy()
    sigma = 1.0
    for g in range(gens):
        cand = [mean + sigma * step * rng.standard_normal(len(x0)) for _ in range(pop)]
        vals = [f(c) for c in cand]
        order = np.argsort(vals)
        elite = [cand[i] for i in order[:keep]]
        mean = np.mean(elite, axis=0)
        if vals[order[0]] < best_f:
            best_f, best_x = float(vals[order[0]]), cand[order[0]].copy()
        sigma *= 0.93
        if verbose:
            print(f"  gen {g + 1}/{gens} best {best_f:.4f}", flush=True)
    return best_x, best_f


# ----------------------------------------------------------------------------- templates


def fit_templates(rows: list[dict]) -> dict[str, dict[str, tuple[float, float]]]:
    idx = {f: i + 1 for i, f in enumerate(dataset.STAT_FIELDS)}
    out: dict[str, dict[str, tuple[float, float]]] = {}
    for pos, comps in {k: list(v) for k, v in pm.TEMPLATE.items()}.items():
        mats = []
        for r in rows:
            if r["pos"] != pos:
                continue
            pl = [w for w in r["weeks"] if w and w[0]]
            if len(pl) < 8:
                continue
            mats.append([np.mean([w[idx["pts_ppr"]] for w in pl])] + [np.mean([w[idx[c]] for w in pl]) for c in comps])
        if not mats:
            continue
        m = np.array(mats)
        out[pos] = {}
        for j, c in enumerate(comps, 1):
            b, a = np.polyfit(m[:, 0], m[:, j], 1)
            out[pos][c] = (round(float(a), 3), round(float(b), 4))
    return out


# ----------------------------------------------------------------------------- weekly


def _weekly_loss(rows_pos: list[dict], pos: str, vec: np.ndarray, keys: list[str], copies: int = 1) -> float:
    saved = dict(pm.WEEK[pos])
    for k, v in zip(keys, vec):
        pm.WEEK[pos][k] = float(max(1e-3, v))
    try:
        sims = [[bt.simulate_row(r, None, c) for c in range(copies)] for r in rows_pos]
        res = bt.weekly_shape(rows_pos, sims)
    finally:
        pm.WEEK[pos].update(saved)
    row = res.get(pos)
    if row is None:
        return 1e9
    dq = np.array(row["sim_q"]) - np.array(row["real_q"])
    stat = sum((v["sim"] - v["real"]) ** 2 for v in row.get("stat_cv", {}).values())
    return float((dq**2).sum() + 6.0 * (row["sim_cv"] - row["real_cv"]) ** 2 + 3.0 * stat + 20.0 * ((row["sim_boom"] - row["real_boom"]) ** 2 + (row["sim_bust"] - row["real_bust"]) ** 2))


def fit_weekly(rows: list[dict], gens: int = 10, max_rows: int = 160) -> dict[str, dict[str, float]]:
    out = {}
    keys = ["sg", "vol_cv", "eff", "kappa", "td_cv"]
    for pos in CORE:
        sel = [r for r in rows if r["pos"] == pos and r["adp"] and r["adp"] <= 150]
        sel = sel[:: max(1, len(sel) // max_rows)]
        print(f"weekly {pos}: {len(sel)} player-seasons", flush=True)
        x0 = np.array([pm.WEEK[pos][k] for k in keys])
        best, f = evolve(lambda v: _weekly_loss(sel, pos, v, keys), x0, x0 * 0.25, gens, pop=10, keep=3)
        out[pos] = {k: round(float(max(1e-3, v)), 3) for k, v in zip(keys, best)}
        print(pos, out[pos], f, flush=True)
        pm.WEEK[pos].update(out[pos])
    return out


# ----------------------------------------------------------------------------- season


SEASON_FREE = [
    "b_tier", "gain_tier", "b_solid", "b_solid_qb", "sigma0", "sigma_tier", "qb_sig", "pb0", "pb_rook", "pb_age", "pb_tier",
    "pu0", "pu_rook", "pu_age", "pu_tier", "bust_mult", "bust_sd", "gain_mean", "gain_rook", "qb_gain", "te_gain",
]
SEASON_STEP = {
    "b_tier": 0.05, "gain_tier": 0.15,
    "b_solid": 0.04, "b_solid_qb": 0.04, "sigma0": 0.03, "sigma_tier": 0.1, "qb_sig": 0.15, "pb0": 0.4, "pb_rook": 0.4,
    "pb_age": 0.3, "pb_tier": 0.3, "pu0": 0.4, "pu_rook": 0.4, "pu_age": 0.3, "pu_tier": 0.3, "bust_mult": 0.06,
    "bust_sd": 0.05, "gain_mean": 0.8, "gain_rook": 0.3, "qb_gain": 0.15, "te_gain": 0.15,
}


# Plausible ranges keep the search from exploiting degenerate directions (a negative
# QB breakout gain, older players busting less) that fit noise but mean nothing.
SEASON_BOUNDS = {
    "b_tier": (-0.15, 0.15), "gain_tier": (0.0, 0.7), "b_solid": (0.8, 1.05), "b_solid_qb": (0.7, 1.0),
    "sigma0": (0.05, 0.2), "sigma_tier": (0.1, 1.0), "qb_sig": (0.4, 1.2), "pb0": (-4.0, -0.5), "pb_rook": (0.0, 2.0),
    "pb_age": (0.0, 1.0), "pb_tier": (-0.8, 0.8), "pu0": (-3.0, 0.0), "pu_rook": (0.0, 1.5), "pu_age": (0.0, 1.0),
    "pu_tier": (-1.0, 0.8), "bust_mult": (0.45, 0.85), "bust_sd": (0.08, 0.35), "gain_mean": (1.5, 8.0),
    "gain_rook": (0.5, 2.0), "qb_gain": (0.2, 1.0), "te_gain": (0.3, 1.2),
}


def _std_d(proj: float, ppg: float) -> float:
    return (ppg - proj) / max(2.5, 0.2 * proj)


def season_loss(rows: list[dict], vec: np.ndarray, copies: int = 2, ip=None) -> float:
    vec = np.array([min(max(v, SEASON_BOUNDS[k][0]), SEASON_BOUNDS[k][1]) for k, v in zip(SEASON_FREE, vec)])
    sp = dataclasses.replace(pm.SEASON, **{k: float(v) for k, v in zip(SEASON_FREE, vec)})
    ip = ip or pm.INSEASON
    groups_real: dict[str, list[float]] = defaultdict(list)
    groups_sim: dict[str, list[float]] = defaultdict(list)
    rate = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0.0])  # real brk, real bust, sim brk, sim bust, n
    ranks = bt.rank_by_adp(rows)
    for r in rows:
        real = dataset.season_summary(r)
        if real["played"] < 4 or r["proj_ppg"] < 3.0:
            continue
        sims = [bt.simulate_row(r, ranks.get((r["season"], r["pid"])), c, (sp, ip)) for c in range(copies)]
        sims = [s for s in sims if s["played"] >= 4]
        if not sims:
            continue
        tl = pm.tier_label(r["pos"], r["proj_ppg"])
        gs = [f"pos:{r['pos']}", f"pt:{r['pos']}:{tl}", f"rk:{'rookie' if r['rookie'] else 'vet'}:{pm.tier_label(r['pos'], r['proj_ppg'])}",
              f"age:{bt.age_bucket(r['age'])}", f"tier:{pm.tier_label(r['pos'], r['proj_ppg'])}"]
        hr = bt.hit_rates(real, r["proj_ppg"])
        for g in gs:
            groups_real[g].append(_std_d(r["proj_ppg"], real["ppg"]))
            groups_sim[g] += [_std_d(r["proj_ppg"], s["ppg"]) for s in sims]
            a = rate[g]
            a[0] += hr["breakout"]
            a[1] += hr["bust"]
            for s in sims:
                h = bt.hit_rates(s, r["proj_ppg"])
                a[2] += h["breakout"] / len(sims)
                a[3] += h["bust"] / len(sims)
            a[4] += 1
    loss = 0.0
    for g, real_v in groups_real.items():
        n = len(real_v)
        if n < 15:
            continue
        qr = np.percentile(real_v, [10, 25, 50, 75, 90])
        qs = np.percentile(groups_sim[g], [10, 25, 50, 75, 90])
        loss += np.sqrt(n) * float(((qr - qs) ** 2).sum())
        a = rate[g]
        loss += np.sqrt(n) * 25.0 * ((a[0] - a[2]) / a[4]) ** 2 + np.sqrt(n) * 25.0 * ((a[1] - a[3]) / a[4]) ** 2
    return float(loss)


def fit_season(rows: list[dict], gens: int = 14, copies: int = 2) -> dict[str, float]:
    x0 = np.array([getattr(pm.SEASON, k) for k in SEASON_FREE])
    step = np.array([SEASON_STEP[k] for k in SEASON_FREE])
    print(f"season fit on {len(rows)} player-seasons", flush=True)
    best, f = evolve(lambda v: season_loss(rows, v, copies), x0, step, gens, pop=12, keep=3)
    out = {k: round(float(min(max(v, SEASON_BOUNDS[k][0]), SEASON_BOUNDS[k][1])), 4) for k, v in zip(SEASON_FREE, best)}
    print(json.dumps(out), f)
    return out


# ----------------------------------------------------------------------------- in-season


def injury_pmf(rows: list[dict]) -> dict[str, Any]:
    core = [r for r in rows if r["pos"] in CORE and ((r["adp"] and r["adp"] <= 120) or r["proj_ppg"] >= 9)]
    lengths = []
    for r in core:
        seq = [bool(w[0]) for w in r["weeks"] if w is not None]
        i = 0
        while i < len(seq):
            if not seq[i]:
                j = i
                while j < len(seq) and not seq[j]:
                    j += 1
                lengths.append(j - i)
                i = j
            else:
                i += 1
    n = len(lengths)
    pmf = [round(sum(1 for x in lengths if x == k) / n, 3) for k in range(1, 9)]
    return {"episodes": n, "pmf": pmf, "tail": round(sum(1 for x in lengths if x >= 9) / n, 3)}


def fit_inseason(rows: list[dict], copies: int = 6) -> dict[str, Any]:
    core = [r for r in rows if r["pos"] in CORE and ((r["adp"] and r["adp"] <= 120) or r["proj_ppg"] >= 9)]
    real_miss = float(np.mean([dataset.season_summary(r)["missed"] for r in core]))
    real_split = bt.split_half_report(core, [[{"pts": dataset.season_summary(r)["pts"]}] for r in core])["real_sd"]
    best: dict[str, Any] = {}
    # injury hazard: match mean games missed
    for hz in (0.045, 0.052, 0.058, 0.065, 0.072):
        ip = dataclasses.replace(pm.INSEASON, hazard=hz)
        sims = bt.simulate_panel(core, 3, (pm.SEASON, ip))
        m = float(np.mean([x["missed"] for ss in sims for x in ss]))
        print(f"hazard {hz}: sim missed {m:.2f} vs real {real_miss:.2f}", flush=True)
        if "hazard" not in best or abs(m - real_miss) < best["hazard_err"]:
            best.update(hazard=hz, hazard_err=abs(m - real_miss))
    # role-change rate: match half-split SD
    for rr in (0.0, 0.3, 0.55, 0.8, 1.1):
        ip = dataclasses.replace(pm.INSEASON, hazard=best["hazard"], role_rate=rr, role_rate_deep=rr * 0.8)
        sims = bt.simulate_panel(core, copies, (pm.SEASON, ip))
        rep = bt.split_half_report(core, sims)
        lag = bt.lag1_report(core, sims)
        print(f"role_rate {rr}: split sd {rep['sim_sd']} (real {real_split}) lag1 {lag}", flush=True)
        err = abs(rep["sim_sd"] - real_split)
        if "role_err" not in best or err < best["role_err"]:
            best.update(role_rate=rr, role_err=err)
    return best


# ----------------------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["templates", "injuries", "weekly", "season", "inseason"])
    ap.add_argument("--train", nargs="*", type=int, default=[2021, 2022, 2023])
    ap.add_argument("--gens", type=int, default=None)
    ap.add_argument("--copies", type=int, default=3)
    args = ap.parse_args(argv)
    rows = [r for r in dataset.load_panel() if r["season"] in args.train]
    if args.stage == "templates":
        print(json.dumps(fit_templates(rows), indent=1))
    elif args.stage == "injuries":
        print(json.dumps(injury_pmf(rows)))
    elif args.stage == "weekly":
        fit_weekly(rows, gens=args.gens or 10)
    elif args.stage == "season":
        fit_season([r for r in rows if r["pos"] in CORE], gens=args.gens or 14, copies=args.copies)
    elif args.stage == "inseason":
        print(json.dumps(fit_inseason(rows)))


if __name__ == "__main__":
    main()

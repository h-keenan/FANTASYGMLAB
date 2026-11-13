"""Fit the player model's calibrated constants to the real panel.

Each stage fits on the TRAIN seasons only (default 2021-2023); ``backtest.py``
then scores the held-out seasons (2024-2025). Stages:

    templates   least-squares stat-line curves (stat vs PPR points) per position
    injuries    empirical episode-length pmf and hazard scale
    weekly      per-position weekly dispersion (game factor, volume, efficiency, yards, TD mixing)
    season      season-level archetype mixture (breakout / bust / solid)
    season2     the v2 season-level fit: adds role collapse, QB/TE/rookie spread, star role stability and
                finish-rate targets, scored on the full simulator across worker processes
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
import math
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
# v2 structure (``season2``): the new parameters plus the bounds the v1 fit was straining against.
SEASON2_NEW = ["pc0", "pc_tier", "pc_rook", "collapse_mult", "collapse_sd", "pu_qb", "qb_bust_mult", "sig_rook", "te_sig",
               "ps0", "ps_tier"]
INSEASON2_NEW = ["role_star"]  # role_qb is fixed (0.1) by a one-dimensional fit to the real QB season SD
SEASON2_STEP = {"pc0": 0.5, "pc_tier": 0.4, "pc_rook": 0.4, "collapse_mult": 0.06, "collapse_sd": 0.08, "pu_qb": 0.4,
                "qb_bust_mult": 0.05, "sig_rook": 0.15, "te_sig": 0.15, "ps0": 0.4, "ps_tier": 0.3,
                "role_star": 0.4, "role_qb": 0.2}
SEASON2_BOUNDS = {"pc0": (-6.0, -0.5), "pc_tier": (0.0, 2.0), "pc_rook": (0.0, 2.0), "collapse_mult": (0.15, 0.6),
                  "collapse_sd": (0.1, 0.6), "pu_qb": (-2.0, 1.0), "qb_bust_mult": (0.6, 0.95), "sig_rook": (0.0, 1.0),
                  "te_sig": (0.7, 1.6), "ps0": (-4.0, -1.0), "ps_tier": (0.0, 1.2), "role_star": (0.0, 2.5), "role_qb": (0.0, 1.0),
                  # v1 parameters that sat on a bound are widened for the v2 fit
                  "qb_sig": (0.15, 1.2), "bust_sd": (0.08, 0.6), "pb_rook": (0.0, 3.0), "pb_age": (0.0, 1.5),
                  "pu_age": (0.0, 1.5), "gain_rook": (0.3, 2.0), "qb_gain": (0.05, 1.0)}
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


_POOL_ROWS: list[dict] = []
_POOL_RANKS: dict = {}


def _sim_light(args) -> dict[str, Any]:
    i, c, sp, ip = args
    r = _POOL_ROWS[i]
    x = bt.simulate_row(r, _POOL_RANKS.get((r["season"], r["pid"])), c, (sp, ip))
    return {k: x[k] for k in ("played", "available", "missed", "ppg", "total")}


def _simulate_rows(rows: list[dict], ranks: dict, copies: int, sp, ip, workers: int) -> list[list[dict]]:
    """Full-simulator season summaries for every row and copy, optionally across worker processes
    (fork: rows are inherited, only the small parameter objects are pickled)."""

    global _POOL_ROWS, _POOL_RANKS
    _POOL_ROWS, _POOL_RANKS = rows, ranks
    jobs = [(i, c, sp, ip) for i in range(len(rows)) for c in range(copies)]
    if workers > 1:
        import multiprocessing as mp

        with mp.get_context("fork").Pool(workers) as pool:
            out = pool.map(_sim_light, jobs, chunksize=64)
    else:
        out = [_sim_light(j) for j in jobs]
    return [out[i * copies:(i + 1) * copies] for i in range(len(rows))]


def season2_loss(rows: list[dict], sp, ip, copies: int = 2, workers: int = 1) -> float:
    """Season-level loss for the v2 structure: quantiles (5-95) of the standardised miss, breakout/bust rates,
    SD of log(actual/projection), and preseason-rank finish rates, over position/tier/rookie/age groups."""

    ranks = bt.rank_by_adp(rows)
    real_g: dict[str, list] = defaultdict(list)
    sim_g: dict[str, list] = defaultdict(list)
    real_l: dict[str, list] = defaultdict(list)
    sim_l: dict[str, list] = defaultdict(list)
    rate = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0.0])
    sims_by_row = dict(enumerate(_simulate_rows(rows, ranks, copies, sp, ip, workers)))
    for i, r in enumerate(rows):
        real = dataset.season_summary(r)
        if real["played"] < 4 or r["proj_ppg"] < 3.0:
            continue
        sims = [s_ for s_ in sims_by_row[i] if s_["played"] >= 4]
        if not sims:
            continue
        tl = pm.tier_label(r["pos"], r["proj_ppg"])
        gs = [f"pos:{r['pos']}", f"pt:{r['pos']}:{tl}", f"rk:{'rookie' if r['rookie'] else 'vet'}:{tl}", f"rkpos:{'rookie' if r['rookie'] else 'vet'}:{r['pos']}",
              f"age:{bt.age_bucket(r['age'])}", f"tier:{tl}"]
        hr = bt.hit_rates(real, r["proj_ppg"])
        lr = float(np.log(max(real["ppg"] / r["proj_ppg"], 0.05)))
        for g in gs:
            real_g[g].append(_std_d(r["proj_ppg"], real["ppg"]))
            sim_g[g] += [_std_d(r["proj_ppg"], s_["ppg"]) for s_ in sims]
            real_l[g].append(lr)
            sim_l[g] += [float(np.log(max(s_["ppg"] / r["proj_ppg"], 0.05))) for s_ in sims]
            a = rate[g]
            a[0] += hr["breakout"]
            a[1] += hr["bust"]
            for s_ in sims:
                h = bt.hit_rates(s_, r["proj_ppg"])
                a[2] += h["breakout"] / len(sims)
                a[3] += h["bust"] / len(sims)
            a[4] += 1
    loss = 0.0
    for g, real_v in real_g.items():
        n = len(real_v)
        if n < 15:
            continue
        qr = np.percentile(real_v, [5, 10, 25, 50, 75, 90, 95])
        qs = np.percentile(sim_g[g], [5, 10, 25, 50, 75, 90, 95])
        loss += np.sqrt(n) * float(((qr - qs) ** 2).sum())
        a = rate[g]
        loss += np.sqrt(n) * 25.0 * ((a[0] - a[2]) / a[4]) ** 2 + np.sqrt(n) * 25.0 * ((a[1] - a[3]) / a[4]) ** 2
        loss += np.sqrt(n) * 40.0 * (np.std(real_l[g]) - np.std(sim_l[g])) ** 2
    # finish rates: ADP top-12 / 13-24 at a position finishing top-12 / top-24 / outside 36 (total points)
    by = defaultdict(list)
    for i, r in enumerate(rows):
        if r["pos"] in CORE and (r["season"], r["pid"]) in ranks:
            by[(r["season"], r["pos"])].append(i)
    acc = defaultdict(lambda: [np.zeros(3), np.zeros(3), 0])
    for (season, pos), idxs in by.items():
        if len(idxs) < 24:
            continue
        for tag in ["real", *range(copies)]:
            tot = {i: (dataset.season_summary(rows[i])["total"] if tag == "real" else sims_by_row[i][tag]["total"]) for i in idxs}
            fin = {i: k + 1 for k, i in enumerate(sorted(idxs, key=lambda i: -tot[i]))}
            for i in idxs:
                rk = ranks[(rows[i]["season"], rows[i]["pid"])]
                cat = "top12" if rk <= 12 else ("13-24" if rk <= 24 else None)
                if cat is None:
                    continue
                v = np.array([fin[i] <= 12, fin[i] <= 24, fin[i] > 36], dtype=float)
                a = acc[f"{pos}:{cat}"]
                if tag == "real":
                    a[0] += v
                    a[2] += 1
                else:
                    a[1] += v / copies
    for g, (rv, sv, n) in acc.items():
        if n >= 20:
            loss += 40.0 * np.sqrt(n) * float((((rv - sv) / n) ** 2).sum())
    return float(loss)


def fit_season2(rows: list[dict], gens: int = 24, copies: int = 2, include_new: bool = True, seed: int = 3, workers: int = 8) -> dict[str, float]:
    """Search the v2 season-level constants. ``include_new=False`` refits only the v1 structure (the
    honest before-baseline, same loss, same data, v1 bounds)."""

    names = list(SEASON_FREE) + (SEASON2_NEW if include_new else [])
    in_names = INSEASON2_NEW if include_new else []
    bounds = {**SEASON_BOUNDS, **(SEASON2_BOUNDS if include_new else {})}
    steps = {**SEASON_STEP, **SEASON2_STEP}
    x0 = []
    for k in names:
        v = getattr(pm.SEASON, k)
        x0.append(-3.0 if k == "pc0" and v < -20 else (0.25 if k == "pc_tier" else v))
    x0 += [getattr(pm.INSEASON, k) for k in in_names]
    x0 = np.array(x0, dtype=float)
    allnames = names + in_names
    step = np.array([steps[k] for k in allnames])
    lo = np.array([(bounds | SEASON2_BOUNDS)[k][0] for k in allnames])
    hi = np.array([(bounds | SEASON2_BOUNDS)[k][1] for k in allnames])
    lo[: len(SEASON_FREE)] = [bounds[k][0] for k in SEASON_FREE]
    hi[: len(SEASON_FREE)] = [bounds[k][1] for k in SEASON_FREE]
    x0 = np.clip(x0, lo, hi)

    def build(vec):
        vec = np.clip(vec, lo, hi)
        sp = dataclasses.replace(pm.SEASON, **{k: float(v) for k, v in zip(names, vec[: len(names)])})
        ip = dataclasses.replace(pm.INSEASON, **{k: float(v) for k, v in zip(in_names, vec[len(names):])})
        return sp, ip

    print(f"season2 fit on {len(rows)} player-seasons, {len(allnames)} parameters", flush=True)
    best, f = evolve(lambda v: season2_loss(rows, *build(v), copies, workers), x0, step, gens, pop=16, keep=4, seed=seed)
    out = {k: round(float(v), 4) for k, v in zip(allnames, np.clip(best, lo, hi))}
    print(json.dumps(out), f)
    return out


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
    ap.add_argument("stage", choices=["templates", "injuries", "weekly", "season", "season2", "inseason"])
    ap.add_argument("--train", nargs="*", type=int, default=[2021, 2022, 2023])
    ap.add_argument("--gens", type=int, default=None)
    ap.add_argument("--copies", type=int, default=3)
    ap.add_argument("--v1-structure", action="store_true", help="season2: refit only the v1 parameters (before-baseline)")
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--workers", type=int, default=8)
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
    elif args.stage == "season2":
        fit_season2([r for r in rows if r["pos"] in CORE], gens=args.gens or 24, copies=args.copies if args.copies != 3 else 2,
                    include_new=not args.v1_structure, seed=args.seed, workers=args.workers)
    elif args.stage == "inseason":
        print(json.dumps(fit_inseason(rows)))


if __name__ == "__main__":
    main()

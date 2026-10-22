"""Fit and backtest the IDP rate model (modules/idp_values.py).

Usage:
    python scripts/idp_backtest.py --data DIR [--fit-out modules/idp_model_params.json]

DIR holds ``def_raw_{season}.json`` (week -> {player_id: Sleeper stat line} for
defenders; fetched with ``--fetch``), ``players_slim.json`` (Sleeper /players/nfl
trimmed to position + birth_date) and ``docs/idp-real-leagues.json`` scoring
samples. Season splits: fit on 2022->2023 and 2023->2024 transitions (2024 is
the tune season: ridge alpha and in-season k are chosen on it), 2025 is held
out and never touched by any fitted constant.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import urllib.request
from datetime import date

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules import idp_scoring, idp_values, sleeper  # noqa: E402

SEASONS = (2021, 2022, 2023, 2024, 2025)
COMPS = idp_values.COMPONENTS


def fetch(data_dir: str) -> None:
    os.makedirs(data_dir, exist_ok=True)
    for season in SEASONS:
        out = {}
        for w in range(1, 19):
            url = f"https://api.sleeper.app/v1/stats/nfl/regular/{season}/{w}"
            d = json.load(urllib.request.urlopen(url, timeout=30))
            out[w] = {p: s for p, s in d.items() if any(k.startswith("idp_") or k == "def_snp" for k in s)}
        json.dump(out, open(os.path.join(data_dir, f"def_raw_{season}.json"), "w"))
    pl = json.load(urllib.request.urlopen("https://api.sleeper.app/v1/players/nfl", timeout=90))
    keep = ("position", "fantasy_positions", "birth_date")
    json.dump({k: {x: v.get(x) for x in keep} for k, v in pl.items()}, open(os.path.join(data_dir, "players_slim.json"), "w"))


def load(data_dir):
    rows = {}
    for season in SEASONS:
        raw = json.load(open(os.path.join(data_dir, f"def_raw_{season}.json")))
        per = {}
        for wk, payload in raw.items():
            for pid, stats in payload.items():
                row = sleeper._extract_week_observation(int(wk), stats)
                if row is not None and idp_values.defensive_games([row]):
                    per.setdefault(pid, []).append(row)
        for pid in per:
            per[pid].sort(key=lambda r: r["week"])
        rows[season] = per
    players = json.load(open(os.path.join(data_dir, "players_slim.json")))
    return rows, players


def family_of(players, pid):
    p = players.get(pid) or {}
    return idp_scoring.idp_slot_family(p.get("position")) or idp_scoring.idp_slot_family((p.get("fantasy_positions") or [None])[0])


def age_at(players, pid, season):
    bd = (players.get(pid) or {}).get("birth_date")
    try:
        y, m, d = (int(x) for x in bd.split("-"))
        return (date(season, 9, 1) - date(y, m, d)).days / 365.25
    except Exception:
        return None


def transitions(rows, players, target):
    """(pid, family, prior_summary, age, target_summary) for every defender with a prior-season role."""

    out = []
    for pid, prior_rows in rows[target - 1].items():
        fam = family_of(players, pid)
        if fam is None:
            continue
        prior = idp_values.season_summary(prior_rows)
        if prior["games"] < 4:
            continue
        tgt = idp_values.season_summary(rows[target].get(pid))
        prior2 = idp_values.season_summary(rows.get(target - 2, {}).get(pid)) if (target - 2) in rows else None
        out.append((pid, fam, prior, age_at(players, pid, target), tgt, prior2))
    return out


def design(row, fam, params):
    pid, _f, prior, age, _t, _p2 = row
    d1, d2 = idp_values._age_feature(age, fam, params)
    snap = prior["snap_share"] if prior["snap_share"] is not None else params["mean_snap_share"][fam]
    return d1, d2, snap


def fit_rate_models(trans, alpha, params):
    """Weighted ridge per (family, component) on standardised features."""

    models = {}
    for fam in idp_values.FAMILIES:
        sub = [t for t in trans if t[1] == fam and t[4]["games"] >= 4]
        wts = np.array([min(t[4]["games"], 17) for t in sub], dtype=float)
        models[fam] = {}
        for comp in COMPS:
            def r2(t):
                p2 = t[5]
                ok = p2 and p2["games"] >= idp_values.MIN_PRIOR2_GAMES
                return (p2["rates"].get(comp, 0.0) if ok else t[2]["rates"].get(comp, 0.0))
            X = np.array([[t[2]["rates"].get(comp, 0.0), r2(t), design(t, fam, params)[2], design(t, fam, params)[0], design(t, fam, params)[1]] for t in sub])
            y = np.array([t[4]["rates"].get(comp, 0.0) for t in sub])
            mu, sd = X.mean(0), X.std(0) + 1e-9
            Z = (X - mu) / sd
            W = wts / wts.mean()
            A = np.hstack([np.ones((len(Z), 1)), Z])
            reg = alpha * np.eye(A.shape[1])
            reg[0, 0] = 0
            beta = np.linalg.solve(A.T @ (A * W[:, None]) + reg, A.T @ (W * y))
            b = beta[1:] / sd
            a = beta[0] - float(np.sum(beta[1:] * mu / sd))
            models[fam][comp] = {"a": a, "b": b[0], "b2": b[1], "snap": b[2], "age": b[3], "age2": b[4]}
    return models


def base_params(trans_train):
    params = {"age_center": {}, "mean_snap_share": {}, "position_mean_rates": {}, "k_in_season": {}}
    for fam in idp_values.FAMILIES:
        sub = [t for t in trans_train if t[1] == fam and t[4]["games"] >= 8]
        ages = [t[3] for t in sub if t[3] is not None]
        params["age_center"][fam] = round(float(np.median(ages)), 1) if ages else 26.0
        params["mean_snap_share"][fam] = round(float(np.mean([t[2]["snap_share"] for t in sub if t[2]["snap_share"] is not None])), 4)
        params["position_mean_rates"][fam] = {c: float(np.mean([t[4]["rates"].get(c, 0.0) for t in sub])) for c in COMPS}
    return params


def survival_table(trans_train):
    table, default = {}, {}
    for fam in idp_values.FAMILIES:
        sub = [t for t in trans_train if t[1] == fam and t[2]["games"] >= idp_values.MIN_ROLE_GAMES and t[3] is not None]
        default[fam] = round(float(np.mean([t[4]["games"] >= idp_values.MIN_ROLE_GAMES for t in sub])), 3)
        table[fam] = {}
        for a in range(22, 35):
            near = [t for t in sub if abs(t[3] - a) <= 1.5]
            if len(near) >= 15:
                table[fam][str(a)] = round(float(np.mean([t[4]["games"] >= idp_values.MIN_ROLE_GAMES for t in near])), 3)
    return table, default


def spearman(a, b):
    if len(a) < 5:
        return np.nan
    return float(pd.Series(a).rank().corr(pd.Series(b).rank()))


def league_styles(path):
    leagues = json.load(open(path))
    out = []
    for lg in leagues:
        w = idp_scoring.idp_scoring_weights(lg["scoring"])
        w = {k: v for k, v in w.items() if k not in idp_scoring.THRESHOLD_BONUSES}
        out.append((lg["style"], w))
    return out


def season_eval(trans, params, styles, pool_n=36, label=""):
    res = {}
    fams = {}
    for t in trans:
        if t[2]["games"] < 8 or t[4]["games"] < 8:
            continue
        pr = idp_values.project_prior_rates(t[1], t[2], t[3], prior2=t[5], params=params)
        if pr is None:
            continue
        fams.setdefault(t[1], []).append((t, pr))
    for style in ("all", "tackle-leaning", "sack/big-play-leaning"):
        mae_m, mae_b, bias_m, bias_b, sp_m, sp_b, n = [], [], [], [], [], [], 0
        for st, w in styles:
            if style != "all" and st != style:
                continue
            for fam, items in fams.items():
                pm = np.array([idp_values.rates_to_ppg(pr, w) for _, pr in items])
                pb = np.array([idp_values.rates_to_ppg(t[2]["rates"], w) for t, _ in items])
                act = np.array([idp_values.rates_to_ppg(t[4]["rates"], w) for t, _ in items])
                top = np.argsort(-pb)[:pool_n]
                mae_m.append(np.abs(pm - act).mean()); mae_b.append(np.abs(pb - act).mean())
                bias_m.append((pm - act).mean()); bias_b.append((pb - act).mean())
                sp_m.append(spearman(pm[top], act[top])); sp_b.append(spearman(pb[top], act[top]))
                n = len(items)
        res[style] = {"mae_model": np.mean(mae_m), "mae_base": np.mean(mae_b), "bias_model": np.mean(bias_m), "bias_base": np.mean(bias_b), "spearman_top_model": np.nanmean(sp_m), "spearman_top_base": np.nanmean(sp_b)}
    return res


def weekly_eval(rows, players, season, params, styles, weeks=range(4, 18), use_current=True):
    """Pooled weekly accuracy. Truth = that week's points; every input is from before the week."""

    recs = []
    for pid, cur_rows in rows[season].items():
        fam = family_of(players, pid)
        prior_rows = rows[season - 1].get(pid)
        if fam is None or not prior_rows:
            continue
        prior = idp_values.season_summary(prior_rows)
        if prior["games"] < 4:
            continue
        age = age_at(players, pid, season)
        p2rows = rows.get(season - 2, {}).get(pid)
        prior2 = idp_values.season_summary(p2rows) if p2rows else None
        prior_rates = idp_values.project_prior_rates(fam, prior, age, prior2=prior2, params=params)
        for row in cur_rows:
            wk = row["week"]
            if wk not in weeks:
                continue
            cur = idp_values.season_summary(cur_rows, before_week=wk)
            model = idp_values.update_with_current(fam, prior_rates, cur if use_current else None, params=params)
            tsd = cur["rates"] if cur["games"] else prior["rates"]
            recs.append((pid, fam, wk, model, prior["rates"], tsd, row, prior["snap_share"] or 0.0))
    out = {}
    for style in ("all", "tackle-leaning", "sack/big-play-leaning"):
        acc = {"m": [], "p": [], "s": []}
        mae = {"m": [], "p": [], "s": []}
        bias = {"m": [], "p": [], "s": []}
        sps = {"m": [], "p": [], "s": []}
        for st, w in styles:
            if style != "all" and st != style:
                continue
            pts = lambda rates: idp_values.rates_to_ppg(rates, w)
            df = pd.DataFrame(
                {
                    "fam": [r[1] for r in recs], "wk": [r[2] for r in recs], "snap": [r[7] for r in recs],
                    "m": [pts(r[3]) for r in recs], "p": [pts(r[4]) for r in recs], "s": [pts(r[5]) for r in recs],
                    "a": [idp_scoring.idp_weekly_points(r[6], w) for r in recs],
                }
            )
            for k in ("m", "p", "s"):
                mae[k].append((df[k] - df["a"]).abs().mean()); bias[k].append((df[k] - df["a"]).mean())
            pool = df[df["snap"] >= 0.5]
            for k in ("m", "p", "s"):
                vals = [spearman(g[k].values, g["a"].values) for _, g in pool.groupby(["fam", "wk"])]
                sps[k].append(np.nanmean(vals))
        out[style] = {k: (np.mean(mae[k]), np.mean(bias[k]), np.mean(sps[k])) for k in ("m", "p", "s")}
        out[style]["n"] = len(recs)
    return out


def tune_k(rows, players, season, params, styles):
    """Per-component pseudo-game k for the in-season update, minimising weekly squared error on 2024."""

    grid = (1, 2, 4, 8, 16, 32, 64, 128)
    ks = {}
    items = []
    for pid, cur_rows in rows[season].items():
        fam = family_of(players, pid)
        prior_rows = rows[season - 1].get(pid)
        if fam is None or not prior_rows:
            continue
        prior = idp_values.season_summary(prior_rows)
        if prior["games"] < 4:
            continue
        p2rows = rows.get(season - 2, {}).get(pid)
        pr = idp_values.project_prior_rates(fam, prior, age_at(players, pid, season), prior2=idp_values.season_summary(p2rows) if p2rows else None, params=params)
        if pr is None:
            continue
        for row in cur_rows:
            if 4 <= row["week"] <= 17:
                items.append((fam, pr, idp_values.season_summary(cur_rows, before_week=row["week"]), row))
    for comp in COMPS:
        best = None
        for k in grid:
            se = 0.0
            for fam, pr, cur, row in items:
                n = cur["games"]
                pred = (k * pr[comp] + cur["rates"].get(comp, 0.0) * n) / (k + n)
                se += (pred - float(row.get(comp) or 0.0)) ** 2
            if best is None or se < best[0]:
                best = (se, k)
        ks[comp] = best[1]
    return ks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--leagues", default=os.path.join(os.path.dirname(__file__), "..", "docs", "idp-real-leagues.json"))
    ap.add_argument("--fit-out", default=None)
    a = ap.parse_args()
    if a.fetch:
        fetch(a.data)
    rows, players = load(a.data)
    styles = league_styles(a.leagues)
    tr = {T: transitions(rows, players, T) for T in (2023, 2024, 2025)}

    # Tune season 2024: ridge alpha chosen by fitting on 2023 only and scoring 2024.
    p23 = base_params(tr[2023])
    best = None
    for alpha in (0.5, 2, 8, 32, 128):
        p = dict(p23)
        p["rate_models"] = fit_rate_models(tr[2023], alpha, p)
        r = season_eval(tr[2024], p, styles)["all"]
        print(f"alpha={alpha}: 2024 tune season MAE model {r['mae_model']:.3f} base {r['mae_base']:.3f}")
        if best is None or r["mae_model"] < best[0]:
            best = (r["mae_model"], alpha)
    alpha = best[1]
    p23["rate_models"] = fit_rate_models(tr[2023], alpha, p23)
    p23["k_in_season"] = tune_k(rows, players, 2024, p23, styles)

    print("\n== 2024 (tune) season-level, next-season PPG, established players ==")
    for k, v in season_eval(tr[2024], p23, styles).items():
        print(k, {x: round(float(y), 3) for x, y in v.items()})

    # Final: refit on 2023+2024 transitions, keep k tuned on 2024, test on 2025.
    train = tr[2023] + tr[2024]
    final = base_params(train)
    final["rate_models"] = fit_rate_models(train, alpha, final)
    final["k_in_season"] = p23["k_in_season"]
    final["survival"], final["survival_default"] = survival_table(train)
    final["meta"] = {"alpha": alpha, "fit_seasons": "2022->2023, 2023->2024 transitions", "heldout": "2025"}

    print("\n== 2025 (held out) season-level ==")
    for k, v in season_eval(tr[2025], final, styles).items():
        print(k, {x: round(float(y), 3) for x, y in v.items()})
    print("\n== 2025 (held out) weekly, weeks 4-17: (MAE, bias, Spearman among prior snap share>=0.5) ==")
    for k, v in weekly_eval(rows, players, 2025, final, styles).items():
        print(k, {x: (tuple(round(float(z), 3) for z in y) if isinstance(y, tuple) else y) for x, y in v.items()})
    print("(m = model, p = last-season PPG, s = season-to-date PPG)")
    print("\n== 2024 (tune, model fit on 2023 only) weekly ==")
    for k, v in weekly_eval(rows, players, 2024, p23, styles).items():
        print(k, {x: (tuple(round(float(z), 3) for z in y) if isinstance(y, tuple) else y) for x, y in v.items()})
    if a.fit_out:
        def clean(o):
            if isinstance(o, dict):
                return {k: clean(v) for k, v in o.items()}
            if isinstance(o, (np.floating, float)):
                return round(float(o), 6)
            return o
        json.dump(clean(final), open(a.fit_out, "w"), indent=1, sort_keys=True)


if __name__ == "__main__":
    main()

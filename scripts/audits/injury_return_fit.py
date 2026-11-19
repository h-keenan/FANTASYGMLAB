"""Fit and test the injury return curves (docs/audits/2026-11-injury-discount.md).

usage: injury_return_fit.py PANEL_PARQUET OUT_DIR [--write-table PATH]

Fits on seasons 2021-23 (the panel's 2020 rows only supply the trailing-PPG baseline), tests on 2024-25.
Hierarchy (empirical-Bayes shrinkage, pseudo-count SHRINK per level):
    state  ->  state x age bucket  ->  position x state x age bucket
    state  ->  position x state (age pooled)  ->  position x state x body group
Targets per cell: f4 (fraction of baseline PPG produced over the next 4 team games, zeros included), p4 (share of the next 4
games played), f1/p1 (next game), lost17 (games missed in the next 17).  Production when playing = f4 / p4.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from modules import injury_status as ist  # noqa: E402

SHRINK = 20.0
TRAIN = (2021, 2023)
TEST = (2024, 2025)
STATES = ("Out", "Doubtful", "Questionable", "IR")
AGE_BUCKETS = (1, 2, 3, 4, 6, 8)
TARGETS = ("f1", "p1", "f4", "p4", "lost17")
LEGACY_CATEGORY = {"Out": "moderate", "Doubtful": "moderate", "Questionable": "minor", "IR": "major"}
LEGACY_KEY = {"Out": "out", "Doubtful": "doubtful", "Questionable": "questionable", "IR": "ir"}


def bucket(age: int) -> int:
    return 1 if age <= 1 else 2 if age == 2 else 3 if age == 3 else 4 if age == 4 else 6 if age <= 6 else 8


def prep(panel: pd.DataFrame) -> pd.DataFrame:
    d = panel.copy()
    d["pos"] = d.pos.astype(str)
    d["state"] = d.state.astype(str)
    d["body"] = d.body.astype(str)
    d["ab"] = d.age_k.map(bucket)
    d["p1"] = d.played.astype(float)
    return d


def shrunk(df: pd.DataFrame, keys: list[str], prior: dict, parent_keys: list[str]) -> dict:
    """Per-cell (n, {target: estimate}) shrunk toward the parent cell's estimate."""
    out = {}
    for key, g in df.groupby(keys, observed=True):
        key = key if isinstance(key, tuple) else (key,)
        parent = prior[tuple(dict(zip(keys, key))[k] for k in parent_keys)][1]
        est = {}
        for t in TARGETS:
            v = g[t].dropna()
            n = len(v)
            est[t] = float((v.sum() + SHRINK * parent[t]) / (n + SHRINK))
        out[key] = (int(g["f4"].notna().sum()), est)
    return out


def fit(train: pd.DataFrame) -> dict:
    tab: dict = {"ALL": (len(train), {t: float(train[t].mean()) for t in TARGETS})}
    # level 0: state (shrunk to the grand mean)
    s0 = {}
    for s, g in train.groupby("state"):
        est = {t: float((g[t].dropna().sum() + SHRINK * tab["ALL"][1][t]) / (g[t].notna().sum() + SHRINK)) for t in TARGETS}
        s0[(s,)] = (int(g.f4.notna().sum()), est)
    sa = shrunk(train, ["state", "ab"], s0, ["state"])
    pos_sa = {}
    for (p, s, a), g in train.groupby(["pos", "state", "ab"], observed=True):
        parent = sa[(s, a)][1]
        pos_sa[(p, s, a)] = (int(g.f4.notna().sum()), {t: float((g[t].dropna().sum() + SHRINK * parent[t]) / (g[t].notna().sum() + SHRINK)) for t in TARGETS})
    pos_s = {}
    for (p, s), g in train.groupby(["pos", "state"], observed=True):
        parent = s0[(s,)][1]
        pos_s[(p, s)] = (int(g.f4.notna().sum()), {t: float((g[t].dropna().sum() + SHRINK * parent[t]) / (g[t].notna().sum() + SHRINK)) for t in TARGETS})
    pos_s_body = {}
    for (p, s, b), g in train.groupby(["pos", "state", "body"], observed=True):
        parent = pos_s[(p, s)][1]
        pos_s_body[(p, s, b)] = (int(g.f4.notna().sum()), {t: float((g[t].dropna().sum() + SHRINK * parent[t]) / (g[t].notna().sum() + SHRINK)) for t in TARGETS})
    return {"all": tab["ALL"], "state": s0, "state_age": sa, "pos_state_age": pos_sa, "pos_state": pos_s, "pos_state_body": pos_s_body}


def predict(model: dict, state: str, pos: str | None, age: int | None, target: str, body: str | None = None) -> float:
    """Fitted estimate for one player-state; falls back up the hierarchy when a cell is missing."""
    a = bucket(age) if age else None
    if a is not None:
        if pos and (pos, state, a) in model["pos_state_age"]:
            return model["pos_state_age"][(pos, state, a)][1][target]
        if (state, a) in model["state_age"]:
            return model["state_age"][(state, a)][1][target]
    if body and pos and (pos, state, body) in model["pos_state_body"]:
        return model["pos_state_body"][(pos, state, body)][1][target]
    if pos and (pos, state) in model["pos_state"]:
        return model["pos_state"][(pos, state)][1][target]
    return model["state"][(state,)][1][target]


def boot_ci(diff: np.ndarray, players: np.ndarray, n_boot: int = 2000, seed: int = 7) -> tuple[float, float, float]:
    """Mean of diff with a 95% CI from resampling players (rows within a player are not independent)."""
    ids, inv = np.unique(players, return_inverse=True)
    s = np.bincount(inv, weights=diff)
    c = np.bincount(inv).astype(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(ids), size=(n_boot, len(ids)))
    means = s[idx].sum(1) / c[idx].sum(1)
    return float(diff.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def compare(test: pd.DataFrame, model: dict, k: int) -> dict:
    tcol = "f4" if k == 4 else "f1"
    d = test[test[tcol].notna()].copy()
    pts = 4.0 if k == 4 else 1.0
    actual = d[tcol].to_numpy() * pts * d.baseline.to_numpy()
    base = d.baseline.to_numpy()
    preds = {
        "static_current_season_mult": np.array([ist.CURRENT_SEASON_MULTIPLIER[LEGACY_CATEGORY[s]] for s in d.state]),
        "static_weeks_out": np.array([max(0.0, k - (ist.RESERVE_MIN_GAMES_OUT if s == "IR" else float(ist.ROWS_BY_KEY[LEGACY_KEY[s]].weeks_out))) / k for s in d.state]),
        "fitted_age_known": np.array([predict(model, s, p, a, tcol) for s, p, a in zip(d.state, d.pos, d.age_k)]),
        "fitted_age_unknown": np.array([predict(model, s, p, None, tcol) for s, p in zip(d.state, d.pos)]),
        "fitted_state_only": np.array([model["state"][(s,)][1][tcol] for s in d.state]),
    }
    preds = {n: v for n, v in preds.items() if v is not None}
    errs = {n: np.abs(v * pts * base - actual) for n, v in preds.items()}
    out = {"n": int(len(d)), "players": int(d.player_id.nunique()), "mean_actual_fraction": float(d[tcol].mean()), "rows": {}}
    ref = "static_current_season_mult"
    for n, v in preds.items():
        e = v * pts * base - actual
        row = {"mean_pred_fraction": float(v.mean()), "bias_pts": float(e.mean()), "mae_pts": float(np.abs(e).mean()), "rmse_pts": float(np.sqrt((e ** 2).mean()))}
        if n != ref:
            m, lo, hi = boot_ci(errs[ref] - errs[n], d.player_id.to_numpy())
            row["mae_improvement_vs_static_pts"] = m
            row["ci95"] = [lo, hi]
        out["rows"][n] = row
    out["by_state"] = {}
    for s in STATES:
        mk = (d.state == s).to_numpy()
        if mk.sum() == 0:
            continue
        out["by_state"][s] = {"n": int(mk.sum()), "actual": float(d[tcol][mk].mean())} | {n: float(v[mk].mean()) for n, v in preds.items()}
    # calibration of the fitted (age unknown) prediction: deciles
    p = preds["fitted_age_unknown"]
    q = pd.qcut(pd.Series(p), 5, duplicates="drop")
    cal = pd.DataFrame({"pred": p, "act": d[tcol].to_numpy(), "q": q.to_numpy()}).groupby("q", observed=True).agg(n=("pred", "size"), pred=("pred", "mean"), actual=("act", "mean"))
    out["calibration_fitted_age_unknown"] = [{"n": int(r.n), "pred": float(r.pred), "actual": float(r.actual)} for r in cal.itertuples()]
    return out


def lost_games(test: pd.DataFrame, model: dict) -> dict:
    d = test[test.lost17.notna()]
    # Everything is EXCESS games lost: a healthy same-position player also misses games (no stat line), so subtract that baseline.
    healthy = np.array([model["healthy_lost17"].get(p, model["healthy_lost17"]["ALL"]) for p in d.pos])
    actual = d.lost17.to_numpy() - healthy
    table = np.array([4.0 if s == "IR" else float(ist.ROWS_BY_KEY[LEGACY_KEY[s]].weeks_out) for s in d.state])
    fitted = np.maximum(0.0, np.array([predict(model, s, p, a, "lost17") for s, p, a in zip(d.state, d.pos, d.age_k)]) - healthy)
    unk = np.maximum(0.0, np.array([predict(model, s, p, None, "lost17") for s, p in zip(d.state, d.pos)]) - healthy)
    out = {"n": int(len(d)), "mean_actual": float(actual.mean()), "fitted_age_known_mean": float(fitted.mean()), "fitted_age_unknown_mean": float(unk.mean())}
    e_f, e_u = np.abs(fitted - actual), np.abs(unk - actual)
    out["mae_fitted_age_known"], out["mae_fitted_age_unknown"] = float(e_f.mean()), float(e_u.mean())
    out["rmse_fitted_age_unknown"], out["bias_fitted_age_unknown"] = float(np.sqrt(((unk - actual) ** 2).mean())), float((unk - actual).mean())
    if table is not None:
        e_t = np.abs(table - actual)
        out["static_table_mean"], out["mae_static_table"] = float(table.mean()), float(e_t.mean())
        out["rmse_static_table"], out["bias_static_table"] = float(np.sqrt(((table - actual) ** 2).mean())), float((table - actual).mean())
        m, lo, hi = boot_ci(e_t - e_u, d.player_id.to_numpy())
        out["mae_improvement_unknown_vs_table"], out["ci95_unknown_vs_table"] = m, [lo, hi]
        m, lo, hi = boot_ci(e_t - e_f, d.player_id.to_numpy())
        out["mae_improvement_known_vs_table"], out["ci95_known_vs_table"] = m, [lo, hi]
    return out


def table_py(model: dict) -> str:
    """Compact module text: only the cells a runtime lookup needs (position x state x age, state x age, position x state, state)."""
    def r(est):
        return {t: round(v, 4) for t, v in est.items()}
    lines = ['"""Fitted injury return curves (generated by scripts/audits/injury_return_fit.py, fit on nflverse 2021-23).', "",
             "Each entry is (n, {target: shrunk estimate}); targets are documented in the fit script and",
             'docs/audits/2026-11-injury-discount.md. Do not edit by hand."""', "", "from __future__ import annotations", "",
             f"SHRINK = {SHRINK}", f"FIT_SEASONS = {TRAIN}", ""]
    for name in ("state", "state_age", "pos_state", "pos_state_age", "pos_state_body"):
        lines.append(f"{name.upper()} = {{")
        for key in sorted(model[name]):
            n, est = model[name][key]
            lines.append(f"    {tuple(int(x) if isinstance(x, (np.integer,)) else x for x in key)!r}: ({n}, {r(est)!r}),")
        lines.append("}")
        lines.append("")
    lines.append(f"HEALTHY_LOST17 = {({k: round(v, 3) for k, v in model['healthy_lost17'].items()})!r}")
    lines.append(f"ALL = ({model['all'][0]}, {r(model['all'][1])!r})")
    return "\n".join(lines) + "\n"


def main() -> None:
    panel = prep(pd.read_parquet(sys.argv[1]))
    healthy = panel[(panel.state == "none") & panel.played & panel.season.between(*TRAIN)]
    panel = panel[panel.state != "none"]
    out_dir = Path(sys.argv[2])
    train = panel[panel.season.between(*TRAIN)]
    test = panel[panel.season.between(*TEST)]
    model = fit(train)
    model["healthy_lost17"] = {p: float(g.lost17.mean()) for p, g in healthy.groupby("pos")} | {"ALL": float(healthy.lost17.mean())}
    model["healthy_lost17_n"] = int(healthy.lost17.notna().sum())
    results = {"n_train": int(len(train)), "n_test": int(len(test)), "next4": compare(test, model, 4), "next1": compare(test, model, 1), "lost17": lost_games(test, model)}
    cells = {}
    for key, (n, est) in sorted(model["pos_state_age"].items()):
        cells["|".join(map(str, key))] = {"n": n, **{t: round(v, 3) for t, v in est.items()}}
    results["healthy_lost17"] = model["healthy_lost17"]
    results["healthy_lost17_n"] = model["healthy_lost17_n"]
    results["cells_pos_state_age"] = cells
    results["cells_state_age"] = {"|".join(map(str, k)): {"n": n, **{t: round(v, 3) for t, v in e.items()}} for k, (n, e) in sorted(model["state_age"].items())}
    results["cells_pos_state"] = {"|".join(map(str, k)): {"n": n, **{t: round(v, 3) for t, v in e.items()}} for k, (n, e) in sorted(model["pos_state"].items())}
    results["cells_pos_state_body"] = {"|".join(map(str, k)): {"n": n, **{t: round(v, 3) for t, v in e.items()}} for k, (n, e) in sorted(model["pos_state_body"].items()) if n >= 15}
    # does adding the body group help out of sample (age unknown, next 4)?
    d = test[test.f4.notna()]
    base_p = np.array([predict(model, s, p, None, "f4") for s, p in zip(d.state, d.pos)])
    body_p = np.array([predict(model, s, p, None, "f4", b) for s, p, b in zip(d.state, d.pos, d.body)])
    e0, e1 = np.abs(base_p - d.f4.to_numpy()) * 4 * d.baseline.to_numpy(), np.abs(body_p - d.f4.to_numpy()) * 4 * d.baseline.to_numpy()
    m, lo, hi = boot_ci(e0 - e1, d.player_id.to_numpy())
    results["body_group_gain_pts"] = {"mean": m, "ci95": [lo, hi]}
    (out_dir / "results.json").write_text(json.dumps(results, indent=1, default=float))
    if "--write-table" in sys.argv:
        Path(sys.argv[sys.argv.index("--write-table") + 1]).write_text(table_py(model))
    print(json.dumps({k: results[k] for k in ("n_train", "n_test", "next4", "next1", "lost17", "body_group_gain_pts")}, indent=1, default=float))


if __name__ == "__main__":
    main()

"""Grades: calibration + slices on the base run, and train(2021-23)/test(2024-25) tuning comparisons across variants."""
from __future__ import annotations

import os

import sys
from pathlib import Path

import numpy as np
import pandas as pd

R = os.environ.get("REPLAY_REPO", ".")
sys.path.insert(0, R + "/scripts")
import trade_advice_report as T  # noqa: E402

G = Path(os.environ["REPLAY_OUT"] + "/grades")
OUT = Path(os.environ["REPLAY_OUT"] + "/results")
OUT.mkdir(exist_ok=True)
KEY = ["season", "mmdd", "league", "team", "partner", "strategy", "send_ids", "recv_ids", "send_pick", "recv_pick"]
BANDS = ["HARD DECLINE", "DECLINE", "COUNTER", "FAIR / PREFERENCE", "ACCEPT", "SMASH ACCEPT"]
TRAIN, TEST = (2021, 2022, 2023), (2024, 2025)


def load(tag: str) -> pd.DataFrame:
    d = T.prep(pd.read_parquet(G / f"scored_{tag}.parquet"))
    d["k"] = d[KEY].astype(str).agg("|".join, axis=1)
    d["recv_qb"] = d.recv_pos.str.contains("QB")
    d["send_qb"] = d.send_pos.str.contains("QB")
    d["qb_any"] = d.recv_qb | d.send_qb
    d["rb_any"] = d.recv_pos.str.contains("RB") | d.send_pos.str.contains("RB")
    d["early1"] = ((d.send_pick.between(1, 4)) | (d.recv_pick.between(1, 4)))
    d["age_gap"] = d.recv_age.fillna(d.send_age) - d.send_age.fillna(d.recv_age)
    d["age_side"] = np.where(d.age_gap >= 2, "receives older (2y+)", np.where(d.age_gap <= -2, "receives younger (2y+)", "similar age"))
    d["pos_group"] = np.select([d.recv_qb, d.recv_pos.str.contains("TE"), d.recv_pos.str.contains("RB"), d.recv_pos.str.contains("WR")],
                               ["receives QB", "receives TE", "receives RB", "receives WR"], "picks / none")
    d["fmt"] = d.league.map({"dynasty_1qb": "1QB", "dynasty_sf": "Superflex", "dynasty_sf_tep": "SF + TE premium", "redraft_1qb": "redraft 1QB"})
    d["period"] = np.where(d.season.isin(TRAIN), "train", "test")
    return d


def accept(d):
    return d.band.isin(["ACCEPT", "SMASH ACCEPT"])


def decline(d):
    return d.band.isin(["DECLINE", "HARD DECLINE"])


def row(d, outcome="Hs"):
    y = d[outcome]
    m = y.notna()
    out = dict(n=int(m.sum()))
    out["auc_eng"] = T.auc(d.loc[m, "eng_n"], y[m])
    out["auc_mkt"] = T.auc(d.loc[m, "mkt_n"], y[m])
    wa = T.win_stats(d.loc[accept(d) & m, outcome])
    wd = T.win_stats(d.loc[decline(d) & m, outcome])
    out["accept_win"] = 100 * wa[2]
    out["decline_win"] = 100 * wd[2]
    out["spread"] = out["accept_win"] - out["decline_win"]
    out["accept_pts"] = d.loc[accept(d) & m, outcome].mean()
    out["decline_pts"] = d.loc[decline(d) & m, outcome].mean()
    return out


def slice_table(d, groups: dict[str, pd.Series], outcome="Hs"):
    rows = []
    for name, mask in groups.items():
        r = row(d[mask], outcome)
        r["group"] = name
        rows.append(r)
    return pd.DataFrame(rows)[["group", "n", "auc_eng", "auc_mkt", "accept_win", "decline_win", "spread", "accept_pts", "decline_pts"]]


def calibration(d, outcome="Hs"):
    rows = []
    for b in BANDS:
        g = d[d.band == b]
        n, nd, w, se, mean = T.win_stats(g[outcome])
        rows.append(dict(band=b, n=n, decided=nd, win_pct=100 * w, ci95=196 * se, mean_pts=mean))
    return pd.DataFrame(rows)


def paired_auc_delta(base, var, outcome, mask_fn=None, n_boot=300, seed=1):
    m = base.merge(var[["k", "eng_n"]], on="k", suffixes=("", "_v"))
    if mask_fn is not None:
        m = m[mask_fn(m)]
    m = m[m[outcome].notna()]
    if len(m) < 50:
        return np.nan, np.nan, np.nan, len(m)
    x0, x1, y = m.eng_n.to_numpy(), m.eng_n_v.to_numpy(), m[outcome].to_numpy()
    d0 = T.auc(x1, y) - T.auc(x0, y)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        vals.append(T.auc(x1[i], y[i]) - T.auc(x0[i], y[i]))
    return d0, float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5)), len(m)


def spread_delta(base, var, outcome, mask_fn=None):
    m = base.merge(var[["k", "band"]], on="k", suffixes=("", "_v"))
    if mask_fn is not None:
        m = m[mask_fn(m)]
    m = m[m[outcome].notna()]
    def sp(col):
        a = T.win_stats(m.loc[m[col].isin(["ACCEPT", "SMASH ACCEPT"]), outcome])[2]
        b = T.win_stats(m.loc[m[col].isin(["DECLINE", "HARD DECLINE"]), outcome])[2]
        return 100 * (a - b)
    return sp("band_v") - sp("band")


FAMILIES = {
    "P1-5 rebuild/tank starter floor": dict(
        variants=["floor:0.1", "floor:0.2", "floor:0.3"], domain=lambda d: d.strategy.isin(["rebuild", "tank"])),
    "P1-3 redundancy scope": dict(
        variants=["redund:all:0.5", "redund:all:0.75", "redund:qb:0.5", "redund:recv:0.5"], domain=lambda d: d.qb_any),
    "Pick curve, early-1st top end": dict(
        variants=["pick1e:4800"], domain=lambda d: d.early1),
    "Pick curve, all rounds scale": dict(
        variants=["pickall:0.85"], domain=lambda d: (d.send_pick > 0) | (d.recv_pick > 0)),
    "Age curve, 27+ (all positions)": dict(
        variants=["age:old:0.85", "age:old:1.15"], domain=lambda d: d.age_side != "similar age"),
    "Age curve, RB 25+": dict(
        variants=["age:rb:0.8"], domain=lambda d: d.rb_any),
}


def tune_table(base):
    rows = []
    for fam, spec in FAMILIES.items():
        dom = spec["domain"]
        for v in spec["variants"]:
            f = G / f"scored_{v.replace(':', '_')}.parquet"
            if not f.exists():
                continue
            var = load(v.replace(":", "_"))
            rec = dict(family=fam, variant=v)
            # train: 2021-23, outcome Hs (rest of season + next season), domain trades
            a = paired_auc_delta(base, var, "Hs", lambda m: dom(m) & m.season.isin(TRAIN))
            rec.update(train_n=a[3], train_dauc=a[0], train_lo=a[1], train_hi=a[2])
            a = paired_auc_delta(base, var, "Hs", lambda m: dom(m) & (m.season == 2024))
            rec.update(t24_n=a[3], t24_dauc=a[0], t24_lo=a[1], t24_hi=a[2])
            a = paired_auc_delta(base, var, "spor_ros", lambda m: dom(m) & m.season.isin(TEST))
            rec.update(test_ros_n=a[3], test_ros_dauc=a[0], test_ros_lo=a[1], test_ros_hi=a[2])
            a = paired_auc_delta(base, var, "spor_ros", lambda m: dom(m) & m.season.isin(TRAIN))
            rec.update(train_ros_dauc=a[0])
            a = paired_auc_delta(base, var, "spor_ros", lambda m: m.season.isin(TEST))
            rec.update(test_all_ros_dauc=a[0])
            rec["train_spread_d"] = spread_delta(base, var, "Hs", lambda m: dom(m) & m.season.isin(TRAIN))
            rec["test_spread_d"] = spread_delta(base, var, "spor_ros", lambda m: dom(m) & m.season.isin(TEST))
            tr = var[dom(var)]
            b = base[base.k.isin(tr.k)]
            rec["verdicts_changed_pct"] = 100 * (b.merge(tr[["k", "band"]], on="k", suffixes=("", "_v")).pipe(lambda m: (m.band != m.band_v).mean()))
            rows.append(rec)
    return pd.DataFrame(rows)


def main():
    base = load("base")
    base.to_parquet(OUT / "grades_base_prepped.parquet")
    res = {}
    res["n_trades"] = len(base)
    res["calibration_all"] = calibration(base)
    res["calibration_train"] = calibration(base[base.period == "train"])
    res["calibration_test"] = calibration(base[base.period == "test"])
    res["calibration_ros_all"] = calibration(base, "spor_ros")
    res["by_season"] = pd.DataFrame([dict(season=s, **row(base[base.season == s], "Hs" if s < 2025 else "spor_ros")) for s in sorted(base.season.unique())])
    res["by_date"] = pd.DataFrame([dict(date=s, **row(base[base.mmdd == s], "Hs")) for s in sorted(base.mmdd.unique())])
    slices = {}
    slices["posture"] = slice_table(base, {p: base.strategy == p for p in ["contender", "fringe_contender", "retool", "rebuild", "tank"]})
    slices["position"] = slice_table(base, {p: base.pos_group == p for p in ["receives QB", "receives RB", "receives WR", "receives TE", "picks / none"]})
    slices["age"] = slice_table(base, {p: base.age_side == p for p in ["receives older (2y+)", "similar age", "receives younger (2y+)"]})
    slices["picks_vs_players"] = slice_table(base, {"picks involved": (base.send_pick > 0) | (base.recv_pick > 0), "players only": (base.send_pick == 0) & (base.recv_pick == 0),
                                                    "early 1st involved": base.early1})
    slices["format"] = slice_table(base, {p: base.fmt == p for p in ["1QB", "Superflex", "SF + TE premium", "redraft 1QB"]})
    for k, v in slices.items():
        res[f"slice_{k}"] = v
    # train vs test per slice (spread stability)
    stab = []
    for nm, tbl in (("posture", base.strategy), ("format", base.fmt), ("age", base.age_side), ("position", base.pos_group)):
        for g in tbl.unique():
            for per in ("train", "test"):
                sub = base[(tbl == g) & (base.period == per)]
                r_ = row(sub, "Hs" if per == "train" else "spor_ros")
                stab.append(dict(slice=nm, group=g, period=per, **r_))
    res["slice_stability"] = pd.DataFrame(stab)
    res["tuning"] = tune_table(base)
    for k, v in res.items():
        if isinstance(v, pd.DataFrame):
            v.to_csv(OUT / f"grades_{k}.csv", index=False)
    return res


if __name__ == "__main__":
    r = main()
    pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_rows", 200)
    for k, v in r.items():
        print("==", k)
        print(v.round(3).to_string() if isinstance(v, pd.DataFrame) else v)

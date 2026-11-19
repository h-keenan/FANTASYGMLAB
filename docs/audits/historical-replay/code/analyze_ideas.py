"""Trade IDEAS: outcome tables, slices, GM Plan lean / hold / buy-sell tags, and cap / handshake tuning variants."""
from __future__ import annotations

import os

import sys
from pathlib import Path

import numpy as np
import pandas as pd

R = os.environ.get("REPLAY_REPO", ".")
sys.path.insert(0, R + "/scripts")
import trade_advice_report as T  # noqa: E402

BASE = Path(os.environ["REPLAY_OUT"])
ID = BASE / "ideas"
OUT = BASE / "results"
OUT.mkdir(exist_ok=True)
TRAIN, TEST = (2021, 2022, 2023), (2024, 2025)
TIE = 3.0


def read(prefix: str, variant: str) -> pd.DataFrame:
    tag = variant.replace(":", "_")
    fs = sorted(ID.glob(f"{prefix}_{tag}_*.parquet"))
    if not fs:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)


def prep_ideas(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["u_h"] = d.u_ros + d.u_y1
    d["p_h"] = d.p_ros + d.p_y1
    d["picks"] = (d.send_pick_n + d.recv_pick_n) > 0
    d["phase"] = d.mmdd.map({"08-20": "preseason (Aug 20)", "10-20": "mid-season (Oct 20)", "12-01": "deadline (Dec 1)"})
    d["fmt"] = d.league.map({"dynasty_1qb": "1QB", "dynasty_sf": "Superflex", "dynasty_sf_tep": "SF + TE premium"})
    d["period"] = np.where(d.season.isin(TRAIN), "train 2021-23", "test 2024-25")
    d["age_gap"] = d.recv_age.fillna(d.send_age) - d.send_age.fillna(d.recv_age)
    d["age_side"] = np.where(d.age_gap >= 2, "gets older (2y+)", np.where(d.age_gap <= -2, "gets younger (2y+)", "similar age"))
    rp = d.recv_pos.fillna("")
    d["pos_group"] = np.select([rp.str.contains("QB"), rp.str.contains("TE"), rp.str.contains("RB"), rp.str.contains("WR")],
                               ["gets QB", "gets TE", "gets RB", "gets WR"], "picks only")
    d["shape"] = np.select([d.picks & (d.n_send + d.n_recv > 2), d.picks, (d.n_send == 1) & (d.n_recv == 1)], ["players + picks", "players + picks", "1-for-1"], "multi-player")
    d["shape"] = np.where(d.picks, "involves picks", np.where((d.n_send == 1) & (d.n_recv == 1), "1-for-1 players", "multi-player, no picks"))
    d["size"] = d.n_teams.astype(int).astype(str) + " teams"
    d["win_h"] = np.where(d.u_h.abs() >= TIE, (d.u_h > 0).astype(float), np.nan)
    d["win_ros"] = np.where(d.u_ros.abs() >= TIE, (d.u_ros > 0).astype(float), np.nan)
    d["winwin"] = ((d.u_h > 0) & (d.p_h > 0)).astype(float)
    d["partner_pays"] = (d.p_h < 0).astype(float)
    return d


def summ(d: pd.DataFrame) -> dict:
    ok = d.u_h.notna()
    return dict(
        n=len(d), n_h=int(ok.sum()),
        ros_pts=d.u_ros.mean(), h_pts=d.u_h[ok].mean(), y2_pts=d.u_y2.mean(),
        win_pct=100 * d.win_h.mean(), win_ros_pct=100 * d.win_ros.mean(),
        winwin_pct=100 * d.winwin[ok].mean(), partner_pts=d.p_h[ok].mean(),
        dpo_pp=100 * d.u_dpo.mean(), dti_pp=100 * d.u_dti.mean(),
        valchg1=d.u_valchg1.mean(), valchg2=d.u_valchg2.mean(), trade_gain=d.trade_gain.mean(),
    )


def slice_tbl(d, col):
    rows = []
    for g, sub in d.groupby(col):
        r = summ(sub)
        r["group"] = g
        rows.append(r)
    t = pd.DataFrame(rows)
    return t[["group"] + [c for c in t.columns if c != "group"]]


def ci_mean(x, n_boot=400, seed=1):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) < 5:
        return np.nan
    rng = np.random.default_rng(seed)
    b = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(n_boot)]
    return float(np.percentile(b, 97.5) - np.percentile(b, 2.5)) / 2


def main():
    ideas = prep_ideas(read("ideas", "base"))
    teams = read("teams", "base")
    teams["period"] = np.where(teams.season.isin(TRAIN), "train", "test")
    res = {}
    res["overall"] = pd.DataFrame([dict(group="all ideas", **summ(ideas))] +
                                  [dict(group=p, **summ(g)) for p, g in ideas.groupby("period")])
    res["ci"] = pd.DataFrame([dict(metric="h_pts +-95%", v=ci_mean(ideas.u_h)), dict(metric="ros_pts +-95%", v=ci_mean(ideas.u_ros)),
                              dict(metric="dpo_pp +-95%", v=100 * ci_mean(ideas.u_dpo)), dict(metric="n_ideas", v=len(ideas)),
                              dict(metric="teams", v=len(teams)), dict(metric="mean ideas per team", v=teams.n_ideas.mean()),
                              dict(metric="teams with zero ideas pct", v=100 * (teams.n_ideas == 0).mean())])
    for col in ("posture", "pos_group", "age_side", "shape", "fmt", "size", "phase", "season", "analyzer_label", "trade_confidence_label",
                "fit_grade", "impact_tag", "idea_rank", "tag", "posture_alignment", "market_realism_label"):
        if col in ideas:
            res[f"by_{col}"] = slice_tbl(ideas, col)
    # train/test stability for the main slices
    stab = []
    for col in ("posture", "pos_group", "age_side", "shape", "fmt", "size", "phase"):
        for (g, per), sub in ideas.groupby([col, "period"]):
            stab.append(dict(slice=col, group=g, period=per, **summ(sub)))
    res["stability"] = pd.DataFrame(stab)
    # engine's own verdict / confidence vs realized: AUC
    a = []
    for name, col in (("trade_gain (engine value gain)", "trade_gain"), ("analyzer_trade_score", "analyzer_trade_score"), ("fit_score", "fit_score"),
                      ("market_realism_score", "market_realism_score"), ("trade_confidence_score", "trade_confidence_score"),
                      ("priority", "priority"), ("mkt_delta_start", "mkt_delta_start")):
        if col in ideas:
            for per, sub in (("all", ideas), ("train", ideas[ideas.period.str.startswith("train")]), ("test", ideas[ideas.period.str.startswith("test")])):
                m = sub.u_h.notna()
                a.append(dict(predictor=name, period=per, n=int(m.sum()), auc_h=T.auc(sub.loc[m, col], sub.loc[m, "u_h"]),
                              auc_ros=T.auc(sub[col], sub.u_ros), rho=sub.loc[m, [col, "u_h"]].corr(method="spearman").iloc[0, 1]))
    res["predictors"] = pd.DataFrame(a)
    # ---- GM Plan: season lean, hold, buy/sell tags
    t = teams.copy()
    t["made_po"] = (t.po_before >= 0.5).astype(float)
    t["phase"] = t.mmdd.map({"08-20": "preseason (Aug 20)", "10-20": "mid-season (Oct 20)", "12-01": "deadline (Dec 1)"})
    lean_rows = []
    for (ph, ln), g in t.groupby(["phase", "lean"]):
        lean_rows.append(dict(phase=ph, lean=ln, teams=len(g), pit_odds_pct=100 * g.po_pit.mean(), realized_odds_pct=100 * g.po_before.mean(),
                              made_playoffs_pct=100 * g.made_po.mean(), title_pit_pct=100 * g.title_pit.mean(), title_realized_pct=100 * g.title_before.mean()))
    res["lean_accuracy"] = pd.DataFrame(lean_rows)
    lean_rows = []
    for (per, ln), g in t.groupby(["period", "lean"]):
        lean_rows.append(dict(period=per, lean=ln, teams=len(g), pit_odds_pct=100 * g.po_pit.mean(), realized_odds_pct=100 * g.po_before.mean(),
                              made_playoffs_pct=100 * g.made_po.mean()))
    res["lean_accuracy_period"] = pd.DataFrame(lean_rows)
    m = ideas.merge(teams[["season", "mmdd", "league", "n_teams", "team", "lean", "hold", "hold_reason", "po_pit"]], on=["season", "mmdd", "league", "n_teams", "team"], how="left")
    m["follow"] = np.where(m.u_lean == "buyer", "buyer", np.where(m.u_lean == "seller", "seller", "hold"))
    lf = []
    for (ln, ph), g in m.groupby(["follow", "phase"]):
        lf.append(dict(lean=ln, phase=ph, **summ(g)))
    res["lean_follow"] = pd.DataFrame(lf)
    lf = []
    top = m[m.idea_rank == 0]
    for ln, g in top.groupby("follow"):
        lf.append(dict(lean=ln, group="top idea", **summ(g)))
    for ln, g in m.groupby("follow"):
        lf.append(dict(lean=ln, group="all ideas", **summ(g)))
    res["lean_follow_top"] = pd.DataFrame(lf)
    # does the lean-aligned half of ideas do better? buyers: ideas with higher lineup gain; sellers: ideas that raise value
    res["posture_alignment"] = slice_tbl(m[m.posture_alignment.notna()], "posture_alignment") if "posture_alignment" in m else pd.DataFrame()
    # hold: what the hold verdict withheld
    h = []
    tm = m.merge(teams[["season", "mmdd", "league", "n_teams", "team"]], on=["season", "mmdd", "league", "n_teams", "team"])
    for hv, g in tm.groupby("hold"):
        s = summ(g)
        s["share_ideas_positive_pct"] = 100 * (g.u_h > 0).mean()
        s["best_idea_h"] = g.groupby(["season", "mmdd", "league", "n_teams", "team"]).u_h.max().mean()
        s["teams"] = g.groupby(["season", "mmdd", "league", "n_teams", "team"]).ngroups
        h.append(dict(hold_verdict=hv, **s))
    res["hold_effect"] = pd.DataFrame(h)
    h = []
    for (hr, per), g in tm[tm.hold].groupby(["hold_reason", "period"]):
        s = summ(g)
        h.append(dict(reason=hr, period=per, **s))
    res["hold_by_reason"] = pd.DataFrame(h)
    for k, v in res.items():
        if isinstance(v, pd.DataFrame):
            v.to_csv(OUT / f"ideas_{k}.csv", index=False)
    return res


def tune(variants: list[str]):
    base = prep_ideas(read("ideas", "base"))
    base = base[(base.n_teams == 12) & base.league.isin(["dynasty_sf"])]
    bteams = read("teams", "base")
    bteams = bteams[(bteams.n_teams == 12) & bteams.league.isin(["dynasty_sf"])]
    out = []
    unit = ["season", "mmdd", "league", "team"]

    def agg(d, teams_df, label):
        r = summ(d)
        r["ideas_per_team"] = len(d) / max(1, len(teams_df))
        return r

    def boot_diff(a, b, col, n_boot=300, seed=2):
        """difference of per-league-date mean `col` (variant minus base), bootstrap over league-dates."""
        ga = a.groupby(unit)[col].mean()
        gb = b.groupby(unit)[col].mean()
        j = pd.concat([ga, gb], axis=1, keys=["a", "b"]).dropna()
        if len(j) < 20:
            return np.nan, np.nan, np.nan
        dlt = (j.a - j.b).to_numpy()
        rng = np.random.default_rng(seed)
        bs = [dlt[rng.integers(0, len(dlt), len(dlt))].mean() for _ in range(n_boot)]
        return float(dlt.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))

    for v in variants:
        vd = read("ideas", v)
        vt = read("teams", v)
        if vd.empty:
            continue
        vd = prep_ideas(vd[vd.league == "dynasty_sf"])
        vt = vt[vt.league == "dynasty_sf"]
        for per, seasons in (("train", TRAIN), ("test", TEST)):
            a = vd[vd.season.isin(seasons)]
            b = base[base.season.isin(seasons)]
            ta = vt[vt.season.isin(seasons)]
            tb = bteams[bteams.season.isin(seasons)]
            ra, rb = agg(a, ta, v), agg(b, tb, "base")
            rec = dict(variant=v, period=per, n_ideas=ra["n"], ideas_per_team=ra["ideas_per_team"], base_ideas_per_team=rb["ideas_per_team"])
            for col, key in (("u_h", "h_pts"), ("u_ros", "ros_pts"), ("winwin", "winwin"), ("u_dpo", "dpo"), ("u_valchg1", "valchg1")):
                d, lo, hi = boot_diff(a, b, col)
                rec[f"d_{key}"] = d
                rec[f"d_{key}_lo"] = lo
                rec[f"d_{key}_hi"] = hi
            rec["h_pts"], rec["base_h_pts"] = ra["h_pts"], rb["h_pts"]
            rec["winwin_pct"], rec["base_winwin_pct"] = ra["winwin_pct"], rb["winwin_pct"]
            rec["partner_pts"], rec["base_partner_pts"] = ra["partner_pts"], rb["partner_pts"]
            rec["mean_trade_gain"], rec["base_trade_gain"] = ra["trade_gain"], rb["trade_gain"]
            out.append(rec)
    t = pd.DataFrame(out)
    t.to_csv(OUT / "ideas_tuning.csv", index=False)
    return t


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "tune":
        pd.set_option("display.width", 300, "display.max_columns", 60)
        print(tune(sys.argv[2:]).round(3).to_string())
        sys.exit(0)
    pd.set_option("display.width", 260, "display.max_columns", 50, "display.max_rows", 300)
    r = main()
    for k, v in r.items():
        print("==", k)
        print(v.round(2).to_string() if isinstance(v, pd.DataFrame) else v)

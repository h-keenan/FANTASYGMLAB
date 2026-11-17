"""Tables and charts for ``docs/audits/2026-11-projections-backtest.md`` from ``projections_audit_backtest.py``.

    python scripts/projections_audit_analyze.py --after /tmp/pa2 --before /tmp/pa --out /tmp/pa2 --charts docs/audits/projections-backtest

``--after`` / ``--before`` are directories holding ``rows.parquet`` (``build``), ``ros.parquet`` (``ros``) and, for ``--after``,
``sleeper_cmp.parquet`` (``sleeper``). Writes ``tables.md`` (one fragment per section) to ``--out`` and PNG charts to ``--charts``.

Pools (point-in-time, weeks >= 2, players the model itself projects as a certain zero removed):

* ``played``  the player-week has a stat line (conditional on playing; what the v3 walk-forward scored).
* ``pool``    the position's top-N by OUR estimate that week (QB 24, RB 48, WR 60, TE 24, K 16), selected before the game,
              whether or not they played; non-appearances score 0.
* ``rel``     any player-week with an estimate >= 4 points (used for niche scenarios, where the top-N cut would hide the case).
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

N = {"QB": 24, "RB": 48, "WR": 60, "TE": 24, "K": 16}
OFFENSE = ("QB", "RB", "WR", "TE")


def prep(rows: pd.DataFrame, before: pd.DataFrame | None = None) -> pd.DataFrame:
    d = rows[(rows.status == "ok") & (rows.week >= 2)].copy()
    d = d[d.avail_mult != 0.0]
    d["rank"] = d.groupby(["season", "week", "pos"]).est.rank(ascending=False, method="first")
    d["pool"] = d["rank"] <= d.pos.map(N)
    d["err"] = d.est - d.actual
    d["covered"] = (d.actual >= d.low - 1e-9) & (d.actual <= d.high + 1e-9)
    d["tier"] = pd.cut(d["rank"], [0, 12, 24, 48, 999], labels=["top-12", "13-24", "25-48", "deeper"])
    d["phase"] = pd.cut(d.week, [0, 3, 9, 14, 17, 18], labels=["wk2-3 early", "wk4-9 mid", "wk10-14 late", "wk15-17 playoffs", "wk18"])
    d["age_b"] = pd.cut(d.age, [0, 23, 26, 29, 32, 60], labels=["<=23", "24-26", "27-29", "30-32", "33+"])
    if before is not None:
        b = before[(before.status == "ok")][["season", "pid", "week", "est", "low", "high"]].rename(columns={"est": "est_b", "low": "low_b", "high": "high_b"})
        d = d.merge(b, on=["season", "pid", "week"], how="left")
        d["err_b"] = d.est_b - d.actual
        d["covered_b"] = (d.actual >= d.low_b - 1e-9) & (d.actual <= d.high_b + 1e-9)
    return d


def md(df: pd.DataFrame, digits=2) -> str:
    df = df.copy()
    idx = df.index.to_frame(index=False)
    idx.columns = [str(c) if c is not None and str(c) != "0" else "" for c in idx.columns]
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(list(idx.columns) + cols) + " |", "|" + "---|" * (len(idx.columns) + len(cols))]
    for (_, irow), (_, row) in zip(idx.iterrows(), df.iterrows()):
        cells = [str(v) for v in irow.values]
        for c, v in zip(cols, row.values):
            if c == "n" or (isinstance(v, (int, np.integer))):
                cells.append(f"{int(v):,}")
            elif isinstance(v, (float, np.floating)):
                cells.append("-" if np.isnan(v) else f"{v:.{digits}f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def spearman(g: pd.DataFrame, col: str) -> float:
    vals = []
    for _, x in g.groupby(["season", "week", "pos"]):
        if len(x) >= 8 and x[col].nunique() > 1 and x.actual.nunique() > 1:
            vals.append(x[col].rank().corr(x.actual.rank()))
    return float(np.nanmean(vals)) if vals else float("nan")


def m_row(g: pd.DataFrame) -> pd.Series:
    """MAE / bias of the shipped model (v3.3), the previous model (v3.2) and the two naive baselines, plus 68% coverage."""
    out = {"n": len(g), "v3.3 MAE": (g.est - g.actual).abs().mean(), "v3.2 MAE": g.err_b.abs().mean()}
    gm = g.dropna(subset=["b_last3", "b_std"])
    out["last-3 MAE"] = (gm.b_last3 - gm.actual).abs().mean()
    out["season-avg MAE"] = (gm.b_std - gm.actual).abs().mean()
    out["v3.3 bias"] = (g.est - g.actual).mean()
    out["v3.2 bias"] = g.err_b.mean()
    out["last-3 bias"] = (gm.b_last3 - gm.actual).mean()
    out["68% cov v3.3"] = g.covered.mean() * 100
    out["cov v3.2"] = g.covered_b.mean() * 100
    return pd.Series(out)


def scenario_flags(d: pd.DataFrame, rows: pd.DataFrame) -> pd.DataFrame:
    allr = rows[rows.status != "no_history"].copy()
    allr["healthy_dnp"] = (~allr.played) & (allr.rost_status == "Active") & (allr.inj.fillna("") == "")
    allr = allr.sort_values(["pid", "season", "week"])
    allr["scr4"] = allr.groupby(["pid", "season"]).healthy_dnp.transform(lambda s: s.shift(1).rolling(4, min_periods=1).sum())
    d = d.merge(allr[["pid", "season", "week", "scr4"]], on=["pid", "season", "week"], how="left")
    # RB committee: the two best RBs of a team that week have estimates within 25% of each other and both >= 7
    rb = d[d.pos == "RB"].sort_values(["season", "week", "team", "est"], ascending=[True, True, True, False])
    top2 = rb.groupby(["season", "week", "team"]).est.apply(lambda s: list(s.iloc[:2]))
    com = {k: (len(v) == 2 and v[1] >= 7 and v[1] >= 0.75 * v[0]) for k, v in top2.items()}
    d["rb_committee"] = [bool(com.get((s, w, t), False)) and p == "RB" and r <= 2 for s, w, t, p, r in zip(d.season, d.week, d.team, d.pos, d.depth.fillna(9))]
    return d


def scenario_table(d: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rel = d[d.est >= 4]
    out = rel[(rel.roof == "outdoors")]
    sc = {
        "all relevant (est >= 4)": rel,
        "rookie, games 2-4 (first projection)": rel[(rel.rookie_year == rel.season) & (rel.n_cur <= 3)],
        "returning after >= 2 missed team games": rel[(rel.gap >= 2) & (rel.n_cur >= 1)],
        "no game yet this season, week >= 3": rel[(rel.n_cur == 0) & (rel.week >= 3)],
        "new team in season": rel[(rel.n_cur > 0) & (rel.team != rel.team_last)],
        "new team, weeks 1-3": rel[(rel.n_cur == 0) & (rel.week <= 3) & (rel.team != rel.team_last)],
        "QB changed vs last game (RB/WR/TE)": rel[rel.pos.isin(["RB", "WR", "TE"]) & rel.qb_prev.notna() & (rel.game_qb != rel.qb_prev)],
        "same QB (RB/WR/TE)": rel[rel.pos.isin(["RB", "WR", "TE"]) & rel.qb_prev.notna() & (rel.game_qb == rel.qb_prev)],
        "handcuff, starter Out/Doubtful": rel[rel.role == "handcuff_starter_out"],
        "RB committee (top-2 within 25%)": rel[rel.rb_committee],
        "backup QB role": d[d.role == "backup_qb"],
        "suspended-list code (RES/R48)": d[d.rw_abbr == "R48"],
        "short week (rest <= 5 days)": rel[rel.rest <= 5],
        "Thursday game": rel[rel.weekday == "Thursday"],
        "after bye (rest >= 13)": rel[rel.rest >= 13],
        "Monday game": rel[rel.weekday == "Monday"],
        "week 18": rel[rel.week == 18],
        "Questionable": rel[rel.inj == "Questionable"],
        "Doubtful": d[d.inj == "Doubtful"],
        "healthy scratch in last 4 team games (>= 1)": rel[rel.scr4 >= 1],
        "healthy scratch in last 4 team games (>= 2)": rel[rel.scr4 >= 2],
        "outdoor, wind >= 15 mph": out[out.wind >= 15],
        "outdoor, temp <= 32 F": out[out.temp <= 32],
        "dome / closed roof": rel[rel.roof.isin(["dome", "closed"])],
    }
    rows = []
    for k, g in sc.items():
        if len(g) == 0:
            continue
        gm = g.dropna(subset=["b_last3", "b_std"])
        rows.append({"scenario": k, "n": len(g), "played %": g.played.mean() * 100, "est v3.3": g.est.mean(), "est v3.2": g.est_b.mean(), "actual": g.actual.mean(),
                     "bias v3.3": g.err.mean(), "bias v3.2": g.err_b.mean(), "MAE v3.3": g.err.abs().mean(), "MAE v3.2": g.err_b.abs().mean(),
                     "MAE last-3": (gm.b_last3 - gm.actual).abs().mean(), "68% cov v3.3": g.covered.mean() * 100, "cov v3.2": g.covered_b.mean() * 100})
    return pd.DataFrame(rows).set_index("scenario"), sc


def sleeper_benchmark(d: pd.DataFrame, sl: Path) -> str:
    """Reference only: Sleeper's own weekly projections (a Rotowire feed, no redistribution licence, never an input)
    on the same player-weeks as the model."""
    import json

    proj = {}
    for s in sorted(d.season.unique()):
        for w in range(1, 19):
            f = sl / f"proj_{s}_{w}.json"
            if not f.exists():
                continue
            for r in json.loads(f.read_text()):
                v = (r.get("stats") or {}).get("pts_ppr")
                if v is not None:
                    proj[(int(s), w, str(r["player_id"]))] = float(v)
    x = d[d.sleeper_id.notna() & d.played].copy()
    x["sproj"] = [proj.get((int(s), int(w), str(int(i)))) for s, w, i in zip(x.season, x.week, x.sleeper_id)]
    x = x.dropna(subset=["sproj", "b_last3", "b_std"])
    # the relevant pool: Sleeper's top-N per position-week among players who played (the v3 walk-forward definition)
    x["srank"] = x.groupby(["season", "week", "pos"]).sproj.rank(ascending=False, method="first")
    rel = x[x.srank <= x.pos.map(N)]
    rows = []
    for name, g in (("all played with a Sleeper projection", x), ("Sleeper top-N pool (v3 walk-forward definition)", rel)):
        rows.append({"pool": name, "n": len(g), "v3.3 MAE": (g.est - g.actual).abs().mean(), "Sleeper MAE": (g.sproj - g.actual).abs().mean(),
                     "last-3 MAE": (g.b_last3 - g.actual).abs().mean(), "season-avg MAE": (g.b_std - g.actual).abs().mean(),
                     "v3.3 bias": (g.est - g.actual).mean(), "Sleeper bias": (g.sproj - g.actual).mean(),
                     "rho v3.3": spearman(g, "est"), "rho Sleeper": spearman(g, "sproj")})
    return md(pd.DataFrame(rows).set_index("pool"), 3)


def mean_calibration_table(d: pd.DataFrame) -> str:
    """P1 experiment: one multiplicative lift per position (fit on EARLIER seasons only, ratio of sums on the top-N pool) so
    the estimate is a mean rather than a median-like number. Scored on the top-N pool, non-appearances scored 0."""
    rows = []
    for s in (2023, 2024, 2025, 2026):
        tr = d[(d.season < s) & d.pool & (d.pos != "K")]
        lift = tr.groupby("pos").apply(lambda g: g.actual.sum() / g.est.sum())
        te = d[(d.season == s) & d.pool].copy()
        te["est2"] = te.est * te.pos.map(lift).fillna(1.0)
        te["low2"], te["high2"] = te.low * te.pos.map(lift).fillna(1.0), te.high * te.pos.map(lift).fillna(1.0)
        te["cov2"] = (te.actual >= te.low2 - 1e-9) & (te.actual <= te.high2 + 1e-9)
        rows.append({"season": s, "n": len(te), "MAE now": (te.est - te.actual).abs().mean(), "MAE lifted": (te.est2 - te.actual).abs().mean(),
                     "bias now": (te.est - te.actual).mean(), "bias lifted": (te.est2 - te.actual).mean(),
                     "median error now": (te.est - te.actual).median(), "median error lifted": (te.est2 - te.actual).median(),
                     "cov now": te.covered.mean() * 100, "cov lifted": te.cov2.mean() * 100,
                     "lifts": ", ".join(f"{k} {v:.3f}" for k, v in lift.items())})
    return md(pd.DataFrame(rows).set_index("season"), 3)


def ros_tables(after: Path, before: Path) -> tuple[str, pd.DataFrame]:
    def load(p):
        r = pd.read_parquet(p)
        return r[r.season <= 2025].dropna(subset=["b_last3", "b_std"])

    b, a = load(before / "ros.parquet"), load(after / "ros.parquet")
    k = ["season", "vantage", "pid"]
    m = b.merge(a[k + ["ros_est"]], on=k, suffixes=("", "_new"))
    m["rank"] = m.groupby(["season", "vantage", "pos"]).ros_est.rank(ascending=False, method="first")
    m = m[m["rank"] <= m.pos.map(N)]
    m["e0"], m["e1"] = m.ros_est - m.ros_actual, m.ros_est_new - m.ros_actual

    def rep(g):
        return pd.Series({"n": len(g), "v3.3 MAE": g.e1.abs().mean(), "v3.2 MAE": g.e0.abs().mean(), "last-3 MAE": (g.b_last3 - g.ros_actual).abs().mean(),
                          "season-avg MAE": (g.b_std - g.ros_actual).abs().mean(), "v3.3 bias %": g.e1.sum() / g.ros_actual.sum() * 100,
                          "v3.2 bias %": g.e0.sum() / g.ros_actual.sum() * 100, "last-3 bias %": (g.b_last3 - g.ros_actual).sum() / g.ros_actual.sum() * 100,
                          "avg games played share": (g.games_played / g.rem_games).mean() * 100})

    parts = []
    for col, name in (("vantage", "vantage week"), ("pos", "position"), ("season", "season")):
        parts.append(f"By {name}:\n\n" + md(m.groupby(col).apply(rep), 1))
    total = rep(m).to_frame("all").T
    rank = m.groupby(["season", "vantage", "pos"]).apply(
        lambda g: pd.Series({"v3.3": g.ros_est_new.rank().corr(g.ros_actual.rank()), "v3.2": g.ros_est.rank().corr(g.ros_actual.rank()),
                             "last-3": g.b_last3.rank().corr(g.ros_actual.rank()), "season-avg": g.b_std.rank().corr(g.ros_actual.rank())})).mean()
    parts.insert(0, "All:\n\n" + md(total, 1) + "\n\nMean Spearman rank correlation with actual rest-of-season points (within season, vantage, position): " + ", ".join(f"{k} {v:.3f}" for k, v in rank.items()))
    return "\n\n".join(parts), m


def format_table(d: pd.DataFrame) -> str:
    """Half-PPR and TE-premium + 6-pt pass TD: the league-scored estimate vs the unconverted PPR estimate, scored on the pool."""
    p = d[d.pool & d.est_half.notna()]
    rows = []
    for name, est_c, act in (("half-PPR", "est_half", "actual_half"), ("TE premium (+0.5/rec) + 6-pt pass TD", "est_tep6", "actual_tep6")):
        for pos in OFFENSE:
            g = p[p.pos == pos]
            rows.append({"format": name, "pos": pos, "n": len(g), "actual": g[act].mean(), "converted est": g[est_c].mean(), "unconverted PPR est": g.est.mean(),
                         "MAE converted": (g[est_c] - g[act]).abs().mean(), "MAE unconverted": (g.est - g[act]).abs().mean(),
                         "bias converted": (g[est_c] - g[act]).mean(), "bias unconverted": (g.est - g[act]).mean()})
    return md(pd.DataFrame(rows).set_index(["format", "pos"]), 2)


def calibration_charts(d: pd.DataFrame, charts: Path, ros: pd.DataFrame, cmp: pd.DataFrame | None, scen: pd.DataFrame, real: dict | None) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"figure.dpi": 130, "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    colors = {"v3.3": "#1f6fbd", "v3.2": "#9aa5b1", "last-3": "#d9822b", "season-avg": "#6a994e"}
    # 1. MAE by projected tier (played) vs baselines
    g = d[d.played].dropna(subset=["b_last3", "b_std"])
    tiers = ["top-12", "13-24", "25-48", "deeper"]
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.4))
    w = 0.2
    for i, (lab, col) in enumerate((("v3.3", "est"), ("v3.2", "est_b"), ("last-3", "b_last3"), ("season-avg", "b_std"))):
        mae = [(g[g.tier == t][col] - g[g.tier == t].actual).abs().mean() for t in tiers]
        ax[0].bar(np.arange(4) + i * w, mae, w, label=lab, color=colors[lab])
    ax[0].set_xticks(np.arange(4) + 1.5 * w, tiers)
    ax[0].set_ylabel("MAE (PPR points)")
    ax[0].set_title("Error by projected tier (players who played)")
    ax[0].legend(frameon=False)
    # coverage by position
    pos_l = list(OFFENSE) + ["K"]
    cov = [g[g.pos == p].covered.mean() * 100 for p in pos_l]
    ax[1].bar(pos_l, cov, color=colors["v3.3"])
    ax[1].axhline(68, color="k", lw=1, ls="--")
    ax[1].set_ylim(50, 85)
    ax[1].set_ylabel("share of actuals inside low-high (%)")
    ax[1].set_title("68% band coverage by position")
    fig.tight_layout()
    fig.savefig(charts / "01_error_and_coverage.png")
    plt.close(fig)
    # 2. reliability: mean actual vs mean estimate by estimate decile (pool, incl non-appearances)
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.4))
    pool = d[d.pool & d.pos.isin(OFFENSE)].copy()
    pool["b"] = pd.qcut(pool.est, 10, duplicates="drop")
    t = pool.groupby("b").agg(est=("est", "mean"), act=("actual", "mean"), med=("actual", "median"))
    ax[0].plot(t.est, t.act, "o-", label="mean actual", color=colors["v3.3"])
    ax[0].plot(t.est, t.med, "s--", label="median actual", color=colors["last-3"])
    ax[0].plot([0, t.est.max()], [0, t.est.max()], "k:", lw=1)
    ax[0].set_xlabel("estimate (decile mean)")
    ax[0].set_ylabel("actual PPR")
    ax[0].set_title("Reliability, top-N pool (mean vs median)")
    ax[0].legend(frameon=False)
    # bias by tier per position
    pp_ = d[d.pool].groupby(["pos", "tier"]).apply(lambda x: (x.est - x.actual).mean()).unstack()
    pp_ = pp_[[c for c in ["top-12", "13-24", "25-48", "deeper"] if c in pp_]].reindex(["QB", "RB", "WR", "TE", "K"])
    pp_.plot.bar(ax=ax[1], width=0.8, color=["#1f6fbd", "#5a9bd5", "#a8c9e6", "#d0dde9"])
    ax[1].axhline(0, color="k", lw=0.8)
    ax[1].set_ylabel("bias, estimate - actual (pts)")
    ax[1].set_title("Bias by position and projected tier (pool)")
    ax[1].legend(frameon=False, ncol=2)
    ax[1].tick_params(axis="x", rotation=0)
    fig.tight_layout()
    fig.savefig(charts / "02_reliability_and_tier_bias.png")
    plt.close(fig)
    # 3. ROS bias before/after by vantage
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.4))
    for col, lab in (("e0", "v3.2"), ("e1", "v3.3")):
        v = ros.groupby("vantage").apply(lambda x: x[col].sum() / x.ros_actual.sum() * 100)
        ax[0].plot(v.index, v.values, "o-", label=lab, color=colors[lab])
    ax[0].axhline(0, color="k", lw=0.8)
    ax[0].set_xlabel("vantage week")
    ax[0].set_ylabel("rest-of-season bias (% of actual)")
    ax[0].set_title("Rest-of-season totals, before vs after")
    ax[0].legend(frameon=False)
    mae = ros.groupby("vantage").apply(lambda x: pd.Series({"v3.3": x.e1.abs().mean(), "v3.2": x.e0.abs().mean(), "last-3": (x.b_last3 - x.ros_actual).abs().mean(), "season-avg": (x.b_std - x.ros_actual).abs().mean()}))
    mae.plot.bar(ax=ax[1], color=[colors[c] for c in mae.columns], width=0.8)
    ax[1].set_ylabel("MAE of rest-of-season total (pts)")
    ax[1].set_xlabel("vantage week")
    ax[1].tick_params(axis="x", rotation=0)
    ax[1].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(charts / "03_rest_of_season.png")
    plt.close(fig)
    # 4. scenarios: bias before/after
    sc = scen.drop(index=[i for i in scen.index if i.startswith("all relevant")]).copy()
    sc = sc[sc.n >= 60].sort_values("bias v3.2")
    fig, ax = plt.subplots(figsize=(8.6, 6))
    y = np.arange(len(sc))
    ax.barh(y + 0.2, sc["bias v3.2"], 0.4, color=colors["v3.2"], label="v3.2 (before)")
    ax.barh(y - 0.2, sc["bias v3.3"], 0.4, color=colors["v3.3"], label="v3.3 (after)")
    ax.set_yticks(y, [f"{i} (n={int(n):,})" for i, n in zip(sc.index, sc.n)])
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel("bias, estimate - actual (PPR points per player-week)")
    ax.set_title("Niche scenarios: bias before and after")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(charts / "04_scenarios.png")
    plt.close(fig)
    # 5. independence
    if cmp is not None and len(cmp):
        fig, ax = plt.subplots(figsize=(6, 3.2))
        t = cmp.groupby("season").apply(lambda x: pd.Series({"nflverse stats": (x.nv - x.actual).abs().mean(), "Sleeper stats (production)": (x.sl - x.actual).abs().mean()}))
        t.plot.bar(ax=ax, color=["#6a994e", "#1f6fbd"], width=0.75)
        ax.set_ylim(3.8, 4.7)
        ax.set_ylabel("MAE (PPR points)")
        ax.set_title("Same estimator, two stat feeds")
        ax.tick_params(axis="x", rotation=0)
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(charts / "05_independence.png")
        plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--after", type=Path, required=True)
    ap.add_argument("--before", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--charts", type=Path, required=True)
    ap.add_argument("--sl", type=Path, default=None, help="Sleeper cache (proj_YYYY_W.json) for the reference benchmark table")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    a.charts.mkdir(parents=True, exist_ok=True)
    rows_a = pd.read_parquet(a.after / "rows.parquet")
    rows_b = pd.read_parquet(a.before / "rows.parquet")
    d = prep(rows_a, rows_b)
    mean_cal = mean_calibration_table(d)
    d = d[d.season >= 2023]
    d = scenario_flags(d, rows_a)
    sections: dict[str, str] = {}

    played = d[d.played].dropna(subset=["b_last3", "b_std", "est_b"])
    pool = d[d.pool].dropna(subset=["b_last3", "b_std", "est_b"])
    head = []
    for name, g in (("Played player-weeks (conditional on playing)", played), ("Top-N pool by estimate, non-appearances scored 0", pool)):
        t = g.groupby("season").apply(m_row)
        t = pd.concat([t, m_row(g).to_frame("all").T])
        rho = {"v3.3": "est", "v3.2": "est_b", "last-3": "b_last3", "season-avg": "b_std"}
        for lab, col in rho.items():
            t[f"rho {lab}"] = [spearman(g[g.season == s], col) for s in t.index[:-1]] + [spearman(g, col)]
        head.append(f"**{name}**\n\n" + md(t, 3))
    sections["headline"] = "\n\n".join(head)
    if a.sl is not None:
        sections["benchmark"] = sleeper_benchmark(d, a.sl)
    for key, col in (("position", "pos"), ("tier", "tier"), ("age", "age_b"), ("phase", "phase")):
        parts = []
        for name, g in (("played", played), ("pool", pool)):
            parts.append(f"{name}:\n\n" + md(g.groupby(col).apply(m_row), 2))
        sections[key] = "\n\n".join(parts)
    # role: derived depth order and RB committee
    r = pool[pool.pos.isin(OFFENSE)].copy()
    r["role_b"] = np.select([r.depth == 1, r.depth == 2], ["depth 1", "depth 2"], "depth 3+")
    sections["role"] = md(r.groupby(["pos", "role_b"]).apply(m_row), 2)
    t = pool.groupby(["pos", "tier"]).apply(lambda g: pd.Series({"n": len(g), "played %": g.played.mean() * 100, "est": g.est.mean(), "actual": g.actual.mean(),
                                                                  "bias": g.err.mean(), "bias | played": g[g.played].err.mean(), "median err | played": g[g.played].err.median(),
                                                                  "MAE": g.err.abs().mean(), "68% cov": g.covered.mean() * 100}))
    sections["pos_tier"] = md(t, 2)
    scen, _sc = scenario_table(d)
    sections["scenarios"] = md(scen, 2)
    sections["format"] = format_table(d)
    sections["mean_cal"] = mean_cal
    # wind by position
    o = d[(d.roof == "outdoors") & (d.est >= 3) & d.pos.isin(OFFENSE) & d.played]
    wt = []
    for pos in OFFENSE:
        g = o[o.pos == pos]
        hi, lo = g[g.wind >= 15], g[g.wind < 15]
        wt.append({"pos": pos, "n wind>=15": len(hi), "actual/est, wind>=15": hi.actual.sum() / hi.est.sum(), "n calm": len(lo), "actual/est, calm": lo.actual.sum() / lo.est.sum()})
    sections["wind"] = md(pd.DataFrame(wt).set_index("pos"), 3)
    ros_md, ros = ros_tables(a.after, a.before)
    sections["ros"] = ros_md
    cmp = None
    if (a.after / "sleeper_cmp.parquet").exists():
        cmp = pd.read_parquet(a.after / "sleeper_cmp.parquet").dropna(subset=["nv", "sl"])
        cmp = cmp[cmp.season >= 2023]
        diff = (cmp.nv - cmp.actual).abs() - (cmp.sl - cmp.actual).abs()
        t = cmp.groupby("season").apply(lambda g: pd.Series({"n": len(g), "MAE nflverse feed": (g.nv - g.actual).abs().mean(), "MAE Sleeper feed": (g.sl - g.actual).abs().mean(),
                                                              "bias nflverse": (g.nv - g.actual).mean(), "bias Sleeper": (g.sl - g.actual).mean(),
                                                              "mean |difference|": (g.nv - g.sl).abs().mean()}))
        tt = pd.concat([t, pd.DataFrame([{"n": len(cmp), "MAE nflverse feed": (cmp.nv - cmp.actual).abs().mean(), "MAE Sleeper feed": (cmp.sl - cmp.actual).abs().mean(),
                                          "bias nflverse": (cmp.nv - cmp.actual).mean(), "bias Sleeper": (cmp.sl - cmp.actual).mean(), "mean |difference|": (cmp.nv - cmp.sl).abs().mean()}], index=["all"])])
        sections["independence"] = md(tt, 3) + f"\n\nPaired difference in absolute error (nflverse minus Sleeper): {diff.mean():+.3f} (standard error {diff.std() / np.sqrt(len(diff)):.3f}, n={len(diff):,})."
        sections["independence_pos"] = md(cmp.groupby("pos").apply(lambda g: pd.Series({"n": len(g), "MAE nflverse": (g.nv - g.actual).abs().mean(), "MAE Sleeper": (g.sl - g.actual).abs().mean()})), 3)
    # unmodeled starters (rookies / no history)
    nh = rows_a[(rows_a.status == "no_history") & (rows_a.season >= 2023)].copy()
    nh["round"] = pd.cut(nh.draft_number, [0, 32, 64, 100, 300], labels=["R1", "R2", "R3", "R4+"]).astype(object).fillna("UDFA")
    anchors = {"QB": 12.0, "RB": 4.5, "WR": 5.0, "TE": 3.5, "K": 7.0}
    ft = nh.groupby(["pos", "round"]).agg(n=("actual", "size"), mean=("actual", "mean"), median=("actual", "median"), sd=("actual", "std"))
    ft["fallback anchor"] = [anchors.get(p) for p, _r in ft.index]
    sections["fallback"] = md(ft, 2)
    (a.out / "tables.md").write_text("\n\n".join(f"<!-- {k} -->\n{v}" for k, v in sections.items()))
    calibration_charts(d, a.charts, ros, cmp, scen, None)
    print((a.out / "tables.md").read_text())


if __name__ == "__main__":
    main()

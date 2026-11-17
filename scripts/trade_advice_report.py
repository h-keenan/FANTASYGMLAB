"""Tables and charts for ``docs/audits/2026-11-trade-advice-backtest.md`` from scored backtest trades.

    python scripts/trade_advice_report.py --scored S.parquet --out DIR [--tag before|after] [--compare OTHER.parquet]

Prints markdown tables to stdout (the audit doc pastes them) and writes PNGs to ``--out``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

TIE = 3.0  # |points over replacement| below this is a coin flip, not a win or a loss


def prep(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d = d[d.vor_ros.notna()].copy()
    d["H"] = d.vorc_ros + d.vorc_y1  # points over replacement (below-replacement assets count 0); NaN for 2025 (no complete next season)
    d["Hs"] = d.spor_ros + d.spor_y1  # receiving roster's hindsight starting-lineup points delta
    d["Hs3"] = d.Hs + d.spor_y2  # three-season window (trades through 2023)
    d["mkt_d"] = d.mkt_recv - d.mkt_send
    d["mkt_n"] = d.mkt_d / np.maximum(1.0, np.maximum(d.mkt_recv, d.mkt_send))
    d["eng_n"] = d.trade_score / np.maximum(1.0, d.deal_size)
    d["raw_n"] = d.raw_value_delta / np.maximum(1.0, d.deal_size)
    d["nv_d"] = d.naive_recv - d.naive_send
    d["nv_n"] = d.nv_d / np.maximum(1.0, np.maximum(d.naive_recv, d.naive_send))
    d["picks"] = (d.send_pick > 0) | (d.recv_pick > 0)
    d["contender"] = d.strategy.isin(["contender", "fringe_contender"])
    return d


def auc(x, y, tie=TIE):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    m = (np.abs(y) >= tie) & ~np.isnan(x) & ~np.isnan(y)
    x, yb = x[m], y[m] > 0
    if yb.sum() < 5 or (~yb).sum() < 5:
        return np.nan
    r = pd.Series(x).rank().to_numpy()
    n1, n0 = yb.sum(), (~yb).sum()
    return float((r[yb].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def auc_ci(x, y, n_boot=200, seed=3):
    rng = np.random.default_rng(seed)
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    m = ~np.isnan(x) & ~np.isnan(y)
    x, y = x[m], y[m]
    vals = []
    for _ in range(n_boot):
        i = rng.integers(0, len(x), len(x))
        vals.append(auc(x[i], y[i]))
    return float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5))


def win_stats(y, tie=TIE):
    y = np.asarray(y, float)
    y = y[~np.isnan(y)]
    dec = y[np.abs(y) >= tie]
    n = len(dec)
    w = float((dec > 0).mean()) if n else np.nan
    se = float(np.sqrt(w * (1 - w) / n)) if n else np.nan
    return len(y), n, w, se, float(y.mean()) if len(y) else np.nan


def table_by(d, col, outcome="H", order=None):
    rows = []
    groups = d.groupby(col)
    keys = order or list(groups.groups)
    for k in keys:
        if k not in groups.groups:
            continue
        g = groups.get_group(k)
        n, nd, w, se, mean = win_stats(g[outcome])
        rows.append(dict(group=k, n=n, decided=nd, win_pct=100 * w, ci95=196 * se, mean_gain=mean, mv_chg_1y=g.mv_chg.mean()))
    return pd.DataFrame(rows)


def md(df: pd.DataFrame, floatfmt="{:.1f}") -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                cells.append("" if np.isnan(v) else floatfmt.format(v))
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def predictor_table(d, outcome="H"):
    rows = []
    for name, col in (("Engine verdict score (trade_score / deal)", "eng_n"), ("Engine raw value delta", "raw_n"),
                      ("Market delta (FantasyCalc-scale, point in time)", "mkt_n"), ("Naive: last-season PPG delta", "nv_n")):
        m = d[outcome].notna()
        a = auc(d.loc[m, col], d.loc[m, outcome])
        lo, hi = auc_ci(d.loc[m, col].to_numpy(), d.loc[m, outcome].to_numpy())
        rho = d.loc[m, [col, outcome]].corr(method="spearman").iloc[0, 1]
        rows.append(dict(predictor=name, n=int(m.sum()), auc=a, ci_lo=lo, ci_hi=hi, spearman=rho))
    return pd.DataFrame(rows)


def beyond_market(d, outcome="H"):
    """OLS of the outcome on the market delta and the engine's departure from it (standardised)."""
    m = d[outcome].notna()
    x1 = d.loc[m, "mkt_n"].to_numpy()
    x2 = (d.loc[m, "eng_n"] - d.loc[m, "mkt_n"]).to_numpy()
    y = d.loc[m, outcome].to_numpy()
    z = lambda v: (v - v.mean()) / (v.std() or 1)  # noqa: E731
    X = np.column_stack([np.ones(len(y)), z(x1), z(x2)])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ beta
    cov = np.linalg.inv(X.T @ X) * res.var()
    se = np.sqrt(np.diag(cov))
    return pd.DataFrame(dict(term=["intercept", "market delta (std)", "engine minus market (std)"], coef=beta, se=se, t=beta / se))


def charts(d, out: Path, tag: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out.mkdir(parents=True, exist_ok=True)
    C = {"engine": "#2563eb", "market": "#d97706", "naive": "#6b7280", "good": "#15803d", "bad": "#b91c1c"}
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

    # 1 calibration: win rate by engine verdict
    order = ["HARD DECLINE", "DECLINE", "COUNTER", "FAIR / PREFERENCE", "ACCEPT", "SMASH ACCEPT"]
    t = table_by(d, "band", "Hs", order)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(t.group, t.win_pct, yerr=t.ci95, color=C["engine"], capsize=3)
    ax.axhline(50, color="#444", lw=1, ls="--")
    for i, r in t.iterrows():
        ax.text(i, 3, f"n={int(r.n)}", ha="center", color="white", fontsize=8)
    ax.set_ylabel("trades that won (%), lineup points")
    ax.set_title(f"Win rate by engine verdict band ({tag})")
    plt.xticks(rotation=20)
    fig.tight_layout()
    fig.savefig(out / f"01_verdict_calibration_{tag}.png", dpi=130)
    plt.close(fig)

    # 2 AUC bars with CI
    p = predictor_table(d, "Hs")
    fig, ax = plt.subplots(figsize=(8, 3.6))
    cols = [C["engine"], "#93c5fd", C["market"], C["naive"]]
    ax.barh(p.predictor, p.auc, xerr=[p.auc - p.ci_lo, p.ci_hi - p.auc], color=cols, capsize=3)
    ax.axvline(0.5, color="#444", lw=1, ls="--")
    ax.set_xlim(0.45, max(0.7, p.ci_hi.max() + 0.02))
    ax.set_xlabel("AUC: predicts which roster gains more lineup points")
    ax.set_title(f"Predictive power vs baselines ({tag})")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(out / f"02_predictors_auc_{tag}.png", dpi=130)
    plt.close(fig)

    # 3 mean outcome by engine score decile vs market decile
    fig, ax = plt.subplots(figsize=(8, 4))
    for col, lab, colr in (("eng_n", "Engine score / deal", C["engine"]), ("mkt_n", "Market delta / deal", C["market"]), ("nv_n", "Naive PPG delta", C["naive"])):
        m = d.Hs.notna()
        q = pd.qcut(d.loc[m, col].rank(method="first"), 10, labels=False)
        g = d.loc[m].groupby(q).Hs.mean()
        ax.plot(range(1, 11), g.to_numpy(), marker="o", label=lab, color=colr)
    ax.axhline(0, color="#444", lw=1, ls="--")
    ax.set_xlabel("decile of predictor (1 = worst for the user, 10 = best)")
    ax.set_ylabel("mean starting-lineup points gained (ROS + next season)")
    ax.legend()
    ax.set_title(f"Realized gain by predictor decile ({tag})")
    fig.tight_layout()
    fig.savefig(out / f"03_decile_outcome_{tag}.png", dpi=130)
    plt.close(fig)

    # 4 AUC by kind / posture
    fig, axs = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for ax, col, title in ((axs[0], "kind", "trade shape"), (axs[1], "strategy", "user posture")):
        keys = sorted(d[col].unique())
        x = np.arange(len(keys))
        for j, (pcol, lab, colr) in enumerate((("eng_n", "engine", C["engine"]), ("mkt_n", "market", C["market"]), ("nv_n", "naive", C["naive"]))):
            vals = [auc(d[d[col] == k][pcol], d[d[col] == k].Hs) for k in keys]
            ax.bar(x + (j - 1) * 0.27, vals, 0.27, label=lab, color=colr)
        ax.axhline(0.5, color="#444", lw=1, ls="--")
        ax.set_xticks(x)
        ax.set_xticklabels(keys, rotation=25, ha="right")
        ax.set_title(f"AUC by {title}")
        ax.set_ylim(0.4, 0.75)
    axs[0].legend()
    fig.tight_layout()
    fig.savefig(out / f"04_auc_by_shape_posture_{tag}.png", dpi=130)
    plt.close(fig)


def cnt(series, pos):
    return series.fillna("").map(lambda x: x.split("|").count(pos) if x else 0)


def flags(d):
    d = d.copy()
    for p in ("QB", "RB", "WR", "TE"):
        d["n" + p] = cnt(d.recv_pos, p) - cnt(d.send_pos, p)
    d["recv_old_rb"] = [(("RB" in (p or "").split("|")) and a >= 27) for p, a in zip(d.recv_pos, d.recv_age.fillna(0))]
    d["send_old_rb"] = [(("RB" in (p or "").split("|")) and a >= 27) for p, a in zip(d.send_pos, d.send_age.fillna(0))]
    big = lambda inj, mk: any((i in ("Out", "Doubtful")) and float(m or 0) >= 2500 for i, m in zip((inj or "").split("|"), (mk or "0").split("|")))  # noqa: E731
    d["inj_star_recv"] = [big(i, m) for i, m in zip(d.recv_inj.fillna(""), d.recv_mkt1.fillna(""))]
    d["inj_star_send"] = [big(i, m) for i, m in zip(d.send_inj.fillna(""), d.send_mkt1.fillna(""))]
    return d


NICHES = (
    ("Aging RB received (27+), none sent", lambda d: d.recv_old_rb & ~d.send_old_rb),
    ("Aging RB sent (27+), none received", lambda d: d.send_old_rb & ~d.recv_old_rb),
    ("Injured star (Out/Doubtful, value 2.5k+) received", lambda d: d.inj_star_recv & ~d.inj_star_send),
    ("Injured star sent", lambda d: d.inj_star_send & ~d.inj_star_recv),
    ("Rookie pick, before NFL draft (Apr 15)", lambda d: d.picks & (d.mmdd == "04-15")),
    ("Rookie pick, after NFL draft (May 20)", lambda d: d.picks & (d.mmdd == "05-20")),
    ("Rookie pick, after rookie drafts (Aug 20)", lambda d: d.picks & (d.mmdd == "08-20")),
    ("Rookie pick, in season (Oct/Dec)", lambda d: d.picks & d.in_season),
    ("QB received in Superflex", lambda d: d.league.isin(["dynasty_sf", "dynasty_sf_tep"]) & (d.nQB > 0)),
    ("QB sent in Superflex", lambda d: d.league.isin(["dynasty_sf", "dynasty_sf_tep"]) & (d.nQB < 0)),
    ("QB received in 1QB dynasty", lambda d: (d.league == "dynasty_1qb") & (d.nQB > 0)),
    ("TE in trade, TE-premium league", lambda d: (d.league == "dynasty_sf_tep") & (d.nTE != 0)),
    ("TE in trade, same league without TE premium", lambda d: (d.league == "dynasty_sf") & (d.nTE != 0)),
    ("Handcuff RB bought", lambda d: d.kind == "handcuff"),
    ("Deadline window (Oct 20), contender / fringe", lambda d: (d.mmdd == "10-20") & d.contender & ~d.picks),
    ("Deadline window (Oct 20), rebuild / tank", lambda d: (d.mmdd == "10-20") & d.strategy.isin(["rebuild", "tank"]) & ~d.picks),
    ("Dec 1, contender / fringe", lambda d: (d.mmdd == "12-01") & d.contender & ~d.picks),
    ("2-for-1 consolidation (user sends 2, gets 1)", lambda d: d.kind == "2for1"),
    ("1-for-2 break-up (user sends 1, gets 2)", lambda d: d.kind == "1for2"),
)


def niche_table(d, outcome="Hs"):
    d = flags(d)
    d = d[d[outcome].notna()]
    # one overall slope: outcome points per engine point
    x = d.trade_score.to_numpy(float)
    y = d[outcome].to_numpy(float)
    slope = float((x * (y - y.mean())).sum() / ((x - x.mean()) ** 2).sum())
    rows = []
    for name, f in NICHES:
        g = d[f(d)]
        if len(g) < 40:
            rows.append(dict(niche=name, n=len(g)))
            continue
        acc, dec = g[g.ui_verdict == "ACCEPT"], g[g.ui_verdict == "DECLINE"]
        resid = (g[outcome] - slope * g.trade_score).mean()
        rows.append(dict(niche=name, n=len(g), engine_auc=auc(g.eng_n, g[outcome]), market_auc=auc(g.mkt_n, g[outcome]),
                         naive_auc=auc(g.nv_n, g[outcome]), accept_win=100 * win_stats(acc[outcome])[2] if len(acc) > 20 else np.nan,
                         decline_win=100 * win_stats(dec[outcome])[2] if len(dec) > 20 else np.nan,
                         mean_gain=g[outcome].mean(), bias_pts=resid))
    return pd.DataFrame(rows)


def disagreement(d, outcome="Hs"):
    d = d[d[outcome].notna()]
    rows = []
    for name, m in (
        ("Engine ACCEPT, market agrees", (d.eng_n > .04) & (d.mkt_n > .04)),
        ("Engine ACCEPT, market says lose", (d.eng_n > .04) & (d.mkt_n < -.04)),
        ("Engine DECLINE, market agrees", (d.eng_n < -.04) & (d.mkt_n < -.04)),
        ("Engine DECLINE, market says win", (d.eng_n < -.04) & (d.mkt_n > .04)),
    ):
        n, nd, w, se, mean = win_stats(d[m][outcome])
        rows.append(dict(case=name, n=n, win_pct=100 * w, ci95=196 * se, mean_gain=mean))
    return pd.DataFrame(rows)


def by_horizon(d):
    rows = []
    for lab, col in (("Rest of that season", "spor_ros"), ("Next season", "spor_y1"), ("Season after", "spor_y2"), ("ROS + next season", "Hs"), ("All three", "Hs3")):
        m = d[col].notna()
        if col in ("spor_y2", "Hs3"):
            m &= d.season <= 2023
        g = d[m]
        acc, dec = g[g.ui_verdict == "ACCEPT"], g[g.ui_verdict == "DECLINE"]
        rows.append(dict(horizon=lab, n=len(g), engine_auc=auc(g.eng_n, g[col]), market_auc=auc(g.mkt_n, g[col]), naive_auc=auc(g.nv_n, g[col]),
                         accept_win=100 * win_stats(acc[col])[2], decline_win=100 * win_stats(dec[col])[2]))
    return pd.DataFrame(rows)


def pick_calibration(d):
    p = d[d.kind.isin(["pick_for_player", "player_for_pick"])].copy()
    p["slot"] = np.where(p.kind == "pick_for_player", p.send_pick, p.recv_pick)
    p["eng"] = np.where(p.kind == "pick_for_player", p.send_val, p.recv_val)
    p["mkt"] = np.where(p.kind == "pick_for_player", p.mkt_send, p.mkt_recv)
    p["rnd"] = (p.slot - 1) // 12 + 1
    p["tier"] = pd.cut(((p.slot - 1) % 12) + 1, [0, 4, 8, 12], labels=["early", "mid", "late"])
    g = p.groupby(["rnd", "tier"], observed=True).agg(n=("slot", "size"), engine_pick_value=("eng", "mean"), market_pick_value=("mkt", "mean")).reset_index()
    return g


def asset_tables(a: pd.DataFrame) -> dict:
    """Player-level calibration from ``trade_advice_outcomes.py --assets-out``."""
    a = a[(a.season <= 2024) & a.vor_ros.notna() & a.vor_y1.notna()].copy()
    a["H"] = a.vor_ros.clip(lower=0) + a.vor_y1.clip(lower=0)  # below-replacement seasons count 0 (replaced off waivers)
    out = {}
    d = a[a.league == "dynasty_1qb"].copy()
    d["market_tier"] = pd.cut(d.market, [-1, 500, 1500, 3000, 5000, 8000, 12000], labels=["<500", "500-1.5k", "1.5-3k", "3-5k", "5-8k", "8k+"])
    g = d.groupby("market_tier", observed=True)
    out["floor"] = pd.DataFrame(dict(n=g.size(), market=g.market.mean(), engine=g.score.mean(), gap=g.score.mean() - g.market.mean(),
                                     realized_pts_over_repl=g.H.mean())).reset_index()

    def ols(df, cols):
        X = np.column_stack([np.ones(len(df))] + [df[c].to_numpy(float) for c in cols])
        y = df.H.to_numpy(float)
        b, *_ = np.linalg.lstsq(X, y, rcond=None)
        r = y - X @ b
        se = np.sqrt(np.diag(np.linalg.pinv(X.T @ X) * r.var()))
        return b, se

    rows = []
    for lg in ("dynasty_1qb", "dynasty_sf", "dynasty_sf_tep"):
        d = a[a.league == lg].copy()
        for p in ("QB", "RB", "TE"):
            d["is_" + p] = (d.position == p).astype(float)
        d["old"] = np.clip(d.age - 27, 0, None)
        d["young"] = np.clip(24 - d.age, 0, None)
        d["s"] = d.score / 1000
        d["m"] = d.market / 1000
        for src in ("s", "m"):
            b, se = ols(d, [src, "is_QB", "is_RB", "is_TE", "old", "young"])
            rows.append(dict(league=lg, value=("engine score" if src == "s" else "market"), pts_per_1000=b[1], QB=b[2], RB=b[3], TE=b[4], per_year_past_27=b[5], per_year_under_24=b[6],
                             QB_se=1.96 * se[2], TE_se=1.96 * se[4]))
    out["pos_age"] = pd.DataFrame(rows)
    return out


def compare(before: pd.DataFrame, after: pd.DataFrame, out: Path):
    """Before/after of the same trades re-graded with the fixed engine (same seeds, so the same packages)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    order = ["HARD DECLINE", "DECLINE", "COUNTER", "FAIR / PREFERENCE", "ACCEPT", "SMASH ACCEPT"]
    fig, axs = plt.subplots(1, 2, figsize=(12, 4))
    tb, ta = table_by(before, "band", "Hs", order), table_by(after, "band", "Hs", order)
    x = np.arange(len(order))
    axs[0].bar(x - 0.2, tb.win_pct, 0.4, yerr=tb.ci95, color="#9ca3af", label="before", capsize=2)
    axs[0].bar(x + 0.2, ta.win_pct, 0.4, yerr=ta.ci95, color="#2563eb", label="after", capsize=2)
    axs[0].axhline(50, color="#444", lw=1, ls="--")
    axs[0].set_xticks(x)
    axs[0].set_xticklabels(order, rotation=25, ha="right")
    axs[0].set_ylabel("trades that won (%)")
    axs[0].set_title("Win rate by verdict band")
    axs[0].legend()
    names = ["Engine verdict", "Market", "Naive PPG"]
    cols = ["eng_n", "mkt_n", "nv_n"]
    for j, (d, lab, colr) in enumerate(((before, "before", "#9ca3af"), (after, "after", "#2563eb"))):
        m = d.Hs.notna()
        vals = [auc(d.loc[m, c], d.loc[m, "Hs"]) for c in cols]
        axs[1].bar(np.arange(3) + (j - 0.5) * 0.4, vals, 0.4, color=colr, label=lab)
        for i, v in enumerate(vals):
            axs[1].text(i + (j - 0.5) * 0.4, v + 0.003, f"{v:.3f}", ha="center", fontsize=8)
    axs[1].axhline(0.5, color="#444", lw=1, ls="--")
    axs[1].set_xticks(range(3))
    axs[1].set_xticklabels(names)
    axs[1].set_ylim(0.5, 0.67)
    axs[1].set_ylabel("AUC")
    axs[1].set_title("Predicts which roster gains lineup points")
    axs[1].legend()
    fig.tight_layout()
    fig.savefig(out / "05_before_after.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    pb, pa = pick_calibration(before), pick_calibration(after)
    labels = [f"R{r} {t}" for r, t in zip(pb.rnd, pb.tier)]
    x = np.arange(len(labels))
    ax.bar(x - 0.27, pb.market_pick_value, 0.27, color="#d97706", label="market (FantasyCalc-scale)")
    ax.bar(x, pb.engine_pick_value, 0.27, color="#9ca3af", label="engine before")
    ax.bar(x + 0.27, pa.engine_pick_value, 0.27, color="#2563eb", label="engine after")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel("pick value (engine points)")
    ax.set_title("Pick values vs market (picks traded 2021-2025)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "06_pick_values.png", dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scored", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="before")
    ap.add_argument("--assets")
    ap.add_argument("--compare", help="scored parquet of the same trades graded BEFORE the fixes")
    a = ap.parse_args()
    d = prep(pd.read_parquet(a.scored))
    print(f"trades {len(d)}; with 2-season horizon {int(d.Hs.notna().sum())}")
    for o, label in (("Hs", "starting-lineup points (SPOR), rest of season + next"), ("H", "points over replacement")):
        print(f"\n### predictors, outcome = {label}")
        print(md(predictor_table(d, o), "{:.3f}"))
    print("\n### beyond market"); print(md(beyond_market(d, "Hs"), "{:.3f}"))
    print("\n### verdict calibration"); print(md(table_by(d, "ui_verdict", "Hs", ["ACCEPT", "FAIR", "COUNTER", "DECLINE"])))
    print("\n### band"); print(md(table_by(d, "band", "Hs", ["SMASH ACCEPT", "ACCEPT", "FAIR / PREFERENCE", "COUNTER", "DECLINE", "HARD DECLINE"])))
    print("\n### disagreement"); print(md(disagreement(d)))
    print("\n### horizons"); print(md(by_horizon(d), "{:.3f}"))
    print("\n### niches"); print(md(niche_table(d), "{:.2f}"))
    print("\n### picks"); print(md(pick_calibration(d), "{:.0f}"))
    if a.assets:
        for name, t in asset_tables(pd.read_parquet(a.assets)).items():
            print(f"\n### assets: {name}")
            print(md(t, "{:.2f}"))
    charts(d, Path(a.out), a.tag)
    if a.compare:
        b = prep(pd.read_parquet(a.compare))
        compare(b, d, Path(a.out))
        # The same seeds generate the same packages, so the two runs align row for row.
        keep = ["season", "date", "league", "kind", "team", "partner", "send_ids", "recv_ids", "send_pick", "recv_pick"]
        b, d2 = b.reset_index(drop=True), d.reset_index(drop=True)
        assert len(b) == len(d2) and (b[keep].astype(str) == d2[keep].astype(str)).all().all(), "runs are not the same trades"
        changed = b.ui_verdict != d2.ui_verdict
        print(f"\n### re-graded identical trades: {len(b)}; verdict changed {100 * changed.mean():.1f}%; "
              f"of those, pick trades {100 * (changed & d2.picks).sum() / max(1, changed.sum()):.0f}%")
        ct = pd.crosstab(b.ui_verdict, d2.ui_verdict).reset_index().rename(columns={"ui_verdict": "before / after"})
        print(md(ct, "{:.0f}"))
        for lab, m in (("pick trades", d2.picks), ("player-only trades", ~d2.picks), ("2-for-1 / 1-for-2", d2.kind.isin(["2for1", "1for2"]))):
            m = m & d2.Hs.notna()
            print(f"AUC on {lab} (n={int(m.sum())}): before {auc(b.eng_n[m], b.Hs[m]):.3f} after {auc(d2.eng_n[m], d2.Hs[m]):.3f} market {auc(d2.mkt_n[m], d2.Hs[m]):.3f}")


if __name__ == "__main__":
    main()

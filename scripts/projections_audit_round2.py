"""Round 2 (P1 fixes) before/after tables for ``docs/audits/2026-11-projections-backtest.md``.

    python scripts/projections_audit_round2.py --before /tmp/pa_b --after /tmp/pa_a --out /tmp/pa_r2

``--before`` / ``--after`` are directories holding ``rows.parquet`` (``projections_audit_backtest.py build`` over
2016-2026, written by a merge of the per-season builds) and optionally ``ros/ros.parquet`` (``ros``). Same
point-in-time rows and the same pools as ``projections_audit_analyze.py``. Every constant of the round-2 fixes was fit
on 2016-22 (2021-22 alone is too small for the new-team, wind and draft-capital cells) and is only scored here on
2023-26, the headline window. Wind is not part of ``project_player_week`` (it is applied from the game forecast in
``game_weather.apply_weather``), so the "after" columns apply the production ``weather_adjustment`` at the OBSERVED
stadium wind (outdoor games only) to the point estimate, mean estimate and band. Prints markdown tables to stdout
and ``round2_tables.md``.
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
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from projections_audit_analyze import md, prep  # noqa: E402

HEADLINE = [2023, 2024, 2025, 2026]
POSITIONS = ["QB", "RB", "WR", "TE", "K"]
LINEUP = {"QB": 1, "RB": 2, "WR": 3, "TE": 1}


def load(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path / "rows.parquet")


def wind_multiplier(frame: pd.DataFrame) -> pd.Series:
    """Production ``weather_adjustment`` at the observed stadium wind; 1.0 for domes, closed roofs and unknown wind."""

    from modules import game_weather as gw

    cache: dict = {}
    out = []
    for pos, wind, roof in zip(frame.pos, frame.wind, frame.roof):
        if roof != "outdoors" or pd.isna(wind):
            out.append(1.0)
            continue
        key = (pos, float(wind))
        if key not in cache:
            cache[key] = gw.weather_adjustment(pos, {"wind_mph": float(wind), "precip_mm": 0.0, "temp_f": None, "precip_prob_pct": 0})["multiplier"]
        out.append(cache[key])
    return pd.Series(out, index=frame.index)


def joined(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    """After-rows (week >= 2, certain zeros removed) with the before estimate attached and the wind-adjusted columns."""

    d = prep(after, before)
    d["wm"] = wind_multiplier(d)
    d["est_n"] = d.est  # v3.4 point estimate before the weather term
    for col in ("est", "low", "high", "mean_est"):
        d[col + "_w"] = d[col] * d.wm
    # ablation: the new-team prior alone (undo it: the estimate used min(participation, new team))
    presence = np.minimum(d.part_mult, d.nt_mult)
    d["est_nont"] = np.where(presence > 0, d.est / presence * d.part_mult, d.est)
    return d


def spearman(g: pd.DataFrame, col: str) -> float:
    vals = []
    for _, x in g.groupby(["season", "week", "pos"]):
        if len(x) >= 8 and x[col].nunique() > 1 and x.actual.nunique() > 1:
            vals.append(x[col].rank().corr(x.actual.rank()))
    return float(np.nanmean(vals)) if vals else float("nan")


def metrics(g: pd.DataFrame, est: str, low: str, high: str) -> dict:
    e = g[est] - g.actual
    return {"MAE": e.abs().mean(), "bias": e.mean(), "rho": spearman(g, est), "cov68": ((g.actual >= g[low] - 1e-9) & (g.actual <= g[high] + 1e-9)).mean() * 100}


def ba(g: pd.DataFrame, *, est_b="est_b", low_b="low_b", high_b="high_b", est="est_w", low="low_w", high="high_w") -> dict:
    b, a = metrics(g, est_b, low_b, high_b), metrics(g, est, low, high)
    return {"n": len(g), **{f"{k} before": v for k, v in b.items()}, **{f"{k} after": v for k, v in a.items()}}


def pools(d: pd.DataFrame) -> dict[str, pd.DataFrame]:
    h = d[d.season.isin(HEADLINE)]
    return {"played player-weeks": h[h.played], "top-N pool (non-appearances 0)": h[h.pool], "pool, top-12 by estimate": h[h.pool & (h["rank"] <= 12)]}


def overall_table(d: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({k: ba(g) for k, g in pools(d).items()}).T


def position_table(d: pd.DataFrame) -> pd.DataFrame:
    g = d[d.season.isin(HEADLINE) & d.played]
    return pd.DataFrame({pos: ba(g[g.pos == pos]) for pos in POSITIONS}).T


def cov_table(d: pd.DataFrame) -> pd.DataFrame:
    """68% interval coverage before / after, by projected tier, handcuffs and position (played + non-appearances)."""

    g = d[d.season.isin(HEADLINE)]
    rows = {}
    for tier in ["top-12", "13-24", "25-48", "deeper"]:
        x = g[g.tier == tier]
        rows[f"tier {tier}"] = {"n": len(x), "cov before": x.covered_b.mean() * 100, "cov after": ((x.actual >= x.low_w - 1e-9) & (x.actual <= x.high_w + 1e-9)).mean() * 100}
    for label, x in (("handcuff, starter Out/Doubtful", g[g.role == "handcuff_starter_out"]), ("backup QB role", g[g.role == "backup_qb"])):
        rows[label] = {"n": len(x), "cov before": x.covered_b.mean() * 100, "cov after": ((x.actual >= x.low_w - 1e-9) & (x.actual <= x.high_w + 1e-9)).mean() * 100}
    for pos in ["QB", "RB", "WR", "TE", "K"]:
        x = g[g.pos == pos]
        rows[f"position {pos}"] = {"n": len(x), "cov before": x.covered_b.mean() * 100, "cov after": ((x.actual >= x.low_w - 1e-9) & (x.actual <= x.high_w + 1e-9)).mean() * 100}
    return pd.DataFrame(rows).T


def mean_table(d: pd.DataFrame) -> pd.DataFrame:
    g = d[d.season.isin(HEADLINE) & d.pool]
    rows = {}
    for pos in POSITIONS + ["all"]:
        x = g if pos == "all" else g[g.pos == pos]
        rows[pos] = {"n": len(x), "point bias": (x.est_w - x.actual).mean(), "mean-field bias": (x.mean_est_w - x.actual).mean(),
                     "point MAE": (x.est_w - x.actual).abs().mean(), "mean-field MAE": (x.mean_est_w - x.actual).abs().mean(),
                     "point rho": spearman(x, "est_w") if pos != "all" else np.nan, "mean-field rho": spearman(x, "mean_est_w") if pos != "all" else np.nan}
    return pd.DataFrame(rows).T


def lineup_table(d: pd.DataFrame) -> pd.DataFrame:
    """A typical lineup per NFL team-week (its best QB1 / RB2 / WR3 / TE1 by point estimate; the same players for both totals),
    total projected vs total actual points, non-appearances 0."""

    rows = {}
    for tag, seas in (("2023-26 holdout", HEADLINE), ("2016-22 fit window", range(2016, 2023))):
        g = d[d.season.isin(list(seas))].sort_values("est", ascending=False)
        x = pd.concat([g[g.pos == pos].groupby(["season", "week", "team"]).head(k) for pos, k in LINEUP.items()])
        t = x.groupby(["season", "week", "team"]).agg(est=("est_w", "sum"), mean_est=("mean_est_w", "sum"), actual=("actual", "sum"), n=("pid", "size"))
        t = t[t.n == sum(LINEUP.values())]
        rows[tag] = {"team-weeks": len(t), "actual total": t.actual.mean(), "point total": t.est.mean(), "mean total": t.mean_est.mean(),
                     "point bias": (t.est - t.actual).mean(), "mean-field bias": (t.mean_est - t.actual).mean(),
                     "point MAE": (t.est - t.actual).abs().mean(), "mean-field MAE": (t.mean_est - t.actual).abs().mean()}
    return pd.DataFrame(rows).T


def wind_table(d: pd.DataFrame) -> pd.DataFrame:
    """Outdoor games (domes and closed roofs excluded) by observed stadium wind; estimate >= 3 before."""

    x = d[(d.roof == "outdoors") & d.wind.notna() & (d.est_b >= 3)]
    rows = {}
    for tag, seas in (("2023-26 holdout", HEADLINE), ("2016-26 all", range(2016, 2027))):
        g = x[x.season.isin(list(seas))]
        for pos in ["QB", "RB", "WR", "TE", "K", "all"]:
            y = g if pos == "all" else g[g.pos == pos]
            for label, z in (("wind >= 15", y[y.wind >= 15]), ("wind >= 20", y[y.wind >= 20]), ("wind < 15", y[y.wind < 15])):
                if len(z) < 15:
                    continue
                rows[(tag, pos, label)] = {"n": len(z), "mean mult": z.wm.mean(), "bias before": (z.est_b - z.actual).mean(), "bias after": (z.est_w - z.actual).mean(),
                                           "bias mean-field": (z.mean_est_w - z.actual).mean(), "MAE before": (z.est_b - z.actual).abs().mean(), "MAE after": (z.est_w - z.actual).abs().mean()}
    out = pd.DataFrame(rows).T
    out.index.names = ["window", "pos", "games"]
    return out


def mover_table(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    """Players whose last game was for another team (prior-season last team != current team), weeks 1+, estimate >= 4, by games
    already played for the new team. Same rows before / after."""

    key = ["season", "week", "pid"]
    b = before[before.status == "ok"][key + ["est", "low", "high"]].rename(columns={"est": "est_b", "low": "low_b", "high": "high_b"})
    d = after[after.status == "ok"].merge(b, on=key, how="left")
    d = d[(d.avail_mult != 0.0) & d.pos.isin(["QB", "RB", "WR", "TE"])]
    d["mover"] = d.team_prior.notna() & (d.team_prior != d.team) & (d.n_prev > 0)
    rel = d[d.est_b >= 4]
    rows = {}
    for tag, seas in (("2016-22 (fit)", range(2016, 2023)), ("2023-26 (holdout)", HEADLINE)):
        g = rel[rel.season.isin(list(seas)) & (rel.week <= 8)]
        for label, sel in (("non-movers, weeks 1-3", g[~g.mover & (g.week <= 3)]), ("movers, 0 games for new team", g[g.mover & (g.n_cur == 0)]),
                           ("movers, 1 game", g[g.mover & (g.n_cur == 1)]), ("movers, 2 games", g[g.mover & (g.n_cur == 2)]), ("movers, 3-6 games", g[g.mover & g.n_cur.between(3, 6)])):
            if len(sel) == 0:
                continue
            rows[(tag, label)] = {"n": len(sel), "played %": sel.played.mean() * 100, "actual": sel.actual.mean(), "est before": sel.est_b.mean(), "est after": sel.est.mean(),
                                  "bias before": (sel.est_b - sel.actual).mean(), "bias after": (sel.est - sel.actual).mean(), "MAE before": (sel.est_b - sel.actual).abs().mean(),
                                  "MAE after": (sel.est - sel.actual).abs().mean(), "cov before": ((sel.actual >= sel.low_b - 1e-9) & (sel.actual <= sel.high_b + 1e-9)).mean() * 100,
                                  "cov after": ((sel.actual >= sel.low - 1e-9) & (sel.actual <= sel.high + 1e-9)).mean() * 100}
    out = pd.DataFrame(rows).T
    out.index.names = ["window", "cohort"]
    return out


def newteam_overall(d: pd.DataFrame) -> pd.DataFrame:
    """The new-team prior alone (estimate with vs without it), on all projected player-weeks."""

    rows = {}
    for tag, seas in (("2016-22 (fit)", range(2016, 2023)), ("2023-26 (holdout)", HEADLINE)):
        g = d[d.season.isin(list(seas)) & d.played]
        rows[tag + ", played"] = {"n": len(g), "MAE without": (g.est_nont - g.actual).abs().mean(), "MAE with": (g.est - g.actual).abs().mean(),
                                  "rho without": spearman(g, "est_nont"), "rho with": spearman(g, "est")}
        g = d[d.season.isin(list(seas)) & d.pool]
        rows[tag + ", pool"] = {"n": len(g), "MAE without": (g.est_nont - g.actual).abs().mean(), "MAE with": (g.est - g.actual).abs().mean(),
                                "rho without": spearman(g, "est_nont"), "rho with": spearman(g, "est")}
    return pd.DataFrame(rows).T


def anchors_table(after: pd.DataFrame) -> pd.DataFrame:
    """Realized points of no-history players who played, by draft round, against the old flat anchor and the new round-aware table."""

    from modules import matchup_win_probability as mwp

    old = {"QB": 12.0, "RB": 4.5, "WR": 5.0, "TE": 3.5, "K": 7.0}
    h = after[(after.status == "no_history") & after.pos.isin(["QB", "RB", "WR", "TE"])].copy()
    pk = h.draft_number
    h["round"] = np.select([pk.isna(), pk <= 32, pk <= 64, pk <= 105], [0, 1, 2, 3], 4)
    h["new_round"] = [mwp.REPLACEMENT_WEEK_BY_ROUND[p][int(r)][0] for p, r in zip(h.pos, h["round"])]
    h["new_unknown"] = [mwp.REPLACEMENT_WEEK[p][0] for p in h.pos]
    h["old"] = h.pos.map(old)
    rows = {}
    for tag, seas in (("2016-22 (fit)", range(2016, 2023)), ("2023-26 (holdout)", HEADLINE)):
        g = h[h.season.isin(list(seas))]
        for pos in ["QB", "RB", "WR", "TE", "all"]:
            x = g if pos == "all" else g[g.pos == pos]
            rows[(tag, pos)] = {"n": len(x), "actual mean": x.actual.mean(), "old anchor": x.old.mean(), "bias old": (x.old - x.actual).mean(), "MAE old": (x.old - x.actual).abs().mean(),
                                "unknown-capital anchor": x.new_unknown.mean(), "bias unknown": (x.new_unknown - x.actual).mean(), "MAE unknown": (x.new_unknown - x.actual).abs().mean(),
                                "by-round anchor": x.new_round.mean(), "bias by-round": (x.new_round - x.actual).mean(), "MAE by-round": (x.new_round - x.actual).abs().mean()}
    out = pd.DataFrame(rows).T
    out.index.names = ["window", "pos"]
    return out


def ros_table(b: pd.DataFrame, a: pd.DataFrame) -> pd.DataFrame:
    """Rest-of-season totals, the audit's pool: 2021-25, position top-N by the BEFORE estimate (QB 24 / RB 48 / WR 60 / TE 24 / K 16),
    every vantage (weeks 1, 5, 9, 13), games through week 17."""

    from projections_audit_analyze import N

    key = ["season", "vantage", "pid"]
    b = b[b.season <= 2025].dropna(subset=["b_last3", "b_std"])
    m = b.merge(a[key + ["ros_est", "ros_mean_est"]].rename(columns={"ros_est": "ros_new", "ros_mean_est": "ros_mean"}), on=key, how="inner")
    m["rank"] = m.groupby(["season", "vantage", "pos"]).ros_est.rank(ascending=False, method="first")
    m = m[m["rank"] <= m.pos.map(N)]
    rows = {}
    for tag, x in [("all", m)] + [(p, m[m.pos == p]) for p in POSITIONS] + [(f"vantage week {v}", m[m.vantage == v]) for v in (1, 5, 9, 13)]:
        def rho(col):
            vals = []
            for _, g in x.groupby(["season", "vantage", "pos"]):
                if len(g) >= 8 and g[col].nunique() > 1 and g.ros_actual.nunique() > 1:
                    vals.append(g[col].rank().corr(g.ros_actual.rank()))
            return float(np.nanmean(vals)) if vals else np.nan
        rows[tag] = {"n": len(x), "MAE before": (x.ros_est - x.ros_actual).abs().mean(), "MAE after": (x.ros_new - x.ros_actual).abs().mean(),
                     "bias % before": (x.ros_est.sum() / x.ros_actual.sum() - 1) * 100, "bias % after (point)": (x.ros_new.sum() / x.ros_actual.sum() - 1) * 100,
                     "bias % after (mean-field)": (x.ros_mean.sum() / x.ros_actual.sum() - 1) * 100, "rho before": rho("ros_est"), "rho after": rho("ros_new")}
    return pd.DataFrame(rows).T


def charts(d: pd.DataFrame, before: pd.DataFrame, after: pd.DataFrame, ros: pd.DataFrame | None, out: Path) -> None:
    """Four PNGs (docs/audits/projections-backtest/07..10): bias by position (mean-field), windy-game bias, new-team movers, coverage + ROS."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out.mkdir(parents=True, exist_ok=True)
    ink, grey, blue, orange = "#1f2933", "#9aa5b1", "#2f6fdb", "#e07b00"
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": grey, "axes.labelcolor": ink, "text.color": ink,
                         "xtick.color": ink, "ytick.color": ink})

    def bars(ax, labels, series, colors, title, ylabel, zero=True):
        w = 0.8 / len(series)
        for i, (name, vals) in enumerate(series):
            xs = np.arange(len(labels)) + i * w - 0.4 + w / 2
            ax.bar(xs, vals, w, label=name, color=colors[i])
            for x, v in zip(xs, vals):
                ax.text(x, v + (0.03 if v >= 0 else -0.03), f"{v:+.2f}" if zero else f"{v:.0f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=7)
        ax.set_xticks(np.arange(len(labels)), labels)
        ax.set_title(title, loc="left", fontsize=10, fontweight="bold")
        ax.set_ylabel(ylabel)
        if zero:
            ax.axhline(0, color=ink, lw=0.8)
        ax.legend(frameon=False, fontsize=8)

    m = mean_table(d).loc[["QB", "RB", "WR", "TE", "all"]]
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    bars(ax[0], list(m.index), [("point estimate", m["point bias"].values), ("mean-calibrated", m["mean-field bias"].values)], [grey, blue],
         "Pool bias (estimate - actual), 2023-26", "points per player-week")
    lt = lineup_table(d)
    bars(ax[1], list(lt.index), [("point total", lt["point bias"].values), ("mean-calibrated total", lt["mean-field bias"].values)], [grey, blue],
         "Typical lineup total (QB1 RB2 WR3 TE1)", "points per team-week")
    fig.tight_layout()
    fig.savefig(out / "07_round2_mean_field.png", dpi=150)
    plt.close(fig)

    w = wind_table(d)
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    for a, win in zip(ax, ["2023-26 holdout", "2016-26 all"]):
        x = w.loc[win].xs("wind >= 15", level="games").loc[["QB", "RB", "WR", "TE", "K"]]
        bars(a, list(x.index), [("before (v3.3)", x["bias before"].values), ("after, point", x["bias after"].values), ("after, mean-calibrated", x["bias mean-field"].values)],
             [grey, blue, orange], f"Wind >= 15 mph games: bias, {win}", "estimate - actual")
    fig.tight_layout()
    fig.savefig(out / "08_round2_wind.png", dpi=150)
    plt.close(fig)

    mv = mover_table(before, after).loc["2023-26 (holdout)"].drop("non-movers, weeks 1-3")
    mv16 = mover_table(before, after).loc["2016-22 (fit)"].drop("non-movers, weeks 1-3")
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    for a, frame, name in ((ax[0], mv16, "2016-22 (fit)"), (ax[1], mv, "2023-26 (holdout)")):
        labels = [c.replace("movers, ", "").replace(" for new team", "") for c in frame.index]
        bars(a, labels, [("before", frame["bias before"].values), ("after", frame["bias after"].values)], [grey, blue], f"New-team movers: bias, {name}", "estimate - actual")
        a.tick_params(axis="x", labelsize=7)
    fig.tight_layout()
    fig.savefig(out / "09_round2_new_team.png", dpi=150)
    plt.close(fig)

    c = cov_table(d)
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    keep = ["tier top-12", "tier 13-24", "tier 25-48", "tier deeper", "handcuff, starter Out/Doubtful", "backup QB role"]
    bars(ax[0], [k.replace("tier ", "").replace("handcuff, starter Out/Doubtful", "handcuff").replace("backup QB role", "backup QB") for k in keep],
         [("before", c.loc[keep, "cov before"].values), ("after", c.loc[keep, "cov after"].values)], [grey, blue], "68% interval coverage (%)", "% of actuals inside the band", zero=False)
    ax[0].axhline(68, color=orange, lw=1, ls="--")
    ax[0].set_ylim(50, 100)
    if ros is not None:
        r = ros.loc[["all", "QB", "RB", "WR", "TE", "K"]]
        bars(ax[1], list(r.index), [("before", r["bias % before"].values), ("after, point", r["bias % after (point)"].values)], [grey, blue],
             "Rest-of-season total bias (% of actual)", "% over / under")
    fig.tight_layout()
    fig.savefig(out / "10_round2_coverage_ros.png", dpi=150)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--charts", type=Path, help="write 07..10 PNGs here")
    ap.add_argument("--before", type=Path, required=True)
    ap.add_argument("--after", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    before, after = load(a.before), load(a.after)
    d = joined(before, after)
    sections = [
        ("Overall, v3.3 -> v3.4 (2023-26, weeks 2+; after includes the wind term at observed wind)", overall_table(d)),
        ("By position (played player-weeks)", position_table(d)),
        ("Fix 1: mean-calibrated field, top-N pool (bias = estimate - actual, non-appearances 0)", mean_table(d)),
        ("Fix 1: typical lineup total (QB1 RB2 WR3 TE1 per team-week)", lineup_table(d)),
        ("Fix 2: no-history players who played, by draft round (anchor vs realized)", anchors_table(after)),
        ("Fix 3: wind (outdoor games; stadium wind observed)", wind_table(d)),
        ("Fix 4: new-team movers", mover_table(before, after)),
        ("Fix 4: new-team prior alone, all projected player-weeks", newteam_overall(d)),
        ("Fix 5: 68% interval coverage", cov_table(d)),
    ]
    ros_b, ros_a = a.before / "ros" / "ros.parquet", a.after / "ros" / "ros.parquet"
    if ros_b.exists() and ros_a.exists():
        sections.append(("Fix 5 and overall: rest-of-season totals (weeks 1-17 vantage 1/5/9/13, 2021-25)", ros_table(pd.read_parquet(ros_b), pd.read_parquet(ros_a))))
    if a.charts:
        ros_tbl = ros_table(pd.read_parquet(ros_b), pd.read_parquet(ros_a)) if ros_b.exists() and ros_a.exists() else None
        charts(d, before, after, ros_tbl, a.charts)
    text = "\n\n".join(f"### {title}\n\n{md(tbl)}" for title, tbl in sections)
    (a.out / "round2_tables.md").write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

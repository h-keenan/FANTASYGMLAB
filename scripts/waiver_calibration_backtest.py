"""Walk-forward backtest of the waiver / FAAB catalyst constants (2021-2025).

    python scripts/waiver_calibration_backtest.py --cache <dir with stats_{season}_{week}.json>

Reuses the throwaway Sleeper weekly-stats cache of ``projection_walkforward.py``
(``fetch`` it first). Nothing is written to ``data/`` and no database is
touched. Results: ``docs/waiver-streaming-calibration-2026-10.md``.

Setup: at every week w in 5..14 of every season, the "free agent" proxy is every
player who played in week w-1 but is NOT among the top ``ROSTERED_N`` of his
position by season-to-date PPR average (a 12-team league keeps ~2x starters on
rosters). Outcome = mean PPR points per week over weeks w..w+3 (a missed game
counts as 0, so availability is priced in). Everything a predictor uses is
known before week w. Constants are chosen on EARLIER seasons only, then scored
on the next season (folds: test 2023, 2024, 2025 with training = all earlier).
Confidence intervals are cluster bootstraps over (season, week).
"""

from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import projection_walkforward as pw  # noqa: E402

ROSTERED_N = {"QB": 24, "RB": 60, "WR": 84, "TE": 24}
POS = ("QB", "RB", "WR", "TE")
WEEKS = range(5, 15)
RNG = np.random.default_rng(7)


def build(table: pd.DataFrame) -> pd.DataFrame:
    """One row per (season, week, player) FA-proxy candidate with features + outcome."""
    rows = []
    for (s, p), g in table[table.pos.isin(POS)].groupby(["season", "pos"]):
        piv = g.pivot_table(index="pid", columns="week", values="pts", aggfunc="sum")
        piv = piv.reindex(columns=range(1, 19))
        played = ~piv.isna()
        pts = piv.fillna(0.0)
        tgt = g.pivot_table(index="pid", columns="week", values="rec_tgt", aggfunc="sum").reindex(columns=range(1, 19)).fillna(0.0)
        rus = g.pivot_table(index="pid", columns="week", values="rush_att", aggfunc="sum").reindex(columns=range(1, 19)).fillna(0.0)
        pa = g.pivot_table(index="pid", columns="week", values="pass_att", aggfunc="sum").reindex(columns=range(1, 19)).fillna(0.0)
        usage = (tgt + rus) if p != "QB" else (pa + rus)
        for w in WEEKS:
            prior_w = list(range(1, w))
            pl = played[prior_w]
            n = pl.sum(axis=1)
            avg = (pts[prior_w].sum(axis=1) / n.replace(0, np.nan))
            rank = avg.rank(ascending=False, method="first")
            ok = (n >= 1) & pl[w - 1] & (rank > ROSTERED_N[p])
            if not ok.any():
                continue
            nxt = pts[[w, w + 1, w + 2, w + 3]].mean(axis=1)
            bound = float(avg[rank == ROSTERED_N[p]].iloc[0]) if (rank == ROSTERED_N[p]).any() else np.nan
            for pid in piv.index[ok.values]:
                gms = [x for x in prior_w if played.at[pid, x]]
                rows.append(dict(
                    season=s, week=w, pos=p, pid=pid, n=int(n[pid]), avg=float(avg[pid]),
                    pts=[float(pts.at[pid, x]) for x in gms],
                    use=[float(usage.at[pid, x]) for x in gms],
                    last=float(pts.at[pid, w - 1]), y=float(nxt[pid]),
                    top_rank=float(rank[pid]), bound=bound,
                ))
    return pd.DataFrame(rows)


def spearman_by_cohort(df: pd.DataFrame, col: str) -> pd.Series:
    out = {}
    for k, g in df.groupby(["season", "week", "pos"]):
        if len(g) >= 8 and g[col].nunique() > 1:
            out[k] = g[col].rank().corr(g.y.rank())
    return pd.Series(out)


def topk_value(df: pd.DataFrame, col: str, k: int = 5) -> pd.Series:
    out = {}
    for key, g in df.groupby(["season", "week", "pos"]):
        if len(g) >= 10:
            out[key] = g.nlargest(k, col, keep="first").y.mean()
    return pd.Series(out)


def boot_ci(series: pd.Series, n=2000) -> tuple[float, float, float]:
    """Cluster (season, week) bootstrap CI of the mean."""
    s = series.dropna()
    cl = s.groupby(level=[0, 1]).mean().values
    if len(cl) == 0:
        return (np.nan,) * 3
    idx = RNG.integers(0, len(cl), (n, len(cl)))
    m = cl[idx].mean(1)
    return float(cl.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def paired_ci(a: pd.Series, b: pd.Series) -> tuple[float, float, float]:
    d = (a - b).dropna()
    return boot_ci(d)


# ------------------------------------------------------------- predictors
def season_avg(r):
    return r["avg"]


def recency_pred(window: int, decay: float, gain: float):
    """Production formulation: baseline * (1 + clip(trend)) where trend compares the
    recency-weighted window of usage to the earlier-season baseline usage."""
    w = np.array([decay ** i for i in range(window)])
    w = w / w.sum()

    def f(r):
        u = r["use"]
        if len(u) < 4:
            return r["avg"]
        recent = np.array(u[::-1][:window])
        ww = w[: len(recent)] / w[: len(recent)].sum()
        usage_rate = float((recent * ww).sum())
        base = np.mean(u[:-window]) if len(u) > window else np.mean(u)
        trend = 0.0 if base <= 0 else np.clip(usage_rate / base - 1.0, -0.4, 0.4)
        return r["avg"] * (1.0 + gain * trend)
    return f


def breakout_flag(min_pts, jump, ratio):
    def f(r):
        p = r["pts"]
        last = p[-1]
        prior = p[:-1]
        base = np.mean(prior) if prior else 0.0
        if last < min_pts or last < base + jump:
            return False
        if base > 0 and last < base * ratio:
            return False
        return True
    return f


def evaluate(cache: Path) -> dict:
    table = pw.load_table(cache)
    df = build(table)
    print(f"FA-proxy rows: {len(df)}, cohorts: {df.groupby(['season','week','pos']).ngroups}")
    res = {}
    seasons = sorted(df.season.unique())

    # ---- 1. which score ranks FAs best?
    df["p_avg"] = df.apply(season_avg, axis=1)
    df["p_last"] = df["last"]
    df["p_last3"] = df.pts.apply(lambda p: np.mean(p[-3:]))
    df["p_last4use"] = df.apply(recency_pred(4, 0.75, 1.0), axis=1)
    test = df[df.season >= 2023]
    print("\n== A. predictor comparison (test 2023-2025), FA proxy, next-4-week PPR")
    rows = []
    for c in ("p_avg", "p_last", "p_last3", "p_last4use"):
        sp = spearman_by_cohort(test, c)
        tk = topk_value(test, c)
        rows.append((c, boot_ci(sp), boot_ci(tk), len(sp)))
        print(f"  {c:11s} spearman {rows[-1][1][0]:.3f} [{rows[-1][1][1]:.3f},{rows[-1][1][2]:.3f}]  top5 next4 pts {rows[-1][2][0]:.2f} [{rows[-1][2][1]:.2f},{rows[-1][2][2]:.2f}] cohorts {len(sp)}")
    res["A"] = rows
    base_sp, base_tk = spearman_by_cohort(test, "p_avg"), topk_value(test, "p_avg")
    for c in ("p_last", "p_last3", "p_last4use"):
        d1 = paired_ci(spearman_by_cohort(test, c), base_sp)
        d2 = paired_ci(topk_value(test, c), base_tk)
        print(f"   {c} - p_avg: spearman {d1[0]:+.3f} [{d1[1]:+.3f},{d1[2]:+.3f}]  top5 {d2[0]:+.2f} [{d2[1]:+.2f},{d2[2]:+.2f}]")

    # ---- 2. recency window / decay / gain, walk-forward
    print("\n== B. recency window grid (walk-forward: pick on earlier seasons, score next)")
    grid = list(itertools.product((2, 3, 4, 6), (0.6, 0.75, 0.9), (0.0, 0.5, 1.0, 2.0)))
    cache_pred = {}
    for g in grid:
        f = recency_pred(*g)
        cache_pred[g] = df.apply(f, axis=1)
    cur = (4, 0.75, 1.0)  # production: 4 games, weights .4/.3/.2/.1 ~ decay 0.75, full trend
    for t in (2023, 2024, 2025):
        tr = df[df.season < t]
        scores = {}
        for g in grid:
            d = tr.assign(pp=cache_pred[g].loc[tr.index])
            scores[g] = spearman_by_cohort(d, "pp").mean()
        best = max(scores, key=scores.get)
        te = df[df.season == t]
        out = []
        for g in (cur, best, (4, 0.75, 0.0)):
            d = te.assign(pp=cache_pred[g].loc[te.index])
            out.append((g, spearman_by_cohort(d, "pp").mean()))
        print(f"  test {t}: best-on-train {best} (train rho {scores[best]:.4f}, current {scores[cur]:.4f}); test rho: "
              + ", ".join(f"{g}={v:.4f}" for g, v in out))
    allbest = {g: spearman_by_cohort(df.assign(pp=cache_pred[g]), "pp").mean() for g in grid}
    print("  all-season mean rho: current", round(allbest[cur], 4), "no-trend", round(allbest[(4, .75, 0.0)], 4),
          "max", max(allbest.items(), key=lambda kv: kv[1]))
    d = paired_ci(spearman_by_cohort(df.assign(pp=cache_pred[cur]), "pp"), spearman_by_cohort(df.assign(pp=cache_pred[(4, .75, 0.0)]), "pp"))
    print(f"  current vs no-trend (all seasons) rho diff {d[0]:+.4f} [{d[1]:+.4f},{d[2]:+.4f}]")

    # ---- 3. breakout thresholds
    print("\n== C. breakout catalyst: lift of flagged FAs over the season-average expectation")
    df["est"] = df["p_avg"]

    def lift(flag):
        fl = df.apply(flag, axis=1)
        s = df[fl]
        if len(s) < 30:
            return None
        ratio = s.y.sum() / max(s.est.sum(), 1e-9)       # multiplier supported vs season average
        resid = (s.y - s.est)
        cl = resid.groupby([s.season, s.week]).mean().values
        idx = RNG.integers(0, len(cl), (1000, len(cl)))
        ratios = []
        sg = s.groupby([s.season, s.week])
        ys = sg.y.sum().values
        es = sg.est.sum().values
        for ii in idx[:1000]:
            ratios.append(ys[ii].sum() / max(es[ii].sum(), 1e-9))
        return len(s), ratio, float(np.percentile(ratios, 2.5)), float(np.percentile(ratios, 97.5)), s.y.mean()
    cfg = []
    for mp, jp, rt in itertools.product((8, 10, 12, 15), (4, 6, 8, 10), (1.4, 1.8, 2.2)):
        r = lift(breakout_flag(mp, jp, rt))
        if r:
            cfg.append(((mp, jp, rt), r))
    for (c, r) in cfg:
        if c in {(12, 8, 1.8), (8, 4, 1.4), (10, 6, 1.8), (15, 8, 1.8), (12, 6, 1.4), (12, 10, 2.2)}:
            print(f"  {c}: n={r[0]} next4/season-avg = {r[1]:.3f} [{r[2]:.3f},{r[3]:.3f}], mean next4 pts {r[4]:.2f}")
    cur_r = dict(cfg)[(12, 8, 1.8)]
    print("  best by multiplier among n>=300:", max(((c, r) for c, r in cfg if r[0] >= 300), key=lambda x: x[1][1]))
    res["C"] = cfg
    # last-week-only (no-threshold) benchmark
    allr = df.y.sum() / df.est.sum()
    print(f"  all FA rows: next4/season-avg = {allr:.3f}; breakout-current = {cur_r[1]:.3f} => relative lift {cur_r[1]/allr:.3f} (code multiplier 1.20)")
    # excluding the breakout game from the baseline (his "own earlier baseline")
    fl = df.apply(breakout_flag(12, 8, 1.8), axis=1)
    s = df[fl]
    pre = s.pts.apply(lambda p: np.mean(p[:-1]) if len(p) > 1 else np.nan)
    ok = pre.notna() & (pre > 0)
    print(f"  breakout (12,8,1.8) vs PRE-breakout baseline: next4/pre-baseline = {s.y[ok].sum()/pre[ok].sum():.3f} (n={ok.sum()})")

    print("\n== D. role catalyst: usage trending up (production formulation, >=4 games, trend>=0.05)")
    tr = df.apply(lambda r: recency_pred(4, 0.75, 1.0)(r) / r["avg"] - 1.0 if r["avg"] > 0 and len(r["use"]) >= 4 else np.nan, axis=1)
    for thr in (0.05, 0.10, 0.15, 0.20, 0.30):
        s = df[tr >= thr]
        sg = s.groupby(["season", "week"])
        ys, es = sg.y.sum().values, sg.est.sum().values
        idx = RNG.integers(0, len(ys), (1000, len(ys)))
        rr = [ys[i].sum() / es[i].sum() for i in idx]
        print(f"  trend>={thr:.2f}: n={len(s)} next4/season-avg = {s.y.sum()/s.est.sum():.3f} [{np.percentile(rr,2.5):.3f},{np.percentile(rr,97.5):.3f}]  (code gate 0.05, multiplier 1.15)")

    print("\n== E. Priority-add cutoff: top-q of FA score (v3-style usage-trend score) per cohort; hit = next4 pts beat rostered boundary")
    df["score"] = cache_pred[cur]
    df["hit"] = df.y > df.bound
    for q in (0.50, 0.70, 0.85, 0.90, 0.95, 0.98):
        grp = df.groupby(["season", "week", "pos"])
        sel = df[(grp.score.transform(lambda x: x.quantile(q)) <= df.score) & (grp.score.transform("size") >= 8)]
        cl = sel.groupby(["season", "week"]).hit.mean().values
        idx = RNG.integers(0, len(cl), (1000, len(cl)))
        m = cl[idx].mean(1)
        print(f"  top {int((1-q)*100):2d}% : n={len(sel)} hit-rate {cl.mean():.3f} [{np.percentile(m,2.5):.3f},{np.percentile(m,97.5):.3f}]  mean next4 {sel.y.mean():.2f}")
    print("  top-k per position cohort (k): hit rate / mean next4")
    for k in (1, 2, 3, 5):
        rk = df.groupby(["season", "week", "pos"]).score.rank(method="first", ascending=False)
        sel = df[(rk <= k) & (df.groupby(["season", "week", "pos"]).score.transform("size") >= 8)]
        print(f"   k={k}: n={len(sel)} hit {sel.hit.mean():.3f} next4 {sel.y.mean():.2f}")

    print("\n== F. FAAB base_pct by position (code: RB .10, WR .07, TE .05, QB .02): top-3 FA per week")
    rk = df.groupby(["season", "week", "pos"]).score.rank(method="first", ascending=False)
    sel = df[(rk <= 3) & (df.groupby(["season", "week", "pos"]).score.transform("size") >= 8)]
    sel = sel.assign(par=sel.y - sel.bound)
    print(sel.groupby("pos").agg(n=("y", "size"), next4=("y", "mean"), hit=("hit", "mean"), par=("par", "mean")).round(3).to_string())
    return dict(df=df, cfg=cfg)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, required=True)
    a = ap.parse_args(argv)
    evaluate(a.cache)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

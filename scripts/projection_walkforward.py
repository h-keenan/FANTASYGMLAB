"""Walk-forward evaluation of the projection model (v2/v3 usage empirical-Bayes).

Every season is scored with constants fitted only on EARLIER seasons, so the
numbers cannot be flattered by tuning on the year being scored. The newest
(partial) season is the frozen holdout. Results: ``docs/projections-v3-walkforward.md``.

    python scripts/projection_walkforward.py fetch      # download 2021+ stats into a throwaway cache
    python scripts/projection_walkforward.py evaluate   # print per-season tables

The cache lives outside the repo (``--cache``, default: system temp dir).
Nothing is written to ``data/`` and no database is touched.

What is fitted per fold (training seasons only): the per-position usage
coefficients (least squares), the pooled shrinkage settings (usage half-life,
efficiency half-life, k), the per-position error-scale knots and the
per-position 16th/84th percentile interval multipliers. The vectorised
estimator below is the same maths as ``player_projections._player_usage_trend``
(checked equal to 1e-14 on a random sample).
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

POS = ("QB", "RB", "WR", "TE", "K")
OFF = ("QB", "RB", "WR", "TE")
FEAT = {"QB": ("pass_att", "rush_att"), "RB": ("rush_att", "rec_tgt"), "WR": ("rec_tgt", "rush_att"),
        "TE": ("rec_tgt", "rush_att"), "K": ()}
POOL_N = {"QB": 24, "RB": 48, "WR": 60, "TE": 24, "K": 16}
WEEKS = range(4, 18)
INF = 1e9
HLS = [1.5, 2, 3, 4, 6, 10, INF]
KS = [1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48]
FIRST_SEASON = 2021
# Projections v2 as shipped in #1388 (tuned on 2024 only), frozen here so the
# comparison stays meaningful after the constants in player_projections change.
V2_USAGE_COEF = {"QB": (-0.0593, 0.3995, 1.0498), "RB": (-0.2703, 0.7115, 1.3692), "WR": (-0.0125, 1.7488, 0.8074),
                 "TE": (0.0920, 1.6841, 1.5814), "K": (8.0847,)}
V2_SHRINKAGE = {"QB": (2.0, INF, 4.0), "RB": (3.0, 3.0, 6.0), "WR": (6.0, INF, 3.0), "TE": (4.0, INF, 3.0), "K": (2.0, INF, 32.0)}
_Q = "&".join(f"position[]={p}" for p in POS)


# ---------------------------------------------------------------- data
def _get(url: str, path: Path) -> None:
    if path.exists() and path.stat().st_size > 100:
        return
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FantasyDesk-walkforward/1.0"})
            path.write_bytes(urllib.request.urlopen(req, timeout=90).read())
            return
        except Exception:
            time.sleep(2)
    path.write_bytes(b"[]")


def fetch(cache: Path, last_season: int) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    jobs = []
    for s in range(FIRST_SEASON, last_season + 1):
        for w in range(1, 19):
            jobs.append((f"https://api.sleeper.com/stats/nfl/{s}/{w}?season_type=regular&{_Q}", cache / f"stats_{s}_{w}.json"))
            jobs.append((f"https://api.sleeper.com/projections/nfl/{s}/{w}?season_type=regular&{_Q}", cache / f"proj_{s}_{w}.json"))
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(lambda a: _get(*a), jobs))


def load_table(cache: Path) -> pd.DataFrame:
    rows = []
    for p in sorted(cache.glob("stats_*_*.json")):
        _, s, w = p.stem.split("_")
        s, w = int(s), int(w)
        sp = {}
        pp_ = cache / f"proj_{s}_{w}.json"
        if pp_.exists():
            for r in json.loads(pp_.read_text()):
                v = (r.get("stats") or {}).get("pts_ppr")
                if v is not None:
                    sp[r["player_id"]] = float(v)
        for r in json.loads(p.read_text()):
            pos = str((r.get("player") or {}).get("position") or "").upper()
            st = r.get("stats") or {}
            if pos not in POS or not float(st.get("gp") or 0) > 0:
                continue
            rows.append(dict(season=s, week=w, pid=r["player_id"], pos=pos, pts=float(st.get("pts_ppr") or 0.0),
                             pass_att=float(st.get("pass_att") or 0), rush_att=float(st.get("rush_att") or 0),
                             rec_tgt=float(st.get("rec_tgt") or 0), sproj=sp.get(r["player_id"])))
    return pd.DataFrame(rows)


class Panel:
    """players x 18 weeks matrices for one season and position."""

    def __init__(self, table: pd.DataFrame, season: int, pos: int):
        d = table[(table.season == season) & (table.pos == pos) & (table.week <= 18)]
        self.season, self.pos = season, pos
        self.pids = sorted(d.pid.unique())
        ix = {p: i for i, p in enumerate(self.pids)}
        n = len(self.pids)
        self.P = np.zeros((n, 18), bool)
        self.A = np.zeros((n, 18))
        self.S = np.full((n, 18), np.nan)
        self.F = np.zeros((n, 18, len(FEAT[pos])))
        for r in d.itertuples(index=False):
            i, w = ix[r.pid], r.week - 1
            self.P[i, w], self.A[i, w] = True, r.pts
            if r.sproj is not None and r.sproj == r.sproj:
                self.S[i, w] = r.sproj
            for j, f in enumerate(FEAT[pos]):
                self.F[i, w, j] = getattr(r, f)


# ---------------------------------------------------------------- model
def fit_coef(panels: list[Panel]) -> np.ndarray:
    pos = panels[0].pos
    y = np.concatenate([p.A[p.P] for p in panels])
    if not FEAT[pos]:
        return np.array([y.mean()])
    X = np.vstack([p.F[p.P] for p in panels])
    return np.linalg.lstsq(np.hstack([np.ones((len(X), 1)), X]), y, rcond=None)[0]


def _w(age, hl):
    return np.ones_like(age) if hl >= INF else 0.5 ** (age / hl)


def estimate(p: Panel, coef, hu, hr, k, weeks=WEEKS) -> pd.DataFrame:
    """One row per player-week with >=1 earlier game who played that week."""
    implied = coef[0] + (p.F @ coef[1:] if len(coef) > 1 else 0.0)
    implied = np.broadcast_to(implied, p.A.shape)
    out = []
    for w in weeks:
        c = w - 1
        mask = p.P[:, :c]
        games = mask.sum(1)
        ok = (games > 0) & p.P[:, c]
        if not ok.any():
            continue
        last = np.where(mask.any(1), c - 1 - np.argmax(mask[:, ::-1], axis=1), 0)
        age = np.maximum(last[:, None] - np.arange(c)[None, :], 0).astype(float)
        m = mask.astype(float)
        wu, wr = _w(age, hu) * m, _w(age, hr) * m
        with np.errstate(invalid="ignore", divide="ignore"):
            imean = (wu * implied[:, :c]).sum(1) / wu.sum(1)
            rmean = (wr * (p.A[:, :c] - implied[:, :c])).sum(1) / wr.sum(1)
        est = imean + games / (games + k) * rmean
        naive = (m * p.A[:, :c]).sum(1) / np.maximum(games, 1)
        for i in np.where(ok)[0]:
            out.append((p.season, w, p.pos, p.pids[i], est[i], int(games[i]), p.A[i, c], p.S[i, c], naive[i]))
    return pd.DataFrame(out, columns=["season", "week", "pos", "pid", "est", "games", "actual", "sproj", "naive"])


def add_pool(f: pd.DataFrame) -> pd.DataFrame:
    f = f.copy()
    f["pool"] = False
    for _, g in f.groupby(["season", "week", "pos"]):
        top = g[g.sproj.notna()].sort_values("sproj", ascending=False).head(POOL_N[g.pos.iloc[0]])
        f.loc[top.index, "pool"] = True
    return f


def tune_pooled(panels: dict, coefs: dict, seasons: list[int]) -> tuple:
    """Grid-search one (usage half-life, efficiency half-life, k) shared by QB/RB/WR/TE."""
    best = None
    for hu, hr, k in itertools.product(HLS, HLS, KS):
        total = 0.0
        for pos in OFF:
            ef = pd.concat([estimate(panels[(s, pos)], coefs[pos], hu, hr, k) for s in seasons])
            ef = add_pool(ef)
            pool = ef[ef.pool]
            allp = ef[ef.sproj.notna()]
            total += 0.5 * ((pool.est - pool.actual).abs().mean() + (allp.est - allp.actual).abs().mean())
        if best is None or total < best[0]:
            best = (total, hu, hr, k)
    return best[1:]


def tune_kicker(panels: dict, coef, seasons: list[int]) -> float:
    best = None
    for k in KS:
        ef = pd.concat([estimate(panels[(s, "K")], coef, INF, INF, k) for s in seasons])
        mae = (ef.est - ef.actual).abs().mean()
        if best is None or mae < best[0]:
            best = (mae, k)
    return best[1]


def conf_of(games):
    return np.where(games >= 4, 2, np.where(games >= 2, 1, 0))


def fit_interval(f: pd.DataFrame) -> dict:
    """Per position: 5-knot absolute-error scale and 16th/84th percentile of error/scale."""
    model = {}
    for pos in POS:
        g = f[f.pos == pos]
        e, err = g.est.values, g.actual.values - g.est.values
        qs = np.quantile(e, np.linspace(0, 1, 6))
        knots, mae = [], []
        for a, b in zip(qs[:-1], qs[1:]):
            m = (e >= a) & (e <= b)
            knots.append(e[m].mean())
            mae.append(np.abs(err[m]).mean())
        scale = np.interp(e, knots, mae)
        r = err / scale
        model[pos] = dict(knots=knots, mae=mae, z=(np.percentile(r, 16), np.percentile(r, 84)))
    return model


def apply_interval(model: dict, f: pd.DataFrame):
    lo, hi = np.zeros(len(f)), np.zeros(len(f))
    for pos in POS:
        m = (f.pos == pos).values
        sc = np.interp(f.est.values[m], model[pos]["knots"], model[pos]["mae"])
        lo[m] = np.maximum(0, f.est.values[m] + model[pos]["z"][0] * sc)
        hi[m] = np.maximum(0, f.est.values[m] + model[pos]["z"][1] * sc)
    return lo, hi


def pairwise(g: pd.DataFrame, col: str) -> float:
    hit = tot = 0.0
    for _, gg in g.groupby(["season", "week", "pos"]):
        a, e = gg.actual.values, gg[col].values
        da, de = a[:, None] - a[None, :], e[:, None] - e[None, :]
        m = da > 0
        tot += m.sum()
        hit += ((de > 0) & m).sum() + 0.5 * ((de == 0) & m).sum()
    return hit / tot if tot else float("nan")


def metrics(g: pd.DataFrame, col: str, lo="lo", hi="hi") -> dict:
    e = g[col] - g.actual
    r = dict(n=len(g), mae=e.abs().mean(), bias=e.mean(), hit=pairwise(g, col))
    if col == "est" and lo in g:
        r["cov"] = ((g.actual >= g[lo]) & (g.actual <= g[hi])).mean()
    return r


# ---------------------------------------------------------------- driver
def evaluate(cache: Path, last_season: int) -> None:
    table = load_table(cache)
    seasons = sorted(table.season.unique())
    panels = {(s, p): Panel(table, s, p) for s in seasons for p in POS}
    v2 = V2_SHRINKAGE
    v2coef = {p: np.array(c) for p, c in V2_USAGE_COEF.items()}
    rows = []
    for test in seasons[1:]:
        train = [s for s in seasons if s < test]
        coefs = {p: fit_coef([panels[(s, p)] for s in train]) for p in POS}
        hu, hr, k = tune_pooled(panels, coefs, train)
        par = {p: (hu, hr, k) for p in OFF}
        par["K"] = (INF, INF, tune_kicker(panels, coefs["K"], train))
        ftr = pd.concat([estimate(panels[(s, p)], coefs[p], *par[p]) for s in train for p in POS], ignore_index=True)
        interval = fit_interval(ftr)
        fte = add_pool(pd.concat([estimate(panels[(test, p)], coefs[p], *par[p]) for p in POS], ignore_index=True))
        fte["lo"], fte["hi"] = apply_interval(interval, fte)
        f2 = pd.concat([estimate(panels[(test, p)], v2coef[p], *v2[p]) for p in POS], ignore_index=True)
        fte["est_v2"] = f2.set_index(["week", "pos", "pid"]).est.reindex(pd.MultiIndex.from_frame(fte[["week", "pos", "pid"]])).values
        print(f"== {test}: pooled (usage HL, efficiency HL, k) = ({hu}, {hr}, {k}), train {train[0]}-{train[-1]}")
        for name, g in (("relevant players", fte[fte.pool]), ("all with Sleeper proj", fte[fte.sproj.notna()])):
            for label, col in (("v3 (walk-forward)", "est"), ("v2 as shipped", "est_v2"), ("season average", "naive"), ("Sleeper", "sproj")):
                print(f"  {name:24s} {label:18s}", {a: round(b, 3) for a, b in metrics(g, col).items()})
        print("  coverage, all eligible:", round(((fte.actual >= fte.lo) & (fte.actual <= fte.hi)).mean(), 3))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=("fetch", "evaluate"))
    ap.add_argument("--cache", type=Path, default=Path(tempfile.gettempdir()) / "projection_walkforward")
    ap.add_argument("--last-season", type=int, default=2026)
    a = ap.parse_args(argv)
    if a.command == "fetch":
        fetch(a.cache, a.last_season)
    else:
        evaluate(a.cache, a.last_season)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

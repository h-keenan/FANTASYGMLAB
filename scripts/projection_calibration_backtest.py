"""Backtest for the 2026-11 projection calibration pass (re-run weekly).

Reproduces the headline numbers in ``docs/projection-calibration-2026-11.md``
and prints the before/after tables for each calibration item:

    1. league-scoring conversion   (bias / MAE of projected vs actual LEAGUE points)
    2. win-probability spread      (Brier / logloss / reliability, fit early weeks, scored on later)
    3. position shrink             (calibration slope + MAE walk-forward: fit 2024->2025, 2024-25->2026)
    4. prior-season seeding        (week-1 coverage, weeks 2-4 MAE)
    5. playoff-odds slope prior    (held-out game Brier at slope 1.0 vs pooled prior)

    python scripts/projection_calibration_backtest.py fetch   --cache DIR [--seasons 2024 2025 2026]
    python scripts/projection_calibration_backtest.py report  --cache DIR [--leagues DIR] [--items 1 2 3 4 5]

``--cache`` holds Sleeper public ``/stats/nfl/regular/{season}/{week}`` and
``/projections/...`` payloads (``stats_{season}_{week}.json``,
``proj_{season}_{week}.json``). ``--leagues`` holds crawled public league
bundles (``{league_id}.json`` = ``{"league", "rosters", "matchups": {week:
[...]}}``, the public Sleeper endpoints of the same names); without it, items 2
and 5 are skipped. Nothing here touches ``data/players.db`` or the app's caches.
Every estimate is point-in-time: the shipped estimator only sees earlier games.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import player_projections as pp  # noqa: E402
from modules import projection_calibration as cal  # noqa: E402

POS = ("QB", "RB", "WR", "TE", "K")
POOL_N = {"QB": 24, "RB": 48, "WR": 60, "TE": 24, "K": 16}
_API = "https://api.sleeper.com"
_Q = "&".join(f"position[]={p}" for p in POS)
# Sleeper stat key -> weekly-row field (same names modules.sleeper retains).
_ROW_FIELDS = {
    "rec": "receptions", "rec_yd": "receiving_yards", "rec_td": "receiving_tds", "rush_yd": "rushing_yards",
    "rush_td": "rushing_tds", "pass_yd": "passing_yards", "pass_td": "passing_tds", "pass_int": "passing_interceptions",
    "fum_lost": "fumbles_lost", "pass_cmp": "passing_completions", "pass_att": "pass_attempts",
    "rush_att": "rush_attempts", "rec_tgt": "targets",
}


# ------------------------------------------------------------------ data
def _get(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "fantasydesk-backtest/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read())
        except Exception:
            if attempt == 2:
                raise
    return None


def fetch(cache: Path, seasons: List[int]) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    for season in seasons:
        for week in range(1, 19):
            for prefix, path in (("stats", "stats"), ("proj", "projections")):
                out = cache / f"{prefix}_{season}_{week}.json"
                if out.exists():
                    continue
                url = f"{_API}/{path}/nfl/{season}/{week}?season_type=regular&{_Q}"
                try:
                    data = _get(url)
                except Exception:
                    continue
                if data:
                    out.write_text(json.dumps(data))


def load_season(cache: Path, season: int) -> Dict[int, List[dict]]:
    out: Dict[int, List[dict]] = {}
    for week in range(1, 19):
        path = cache / f"stats_{season}_{week}.json"
        if path.exists():
            data = json.loads(path.read_text())
            if isinstance(data, list):
                out[week] = data
    return out


def load_sleeper_proj(cache: Path, season: int) -> Dict[int, Dict[str, float]]:
    out: Dict[int, Dict[str, float]] = {}
    for week in range(1, 19):
        path = cache / f"proj_{season}_{week}.json"
        if path.exists():
            data = json.loads(path.read_text())
            if isinstance(data, list):
                out[week] = {str(r["player_id"]): (r.get("stats") or {}).get("pts_ppr") for r in data if isinstance(r, dict)}
    return out


def game_row(week: int, record: dict) -> dict:
    stats = record.get("stats") or {}
    row = {"week": week, "fantasy_points_ppr": float(stats.get("pts_ppr") or 0.0), "games_played": 1.0}
    for key, field in _ROW_FIELDS.items():
        row[field] = float(stats.get(key) or 0.0)
    return row


def league_points(stats: dict, scoring: Dict[str, float]) -> float:
    return sum(weight * float(stats.get(key) or 0.0) for key, weight in scoring.items() if key in stats)


class Season:
    """Point-in-time view of one season's weekly stats."""

    def __init__(self, cache: Path, season: int, prior: "Season | None" = None):
        self.season = season
        self.prior = prior
        self.stats = load_season(cache, season)
        self.sleeper = load_sleeper_proj(cache, season)
        self.pos: Dict[str, str] = {}
        self.exp: Dict[str, Any] = {}
        self.played: Dict[int, Dict[str, dict]] = {}
        self.raw: Dict[tuple, dict] = {}
        self.teams_played: Dict[int, set] = {}
        self.team: Dict[tuple, str] = {}
        for week, rows in self.stats.items():
            played, teams = {}, set()
            for record in rows:
                pid = str(record["player_id"])
                position = str((record.get("player") or {}).get("position") or "").upper()
                if position in POS:
                    self.pos[pid] = position
                    self.exp[pid] = (record.get("player") or {}).get("years_exp")
                    st = record.get("stats") or {}
                    if float(st.get("gp") or 0) > 0:
                        played[pid] = game_row(week, record)
                        self.raw[(week, pid)] = st
                if float((record.get("stats") or {}).get("gp") or 0) > 0 and record.get("team"):
                    teams.add(record["team"])
                if record.get("team"):
                    self.team[(pid, week)] = record["team"]
            self.played[week], self.teams_played[week] = played, teams

    def history(self, pid: str, before_week: int, carry_prior: bool = False, carry_offset: float = 0.0) -> List[dict]:
        rows = [self.played[w][pid] for w in sorted(self.played) if w < before_week and pid in self.played[w]]
        if carry_prior and self.prior is not None:
            shift = 18 + carry_offset
            old = self.prior.history(pid, 99)
            rows = [dict(r, week=r["week"] - shift) for r in old] + rows
        return rows

    def panel(self, weeks=range(2, 19), **history_kwargs) -> pd.DataFrame:
        """One row per (week, player) with a point-in-time estimate from games before ``week``."""

        out = []
        for week in sorted(self.played):
            if week not in weeks:
                continue
            pids = {p for w in self.played if w < week for p in self.played[w]}
            if history_kwargs.get("carry_prior") and self.prior is not None:
                pids |= {p for w in self.prior.played for p in self.prior.played[w]}
            for pid in pids:
                position = self.pos.get(pid)
                if position is None:
                    continue
                prior_rows = self.history(pid, week, **history_kwargs)
                if not prior_rows:
                    continue
                as_of = max(r["week"] for r in prior_rows)
                trend = pp._player_usage_trend(prior_rows, position=position, upto_week=as_of)
                if trend is None:
                    continue
                est = max(0.0, float(trend["baseline_ppr"]))
                lo, hi = pp._v2_range(est, position, pp._v2_confidence(trend["games_played"]))
                did = pid in self.played[week]
                sleeper = self.sleeper.get(week, {}).get(pid)
                out.append({
                    "season": self.season, "week": week, "pid": pid, "pos": position, "est": est, "lo": lo, "hi": hi,
                    "games": trend["games_played"], "played": did,
                    "actual": self.played[week][pid]["fantasy_points_ppr"] if did else np.nan,
                    "avg": float(trend["simple_avg_ppr"]),
                    "sleeper": float(sleeper) if sleeper is not None else np.nan,
                    "yexp": self.exp.get(pid),
                })
        return pd.DataFrame(out)


def relevant(df: pd.DataFrame) -> pd.DataFrame:
    """Sleeper's top-N per position-week among players who played (the audit's 'relevant' pool)."""

    d = df[df.played & df.sleeper.notna()].copy()
    d["rk"] = d.groupby(["season", "week", "pos"]).sleeper.rank(ascending=False, method="first")
    return d[d.rk <= d.pos.map(POOL_N)]


def phi(z):
    return 0.5 * (1.0 + np.vectorize(math.erf)(np.asarray(z, dtype=float) / math.sqrt(2.0)))


def brier(p, y):
    p = np.clip(np.asarray(p, dtype=float), 1e-4, 1 - 1e-4)
    return float(((p - y) ** 2).mean())


def logloss(p, y):
    p = np.clip(np.asarray(p, dtype=float), 1e-4, 1 - 1e-4)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


# ------------------------------------------------------------------ leagues
def load_leagues(path: Path | None) -> List[dict]:
    if path is None or not path.exists():
        return []
    out = []
    for file in sorted(path.glob("*.json")):
        bundle = json.loads(file.read_text())
        league = bundle.get("league") or {}
        if (league.get("settings") or {}).get("best_ball"):
            continue
        out.append(bundle)
    return out


def scoring_format(scoring: Dict[str, float]) -> str:
    ptd = scoring.get("pass_td", 4)
    return f"rec{scoring.get('rec', 0):g}|ptd{ptd:g}|{'TEP' if scoring.get('bonus_rec_te') else 'noTEP'}"


# ------------------------------------------------------------------ item 1
def item1_scoring(s26: Season, leagues: List[dict], weeks=range(2, 9), shrink_ks=(0.0, 4.0, 8.0)) -> pd.DataFrame:
    """Projected vs actual points in each league's own scoring (relevant pool)."""

    base = relevant(s26.panel(weeks=weeks))
    base = base[base.pos.isin(cal.CONVERTIBLE_POSITIONS)]
    formats: Dict[str, tuple] = {}
    for bundle in leagues:
        scoring = cal.numeric_scoring_settings(bundle["league"].get("scoring_settings"))
        key = json.dumps(scoring, sort_keys=True)
        entry = formats.setdefault(key, [scoring, 0])
        entry[1] += 1
    hist = {(r.week, r.pid): s26.history(r.pid, r.week) for r in base.itertuples()}
    rows = []
    for scoring, n_leagues in formats.values():
        fmt = scoring_format(scoring)
        for r in base.itertuples():
            actual = league_points(s26.raw[(r.week, r.pid)], scoring)
            h = hist[(r.week, r.pid)]
            ref = max(x["week"] for x in h)
            rec = {"fmt": fmt, "w": n_leagues, "pos": r.pos, "actual": actual, "ppr": r.est}
            for k in shrink_ks:
                rec[f"k{k:g}"] = max(0.0, r.est + cal.league_scoring_adjustment(h, r.pos, scoring, reference_week=ref, shrink_k=k))
            rows.append(rec)
    return pd.DataFrame(rows)


def report_item1(df: pd.DataFrame) -> None:
    print("\n== ITEM 1: league-scoring conversion (2026 wk2-8 relevant pool, weighted by league count) ==")
    cols = ["ppr"] + [c for c in df.columns if c.startswith("k")]

    def stats(g: pd.DataFrame) -> str:
        w = g.w.values
        out = []
        for c in cols:
            e = g[c].values - g.actual.values
            out.append(f"{c}: bias {np.average(e, weights=w):+.2f} MAE {np.average(np.abs(e), weights=w):.3f}")
        return " | ".join(out)

    print("ALL      ", stats(df))
    for pos, g in df.groupby("pos"):
        print(f"{pos:8s} ", stats(g))
    df = df.assign(ptd=df.fmt.str.split("|").str[1], tep=df.fmt.str.split("|").str[2], rec=df.fmt.str.split("|").str[0])
    for col in ("rec", "ptd", "tep"):
        for k, g in df.groupby(col):
            print(f"{col}={k:8s}", stats(g))


# ------------------------------------------------------------------ item 2 (matchups)
def matchup_table(s26: Season, leagues: List[dict], weeks=range(2, 9), convert: bool = True) -> pd.DataFrame:
    """One row per decided head-to-head: the shipped pre-game replay
    (mean = estimate, var = ((hi-lo)/2)^2 per modeled starter; league-scored when ``convert``)."""

    panel = s26.panel(weeks=weeks)
    index = {(r.week, r.pid): r for r in panel.itertuples()}
    adj_cache: Dict[tuple, float] = {}
    rows = []
    for bundle in leagues:
        league = bundle["league"]
        scoring = cal.numeric_scoring_settings(league.get("scoring_settings"))
        skey = json.dumps(scoring, sort_keys=True)

        def side(entry: dict, week: int):
            out = []
            for pid, pts in zip(entry.get("starters") or [], entry.get("starters_points") or []):
                if pid in (None, "0"):
                    continue
                r = index.get((week, pid))
                if r is None:
                    out.append((False, 0.0, 0.0, pts, None))
                    continue
                adj = 0.0
                if convert:
                    ck = (skey, week, pid)
                    if ck not in adj_cache:
                        h = s26.history(pid, week)
                        adj_cache[ck] = cal.league_scoring_adjustment(
                            h, r.pos, scoring, reference_week=max(x["week"] for x in h)) if h else 0.0
                    adj = adj_cache[ck]
                est = max(0.0, r.est + adj)
                out.append((True, est, ((r.hi - r.lo) / 2.0) ** 2, pts, r.pos))
            return out

        for week in weeks:
            groups: Dict[Any, list] = defaultdict(list)
            for entry in (bundle["matchups"].get(str(week)) or []):
                groups[entry.get("matchup_id")].append(entry)
            for mid, pair in groups.items():
                if mid is None or len(pair) != 2:
                    continue
                a, b = pair
                if a.get("points") is None or b.get("points") is None or a["points"] == b["points"]:
                    continue
                sa, sb = side(a, week), side(b, week)
                if not sa or not sb:
                    continue
                cov = min(sum(x[0] for x in sa) / len(sa), sum(x[0] for x in sb) / len(sb))
                if cov < 0.6:
                    continue
                rows.append({
                    "league": league["league_id"], "week": week, "n": len(sa),
                    "ma": sum(x[1] for x in sa), "mb": sum(x[1] for x in sb),
                    "va": sum(x[2] for x in sa), "vb": sum(x[2] for x in sb),
                    "act_a": sum(x[3] for x in sa if x[0]), "act_b": sum(x[3] for x in sb if x[0]),
                    "pts_a": a["points"], "pts_b": b["points"], "win": 1.0 if a["points"] > b["points"] else 0.0,
                    "fmt": scoring_format(scoring),
                })
    return pd.DataFrame(rows)


def fit_scale(d: np.ndarray, sd: np.ndarray, y: np.ndarray) -> float:
    grid = np.arange(0.5, 3.01, 0.05)
    return float(grid[int(np.argmin([logloss(phi(d / (c * sd)), y) for c in grid]))])


def reliability(p: np.ndarray, y: np.ndarray) -> List[str]:
    out = []
    for lo, hi in zip([0, .1, .2, .3, .4, .5, .6, .7, .8, .9], [.1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0001]):
        m = (p >= lo) & (p < hi)
        if m.sum():
            out.append(f"  [{lo:.1f},{hi:.1f}) n={m.sum():4d} predicted {p[m].mean():.3f} realized {y[m].mean():.3f}")
    return out


# ------------------------------------------------------------------ item 3 (position shrink)
def build_panels(cache: Path, seasons: List[int], **panel_kwargs) -> Dict[int, pd.DataFrame]:
    out, prior = {}, None
    for season in seasons:
        current = Season(cache, season, prior=prior)
        out[season] = current.panel(**panel_kwargs)
        prior = current
    return out


def pools(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    played = df[df.played & df.actual.notna()]
    out = {"all": played}
    if played.sleeper.notna().any():
        out["relevant"] = relevant(df)
    return out


ANCHOR_QUANTILE = 0.7  # the shipped hinge anchor: 70th percentile of a position's estimates
OFFENSE = ("QB", "RB", "WR", "TE")


def fit_shrink(train: pd.DataFrame, *, anchor_quantile: float | None = ANCHOR_QUANTILE) -> Dict[str, tuple]:
    """Per position (anchor, slope), fitted on played rows only.

    ``anchor_quantile=None``: the rejected full-range form (anchor = mean estimate, slope = OLS slope
    of actual on estimate). Otherwise the shipped one-sided form: anchor = that quantile of the
    estimates, slope = OLS slope of actual on estimate over estimates above the anchor."""

    fit = {}
    played = train[train.played & train.actual.notna() & train.pos.isin(OFFENSE)]
    for pos, g in played.groupby("pos"):
        if anchor_quantile is None:
            anchor, h = float(g.est.mean()), g
        else:
            anchor = float(np.quantile(g.est, anchor_quantile))
            h = g[g.est > anchor]
        x, y = h.est.values, h.actual.values
        slope = float(np.cov(x, y, bias=True)[0, 1] / x.var()) if len(x) > 2 and x.var() > 0 else 1.0
        fit[pos] = (anchor, min(1.0, max(0.0, slope)))
    return fit


def apply_shrink(df: pd.DataFrame, fit: Dict[str, tuple], *, one_sided: bool = True) -> np.ndarray:
    est = df.est.values.copy()
    for pos, (anchor, slope) in fit.items():
        m = ((df.pos == pos) & ((df.est > anchor) if one_sided else True)).values
        est[m] = anchor + slope * (est[m] - anchor)
    return est


def metrics(df: pd.DataFrame, est: np.ndarray) -> Dict[str, float]:
    e = est - df.actual.values
    return {"mae": float(np.abs(e).mean()), "rmse": float(np.sqrt((e ** 2).mean())), "bias": float(e.mean()), "n": len(df)}


def calibration_slope(df: pd.DataFrame, est: np.ndarray) -> float:
    return float(np.cov(est, df.actual.values, bias=True)[0, 1] / est.var()) if est.var() > 0 else float("nan")


def coverage(df: pd.DataFrame, est: np.ndarray) -> float:
    bands = [pp._v2_range(max(0.0, e), p, "x") for e, p in zip(est, df.pos)]
    lo, hi = np.array([b[0] for b in bands]), np.array([b[1] for b in bands])
    return float(((df.actual.values >= lo) & (df.actual.values <= hi)).mean())


def report_item3(panels: Dict[int, pd.DataFrame], first_test: int = 2022) -> Dict[str, Any]:
    print("\n== ITEM 3: position shrink (walk-forward: fit on all earlier seasons, score the next) ==")
    seasons = sorted(panels)
    wins: Dict[str, int] = defaultdict(int)
    for test in [s for s in seasons if s >= first_test]:
        train = pd.concat([panels[s] for s in seasons if s < test])
        top, full = fit_shrink(train), fit_shrink(train, anchor_quantile=None)
        print(f"{test}  one-sided top-tier shrink (shipped) vs full-range shrink (rejected):")
        for name, df in pools(panels[test]).items():
            df = df[df.pos.isin(OFFENSE)]
            base = metrics(df, df.est.values)
            a, b = metrics(df, apply_shrink(df, top)), metrics(df, apply_shrink(df, full, one_sided=False))
            print(f"   {name:9s} MAE {base['mae']:.3f} -> top {a['mae']:.3f} | full {b['mae']:.3f}   "
                  f"RMSE {base['rmse']:.3f} -> top {a['rmse']:.3f} | full {b['rmse']:.3f}")
            wins[name + " MAE"] += a["mae"] <= base["mae"] - 0.01
            wins[name + " RMSE"] += a["rmse"] < base["rmse"]
        played = pools(panels[test])["all"]
        played = played[played.pos.isin(OFFENSE)]
        qb = played[played.pos == "QB"]
        print(f"   QB calibration slope {calibration_slope(qb, qb.est.values):.2f} -> "
              f"{calibration_slope(qb, apply_shrink(qb, top)):.2f};  68% band coverage "
              f"{coverage(played, played.est.values):.3f} -> {coverage(played, apply_shrink(played, top)):.3f}")
    fit_all = fit_shrink(pd.concat(panels.values()))
    print("seasons the shipped form wins (of %d):" % len([s for s in seasons if s >= first_test]), dict(wins))
    print("refit (all seasons), paste into projection_calibration.TOP_SHRINK:",
          {p: (round(a, 2), round(b, 3)) for p, (a, b) in fit_all.items()})
    return {"wins": dict(wins), "fit_all": fit_all}


# ------------------------------------------------------------------ item 2 report
def report_item2(M: pd.DataFrame, M_ppr: pd.DataFrame | None = None) -> Dict[str, float]:
    print("\n== ITEM 2: win-probability spread (2026 wk2-8 decided matchups, league-scored estimates) ==")
    D = M.assign(d=M.ma - M.mb, V=M.va + M.vb)
    y, d, sd = D.win.values, D.d.values, np.sqrt(D.V).values
    print(f"n={len(D)} matchups, {D.league.nunique()} leagues; coin flip Brier 0.2500 logloss 0.6931")
    print(f"as shipped before (independent-starter sd)       Brier {brier(phi(d / sd), y):.4f} logloss {logloss(phi(d / sd), y):.4f}")
    print(f"flat team SD 22 (old trade_posture constant)    Brier {brier(phi(d / (math.sqrt(2) * 22)), y):.4f} logloss {logloss(phi(d / (math.sqrt(2) * 22)), y):.4f}")
    if M_ppr is not None:
        dp, sp = (M_ppr.ma - M_ppr.mb).values, np.sqrt(M_ppr.va + M_ppr.vb).values
        print(f"PPR-only estimates (no scoring conversion)      Brier {brier(phi(dp / sp), M_ppr.win.values):.4f} logloss {logloss(phi(dp / sp), M_ppr.win.values):.4f}")
    c_all = fit_scale(d, sd, y)
    print(f"pooled fitted c = {c_all:.2f} (shipped WIN_PROB_SPREAD_MULTIPLIER = {cal.WIN_PROB_SPREAD_MULTIPLIER})")
    ids = sorted(D.league.unique())
    fold = {l: i % 5 for i, l in enumerate(np.random.RandomState(0).permutation(ids))}
    D["fold"] = D.league.map(fold)
    p_cv = np.zeros(len(D))
    for f in range(5):
        tr = (D.fold != f).values
        c = fit_scale(d[tr], sd[tr], y[tr])
        p_cv[~tr] = phi(d[~tr] / (c * sd[~tr]))
    print(f"5-fold CV by league, c refit per fold            Brier {brier(p_cv, y):.4f} logloss {logloss(p_cv, y):.4f}")
    tr = (D.week <= 5).values
    c = fit_scale(d[tr], sd[tr], y[tr])
    print(f"fit wk2-5 (c={c:.2f}), test wk6-8: before Brier {brier(phi(d[~tr] / sd[~tr]), y[~tr]):.4f} / {logloss(phi(d[~tr] / sd[~tr]), y[~tr]):.4f}"
          f"  after {brier(phi(d[~tr] / (c * sd[~tr])), y[~tr]):.4f} / {logloss(phi(d[~tr] / (c * sd[~tr])), y[~tr]):.4f}")
    p = phi(d / (cal.WIN_PROB_SPREAD_MULTIPLIER * sd))
    print(f"with the shipped multiplier                      Brier {brier(p, y):.4f} logloss {logloss(p, y):.4f}")
    print("reliability, before:"); print("\n".join(reliability(phi(d / sd), y)))
    print("reliability, after:"); print("\n".join(reliability(p, y)))
    print("by lineup size (modeled starters per team): best c")
    for lo, hi in ((0, 8), (8, 11), (11, 30)):
        g = D[(D.n >= lo) & (D.n < hi)]
        if len(g) >= 100:
            print(f"   n in [{lo},{hi}) rows {len(g)}: c={fit_scale(g.d.values, np.sqrt(g.V).values, g.win.values):.2f}")
    return {"c": c_all}


# ------------------------------------------------------------------ item 4 report
def report_item4(cache: Path, seasons: List[int], offsets=(0, 6, 12, 24)) -> None:
    print("\n== ITEM 4: prior-season seeding (same-player matched MAE vs current-season-only history) ==")
    cur, prior = {}, None
    for s in seasons:
        cur[s] = Season(cache, s, prior=prior)
        prior = cur[s]
    for offset in offsets:
        rows = []
        for s in seasons[1:]:
            a = cur[s].panel(weeks=range(1, 19))
            b = cur[s].panel(weeks=range(1, 19), carry_prior=True, carry_offset=offset)
            a, b = (x[x.played & x.actual.notna()] for x in (a, b))
            m = a.merge(b, on=["week", "pid"], suffixes=("_a", "_b"))
            row = {"season": s}
            for name, lo, hi in (("wk2-4", 2, 4), ("wk5-8", 5, 8)):
                g = m[m.week.between(lo, hi)]
                row[name] = (float(np.abs(g.est_a - g.actual_a).mean()), float(np.abs(g.est_b - g.actual_b).mean()))
            w1 = b[(b.week == 1) & b.sleeper.notna()]
            row["wk1"] = (float(np.abs(w1.est - w1.actual).mean()), float(np.abs(w1.sleeper - w1.actual).mean()), len(w1))
            row["cover1"] = float(((b[b.week == 1].actual >= b[b.week == 1].lo) & (b[b.week == 1].actual <= b[b.week == 1].hi)).mean())
            rows.append(row)
        tag = " (SHIPPED)" if offset == cal.PRIOR_SEASON_AGE_OFFSET_WEEKS else ""
        print(f"offset d={offset}{tag}")
        for name in ("wk2-4", "wk5-8"):
            better = sum(r[name][1] < r[name][0] for r in rows)
            print(f"   {name}: " + " ".join(f"{r['season']}:{r[name][0]:.3f}->{r[name][1]:.3f}" for r in rows) + f"   better in {better}/{len(rows)}")
        print("   wk1 (no projection before): ours vs Sleeper MAE " + " ".join(f"{r['season']}:{r['wk1'][0]:.2f}/{r['wk1'][1]:.2f}" for r in rows)
              + "  68% band coverage " + " ".join(f"{r['cover1']:.2f}" for r in rows))


# ------------------------------------------------------------------ item 5 (playoff slope prior)
def _slope_mle(x: np.ndarray, y: np.ndarray, *, start: float, prior: float | None = None, lam: float = 0.0,
               max_slope: float = 6.0) -> float:
    slope = start
    for _ in range(40):
        p = 1.0 / (1.0 + np.exp(-np.clip(slope * x, -50, 50)))
        grad = float(np.sum(x * (y - p))) - (lam * (slope - prior) if prior is not None else 0.0)
        hess = float(-np.sum(x * x * p * (1 - p))) - lam
        if hess == 0:
            break
        step = grad / hess
        slope = float(np.clip(slope - step, -max_slope, max_slope))
        if abs(step) < 1e-7:
            break
    return slope


def playoff_slope_games(leagues: List[dict], vantage: int, last_week: int = 8) -> pd.DataFrame:
    """Game rows (train = before ``vantage``, test = vantage..last_week) with z-scored strength
    proxy = season-to-date points-for through week ``vantage-1`` (a stand-in for Roster Power,
    which is not recoverable historically)."""

    rows = []
    for bundle in leagues:
        league = bundle["league"]
        pf: Dict[Any, List[float]] = defaultdict(list)
        games = []
        for week in range(1, last_week + 1):
            groups: Dict[Any, list] = defaultdict(list)
            for entry in bundle["matchups"].get(str(week)) or []:
                groups[entry.get("matchup_id")].append(entry)
            for mid, pair in groups.items():
                if mid is None or len(pair) != 2:
                    continue
                a, b = pair
                if a.get("points") is None or b.get("points") is None or a["points"] == b["points"]:
                    continue
                if week < vantage:
                    pf[a["roster_id"]].append(a["points"])
                    pf[b["roster_id"]].append(b["points"])
                games.append((week, a["roster_id"], b["roster_id"], 1.0 if a["points"] > b["points"] else 0.0))
        if len(pf) < 6 or min(len(v) for v in pf.values()) < 2:
            continue
        means = {k: float(np.mean(v)) for k, v in pf.items()}
        mu, sd = float(np.mean(list(means.values()))), float(np.std(list(means.values())))
        if sd <= 0:
            continue
        z = {k: (v - mu) / sd for k, v in means.items()}
        for week, ra, rb, win in games:
            if ra in z and rb in z:
                rows.append({"league": league["league_id"], "week": week, "x": z[ra] - z[rb], "y": win,
                             "test": week >= vantage})
    return pd.DataFrame(rows)


def report_item5(leagues: List[dict], vantages=(4, 5, 6), pseudo_games=(0, 25, 50, 100, 200),
                 fisher_per_game: float = 0.4) -> Dict[str, Any]:
    print("\n== ITEM 5: playoff-odds win-model slope (held-out games; strength proxy = PF-to-date z) ==")
    summary = {}
    for v in vantages:
        G = playoff_slope_games(leagues, v)
        ids = sorted(G.league.unique())
        half = {l: i % 2 for i, l in enumerate(ids)}
        G["half"] = G.league.map(half)
        results = defaultdict(list)
        pooled = {}
        for h in (0, 1):  # prior mean fit on the OTHER half's test games only
            other = G[(G.half != h) & G.test]
            pooled[h] = _slope_mle(other.x.values, other.y.values, start=0.5)
        for lid, g in G.groupby("league"):
            tr, te = g[~g.test], g[g.test]
            if len(te) < 4:
                continue
            h = half[lid]
            mu = pooled[h]
            xs, ys = te.x.values, te.y.values
            variants = {"default 1.0": 1.0, "pooled const": mu}
            variants["per-league MLE (shipped, >=12 games)"] = (
                _slope_mle(tr.x.values, tr.y.values, start=1.0) if len(tr) >= 12 else 1.0
            )
            for m in pseudo_games:
                if m:
                    variants[f"MAP m={m}"] = _slope_mle(tr.x.values, tr.y.values, start=mu, prior=mu, lam=m * fisher_per_game)
            for name, slope in variants.items():
                p = 1.0 / (1.0 + np.exp(-slope * xs))
                results[name].append((brier(p, ys) * len(ys), logloss(p, ys) * len(ys), len(ys)))
        print(f"\nvantage week {v}: test games {int(G.test.sum())}, pooled slope by half {pooled[0]:.2f}/{pooled[1]:.2f}")
        for name, vals in results.items():
            n = sum(t[2] for t in vals)
            b, ll = sum(t[0] for t in vals) / n, sum(t[1] for t in vals) / n
            summary[(v, name)] = (b, ll)
            print(f"  {name:40s} Brier {b:.4f} logloss {ll:.4f}")
    return summary


# ------------------------------------------------------------------ main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["fetch", "report"])
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--leagues", type=Path, default=None)
    ap.add_argument("--seasons", type=int, nargs="+", default=[2021, 2022, 2023, 2024, 2025, 2026])
    ap.add_argument("--items", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    args = ap.parse_args()
    if args.command == "fetch":
        fetch(args.cache, args.seasons)
        return
    seasons = sorted(args.seasons)
    leagues = load_leagues(args.leagues)
    newest = seasons[-1]
    s_new = Season(args.cache, newest, prior=Season(args.cache, newest - 1) if newest - 1 in seasons else None)
    last = max(s_new.stats) if s_new.stats else 0
    weeks = range(2, min(last, 8) + 1)
    if 1 in args.items:
        if leagues:
            report_item1(item1_scoring(s_new, leagues, weeks=weeks))
        else:
            print("item 1 skipped: pass --leagues")
    if 2 in args.items:
        if leagues:
            M, M0 = matchup_table(s_new, leagues, weeks=weeks), matchup_table(s_new, leagues, weeks=weeks, convert=False)
            report_item2(M, M0)
        else:
            print("item 2 skipped: pass --leagues")
    if 3 in args.items:
        report_item3(build_panels(args.cache, seasons, weeks=range(2, 19)), first_test=seasons[1])
    if 4 in args.items:
        report_item4(args.cache, seasons)
    if 5 in args.items:
        if leagues:
            report_item5(leagues)
        else:
            print("item 5 skipped: pass --leagues")


if __name__ == "__main__":
    main()

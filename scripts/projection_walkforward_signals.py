"""Walk-forward experiments on top of the v3 projection baseline.

Two questions, both judged ONLY by the walk-forward test in
``projection_walkforward.py`` (constants fitted on earlier seasons, scored on the
next one):

  A. a recency-weighted league-level calibration of the known under-projection bias;
  B. injury-report and depth-chart signals as availability / role inputs.

Ship rule: a variant ships only if it improves MAE by >= 0.01 on BOTH pools
(relevant players, all with a Sleeper projection) in >= 3 of the 5 scored seasons.
Sleeper projections are a benchmark only; nothing here feeds them to the model.

    python scripts/projection_walkforward_signals.py fetch-signals --signals /tmp/nv
    python scripts/projection_walkforward_signals.py run --cache /tmp/pwf --signals /tmp/nv

Point-in-time inputs are nflverse injury reports (``injuries_<season>.csv``, final
report of the week) and depth charts (weekly files 2021-24, daily snapshots 2025+;
for 2025+ the latest snapshot on or before the week's Thursday is used). A
player-week with no signal row is treated as "no information" and left
unadjusted; coverage per season is printed. Nothing is written to ``data/``.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import projection_walkforward as pw  # noqa: E402

ROOT = pw.ROOT
SEASON_LEN = 20  # time index spacing so the offseason is a gap between seasons
SCORED = range(4, 18)
NV_BASE = "https://" + "git" + "hub.com/nflverse/nflverse-data/releases/download/"
IDS_URL = "https://raw." + "git" + "hubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"


# ------------------------------------------------------------------ data
def fetch_signals(d: Path, last_season: int) -> None:
    d.mkdir(parents=True, exist_ok=True)
    jobs = [(f"{NV_BASE}{k}/{k}_{s}.csv", d / f"{k}_{s}.csv") for k in ("injuries", "depth_charts")
            for s in range(pw.FIRST_SEASON, last_season + 1)] + [(IDS_URL, d / "db_playerids.csv")]
    for url, path in jobs:
        if not path.exists():
            path.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "FantasyDesk-walkforward/1.0"}), timeout=300).read())


def id_map(d: Path) -> dict:
    df = pd.read_csv(d / "db_playerids.csv", usecols=["sleeper_id", "gsis_id"]).dropna()
    m = {str(int(float(a))): g for a, g in zip(df.sleeper_id, df.gsis_id)}
    try:
        sp = json.loads((ROOT / "data" / "sleeper_players.json").read_text())
        for pid, v in sp.items():
            if v.get("gsis_id") and pid not in m:
                m[pid] = v["gsis_id"]
    except Exception:
        pass
    return m


def week_dates(cache: Path) -> dict:
    out = {}
    for p in sorted(cache.glob("stats_*_*.json")):
        _, s, w = p.stem.split("_")
        try:
            rows = json.loads(p.read_text())
        except Exception:
            continue
        if rows and rows[0].get("date"):
            out[(int(s), int(w))] = pd.Timestamp(rows[0]["date"])
    return out


def injury_table(d: Path, seasons) -> pd.DataFrame:
    fr = []
    for s in seasons:
        f = d / f"injuries_{s}.csv"
        if not f.exists():
            continue
        x = pd.read_csv(f, usecols=lambda c: c in ("season", "game_type", "week", "gsis_id", "report_status", "practice_status", "date_modified"))
        if "date_modified" not in x:  # 2025+ files carry one final row per player-week
            x["date_modified"] = ""
        x = x[x.game_type == "REG"].sort_values("date_modified", kind="stable").groupby(["season", "week", "gsis_id"], as_index=False).last()
        fr.append(x)
    x = pd.concat(fr, ignore_index=True)
    rs = x.report_status.fillna("")
    ps = x.practice_status.fillna("")
    x["inj"] = np.where(rs.isin(["Out", "Doubtful"]), "D", np.where(rs == "Questionable", "Q",
                        np.where(ps.str.contains("Limited"), "L", "none")))
    return x[["season", "week", "gsis_id", "inj", "report_status"]]


def depth_table(d: Path, seasons, wdates: dict) -> pd.DataFrame:
    """(season, week, gsis_id) -> depth rank among QB/RB/WR/TE on the player's team."""
    fr = []
    for s in seasons:
        f = d / f"depth_charts_{s}.csv"
        if not f.exists():
            continue
        if s <= 2024:
            x = pd.read_csv(f, usecols=["season", "club_code", "week", "game_type", "depth_team", "gsis_id", "depth_position", "formation"])
            x = x[(x.game_type == "REG") & (x.formation == "Offense") & x.depth_position.isin(["QB", "RB", "WR", "TE"])].copy()
            x["depth_team"] = pd.to_numeric(x.depth_team, errors="coerce")
            x = x.dropna(subset=["depth_team", "gsis_id", "week"])
            # weekly files give slot-based WR numbers; turn them into an ordinal per team-week-position
            x = x.sort_values(["season", "week", "club_code", "depth_position", "depth_team"])
            x["rank"] = x.groupby(["season", "week", "club_code", "depth_position"]).cumcount() + 1
            x = x.groupby(["season", "week", "gsis_id"], as_index=False)["rank"].min()
            x["week"] = x.week.astype(int)
            fr.append(x)
        else:
            x = pd.read_csv(f, usecols=["dt", "gsis_id", "pos_abb", "pos_rank"])
            x = x[x.pos_abb.isin(["QB", "RB", "WR", "TE"])].dropna(subset=["gsis_id"])
            x["day"] = pd.to_datetime(x.dt.str[:10])
            g = x.groupby(["day", "gsis_id"], as_index=False).pos_rank.min()
            days = sorted(g.day.unique())
            for (ss, w), dt in wdates.items():
                if ss != s:
                    continue
                prior = [d_ for d_ in days if d_ <= dt]
                if not prior or (dt - prior[-1]).days > 14:
                    continue
                snap = g[g.day == prior[-1]][["gsis_id", "pos_rank"]].rename(columns={"pos_rank": "rank"})
                snap["season"], snap["week"] = s, w
                fr.append(snap)
    return pd.concat(fr, ignore_index=True) if fr else pd.DataFrame(columns=["season", "week", "gsis_id", "rank"])


# ------------------------------------------------------------------ folds
def build_folds(cache: Path, out: Path) -> dict:
    if out.exists():
        return pickle.loads(out.read_bytes())
    table = pw.load_table(cache)
    seasons = sorted(table.season.unique())
    panels = {(s, p): pw.Panel(table, s, p) for s in seasons for p in pw.POS}
    folds = {}
    for test in seasons[1:]:
        train = [s for s in seasons if s < test]
        coefs = {p: pw.fit_coef([panels[(s, p)] for s in train]) for p in pw.POS}
        hu, hr, k = pw.tune_pooled(panels, coefs, train)
        par = {p: (hu, hr, k) for p in pw.OFF}
        par["K"] = (pw.INF, pw.INF, pw.tune_kicker(panels, coefs["K"], train))
        ext = pd.concat([pw.estimate(panels[(s, p)], coefs[p], *par[p], weeks=range(2, 18), include_absent=True)
                         for s in train + [test] for p in pw.POS], ignore_index=True)
        print("fold", test, par["QB"], flush=True)
        folds[test] = dict(train=train, ext=ext)
    team = table.drop_duplicates(["season", "pid"], keep="last")[["season", "pid", "team"]]
    res = dict(folds=folds, team=team)
    out.write_bytes(pickle.dumps(res))
    return res


def add_pool_flag(f: pd.DataFrame) -> pd.DataFrame:
    """Sleeper top-N pool, computed on played rows only (does not use our model)."""
    f = f.copy()
    f["pool"] = False
    pl = f[f.played & f.sproj.notna()]
    for _, g in pl.groupby(["season", "week", "pos"]):
        top = g.sort_values("sproj", ascending=False).head(pw.POOL_N[g.pos.iloc[0]])
        f.loc[top.index, "pool"] = True
    return f


# ------------------------------------------------------------------ A: bias calibration
def weekly_resid(ext: pd.DataFrame) -> pd.DataFrame:
    p = ext[ext.played].copy()
    p["t"] = (p.season - pw.FIRST_SEASON) * SEASON_LEN + p.week
    p["res"] = p.actual - p.est
    g = p.groupby(["t", "pos"]).agg(res=("res", "sum"), est=("est", "sum"), n=("res", "size")).reset_index()
    return g


def tracker(ext: pd.DataFrame, half_life: float, form: str, scope: str, lam: float = 300.0) -> np.ndarray:
    """Point-in-time level correction for every row of ``ext`` using only EARLIER weeks."""
    wr = weekly_resid(ext)
    out = np.zeros(len(ext))
    t_all = ((ext.season - pw.FIRST_SEASON) * SEASON_LEN + ext.week).values
    pos_all = ext.pos.values
    for t in np.unique(t_all):
        prev = wr[wr.t < t]
        if prev.empty:
            continue
        decay = 0.5 ** ((t - 1 - prev.t.values) / half_life)
        for pos in pw.POS:
            sel = prev.pos.values == pos if scope == "pos" else np.ones(len(prev), bool)
            if sel.sum() == 0:
                continue
            num = (decay[sel] * prev.res.values[sel]).sum()
            den = (decay[sel] * (prev.n.values[sel] if form == "add" else prev.est.values[sel])).sum()
            val = num / (den + (lam if form == "add" else lam * 10))
            m = (t_all == t) & (pos_all == pos)
            out[m] = val
    return out


def apply_cal(ext: pd.DataFrame, cfg) -> np.ndarray:
    if cfg is None:
        return ext.est.values
    h, form, scope = cfg
    b = tracker(ext, h, form, scope)
    return np.maximum(0.0, ext.est.values + b) if form == "add" else ext.est.values * (1 + b)


def pool_mae(f: pd.DataFrame, col: str) -> tuple:
    f = f[f.played & f.week.isin(SCORED)]
    pool, allp = f[f.pool], f[f.sproj.notna()]
    return (pool[col] - pool.actual).abs().mean(), (allp[col] - allp.actual).abs().mean()


def fit_calibration(ext: pd.DataFrame, train: list[int]) -> tuple:
    """Pick (half-life, form, scope) on training seasons only; None if nothing beats base."""
    e = add_pool_flag(ext)
    tr = e.season.isin(train).values
    base = np.mean(pool_mae(e[tr], "est"))
    best = (base, None)
    for h in (2, 4, 8, 16, 32):
        for form in ("add", "ratio"):
            for scope in ("all", "pos"):
                e["cal"] = apply_cal(ext, (h, form, scope))
                m = np.mean(pool_mae(e[tr], "cal"))
                if m < best[0] - 1e-9:
                    best = (m, (h, form, scope))
    return best[1]


# ------------------------------------------------------------------ B: signals
def attach_signals(ext: pd.DataFrame, team: pd.DataFrame, idm: dict, inj: pd.DataFrame, dep: pd.DataFrame) -> pd.DataFrame:
    f = ext.merge(team, on=["season", "pid"], how="left")
    f["gsis_id"] = f.pid.map(idm)
    f = f.merge(inj, on=["season", "week", "gsis_id"], how="left")
    f["inj_known"] = f.inj.notna()
    f["inj"] = f.inj.fillna("none")
    f["inj_qd"] = f.inj.where(f.inj.isin(["Q", "D"]), "none")  # what Sleeper's injury_status alone can express
    f = f.merge(dep, on=["season", "week", "gsis_id"], how="left")
    f["has_depth"] = f["rank"].notna()
    return f


def teammate_lost(f: pd.DataFrame) -> np.ndarray:
    """Sum of estimates of same-team, same-position players listed Out/Doubtful that week."""
    g = f[(f.inj == "D")].groupby(["season", "week", "team", "pos"]).est.sum().rename("lost").reset_index()
    m = f.merge(g, on=["season", "week", "team", "pos"], how="left")
    lost = m.lost.fillna(0.0).values
    own = np.where((f.inj == "D").values, f.est.values, 0.0)  # do not count the player himself
    return np.maximum(0.0, lost - own)


def fit_ratio_groups(f: pd.DataFrame, keys: list[str], base_level, n0: float = 100.0) -> dict:
    """Relative actual/estimate ratio per group versus the base group, shrunk by n/(n+n0)."""
    out = {}
    base = f[(f[keys[-1]] == base_level)]
    r0 = base.actual.sum() / max(base.est.sum(), 1e-9)
    for key, g in f.groupby(keys):
        r = (g.actual.sum() / max(g.est.sum(), 1e-9)) / r0
        out[key if isinstance(key, tuple) else (key,)] = 1 + (r - 1) * len(g) / (len(g) + n0)
    return out


class Signals:
    """Layers fitted on training rows only; ``apply`` returns adjusted estimates."""

    def __init__(self, layers: tuple):
        self.layers, self.inj_mult, self.beta, self.dep_mult = layers, {}, {}, {}
        self.icol = "inj" if "inj" in layers else ("inj_qd" if "injqd" in layers else None)

    def fit(self, f: pd.DataFrame, col: str):
        t = f[f.played & f.week.isin(SCORED) & f.pos.isin(pw.OFF)].copy()
        t["x"] = t[col]
        cur = t.x.values.copy()
        if self.icol:
            tt = t.assign(est=cur)
            self.inj_mult = {k[0]: v for k, v in fit_ratio_groups(tt, [self.icol], "none").items() if k[0] != "none"}
            cur = cur * t[self.icol].map(self.inj_mult).fillna(1.0).values
        if "mate" in self.layers:
            lost = teammate_lost(f)
            lt = pd.Series(lost, index=f.index).loc[t.index].values
            for pos in pw.OFF:
                m = (t.pos == pos).values & (lt > 0)
                if m.sum() < 30:
                    continue
                r = (t.actual.values[m] - cur[m])
                b = float((r * lt[m]).sum() / ((lt[m] ** 2).sum() + 1e-9))
                self.beta[pos] = float(np.clip(b * m.sum() / (m.sum() + 100), 0.0, 0.6))
            cur = cur + t.pos.map(self.beta).fillna(0.0).values * lt
        if "depth" in self.layers:
            h = t[t.has_depth].copy()
            h["est"] = pd.Series(cur, index=t.index).loc[h.index].values
            h["rb"] = np.minimum(h["rank"], 3).astype(int)
            self.dep_mult = {k: v for k, v in fit_ratio_groups(h, ["pos", "rb"], 1).items() if k[1] != 1}

    def apply(self, f: pd.DataFrame, col: str) -> np.ndarray:
        cur = f[col].values.copy()
        if self.icol:
            cur = cur * f[self.icol].map(self.inj_mult).fillna(1.0).values
        if "mate" in self.layers:
            cur = cur + f.pos.map(self.beta).fillna(0.0).values * teammate_lost(f.assign(est=f[col]))
        if "depth" in self.layers:
            rb = np.minimum(f["rank"].fillna(1), 3).astype(int)
            key = list(zip(f.pos, rb))
            mult = np.array([self.dep_mult.get(k, 1.0) if h else 1.0 for k, h in zip(key, f.has_depth.values)])
            cur = cur * mult
        return np.maximum(0.0, cur)


# ------------------------------------------------------------------ driver
def run(cache: Path, signals: Path, folds_pkl: Path, grid: bool = False) -> None:
    res = build_folds(cache, folds_pkl)
    idm = id_map(signals)
    seasons = sorted(res["folds"])
    allseasons = [pw.FIRST_SEASON] + seasons
    inj = injury_table(signals, allseasons)
    dep = depth_table(signals, allseasons, week_dates(cache))
    variants = ["A_cal", "B_inj", "B_injqd", "B_mate", "B_depth", "B_all", "A+B_all"]
    rows, chosen = [], {}
    for test in seasons:
        fo = res["folds"][test]
        ext, train = fo["ext"].copy(), fo["train"]
        cfg = fit_calibration(ext, train)
        chosen[test] = cfg
        f = attach_signals(ext, res["team"], idm, inj, dep)
        f["cal"] = apply_cal(ext, cfg)
        f = add_pool_flag(f)
        if grid:
            te0 = f[(f.season == test) & f.played & f.week.isin(SCORED)]
            b0 = pool_mae(te0, "est")
            for h in (2, 4, 8, 16, 32):
                for form in ("add", "ratio"):
                    for scope in ("all", "pos"):
                        f["g"] = apply_cal(ext, (h, form, scope))
                        te0 = f[(f.season == test) & f.played & f.week.isin(SCORED)]
                        g0 = pool_mae(te0, "g")
                        print("GRID", test, h, form, scope, round(g0[0] - b0[0], 3), round(g0[1] - b0[1], 3), "bias", round((te0.g - te0.actual).mean(), 3))
        tr = f.season.isin(train)
        for v in variants:
            col = "cal" if v.startswith("A") and v != "A+B_all" else ("cal" if v == "A+B_all" else "est")
            layers = {"B_inj": ("inj",), "B_injqd": ("injqd",), "B_mate": ("mate",), "B_depth": ("depth",), "B_all": ("inj", "mate", "depth"),
                      "A+B_all": ("inj", "mate", "depth"), "A_cal": ()}[v]
            f[v] = f[col].values
            if layers:
                s = Signals(layers)
                s.fit(f[tr], col)
                f[v] = s.apply(f, col)
                if v in ("B_inj", "B_injqd"):
                    print(test, v, {k: round(x, 3) for k, x in s.inj_mult.items()})
        te = f[(f.season == test) & f.played & f.week.isin(SCORED)]
        base_p, base_a = pool_mae(te, "est")
        cov_d = te[te.pos.isin(pw.OFF)].has_depth.mean()
        cov_i = te.inj_known.mean()
        for v in variants:
            vp, va = pool_mae(te, v)
            rows.append(dict(season=test, variant=v, base_pool=base_p, base_all=base_a, d_pool=vp - base_p, d_all=va - base_a,
                             bias_base=(te.est - te.actual).mean(), bias_v=(te[v] - te.actual).mean(),
                             med_base=(te.est - te.actual).median(),
                             cov_depth=cov_d, cov_inj=cov_i))
        print(test, "cal cfg", cfg, "depth cov", round(cov_d, 3), "inj cov", round(cov_i, 3), flush=True)
    r = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    for v in variants:
        x = r[r.variant == v]
        ok = ((x.d_pool <= -0.01) & (x.d_all <= -0.01)).sum()
        print(f"\n{v}: seasons passing both pools by >=0.01: {ok}/5 -> {'SHIP' if ok >= 3 else 'DO NOT SHIP'}")
        print(x[["season", "base_pool", "d_pool", "base_all", "d_all", "bias_base", "med_base", "bias_v", "cov_depth", "cov_inj"]].round(4).to_string(index=False))
    print("\nchosen calibration per fold:", chosen)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=("fetch-signals", "run"))
    ap.add_argument("--cache", type=Path, default=Path(tempfile.gettempdir()) / "projection_walkforward")
    ap.add_argument("--signals", type=Path, default=Path(tempfile.gettempdir()) / "projection_signals")
    ap.add_argument("--folds", type=Path, default=Path(tempfile.gettempdir()) / "projection_folds.pkl")
    ap.add_argument("--last-season", type=int, default=2026)
    ap.add_argument("--grid", action="store_true", help="print every calibration config on the scored season (diagnostic only)")
    a = ap.parse_args(argv)
    if a.command == "fetch-signals":
        fetch_signals(a.signals, a.last_season)
    else:
        run(a.cache, a.signals, a.folds, a.grid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Replay the REAL projection logic on the committed real-history panel (read-only audit).

Reads the sim calibration panel file (``calibration/data/panel.json.gz``) as plain data (2021-2025 weekly box scores and the
Sleeper week-1 projection per player-season), re-runs the shipped weekly estimator
(``modules.player_projections`` usage empirical-Bayes baseline + ``projection_calibration`` top-tier shrink and
prior-season seeding + the shipped 68% band) point-in-time, and tabulates where it is biased or over/under-confident.

    python scripts/sim_projection_audit.py [--json OUT.json] [--csv-dir DIR]

Isolation: this file imports real logic and never imports the sim package (the panel is read as raw JSON). It
changes no real code, writes nothing under ``data/`` and touches no database. Findings and suggested changes
are in ``docs/audits/2026-11-sim-projection-audit.md``; nothing here is wired into real logic.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import player_projections as pp  # noqa: E402
from modules import projection_calibration as pc  # noqa: E402

PANEL = ROOT / "modules" / "sim" / "calibration" / "data" / "panel.json.gz"
OFF = ("QB", "RB", "WR", "TE")
FEAT_IDX = {"pass_attempts": "pass_att", "rush_attempts": "rush_att", "targets": "rec_tgt"}
SHIFT = pc.PRIOR_SEASON_WEEKS + pc.PRIOR_SEASON_AGE_OFFSET_WEEKS


def load_panel() -> tuple[list[str], list[dict]]:
    with gzip.open(PANEL, "rt") as fh:
        raw = json.load(fh)
    return raw["stat_fields"], raw["rows"]


def age_bucket(a):
    return "?" if a is None else ("<24" if a < 24 else "24-26" if a < 27 else "27-29" if a < 30 else "30+")


def played_weeks(row, fields):
    """[(week, pts, {feature: value})] for weeks the player played."""

    fi = {f: i + 1 for i, f in enumerate(fields)}
    out = []
    for w, rec in enumerate(row["weeks"], 1):
        if rec and rec[0]:
            out.append((w, float(rec[fi["pts_ppr"]]), {k: float(rec[fi[v]]) for k, v in FEAT_IDX.items()}))
    return out


def baseline(hist, pos, reference):
    """The shipped v2/v3 usage baseline for ``hist`` = [(week, pts, feats)] with week <= reference."""

    coef = pp._V2_USAGE_COEF[pos]
    feats = pp._V2_USAGE_FEATURES[pos]
    hu, hr, k = pp._V2_SHRINKAGE[pos]
    su = sru = sr = srr = 0.0
    for week, pts, f in hist:
        implied = coef[0] + sum(c * f[name] for c, name in zip(coef[1:], feats))
        age = max(0, reference - week)
        wu, wr = pp._v2_weight(age, hu), pp._v2_weight(age, hr)
        su += wu
        sru += wu * implied
        sr += wr
        srr += wr * (pts - implied)
    g = len(hist)
    return pc.shrink_top_tier(sru / su + g / (g + k) * (srr / sr), pos), g


def replay(fields, rows):
    """One record per (player-season with a prior season, week played): the shipped estimate at that point."""

    by = {(r["season"], r["pid"]): r for r in rows}
    out = []
    for r in rows:
        pos = r["pos"]
        if pos not in OFF:
            continue
        cur = played_weeks(r, fields)
        prev = by.get((r["season"] - 1, r["pid"]))
        prior = [(w - SHIFT, p, f) for w, p, f in played_weeks(prev, fields)] if prev else []
        prior_missed = None
        if prev:
            av = [w for w in prev["weeks"] if w is not None]
            prior_missed = len(av) - sum(1 for w in av if w[0])
        sp = r.get("proj_ppg")
        for w, actual, _f in cur:
            hist = prior + [x for x in cur if x[0] < w]
            if not hist:
                continue
            est, g = baseline(hist, pos, w - 1)
            lo, hi = pp._v2_range(est, pos, pp._v2_confidence(g))
            out.append(dict(season=r["season"], pid=r["pid"], pos=pos, week=w, est=est, actual=actual, lo=lo, hi=hi,
                            games_cur=len([x for x in cur if x[0] < w]), seeded=bool(prior), rookie=bool(r["rookie"]),
                            age=r["age"], prior_missed=prior_missed, sleeper_ppg=sp))
    return out


def summarize(recs, key, bins=None):
    groups = defaultdict(list)
    for x in recs:
        groups[key(x)].append(x)
    res = {}
    for k, g in sorted(groups.items(), key=lambda kv: str(kv[0])):
        if len(g) < 60:
            continue
        e = np.array([x["actual"] - x["est"] for x in g])
        cov = np.mean([x["lo"] <= x["actual"] <= x["hi"] for x in g])
        below = np.mean([x["actual"] < x["lo"] for x in g])
        above = np.mean([x["actual"] > x["hi"] for x in g])
        res[str(k)] = dict(n=len(g), bias=round(float(e.mean()), 3), mae=round(float(np.abs(e).mean()), 3),
                           cov68=round(float(cov), 3), below=round(float(below), 3), above=round(float(above), 3),
                           mean_est=round(float(np.mean([x["est"] for x in g])), 2))
    return res


def season_level(fields, rows):
    """Week-1 shipped estimate (needs a prior season) vs the actual season PPG, and the Sleeper preseason number on the
    same player-seasons. Returns records for ratio / quantile tables."""

    by = {(r["season"], r["pid"]): r for r in rows}
    out = []
    for r in rows:
        pos = r["pos"]
        if pos not in OFF:
            continue
        cur = played_weeks(r, fields)
        if len(cur) < 4:
            continue
        prev = by.get((r["season"] - 1, r["pid"]))
        prior = [(w - SHIFT, p, f) for w, p, f in played_weeks(prev, fields)] if prev else []
        est = baseline(prior, pos, 0)[0] if prior else None
        ppg = float(np.mean([p for _w, p, _f in cur]))
        pm = None
        if prev:
            av = [w for w in prev["weeks"] if w is not None]
            pm = len(av) - sum(1 for w in av if w[0])
        out.append(dict(season=r["season"], pos=pos, est=est, sleeper=r["proj_ppg"], ppg=ppg, rookie=bool(r["rookie"]), age=r["age"],
                        prior_missed=pm))
    return out


def ratio_stats(recs, key, which):
    g = defaultdict(list)
    for x in recs:
        v = x[which]
        if v is None or v < 3.0:
            continue
        g[key(x)].append(np.log(max(x["ppg"], 0.05) / v))
    res = {}
    for k, v in sorted(g.items(), key=lambda kv: str(kv[0])):
        if len(v) >= 25:
            v = np.array(v)
            res[str(k)] = dict(n=len(v), mean=round(float(v.mean()), 3), sd=round(float(v.std()), 3),
                               q10=round(float(np.exp(np.percentile(v, 10))), 2), q50=round(float(np.exp(np.percentile(v, 50))), 2),
                               q90=round(float(np.exp(np.percentile(v, 90))), 2))
    return res


REF_PPG = {"QB": 18.0, "RB": 11.0, "WR": 11.0, "TE": 8.0}


def tier(pos: str, ppg: float) -> str:
    x = ppg / REF_PPG[pos]
    return "elite" if x >= 1.45 else "starter" if x >= 1.0 else "flex" if x >= 0.6 else "depth"


def range_table(sl) -> list[dict]:
    """Empirical season-PPG outcome multipliers (actual PPG over games played / the preseason anchor) by position and
    anchor tier, and by position and rookie flag. Two anchors: Sleeper's week-1 projection (all player-seasons) and the
    shipped estimator's own week-1 value (returning players only). Cells under 25 player-seasons are dropped."""

    qs = (5, 10, 25, 50, 75, 90, 95)
    rows = []

    def add(anchor_name, key, items, anchor_key):
        g = defaultdict(list)
        for x in items:
            a = x[anchor_key]
            if a is None or a < 3.0:
                continue
            g[key(x)].append(max(x["ppg"], 0.05) / a)
        for k, v in sorted(g.items()):
            if len(v) >= 25:
                rows.append(dict(anchor=anchor_name, group=k, n=len(v), **{f"q{q:02d}": round(float(np.percentile(v, q)), 2) for q in qs}))

    for name, items, key_ in (("sleeper_week1", sl, "sleeper"), ("shipped_week1_estimate", [x for x in sl if x["est"] is not None], "est")):
        add(name, lambda x: f"{x['pos']} {tier(x['pos'], x[key_])}", items, key_)
        add(name, lambda x: f"{x['pos']} {'rookie' if x['rookie'] else 'veteran'}", items, key_)
        add(name, lambda x: f"{x['pos']} age {age_bucket(x['age'])}", items, key_)
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", default=None)
    ap.add_argument("--range-csv", default=None, help="write the season-PPG outcome-multiplier table here")
    args = ap.parse_args(argv)
    fields, rows = load_panel()
    recs = replay(fields, rows)
    tier = lambda x: "<5" if x["est"] < 5 else "5-10" if x["est"] < 10 else "10-15" if x["est"] < 15 else "15+"  # noqa: E731
    out = {
        "n_weekly": len(recs),
        "all": summarize(recs, lambda x: "all"),
        "by_pos": summarize(recs, lambda x: x["pos"]),
        "by_pos_tier": summarize(recs, lambda x: f"{x['pos']}:{tier(x)}"),
        "by_age": summarize(recs, lambda x: age_bucket(x["age"])),
        "by_pos_age": summarize(recs, lambda x: f"{x['pos']}:{age_bucket(x['age'])}"),
        "by_rookie": summarize(recs, lambda x: "rookie" if x["rookie"] else "vet"),
        "by_games": summarize(recs, lambda x: "g0 (week 1)" if x["games_cur"] == 0 else "g1-3" if x["games_cur"] < 4 else "g4+"),
        "by_prior_missed": summarize([x for x in recs if x["prior_missed"] is not None],
                                     lambda x: "prior missed 0-1" if x["prior_missed"] <= 1 else "2-4" if x["prior_missed"] <= 4 else "5+"),
        "by_season": summarize(recs, lambda x: x["season"]),
    }
    sl = season_level(fields, rows)
    seeded = [x for x in sl if x["est"] is not None]
    out["season_n"] = len(sl)
    out["season_with_week1_est"] = len(seeded)
    out["season_real_est"] = {
        "by_pos": ratio_stats(seeded, lambda x: x["pos"], "est"),
        "by_age": ratio_stats(seeded, lambda x: age_bucket(x["age"]), "est"),
        "by_pos_age": ratio_stats(seeded, lambda x: f"{x['pos']}:{age_bucket(x['age'])}", "est"),
        "by_prior_missed": ratio_stats([x for x in seeded if x["prior_missed"] is not None],
                                       lambda x: "prior missed 0-1" if x["prior_missed"] <= 1 else "2-4" if x["prior_missed"] <= 4 else "5+", "est"),
        "by_season": ratio_stats(seeded, lambda x: x["season"], "est"),
        "all": ratio_stats(seeded, lambda x: "all", "est"),
    }
    out["season_sleeper_same_players"] = {
        "by_pos": ratio_stats(seeded, lambda x: x["pos"], "sleeper"), "all": ratio_stats(seeded, lambda x: "all", "sleeper"),
        "by_age": ratio_stats(seeded, lambda x: age_bucket(x["age"]), "sleeper"),
        "by_prior_missed": ratio_stats([x for x in seeded if x["prior_missed"] is not None],
                                       lambda x: "prior missed 0-1" if x["prior_missed"] <= 1 else "2-4" if x["prior_missed"] <= 4 else "5+", "sleeper"),
    }
    out["season_sleeper_all"] = {
        "by_pos": ratio_stats(sl, lambda x: x["pos"], "sleeper"),
        "by_rookie": ratio_stats(sl, lambda x: "rookie" if x["rookie"] else "vet", "sleeper"),
        "by_pos_rookie": ratio_stats(sl, lambda x: f"{x['pos']}:{'rookie' if x['rookie'] else 'vet'}", "sleeper"),
    }
    if args.range_csv:
        tbl = range_table(sl)
        cols = ["anchor", "group", "n", "q05", "q10", "q25", "q50", "q75", "q90", "q95"]
        Path(args.range_csv).write_text("\n".join([",".join(cols)] + [",".join(str(r[c]) for c in cols) for r in tbl]) + "\n")
    text = json.dumps(out, indent=1, default=str)
    if args.json:
        Path(args.json).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Backtest: do simulated seasons look like the real ones?

Compares the player model's simulated outcomes with the real 2021-2025 outcomes
in ``data/panel.json.gz`` (see ``dataset.py``): preseason projection and ADP in,
actual weekly box scores out. Every real player-season is replayed through the
model ``--copies`` times with the standard seeding; the simulated outcome
distribution is then compared with the one real outcome per player.

Reported (all out-of-sample when ``--split`` holds seasons out of the fit):

* PIT calibration: where each real season PPG / season total falls in the model's
  predictive distribution for that player (uniform = calibrated), coverage of
  the 50/80/90% central intervals, KS distance.
* Tier hit rates (breakout >= 1.25x, bust <= 0.75x projection; top-12/24 finish
  rates) by position, age bucket, rookie vs veteran and preseason ADP tier, with
  the mean absolute error between simulated and real rates.
* Variance ratios: weekly SD/mean, boom/bust week rates, season-level SD, half-season split.
* Availability: games missed (mean, P(0), P(>=3), P(>=6), P(>=10)) and episode lengths.
* Stat-line sanity: per-game component means by position.

    python -m modules.sim.calibration.backtest [--copies 8] [--train 2021 2022 2023] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from typing import Any, Callable

import numpy as np

from modules.sim import player_model as pm
from modules.sim.calibration import dataset

PPR: dict[str, float] = {}  # empty scoring -> standard PPR, the units the real data is in
CORE = ("QB", "RB", "WR", "TE")
QUANTS = (5, 10, 25, 50, 75, 90, 95)


# ----------------------------------------------------------------------------- groups


def adp_tier(pos_rank: int | None) -> str:
    if pos_rank is None:
        return "unranked"
    if pos_rank <= 12:
        return "top12"
    if pos_rank <= 24:
        return "13-24"
    if pos_rank <= 36:
        return "25-36"
    return "37+"


def age_bucket(age: float | None) -> str:
    if age is None:
        return "?"
    if age < 24:
        return "<24"
    if age < 27:
        return "24-26"
    if age < 30:
        return "27-29"
    return "30+"


def proj_tier(pos: str, ppg: float) -> str:
    return pm.tier_label(pos, ppg)


def rank_by_adp(rows: list[dict]) -> dict[tuple[int, str], int]:
    """(season, pid) -> position rank by preseason ADP (1 = first off the board)."""

    out: dict[tuple[int, str], int] = {}
    by = defaultdict(list)
    for r in rows:
        if r["adp"] is not None:
            by[(r["season"], r["pos"])].append(r)
    for (_s, _p), grp in by.items():
        for i, r in enumerate(sorted(grp, key=lambda x: x["adp"]), 1):
            out[(r["season"], r["pid"])] = i
    return out


def group_keys(row: dict, pos_rank: int | None) -> dict[str, str]:
    return {
        "pos": row["pos"],
        "age": age_bucket(row["age"]),
        "rookie": "rookie" if row["rookie"] else "vet",
        "adp_tier": f"{row['pos']}:{adp_tier(pos_rank)}",
        "proj_tier": f"{row['pos']}:{proj_tier(row['pos'], row['proj_ppg'])}",
    }


# ----------------------------------------------------------------------------- simulation


def environment_for(season: int, copy: int) -> float:
    """The shared league-environment draw for one simulated copy of one season."""

    return pm.draw_environment(np.random.default_rng(np.random.SeedSequence(entropy=91_000 + season, spawn_key=(copy,))))


def simulate_row(row: dict, pos_rank: int | None, copy: int, params=None) -> dict[str, Any]:
    """One simulated season for a real player-season, summarised like ``season_summary``."""

    player = dataset.player_mapping(row, rank_in_pos=pos_rank)
    player["season_environment"] = environment_for(row["season"], copy)
    sp, ip = params if params else (pm.SEASON, pm.INSEASON)
    seed = 7_000_003 * (copy + 1) + row["season"]
    prof = pm._draw_season_profile(player, pm.profile_rng(seed, player["player_id"]), sp, ip)
    weeks = [
        pm._draw_week_points(player, prof, w, pm.week_rng(seed, player["player_id"], w), PPR, ip)
        for w in range(1, pm.SEASON_WEEKS + 1)
    ]
    avail = [i for i, m in enumerate(prof.games_available_mask) if m or prof.unavailable_reason[i] == "injury"]
    played = [w for w in weeks if w.active]
    pts = [w.points for w in played]
    stats = defaultdict(float)
    for w in played:
        for k, v in w.stats.items():
            stats[k] += v
    return {
        "available": len(avail), "played": len(played), "missed": len(avail) - len(played), "pts": pts,
        "ppg": (sum(pts) / len(pts)) if pts else 0.0, "total": sum(pts), "profile": prof, "stats": dict(stats),
        "weeks": weeks,
    }


def simulate_panel(rows: list[dict], copies: int, params=None) -> list[list[dict]]:
    ranks = rank_by_adp(rows)
    return [[simulate_row(r, ranks.get((r["season"], r["pid"])), c, params) for c in range(copies)] for r in rows]


# ----------------------------------------------------------------------------- metrics


def pit(real: float, sims: np.ndarray, rng: np.random.Generator) -> float:
    """Randomised PIT value of a real outcome in the simulated sample (handles ties/atoms)."""

    lo = float((sims < real).mean())
    hi = float((sims <= real).mean())
    return lo + (hi - lo) * float(rng.random())


def ks_uniform(values: np.ndarray) -> float:
    v = np.sort(values)
    n = len(v)
    if n == 0:
        return float("nan")
    grid = np.arange(1, n + 1) / n
    return float(max(np.max(grid - v), np.max(v - (grid - 1.0 / n))))


def pit_report(real_rows: list[dict], sim_rows: list[list[dict]], key: str = "ppg", min_played: int = 4) -> dict[str, Any]:
    rng = np.random.default_rng(11)
    vals = []
    for r, sims in zip(real_rows, sim_rows):
        real = dataset.season_summary(r)
        if real["played"] < min_played:
            continue
        s = np.array([x[key] for x in sims if x["played"] >= min_played])
        if len(s) < max(2, len(sims) // 2):
            continue
        vals.append(pit(real[key], s, rng))
    v = np.array(vals)
    if not len(v):
        return {"n": 0}

    def cov(level: float) -> float:
        lo, hi = (1 - level) / 2, 1 - (1 - level) / 2
        return float(((v >= lo) & (v <= hi)).mean())

    return {
        "n": int(len(v)), "ks": round(ks_uniform(v), 4), "mean_pit": round(float(v.mean()), 3),
        "cov50": round(cov(0.5), 3), "cov80": round(cov(0.8), 3), "cov90": round(cov(0.9), 3),
        "below_p10": round(float((v < 0.1).mean()), 3), "above_p90": round(float((v > 0.9).mean()), 3),
    }


def hit_rates(real: dict, ppg_proj: float) -> dict[str, float]:
    r = real["ppg"] / ppg_proj if ppg_proj > 0 else 0.0
    return {"breakout": float(r >= 1.25), "bust": float(r <= 0.75), "solid": float(0.75 < r < 1.25)}


def tier_hit_table(rows: list[dict], sims: list[list[dict]], group_fn: Callable[[dict], str], min_played: int = 4) -> list[dict]:
    """Per group: real vs simulated breakout/bust/solid rate (PPG vs projection) and MAE."""

    acc = defaultdict(lambda: {"n": 0, "real": defaultdict(float), "sim": defaultdict(float)})
    for r, ss in zip(rows, sims):
        real = dataset.season_summary(r)
        if real["played"] < min_played or r["proj_ppg"] < 3.0:
            continue
        g = acc[group_fn(r)]
        g["n"] += 1
        for k, v in hit_rates(real, r["proj_ppg"]).items():
            g["real"][k] += v
        ok = [x for x in ss if x["played"] >= min_played]
        if not ok:
            continue
        for x in ok:
            for k, v in hit_rates(x, r["proj_ppg"]).items():
                g["sim"][k] += v / len(ok)
    out = []
    for name, g in sorted(acc.items()):
        if g["n"] < 12:
            continue
        row = {"group": name, "n": g["n"]}
        for k in ("breakout", "bust"):
            row[f"real_{k}"] = round(g["real"][k] / g["n"], 3)
            row[f"sim_{k}"] = round(g["sim"][k] / g["n"], 3)
        out.append(row)
    return out


def tier_mae(table: list[dict]) -> float:
    errs = [abs(r[f"real_{k}"] - r[f"sim_{k}"]) for r in table for k in ("breakout", "bust")]
    return round(float(np.mean(errs)), 4) if errs else float("nan")


WEEKLY_STATS = {
    "QB": ("pass_att", "pass_yd", "pass_td", "rush_yd"),
    "RB": ("rush_att", "rush_yd", "rec_tgt", "rec", "rec_yd"),
    "WR": ("rec_tgt", "rec", "rec_yd"),
    "TE": ("rec_tgt", "rec", "rec_yd"),
    "K": ("fgm",),
}


def _stat_cv(rows, sims, pos, core_adp, norm) -> dict[str, dict[str, float]]:
    """Normalised weekly SD of each headline stat (yards, targets, ...), real vs simulated."""

    idx = {f: i + 1 for i, f in enumerate(dataset.STAT_FIELDS)}
    out = {}
    for stat in WEEKLY_STATS.get(pos, ()):
        zr, zs = [], []
        for r, ss in zip(rows, sims):
            if r["pos"] != pos or not (r["adp"] and r["adp"] <= core_adp):
                continue
            zr += norm([w[idx[stat]] for w in r["weeks"] if w and w[0]])
            for x in ss:
                zs += norm([w.stats.get(stat, 0.0) for w in x["weeks"] if w.active])
        if len(zr) > 100 and zs:
            out[stat] = {"real": round(float(np.std(zr)), 3), "sim": round(float(np.std(zs)), 3)}
    return out


def weekly_shape(rows: list[dict], sims: list[list[dict]], core_adp: float = 150.0) -> dict[str, Any]:
    """Weekly dispersion of played games normalised by the player's own half-season mean
    (removes slow role/form drift so the weekly noise is isolated), real vs simulated."""

    def norm(pts: list[float]) -> list[float]:
        h = len(pts) // 2
        if h < 5:
            return []
        a, b = pts[:h], pts[h:]
        ma, mb = float(np.mean(a)), float(np.mean(b))
        if ma <= 0.5 or mb <= 0.5:
            return []
        return [x / ma for x in a] + [x / mb for x in b]

    out: dict[str, Any] = {}
    for pos in CORE + ("K",):
        zr: list[float] = []
        zs: list[float] = []
        for r, ss in zip(rows, sims):
            if r["pos"] != pos or not (r["adp"] and r["adp"] <= core_adp):
                continue
            real = dataset.season_summary(r)
            zr += norm(real["pts"])
            for x in ss:
                zs += norm(x["pts"])
        if len(zr) < 200 or not zs:
            continue
        zr_a, zs_a = np.array(zr), np.array(zs)
        row = {"n_real": len(zr_a), "n_sim": len(zs_a)}
        for tag, a in (("real", zr_a), ("sim", zs_a)):
            row[f"{tag}_cv"] = round(float(a.std()), 3)
            row[f"{tag}_q"] = [round(float(np.percentile(a, q)), 2) for q in QUANTS]
            row[f"{tag}_boom"] = round(float((a > 1.6).mean()), 3)
            row[f"{tag}_bust"] = round(float((a < 0.4).mean()), 3)
        row["stat_cv"] = _stat_cv(rows, sims, pos, core_adp, norm)
        row["cv_ratio"] = round(row["sim_cv"] / row["real_cv"], 3)
        row["q_mae"] = round(float(np.mean(np.abs(np.array(row["sim_q"]) - np.array(row["real_q"])))), 3)
        out[pos] = row
    return out


def availability_report(rows: list[dict], sims: list[list[dict]], core_adp: float = 120.0) -> dict[str, Any]:
    def stats(missed: np.ndarray) -> dict[str, float]:
        return {
            "mean": round(float(missed.mean()), 2), "p0": round(float((missed == 0).mean()), 3),
            "p3": round(float((missed >= 3).mean()), 3), "p6": round(float((missed >= 6).mean()), 3),
            "p10": round(float((missed >= 10).mean()), 3),
        }

    out: dict[str, Any] = {}
    for label, pred in (
        ("all core", lambda r: True),
        *[(pos, (lambda p: lambda r: r["pos"] == p)(pos)) for pos in CORE],
        *[(f"age {b}", (lambda b_: lambda r: age_bucket(r["age"]) == b_)(b)) for b in ("<24", "24-26", "27-29", "30+")],
        ("rookies", lambda r: r["rookie"]),
    ):
        real_m, sim_m = [], []
        for r, ss in zip(rows, sims):
            if r["pos"] not in CORE or not ((r["adp"] and r["adp"] <= core_adp) or r["proj_ppg"] >= 9) or not pred(r):
                continue
            real_m.append(dataset.season_summary(r)["missed"])
            sim_m += [x["missed"] for x in ss]
        if len(real_m) >= 15:
            out[label] = {"n": len(real_m), "real": stats(np.array(real_m)), "sim": stats(np.array(sim_m))}
    return out


def season_variance_report(rows: list[dict], sims: list[list[dict]], min_played: int = 4) -> dict[str, Any]:
    """Variance ratio of log(season PPG / projection): simulated variance over real variance."""

    out: dict[str, Any] = {}
    groups = {
        "all": lambda r: True, **{p: (lambda q: lambda r: r["pos"] == q)(p) for p in CORE},
        "rookies": lambda r: r["rookie"], "veterans": lambda r: not r["rookie"],
        "proj >= 8": lambda r: r["proj_ppg"] >= 8, "proj < 8": lambda r: r["proj_ppg"] < 8,
    }
    for name, pred in groups.items():
        real_v, sim_v = [], []
        for r, ss in zip(rows, sims):
            if r["pos"] not in CORE or r["proj_ppg"] < 3.0 or not pred(r):
                continue
            x = dataset.season_summary(r)
            if x["played"] < min_played:
                continue
            real_v.append(x["ppg"] / r["proj_ppg"])
            sim_v += [y["ppg"] / r["proj_ppg"] for y in ss if y["played"] >= min_played]
        if len(real_v) < 30:
            continue
        lr, ls = np.log(np.maximum(real_v, 0.05)), np.log(np.maximum(sim_v, 0.05))
        out[name] = {"n": len(real_v), "real_sd": round(float(lr.std()), 3), "sim_sd": round(float(ls.std()), 3),
                     "var_ratio": round(float(ls.var() / lr.var()), 2), "real_mean": round(float(lr.mean()), 3),
                     "sim_mean": round(float(ls.mean()), 3)}
    return out


def finish_rates(rows: list[dict], sims: list[list[dict]]) -> dict[str, Any]:
    """Among each season's preseason ADP top-12 / 13-24 at a position, how often they finish
    top-12 / top-24 / outside the top 36 in season total points (real vs simulated)."""

    ranks = rank_by_adp(rows)
    by = defaultdict(list)
    for i, r in enumerate(rows):
        if r["pos"] in CORE and (r["season"], r["pid"]) in ranks:
            by[(r["season"], r["pos"])].append(i)
    cats = {"top12": (1, 12), "13-24": (13, 24)}
    res: dict[str, dict] = defaultdict(lambda: {"real": defaultdict(float), "sim": defaultdict(float), "n": 0})
    ncopy = len(sims[0]) if sims else 0
    for (season, pos), idxs in by.items():
        if len(idxs) < 24:
            continue
        for tag in ("real", *range(ncopy)):
            totals = {}
            for i in idxs:
                totals[i] = dataset.season_summary(rows[i])["total"] if tag == "real" else sims[i][tag]["total"]
            order = sorted(idxs, key=lambda i: -totals[i])
            fin = {i: k + 1 for k, i in enumerate(order)}
            for i in idxs:
                cat = next((c for c, (lo, hi) in cats.items() if lo <= ranks[(rows[i]["season"], rows[i]["pid"])] <= hi), None)
                if cat is None:
                    continue
                key = f"{pos}:{cat}"
                g = res[key]
                w = 1.0 if tag == "real" else 1.0 / ncopy
                tgt = g["real"] if tag == "real" else g["sim"]
                tgt["top12"] += w * (fin[i] <= 12)
                tgt["top24"] += w * (fin[i] <= 24)
                tgt["out36"] += w * (fin[i] > 36)
                if tag == "real":
                    g["n"] += 1
    out = {}
    for key, g in sorted(res.items()):
        if g["n"] < 10:
            continue
        out[key] = {"n": g["n"]}
        for m in ("top12", "top24", "out36"):
            out[key][f"real_{m}"] = round(g["real"][m] / g["n"], 3)
            out[key][f"sim_{m}"] = round(g["sim"][m] / g["n"], 3)
    return out


def split_half_report(rows: list[dict], sims: list[list[dict]]) -> dict[str, Any]:
    def ratio(pts: list[float]) -> float | None:
        if len(pts) < 12:
            return None
        h = len(pts) // 2
        a, b = float(np.mean(pts[:h])), float(np.mean(pts[h:]))
        return float(np.log(max(b, 0.5) / max(a, 0.5)))

    rr, ss_ = [], []
    for r, ss in zip(rows, sims):
        if r["pos"] not in CORE or not ((r["adp"] and r["adp"] <= 120) or r["proj_ppg"] >= 9):
            continue
        x = ratio(dataset.season_summary(r)["pts"])
        if x is not None:
            rr.append(x)
        for s in ss:
            y = ratio(s["pts"])
            if y is not None:
                ss_.append(y)
    rr_a, ss_a = np.array(rr), np.array(ss_)
    return {
        "n_real": len(rr_a), "real_sd": round(float(rr_a.std()), 3), "sim_sd": round(float(ss_a.std()), 3),
        "real_q": [round(float(np.percentile(rr_a, q)), 2) for q in (5, 25, 50, 75, 95)],
        "sim_q": [round(float(np.percentile(ss_a, q)), 2) for q in (5, 25, 50, 75, 95)],
    }


def lag1_report(rows: list[dict], sims: list[list[dict]]) -> dict[str, float]:
    def ac(pts: list[float]) -> float | None:
        if len(pts) < 8:
            return None
        z = np.array(pts) - np.mean(pts)
        d = float((z * z).sum())
        return float((z[:-1] * z[1:]).sum() / d) if d > 0 else None

    rr, ss_ = [], []
    for r, ss in zip(rows, sims):
        if r["pos"] not in CORE or not (r["adp"] and r["adp"] <= 150):
            continue
        x = ac(dataset.season_summary(r)["pts"])
        if x is not None:
            rr.append(x)
        ss_ += [y for y in (ac(s["pts"]) for s in ss) if y is not None]
    return {"real": round(float(np.mean(rr)), 3), "sim": round(float(np.mean(ss_)), 3)}


def stat_line_report(rows: list[dict], sims: list[list[dict]]) -> dict[str, Any]:
    keys = {
        "QB": ("pass_att", "pass_cmp", "pass_yd", "pass_td", "pass_int", "rush_att", "rush_yd", "rush_td"),
        "RB": ("rush_att", "rush_yd", "rush_td", "rec_tgt", "rec", "rec_yd", "rec_td"),
        "WR": ("rec_tgt", "rec", "rec_yd", "rec_td"),
        "TE": ("rec_tgt", "rec", "rec_yd", "rec_td"),
    }
    idx = {f: i + 1 for i, f in enumerate(dataset.STAT_FIELDS)}
    out: dict[str, Any] = {}
    for pos, ks in keys.items():
        real = defaultdict(float)
        sim = defaultdict(float)
        gr = gs = 0
        for r, ss in zip(rows, sims):
            if r["pos"] != pos or not (r["adp"] and r["adp"] <= 100):
                continue
            for w in r["weeks"]:
                if w and w[0]:
                    gr += 1
                    for k in ks:
                        real[k] += w[idx[k]]
            for s in ss:
                gs += s["played"]
                for k in ks:
                    sim[k] += s["stats"].get(k, 0.0)
        if gr and gs:
            out[pos] = {k: {"real": round(real[k] / gr, 2), "sim": round(sim[k] / gs, 2)} for k in ks}
    return out


def _row(cells) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def render_markdown(res: dict[str, Any]) -> str:
    """The result as the tables in docs/fantasy-sim-player-model.md."""

    out: list[str] = []
    out += ["### Season PPG percentile calibration (PIT)", "",
            _row(["group", "n", "KS", "mean PIT", "50% cov", "80% cov", "90% cov", "< p10", "> p90"]), _row(["---"] * 9)]
    for g, p in res["pit"].items():
        if p.get("n"):
            out.append(_row([g, p["n"], p["ks"], p["mean_pit"], p["cov50"], p["cov80"], p["cov90"], p["below_p10"], p["above_p90"]]))
    out += ["", "### Tier hit rates (breakout >= 1.25x projection PPG, bust <= 0.75x)", ""]
    for name, table in res["tier_hit"].items():
        out += [f"**{name}** (MAE {res['tier_hit_mae'][name]})", "",
                _row(["group", "n", "real breakout", "sim breakout", "real bust", "sim bust"]), _row(["---"] * 6)]
        out += [_row([t["group"], t["n"], t["real_breakout"], t["sim_breakout"], t["real_bust"], t["sim_bust"]]) for t in table]
        out.append("")
    out += [f"Overall tier-hit MAE: **{res['tier_hit_mae']['overall']}**", "", "### Weekly variance (played games, normalised by own half-season mean)", "",
            _row(["pos", "real SD", "sim SD", "ratio", "real q05/25/50/75/95", "sim q05/25/50/75/95", "boom real/sim", "bust real/sim"]), _row(["---"] * 8)]
    for pos, r in res["weekly"].items():
        q = lambda a: "/".join(str(x) for x in (a[0], a[2], a[3], a[4], a[6]))  # noqa: E731
        out.append(_row([pos, r["real_cv"], r["sim_cv"], r["cv_ratio"], q(r["real_q"]), q(r["sim_q"]),
                         f"{r['real_boom']}/{r['sim_boom']}", f"{r['real_bust']}/{r['sim_bust']}"]))
    out += ["", "Per-stat weekly SD (real / sim): " + "; ".join(
        f"{pos}: " + ", ".join(f"{k} {v['real']}/{v['sim']}" for k, v in r["stat_cv"].items()) for pos, r in res["weekly"].items()), "",
            "### Games missed (core fantasy players)", "",
            _row(["group", "n", "mean real/sim", "P(0) real/sim", "P(>=3)", "P(>=6)", "P(>=10)"]), _row(["---"] * 7)]
    for g, a in res["availability"].items():
        r, s = a["real"], a["sim"]
        out.append(_row([g, a["n"], f"{r['mean']}/{s['mean']}", f"{r['p0']}/{s['p0']}", f"{r['p3']}/{s['p3']}", f"{r['p6']}/{s['p6']}", f"{r['p10']}/{s['p10']}"]))
    out += ["", "### Preseason-ADP rank vs season finish (share of group)", "",
            _row(["group", "n", "top-12 real/sim", "top-24 real/sim", "outside 36 real/sim"]), _row(["---"] * 5)]
    for g, r in res["finish"].items():
        out.append(_row([g, r["n"], f"{r['real_top12']}/{r['sim_top12']}", f"{r['real_top24']}/{r['sim_top24']}", f"{r['real_out36']}/{r['sim_out36']}"]))
    h = res["half_split"]
    out += ["", "### Season-level variance ratio (log of season PPG / projection)", "",
            _row(["group", "n", "real SD", "sim SD", "var ratio (sim/real)", "real mean", "sim mean"]), _row(["---"] * 7)]
    for g, v in res["season_variance"].items():
        out.append(_row([g, v["n"], v["real_sd"], v["sim_sd"], v["var_ratio"], v["real_mean"], v["sim_mean"]]))
    out += ["", f"Half-season split log-ratio SD: real {h['real_sd']}, sim {h['sim_sd']}; lag-1 autocorrelation: real {res['lag1']['real']}, sim {res['lag1']['sim']}.", "",
            "### Per-game stat lines (ADP top 100)", ""]
    for pos, d in res["stat_lines"].items():
        out.append(f"- {pos}: " + ", ".join(f"{k} {v['real']}/{v['sim']}" for k, v in d.items()))
    return "\n".join(out)


# ----------------------------------------------------------------------------- driver


def run(rows: list[dict], copies: int, params=None) -> dict[str, Any]:
    sims = simulate_panel(rows, copies, params)
    ranks = rank_by_adp(rows)
    by = lambda fn: (lambda r: fn(r, ranks.get((r["season"], r["pid"]))))  # noqa: E731
    pit_groups: dict[str, Any] = {"all": pit_report(rows, sims), "all_total": pit_report(rows, sims, "total")}
    for season in sorted({r["season"] for r in rows}):
        sel = [i for i, r in enumerate(rows) if r["season"] == season and r["pos"] in CORE]
        pit_groups[f"season {season}"] = pit_report([rows[i] for i in sel], [sims[i] for i in sel])
    for pos in CORE:
        sel = [i for i, r in enumerate(rows) if r["pos"] == pos]
        pit_groups[pos] = pit_report([rows[i] for i in sel], [sims[i] for i in sel])
    for name, pred in (
        ("rookies", lambda r: r["rookie"]), ("veterans", lambda r: not r["rookie"]),
        *[(f"age {b}", (lambda b_: lambda r: age_bucket(r["age"]) == b_ and not r["rookie"])(b)) for b in ("<24", "24-26", "27-29", "30+")],
    ):
        sel = [i for i, r in enumerate(rows) if r["pos"] in CORE and pred(r)]
        pit_groups[name] = pit_report([rows[i] for i in sel], [sims[i] for i in sel])
    tables = {
        "by_pos": tier_hit_table([r for r in rows if r["pos"] in CORE], [s for r, s in zip(rows, sims) if r["pos"] in CORE], lambda r: r["pos"]),
        "by_age": tier_hit_table([r for r in rows if r["pos"] in CORE], [s for r, s in zip(rows, sims) if r["pos"] in CORE], lambda r: age_bucket(r["age"])),
        "by_rookie": tier_hit_table([r for r in rows if r["pos"] in CORE], [s for r, s in zip(rows, sims) if r["pos"] in CORE], lambda r: "rookie" if r["rookie"] else "vet"),
        "by_proj_tier": tier_hit_table([r for r in rows if r["pos"] in CORE], [s for r, s in zip(rows, sims) if r["pos"] in CORE], lambda r: proj_tier(r["pos"], r["proj_ppg"])),
        "by_adp_tier": tier_hit_table(
            [r for r in rows if r["pos"] in CORE], [s for r, s in zip(rows, sims) if r["pos"] in CORE],
            lambda r: adp_tier(ranks.get((r["season"], r["pid"]))),
        ),
    }
    tier_all = [row for t in tables.values() for row in t]
    return {
        "n_rows": len(rows), "copies": copies, "pit": pit_groups, "tier_hit": tables,
        "tier_hit_mae": {k: tier_mae(v) for k, v in tables.items()} | {"overall": tier_mae(tier_all)},
        "season_variance": season_variance_report(rows, sims), "weekly": weekly_shape(rows, sims), "availability": availability_report(rows, sims),
        "finish": finish_rates(rows, sims), "half_split": split_half_report(rows, sims),
        "lag1": lag1_report(rows, sims), "stat_lines": stat_line_report(rows, sims),
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--copies", type=int, default=8)
    ap.add_argument("--seasons", nargs="*", type=int, default=None, help="seasons to score (default: all)")
    ap.add_argument("--json", type=str, default=None)
    ap.add_argument("--markdown", action="store_true", help="print the doc tables instead of JSON")
    args = ap.parse_args(argv)
    rows = [r for r in dataset.load_panel() if args.seasons is None or r["season"] in args.seasons]
    result = run(rows, args.copies)
    text = json.dumps(result, indent=1, default=str)
    if args.json:
        with open(args.json, "w") as fh:
            fh.write(text)
    print(render_markdown(result) if args.markdown else text)


if __name__ == "__main__":
    main()

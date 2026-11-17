"""Fantasy Sim player model vs real NFL seasons 2015-2025 (nflverse), season-level distributions.

Audit of 2026-11 (``docs/audits/2026-11-projections-backtest.md``, Part B). The sim side is whole dynasty runs from
``dynasty_run`` on the 2025 panel pool (never ``data/players.db``); the real side is nflverse weekly player stats,
weeks 1-17 (the sim plays 17 weeks with a bye), PPR, players with 8+ games (the same rule as ``season_variance_report``).

    python -m modules.sim.calibration.real_history_report --real /tmp/real_rows.json --seeds 6 --seasons 5 --json out.json --charts docs/audits/projections-backtest

Compared, sim vs real, by position (QB/RB/WR/TE) and by the player's finish (ppg rank 1-12, 13-24, 25-36):

* ``tails``      ppg p10 / p50 / p90 (and mean) of that tier.
* ``next``       the top-12 by ppg, next-year / this-year ppg (same NFL team, 8+ games both years): p10 / p25 / p50 / p90 and share < 0.7.
* ``movers``     breakouts per season (outside the top 24, or under 8 games, then top 12 next year) and busts (top 12, then outside the top 24
                 or under 8 games).
* ``aging``      mean next / this ppg by age bucket (8+ games both years, ppg >= 8).
* ``games``      games missed among last year's top-N (QB 12, RB 24, WR 36, TE 12), age <= 31: mean share missed, share with < 8 games.
* ``scarcity``   ppg of the position's rank-k finisher (k = 1, 6, 12, 24, 36).

Configurations compared on the sim side: the current default for new games (player-model-8 + stability_v 3 + rookie_v 1), the same with stability_v 2 (the previous default), with
``rookie_v`` 0, with ``stability_v`` 1 / ``rookie_v`` 0, with the star terms off (player-model-7 behaviour), and a legacy save (stability_v 0 / rookie_v 0).
"""

from __future__ import annotations


import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

POS = ("QB", "RB", "WR", "TE")
TIERS = (("top-12", 1, 12), ("13-24", 13, 24), ("25-36", 25, 36))
AGE_BUCKETS = ((0, 24), (25, 26), (27, 28), (29, 30), (31, 99))
TOPN = {"QB": 12, "RB": 24, "WR": 36, "TE": 12}
CONFIGS = {
    "model-8 default": {},
    "stability_v 2 (previous default)": {"stability_v": 2},
    "rookie_v 0": {"rookie_v": 0},
    "stability_v 1, rookie_v 0": {"stability_v": 1, "rookie_v": 0},
    "legacy (stability_v 0, rookie_v 0)": {"stability_v": 0, "rookie_v": 0},
    "star terms off (model-7)": {"__star_off__": True},
}


# --------------------------------------------------------------------------- real
# --------------------------------------------------------------------------- sim
def sim_rows(seed: int, n_seasons: int, flags: dict[str, Any]) -> list[dict[str, Any]]:
    from modules.sim import player_model
    from modules.sim.calibration import dynasty_run

    flags = dict(flags)
    star_off = flags.pop("__star_off__", False)
    saved = player_model.SEASON
    if star_off:
        player_model.SEASON = replace(player_model.SEASON, bust_sd_star=0.0, pu_star=0.0)
    try:
        seasons = dynasty_run.run(seed, n_seasons, flags=flags or None, profiles=True)
    finally:
        player_model.SEASON = saved
    rows = []
    for idx, a in enumerate(seasons):
        gp = {pid: (v[0], v[2], None) for pid, v in a.get("tot", {}).items() if v[0] in POS}
        for pid, (pos, ppg, age, _tot, n) in a["pl"].items():
            if pos in POS:
                rows.append({"run": f"{seed}", "season": idx, "pid": pid, "pos": pos, "ppg": ppg, "g": n, "age": age, "team": a["nfl"].get(pid)})
        for pid, (pos, g, age) in gp.items():
            rows.append({"run": f"{seed}", "season": idx, "pid": pid, "pos": pos, "ppg": None, "g": g, "age": age, "team": a["nfl"].get(pid), "gp_only": True})
    return rows


# --------------------------------------------------------------------------- tables
def _q(x, qs):
    return [round(float(np.quantile(x, q)), 3) for q in qs]


def tables(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """All the comparison tables for one population of player-seasons (real or one sim configuration)."""
    played = [r for r in rows if r.get("ppg") is not None and r["g"] >= 8 and not r.get("gp_only")]
    by_key: dict[tuple, dict] = {(r["run"], r["season"], r["pid"]): r for r in played}
    rank: dict[tuple, int] = {}
    groups: dict[tuple, list] = {}
    for r in played:
        groups.setdefault((r["run"], r["season"], r["pos"]), []).append(r)
    for (run, season, pos), g in groups.items():
        for i, r in enumerate(sorted(g, key=lambda x: -x["ppg"]), 1):
            rank[(run, season, r["pid"])] = i
    out: dict[str, Any] = {"tails": {}, "next": {}, "movers": {}, "aging": {}, "games": {}, "scarcity": {}}
    for pos in POS:
        for name, lo, hi in TIERS:
            v = [r["ppg"] for r in played if r["pos"] == pos and lo <= rank[(r["run"], r["season"], r["pid"])] <= hi]
            if v:
                out["tails"][f"{pos} {name}"] = {"n": len(v), "mean": round(float(np.mean(v)), 2), "p10": _q(v, [0.1])[0], "p50": _q(v, [0.5])[0], "p90": _q(v, [0.9])[0]}
        nxt = []
        for r in played:
            if r["pos"] != pos or rank[(r["run"], r["season"], r["pid"])] > 12:
                continue
            n = by_key.get((r["run"], r["season"] + 1, r["pid"]))
            if n and n["team"] == r["team"]:
                nxt.append(n["ppg"] / r["ppg"])
        if nxt:
            nxt = np.array(nxt)
            q = _q(nxt, [0.1, 0.25, 0.5, 0.9])
            out["next"][pos] = {"n": len(nxt), "p10": q[0], "p25": q[1], "p50": q[2], "p90": q[3], "under_0.7": round(float((nxt < 0.7).mean()), 3)}
        seasons = sorted({(r["run"], r["season"]) for r in played})
        pairs = [(a, (a[0], a[1] + 1)) for a in seasons if (a[0], a[1] + 1) in set(seasons)]
        nb = nbu = nseas = 0
        for a, b in pairs:
            cur_top = {r["pid"] for r in played if (r["run"], r["season"]) == a and r["pos"] == pos and rank[(a[0], a[1], r["pid"])] <= 12}
            cur_mid = {r["pid"] for r in played if (r["run"], r["season"]) == a and r["pos"] == pos and rank[(a[0], a[1], r["pid"])] <= 24}
            nxt_top = {r["pid"] for r in played if (r["run"], r["season"]) == b and r["pos"] == pos and rank[(b[0], b[1], r["pid"])] <= 12}
            # a "breakout" must have been somebody's player the year before: outside the top 24 (or under 8 games) but in the pool
            pool_prev = {r["pid"] for r in rows if (r["run"], r["season"]) == a and r["pos"] == pos}
            nb += len([p for p in nxt_top if p in pool_prev and p not in cur_mid])
            nbu += len([p for p in cur_top if p not in {r["pid"] for r in played if (r["run"], r["season"]) == b and r["pos"] == pos and rank[(b[0], b[1], r["pid"])] <= 24}])
            nseas += 1
        out["movers"][pos] = {"seasons": nseas, "breakouts_per_season": round(nb / max(nseas, 1), 2), "busts_per_season": round(nbu / max(nseas, 1), 2)}
        ag = {}
        for lo, hi in AGE_BUCKETS:
            ratios = []
            for r in played:
                if r["pos"] != pos or r["age"] is None or not lo <= int(r["age"]) <= hi or r["ppg"] < 8:
                    continue
                n = by_key.get((r["run"], r["season"] + 1, r["pid"]))
                if n:
                    ratios.append(n["ppg"] / r["ppg"])
            if len(ratios) >= 15:
                ag[f"{lo}-{hi}" if hi < 99 else f"{lo}+"] = {"n": len(ratios), "mean": round(float(np.mean(ratios)), 3), "median": round(float(np.median(ratios)), 3)}
        out["aging"][pos] = ag
        gp = {(r["run"], r["season"], r["pid"]): r["g"] for r in rows if r["pos"] == pos}
        gp_season = {(r["run"], r["season"]): True for r in rows}
        missed, lt8 = [], []
        for r in played:
            if r["pos"] != pos or rank[(r["run"], r["season"], r["pid"])] > TOPN[pos] or (r["age"] or 0) > 31:
                continue
            key = (r["run"], r["season"] + 1, r["pid"])
            if (r["run"], r["season"] + 1) not in gp_season:
                continue
            g = gp.get(key, 0)
            missed.append(1 - min(g, 16) / 16)
            lt8.append(g < 8)
        if missed:
            out["games"][pos] = {"n": len(missed), "mean_share_missed": round(float(np.mean(missed)), 3), "share_under_8": round(float(np.mean(lt8)), 3)}
        sc = {}
        for k in (1, 6, 12, 24, 36):
            v = [r["ppg"] for r in played if r["pos"] == pos and rank[(r["run"], r["season"], r["pid"])] == k]
            if len(v) >= 3:
                sc[str(k)] = round(float(np.mean(v)), 2)
        out["scarcity"][pos] = sc
    return out


# --------------------------------------------------------------------------- driver
def _one(args):
    seed, n, flags = args
    return sim_rows(seed, n, flags)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--real", type=Path, required=True, help="JSON from scripts/real_history_rows.py (nflverse 2015-2025 player-seasons)")
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--seasons", type=int, default=5)
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--configs", nargs="*", default=None, help="subset of config names")
    args = ap.parse_args(argv)
    from multiprocessing import Pool

    real = json.loads(args.real.read_text())
    result: dict[str, Any] = {"real 2015-2025": tables(real), "real 2021-2025": tables([r for r in real if r["season"] >= 2021])}
    for name, flags in CONFIGS.items():
        if args.configs and name not in args.configs:
            continue
        with Pool(args.procs) as pool:
            chunks = pool.map(_one, [(s, args.seasons, flags) for s in range(1, 1 + args.seeds)])
        rows = [r for c in chunks for r in c]
        result[name] = tables(rows)
        print("done", name, flush=True)
    if args.json:
        args.json.write_text(json.dumps(result, indent=1))
    print(json.dumps(result["real 2015-2025"]["next"], indent=1))


if __name__ == "__main__":
    main()

"""Fit the points-over-replacement -> value curve that puts IDP on the offensive scale.

IDP has no observed market (FantasyCalc publishes no IDP values), so the
conversion is anchored to offense: for QB/RB/WR/TE, regress the market value
(data/fantasycalc_values.csv, 0-10,000 scale) on last season's PPR points above a
positional replacement level (12-team 1QB lineup depth), as ``value = a * VOR ** p``.
The same curve is then applied to a defender's projected points over his own
league-specific replacement level.

Usage: python scripts/idp_value_curve.py --stats data/sleeper_player_stats_2025.json \
    --players data/sleeper_players.json --fc data/fantasycalc_values.csv [--params modules/idp_model_params.json]
"""

from __future__ import annotations

import argparse
import csv
import json
import re

import numpy as np

# 12-team, 1 QB / 2 RB / 3 WR / 1 TE / 2 FLEX: replacement = first player outside the starters.
REPLACEMENT_RANK = {"QB": 14, "RB": 30, "WR": 40, "TE": 16}


def norm(name: str) -> str:
    return re.sub(r"[^a-z]", "", re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", name.lower()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", required=True)
    ap.add_argument("--players", required=True)
    ap.add_argument("--fc", required=True)
    ap.add_argument("--params", default=None)
    a = ap.parse_args()
    stats = json.load(open(a.stats))
    players = json.load(open(a.players))
    fc = {}
    for row in csv.DictReader(open(a.fc)):
        if row["position"] in REPLACEMENT_RANK:
            fc[(norm(row["name"]), row["position"])] = float(row["value"])
    pts = {pos: [] for pos in REPLACEMENT_RANK}
    named = []
    for pid, s in stats.items():
        p = players.get(pid) or {}
        pos = p.get("position")
        total = s.get("fantasy_points_ppr")
        if pos in REPLACEMENT_RANK and total is not None and p.get("full_name"):
            pts[pos].append(float(total))
            named.append((norm(p["full_name"]), pos, float(total)))
    repl = {pos: sorted(v, reverse=True)[REPLACEMENT_RANK[pos] - 1] for pos, v in pts.items()}
    xs, ys = [], []
    for key, pos, total in named:
        value = fc.get((key, pos))
        vor = total - repl[pos]
        if value and value >= 1000 and vor > 5:
            xs.append(vor)
            ys.append(value)
    lx, ly = np.log(xs), np.log(ys)
    p, loga = np.polyfit(lx, ly, 1)
    pred = loga + p * lx
    r2 = 1 - float(np.sum((ly - pred) ** 2) / np.sum((ly - ly.mean()) ** 2))
    curve = {"a": round(float(np.exp(loga)), 4), "p": round(float(p), 4), "r2_log": round(r2, 3), "n": len(xs), "replacement_points": repl, "cap": 9000}
    print(curve)
    for vor in (20, 50, 100, 150, 200):
        print(vor, round(curve["a"] * vor ** curve["p"]))
    if a.params:
        params = json.load(open(a.params))
        params["value_curve"] = curve
        json.dump(params, open(a.params, "w"), indent=1, sort_keys=True)


if __name__ == "__main__":
    main()

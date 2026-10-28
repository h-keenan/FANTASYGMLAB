#!/usr/bin/env python3
"""Calibration / sanity check for trade engine v2 (docs/trade-engine-v2.md).

Builds twelve realistic synthetic dynasty rosters from the players table
(a value-ordered snake draft with positional need), treats everyone left as
the waiver pool, generates market-plausible trade cases for every team and
posture, and grades each with the v2 model and with the previous engine
(the same code with the lineup model switched off). Prints sanity stats and
examples as JSON so the doc numbers are reproducible.

Safe by construction: works on a THROWAWAY COPY of the players database
opened with sqlite3 directly. It never calls rankings.load_players /
build_players_table and never writes to the real data/players.db.

    python scripts/trade_engine_v2_calibration.py [--db data/players.db] [--cases 600] [--seed 7] [--week 8]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sqlite3
import statistics
import sys
import tempfile
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

from modules import nfl_schedule, trade_analyzer_fit, trade_lineup_model, trade_offer_analyzer  # noqa: E402

SETTINGS = {
    "league_format": "Dynasty", "qb_format": "1QB", "qb_count": 1, "rb_count": 2, "wr_count": 3, "te_count": 1,
    "k_count": 0, "def_count": 0, "flex_count": 1, "superflex_count": 0, "league_size": 12,
}
STRATEGIES = ("contender", "retool", "rebuild")
TEAMS = 12
ROSTER_NEED = {"QB": 3, "RB": 7, "WR": 8, "TE": 3}
THIN_ROSTER_NEED = {"QB": 2, "RB": 3, "WR": 4, "TE": 1}  # stress case: little depth, holes are real


def load_frame(db_path: str) -> pd.DataFrame:
    tmpdir = tempfile.mkdtemp(prefix="v2calib_")
    copy = os.path.join(tmpdir, "players_copy.db")
    shutil.copyfile(db_path, copy)
    conn = sqlite3.connect(f"file:{copy}?mode=ro", uri=True)
    try:
        df = pd.read_sql(
            "select player_id, name, position, team, age, status, injury_status, injury_body_part, injury_notes, "
            "ppg, games_played, receptions, dynasty_score, value_score, risk_multiplier from players "
            "where position in ('QB','RB','WR','TE') and dynasty_score is not null and dynasty_score > 0",
            conn,
        )
    finally:
        conn.close()
        shutil.rmtree(tmpdir, ignore_errors=True)
    df["player_id"] = df["player_id"].astype(str)
    df["score"] = df["dynasty_score"]
    df["injury_status"] = df["injury_status"].fillna("")
    df["status"] = df["status"].fillna("Active")
    df["team"] = df["team"].fillna("")
    return df.sort_values("dynasty_score", ascending=False).reset_index(drop=True)


def draft(df: pd.DataFrame, rng: random.Random):
    rosters: list[list[str]] = [[] for _ in range(TEAMS)]
    taken: set[str] = set()
    counts = [Counter() for _ in range(TEAMS)]
    order = list(range(TEAMS))
    for rnd in range(22):
        for t in (order if rnd % 2 == 0 else order[::-1]):
            for _, row in df.iterrows():
                pid = row["player_id"]
                pos = row["position"]
                if pid in taken or counts[t][pos] >= ROSTER_NEED[pos]:
                    continue
                if rng.random() < 0.25:  # not everyone drafts straight by value
                    continue
                taken.add(pid)
                rosters[t].append(pid)
                counts[t][pos] += 1
                break
    return rosters, taken


def asset(row) -> dict:
    return {"asset_type": "player", "player_id": row["player_id"], "name": row["name"], "label": row["name"],
            "position": row["position"], "team": row["team"], "status": row["status"],
            "injury_status": row["injury_status"], "age": row["age"],
            "score": int(row["dynasty_score"]), "value_score": int(row["value_score"] or 0)}


def pick_asset(value: int) -> dict:
    return {"asset_type": "pick", "label": "2027 Round", "season": 2027, "round": 2, "score": int(value), "value_score": int(value)}


def grade(roster_df, universe, waiver, send, receive, strategy, week, legacy: bool):
    settings = dict(SETTINGS, current_week=week)
    original = trade_lineup_model.evaluate_trade
    if legacy:
        def boom(*a, **k):
            raise RuntimeError("legacy engine")
        trade_lineup_model.evaluate_trade = boom
    try:
        fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
            roster_df, universe, send, receive, None, strategy, settings, "dynasty_score", waiver_df=waiver
        )
    finally:
        trade_lineup_model.evaluate_trade = original
    if not fit:
        return None, None
    verdict = trade_offer_analyzer.decide_offer_verdict(fit, send_assets=send, receive_assets=receive)
    return fit, verdict


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "players.db"))
    ap.add_argument("--cases", type=int, default=600)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--week", type=int, default=8)
    ap.add_argument("--dump", default="", help="optional path: write every case as JSON")
    ap.add_argument("--thin", action="store_true", help="thin rosters (QB2/RB3/WR4/TE1): stress the hole logic")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    if args.thin:
        ROSTER_NEED.update(THIN_ROSTER_NEED)
    # No schedule data offline: byes are not applied (never invented).
    nfl_schedule.team_bye_week = lambda team, season, **kw: None

    df = load_frame(args.db)
    rosters, taken = draft(df, rng)
    by_id = df.set_index("player_id", drop=False)
    waiver = df[~df["player_id"].isin(taken)].copy()
    cases = []
    started = time.time()
    for n in range(args.cases):
        t = n % TEAMS
        strategy = STRATEGIES[(n // TEAMS) % len(STRATEGIES)]
        mine = by_id.loc[rosters[t]]
        other = by_id.loc[rosters[(t + 1 + rng.randrange(TEAMS - 1)) % TEAMS]]
        kind = rng.choice(["swap", "sell_for_pick", "buy_with_pick", "consolidate", "sell_bench_for_pick"])
        top_mine = mine.sort_values("dynasty_score", ascending=False)
        send, receive = [], []
        if kind == "swap":
            a = top_mine.iloc[rng.randrange(min(12, len(top_mine)))]
            cand = other[(other["dynasty_score"] > a["dynasty_score"] * 0.85) & (other["dynasty_score"] < a["dynasty_score"] * 1.15)]
            if cand.empty:
                continue
            send, receive = [asset(a)], [asset(cand.iloc[rng.randrange(len(cand))])]
        elif kind == "sell_for_pick":
            a = top_mine.iloc[rng.randrange(min(10, len(top_mine)))]
            send, receive = [asset(a)], [pick_asset(a["dynasty_score"] * rng.uniform(0.85, 1.15))]
        elif kind == "sell_bench_for_pick":
            a = top_mine.iloc[-1 - rng.randrange(min(3, len(top_mine)))]
            send, receive = [asset(a)], [pick_asset(a["dynasty_score"] * rng.uniform(0.85, 1.15))]
        elif kind == "buy_with_pick":
            cand = other.sort_values("dynasty_score", ascending=False).iloc[: 12]
            b = cand.iloc[rng.randrange(len(cand))]
            send, receive = [pick_asset(b["dynasty_score"] * rng.uniform(0.85, 1.15))], [asset(b)]
        else:  # consolidate two for one
            hi = min(12, len(top_mine))
            a1, a2 = top_mine.iloc[rng.randrange(min(4, hi - 1), hi)], top_mine.iloc[rng.randrange(min(4, hi - 1), hi)]
            if a1["player_id"] == a2["player_id"]:
                continue
            total = a1["dynasty_score"] + a2["dynasty_score"]
            cand = other[(other["dynasty_score"] > total * 0.8) & (other["dynasty_score"] < total * 1.1)]
            if cand.empty:
                continue
            send, receive = [asset(a1), asset(a2)], [asset(cand.iloc[rng.randrange(len(cand))])]
        universe = pd.concat([mine, other, waiver], ignore_index=True).drop_duplicates("player_id")
        new_fit, new_v = grade(mine, universe, waiver, send, receive, strategy, args.week, legacy=False)
        old_fit, old_v = grade(mine, universe, waiver, send, receive, strategy, args.week, legacy=True)
        if not new_fit or not old_fit or not new_fit.get("lineup_model"):
            continue
        m = new_fit["lineup_model"]
        cases.append({
            "kind": kind, "strategy": strategy, "send": [a["label"] for a in send], "receive": [a["label"] for a in receive],
            "old_tone": old_v.tone, "new_tone": new_v.tone, "old_band": old_v.band, "new_band": new_v.band,
            "value_delta": new_fit["value_delta"], "old_value_delta": old_fit["value_delta"], "trade_score": new_fit["trade_score"],
            "ros_points_delta": m["points"]["ros_delta"], "context_points": m["points"]["friction_delta"],
            "confidence_pct": m["confidence_pct"], "old_conf": old_v.confidence, "new_conf": new_v.confidence,
            "worst_position": m["worst_position"], "basis": m["basis_counts"], "explanation": m["explanation"],
            "pickup": (m.get("pickup") or {}).get("name"), "points": m["points"], "components": m["components"],
        })
    elapsed = time.time() - started

    changed = [c for c in cases if c["old_tone"] != c["new_tone"]]
    order = {"decline": 0, "counter": 1, "fair": 2, "accept": 3}
    harsher = [c for c in changed if order[c["new_tone"]] < order[c["old_tone"]]]
    kinder = [c for c in changed if order[c["new_tone"]] > order[c["old_tone"]]]
    by_kind = {k: {"n": sum(1 for c in cases if c["kind"] == k),
                   "changed": sum(1 for c in changed if c["kind"] == k)} for k in sorted({c["kind"] for c in cases})}
    by_posture = {s: {"n": sum(1 for c in cases if c["strategy"] == s),
                      "changed": sum(1 for c in changed if c["strategy"] == s),
                      "mean_score_minus_market": round(statistics.mean(
                          c["trade_score"] - c["value_delta"] for c in cases if c["strategy"] == s), 1)} for s in STRATEGIES}
    agree = sum(1 for c in cases if (c["ros_points_delta"] >= 0) == (c["value_delta"] >= 0))
    out = {
        "week": args.week, "seed": args.seed, "rosters": "thin" if args.thin else "deep", "teams": TEAMS, "players": len(df), "waiver_pool": len(waiver),
        "cases": len(cases), "seconds_per_case_both_engines": round(elapsed / max(1, len(cases)), 3),
        "tone_changed": len(changed), "tone_changed_share": round(len(changed) / max(1, len(cases)), 3),
        "harsher": len(harsher), "kinder": len(kinder),
        "tone_transitions": dict(Counter(f"{c['old_tone']}->{c['new_tone']}" for c in changed).most_common()),
        "new_tone_mix": dict(Counter(c["new_tone"] for c in cases)), "old_tone_mix": dict(Counter(c["old_tone"] for c in cases)),
        "by_kind": by_kind, "by_posture": by_posture,
        "points_sign_agrees_with_market_sign": round(agree / max(1, len(cases)), 3),
        "confidence_pct": {"min": min(c["confidence_pct"] for c in cases), "median": statistics.median(c["confidence_pct"] for c in cases),
                           "max": max(c["confidence_pct"] for c in cases)},
        "new_confidence_labels": dict(Counter(c["new_conf"] for c in cases)), "old_confidence_labels": dict(Counter(c["old_conf"] for c in cases)),
        "median_abs_score_minus_market": round(statistics.median(abs(c["trade_score"] - c["value_delta"]) for c in cases), 0),
        "basis_mix_players": dict(sum((Counter(c["basis"]) for c in cases), Counter())),
        "examples_harsher": harsher[:5], "examples_kinder": kinder[:5],
        "examples_unchanged": [c for c in cases if c["old_tone"] == c["new_tone"]][:3],
    }
    if args.dump:
        with open(args.dump, "w", encoding="utf-8") as handle:
            json.dump(cases, handle, indent=1, default=str)
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()

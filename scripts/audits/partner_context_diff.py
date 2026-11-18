"""Before/after diff of trade ideas with DYNASTYGM_PARTNER_CONTEXT_V1 off vs on.

Real league data needs secrets, so this uses SYNTHETIC seeded 12-team leagues
(3 seeds, 36 teams, each team takes a turn as "me"). Rosters have age cohorts
(old cores, young cores, balanced), pick stashes are uneven (some teams hold
extra early firsts, some hold none) and tendencies are seeded with a mix of
sample sizes. Pick values come from the real ``_build_roster_pick_assets``.

    .venv313/bin/python scripts/audits/partner_context_diff.py OUT.md
"""

from __future__ import annotations

import os
import random
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402

from modules import partner_context, trade_ideas  # noqa: E402

SEEDS = (11, 23, 37)
TEAMS = 12
POS_PLAN = [("QB", 2), ("RB", 4), ("WR", 5), ("TE", 2)]
BASE = {"QB": 6200, "RB": 5200, "WR": 5600, "TE": 3800}


def make_league(seed: int):
    rng = random.Random(seed)
    players, rosters, summary = [], [], []
    cohorts = ["old"] * 3 + ["young"] * 3 + ["mid"] * 6
    rng.shuffle(cohorts)
    pid = 0
    for rid in range(1, TEAMS + 1):
        cohort = cohorts[rid - 1]
        mean_age = {"old": 30.0, "young": 23.5, "mid": 26.5}[cohort]
        ids = []
        for pos, count in POS_PLAN:
            for _ in range(count):
                pid += 1
                age = max(21, min(36, round(rng.gauss(mean_age, 1.8))))
                value = int(BASE[pos] * rng.uniform(0.35, 1.15) * (1.0 - max(0, age - 29) * 0.04))
                players.append({"player_id": f"p{pid}", "name": f"P{pid}", "position": pos, "team": "XXX",
                                "age": age, "value_score": value, "dynasty_score": value,
                                "player_tier": "Starter" if value > 4200 else "Depth"})
                ids.append(f"p{pid}")
        rosters.append({"roster_id": rid, "players": ids, "platform": "sleeper"})
        total = sum(p["value_score"] for p in players if p["player_id"] in ids)
        ages = [p["age"] for p in players if p["player_id"] in ids]
        strategy = {"old": rng.choice(["contender", "contender", "retool"]),
                    "young": rng.choice(["rebuild", "retool", "rebuild"]),
                    "mid": rng.choice(["contender", "retool", "fringe_contender", "rebuild"])}[cohort]
        summary.append({"roster_id": rid, "team_name": f"Team {rid}", "mode": strategy, "strategy": strategy,
                        "total_score": total, "avg_age": sum(ages) / len(ages)})
    # Uneven pick stash: a few teams buy extra firsts, a few sell all of theirs.
    traded = []
    sellers = rng.sample(range(1, TEAMS + 1), 3)
    buyers = rng.sample([r for r in range(1, TEAMS + 1) if r not in sellers], 2)
    for season in (2027, 2028):
        for s in sellers:
            for rnd in (1, 2):
                traded.append({"season": str(season), "round": rnd, "roster_id": s,
                               "owner_id": rng.choice(buyers), "previous_owner_id": s})
    profiles = {"teams": {}}
    for rid in range(1, TEAMS + 1):
        buys, sells = rng.randint(0, 5), rng.randint(0, 5)
        lean = "Seller" if sells >= 2 and sells > buys else "Buyer" if buys >= 2 and buys > sells else "Neutral"
        profiles["teams"][str(rid)] = {"tendency": {"lean": lean, "buy_count": buys, "sell_count": sells}}
    league = {"season": "2026", "status": "complete", "settings": {"draft_rounds": 4, "type": 2}, "total_rosters": TEAMS}
    adapter = SimpleNamespace(
        get_rosters=lambda _l: rosters, get_league=lambda _l: league, get_traded_picks=lambda _l: traded,
    )
    return pd.DataFrame(players), pd.DataFrame(summary), adapter, profiles


def run(seed: int, my_rid: int, on: bool):
    players, summary, adapter, profiles = make_league(seed)
    os.environ[partner_context.PARTNER_CONTEXT_ENV_KEY] = "1" if on else "0"
    with patch.object(trade_ideas._UserSideAnalyzerGate, "passes", lambda self, idea: True):
        return trade_ideas.build_trade_ideas(
            players, f"synthetic-{seed}", summary, my_rid, [], [], {}, max_ideas=40, score_field="value_score",
            league_settings={"league_type": "dynasty", "type": 2}, adapter=adapter,
            team_profiles=profiles, _pipeline_cache_enabled=False,
        )


def key(idea) -> str:
    return trade_ideas._package_key(idea["send_assets"], idea["receive_assets"]) + f"|{idea.get('partner_team_name')}"


def card(idea) -> str:
    send = ", ".join(a.get("label") or a.get("name") for a in idea["send_assets"])
    recv = ", ".join(a.get("label") or a.get("name") for a in idea["receive_assets"])
    return (f"{idea.get('partner_team_name')}: send [{send}] for [{recv}] | realism {idea.get('market_realism_score')} "
            f"({idea.get('market_realism_label')}), confidence {idea.get('trade_confidence_score')} "
            f"({idea.get('trade_confidence_label')}), edge {idea.get('user_edge_ratio')}, "
            f"partner fit: {idea.get('partner_fit_reason') or '-'}")


def main(out: str) -> None:
    changed = added = removed = same = 0
    edge_shift, score_shift, conf_shift = [], [], []
    before_scores, after_scores = [], []
    before_conf, after_conf = Counter(), Counter()
    before_label, after_label = Counter(), Counter()
    samples = []
    note_count = 0
    runs = 0
    for seed in SEEDS:
        for rid in range(1, TEAMS + 1):
            off, on = run(seed, rid, False), run(seed, rid, True)
            runs += 1
            off_by, on_by = {key(i): i for i in off}, {key(i): i for i in on}
            for k, a in off_by.items():
                b = on_by.get(k)
                before_scores.append(a["market_realism_score"])
                before_conf[a["trade_confidence_label"]] += 1
                before_label[a["market_realism_label"]] += 1
                if b is None:
                    removed += 1
                    continue
                edge_shift.append(float(b.get("user_edge_ratio") or 0) - float(a.get("user_edge_ratio") or 0))
                score_shift.append(b["market_realism_score"] - a["market_realism_score"])
                conf_shift.append(b["trade_confidence_score"] - a["trade_confidence_score"])
                if (a["market_realism_score"], a["trade_confidence_score"], a.get("partner_fit_reason")) != (
                    b["market_realism_score"], b["trade_confidence_score"], b.get("partner_fit_reason")):
                    changed += 1
                    if len(samples) < 5 and a["market_realism_score"] != b["market_realism_score"]:
                        samples.append((seed, rid, "changed", card(a), card(b)))
                else:
                    same += 1
            for k, b in on_by.items():
                after_scores.append(b["market_realism_score"])
                after_conf[b["trade_confidence_label"]] += 1
                after_label[b["market_realism_label"]] += 1
                if b.get("partner_fit_reason") and any(
                    t in b["partner_fit_reason"] for t in ("older core", "younger core", "short on picks", "deep in early picks", "vets lately")
                ):
                    note_count += 1
                if k not in off_by:
                    added += 1
                    if len([s for s in samples if s[2] == "added"]) < 1:
                        samples.append((seed, rid, "added", "-", card(b)))
            for k, a in off_by.items():
                if k not in on_by and len([s for s in samples if s[2] == "removed"]) < 1:
                    samples.append((seed, rid, "removed", card(a), "-"))

    def avg(xs):
        return round(sum(xs) / len(xs), 4) if xs else 0.0

    def dist(counter):
        return ", ".join(f"{k}: {v}" for k, v in sorted(counter.items()))

    def quart(xs):
        s = sorted(xs)
        return f"min {s[0]}, p25 {s[len(s)//4]}, median {s[len(s)//2]}, p75 {s[3*len(s)//4]}, max {s[-1]}" if s else "-"

    lines = [
        "# Partner context (handshakes 3-5): before / after",
        "",
        "Flag `DYNASTYGM_PARTNER_CONTEXT_V1` off (before) vs on (after). SYNTHETIC seeded 12-team leagues "
        f"(seeds {list(SEEDS)}, {len(SEEDS) * TEAMS} teams, each team as 'me' = {runs} searches): real league data needs "
        "secrets that were not available. Generator: `scripts/audits/partner_context_diff.py`.",
        "",
        f"Bounds: per factor age {partner_context.AGE_MAX_POINTS}, picks {partner_context.PICK_MAX_POINTS}, "
        f"tendency {partner_context.TENDENCY_MAX_POINTS}; combined +/-{partner_context.COMBINED_MAX_POINTS} of 100; "
        f"cap shift +/-{partner_context.CAP_SHIFT_MAX} only when 2+ factors agree; 12% ceiling untouched.",
        "",
        "## Counts",
        f"- Ideas before: {len(before_scores)}, after: {len(after_scores)}",
        f"- Unchanged: {same}, changed (score, confidence or reason line): {changed}, added: {added}, removed: {removed}",
        f"- Ideas whose reason line carries a new-factor note: {note_count}",
        "",
        "## Shifts on ideas present in both",
        f"- Average user-edge-ratio shift: {avg(edge_shift)}",
        f"- Average market-realism (acceptance) shift: {avg(score_shift)} points; distribution of shift: {quart(score_shift)}",
        f"- Average confidence shift: {avg(conf_shift)} points; distribution of shift: {quart(conf_shift)}",
        "",
        "## Distributions",
        f"- Realism score before: {quart(before_scores)}",
        f"- Realism score after: {quart(after_scores)}",
        f"- Realism label before: {dist(before_label)}",
        f"- Realism label after: {dist(after_label)}",
        f"- Confidence label before: {dist(before_conf)}",
        f"- Confidence label after: {dist(after_conf)}",
        "",
        "## Sample cards (before -> after)",
    ]
    for seed, rid, kind, before, after in samples:
        lines += [f"### seed {seed}, me = roster {rid}, {kind}", f"- before: {before}", f"- after: {after}", ""]
    Path(out).write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:22]))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "partner_context_diff.md")

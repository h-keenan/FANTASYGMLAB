"""Before/after diff harness for handshake items 7-10 (flag off vs on).

SYNTHETIC seeded 12-team leagues (same generator as partner_context_diff.py);
each team takes a turn as "me" in every seed. Off = the item's flag set to 0
(today's output), on = the flag default.

    .venv313/bin/python scripts/audits/handshakes_7_10_diff.py ITEM OUT.md

ITEM is one of 7 (GM Plan team outlook), 8 (live draft), 9 (playoff odds),
10 (usage roles). Items are added by the PR that ships them.
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
from partner_context_diff import SEEDS, TEAMS, make_league  # noqa: E402

from modules import gm_plan, gm_plan_outlook, roster_value_model, team_profile, trade_ideas  # noqa: E402

SETTINGS = {"league_type": "dynasty", "type": 2}


def synthetic_profile(seed: int):
    players, summary, adapter, _leans = make_league(seed)
    rosters = adapter.get_rosters("x")
    league = adapter.get_league("x")
    # Real needs table and real pick assets over the synthetic league.
    needs = roster_value_model.league_needs(
        valued=players, rosters=rosters, league=league, settings=SETTINGS, score_field="value_score"
    )
    with patch.object(trade_ideas, "_pick_team_context", trade_ideas._pick_team_context):
        picks = trade_ideas._build_roster_pick_assets("x", rosters, summary, league_settings=SETTINGS, adapter=adapter)
    frame = summary.assign(strategy_label=summary["strategy"].str.title(), archetype_label="", power_rank=range(1, len(summary) + 1))
    leans = {r: {"tendency": ("Seller" if r % 3 == 0 else "Buyer" if r % 3 == 1 else "Neutral"), "buy_count": r % 5, "sell_count": (r * 2) % 5} for r in range(1, TEAMS + 1)}
    profile = team_profile.build_team_profiles(
        league_id=f"synthetic-{seed}", lens="dynasty", valued=players, rosters=rosters, rankings_frame=frame,
        league_needs=needs, pick_assets_by_owner=picks, pick_flow={}, trade_leans=leans, manager_profile=None,
        score_field="value_score",
    )
    lookup = {str(p["player_id"]): p for p in players.to_dict("records")}
    return profile, lookup


def item7(out: str) -> None:
    os.environ.pop(gm_plan_outlook.OUTLOOK_ENV_KEY, None)
    topics_on, plans = Counter(), 0
    identical_off = True
    samples: list[str] = []
    call_reasons = Counter()
    for seed in SEEDS:
        profile, lookup = synthetic_profile(seed)
        for rid in range(1, TEAMS + 1):
            for stance in ("rebuilding", "competing", ""):
                items = gm_plan_outlook.build_outlook(
                    my_roster_id=rid, profile=profile, players_by_id=lookup, declared_stance=stance
                )
                base = gm_plan.build_gm_plan(season_phase="offseason_adjacent", team_stance=stance)
                os.environ[gm_plan_outlook.OUTLOOK_ENV_KEY] = "0"
                off = gm_plan.build_gm_plan(season_phase="offseason_adjacent", team_stance=stance, outlook_items=items)
                os.environ.pop(gm_plan_outlook.OUTLOOK_ENV_KEY, None)
                on = gm_plan.build_gm_plan(season_phase="offseason_adjacent", team_stance=stance, outlook_items=items)
                identical_off &= off == base
                plans += 1
                for it in items:
                    topics_on[it["outlook_topic"]] += 1
                    if it["outlook_topic"] == "call":
                        call_reasons[len(it["why"][0].split(", "))] += 1
                if stance == "rebuilding" and len(samples) < 3 and any(i["outlook_topic"] == "call" for i in items) and any(i["outlook_topic"] == "age" for i in items):
                    area = on["focus_areas"][-1]
                    samples.append(f"seed {seed}, me={rid}, declared {stance}:\n" + "\n".join(f"  - [{i['label']}] {i['headline']}\n      why: " + " | ".join(i["why"]) for i in area["items"]))
    lines = [
        "# Handshake 7: GM Plan reads the shared team profile",
        "",
        f"SYNTHETIC seeded 12-team leagues (seeds {list(SEEDS)}; every team as 'me'; 3 stances) = {plans} plans.",
        f"- Flag off output identical to today's plan (no Team Outlook area): {identical_off}",
        "- Flag on: new area `team_outlook`; focus areas 3 -> 4",
        "- Items per topic across all plans: " + ", ".join(f"{k} {v}" for k, v in sorted(topics_on.items())),
        "",
        "## Examples (what the new area says)",
        *samples,
    ]
    Path(out).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


ITEMS = {"7": item7}

if __name__ == "__main__":
    ITEMS[sys.argv[1]](sys.argv[2] if len(sys.argv) > 2 else f"handshakes_{sys.argv[1]}_diff.md")

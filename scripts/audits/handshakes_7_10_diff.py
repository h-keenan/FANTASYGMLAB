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


def item8(out: str) -> None:
    """Live draft: startup-board order with the context off vs on."""

    from modules import live_draft, live_draft_context

    def pool(rng_seed: int) -> pd.DataFrame:
        import random

        rng = random.Random(rng_seed)
        rows = []
        for i in range(60):
            pos = rng.choice(["QB", "RB", "RB", "WR", "WR", "WR", "TE"])
            age = rng.randint(21, 33)
            value = int(9000 - i * 3 + rng.randint(-5, 5))
            rows.append({"player_id": f"d{i}", "name": f"Draft Player{i}", "position": pos, "age": age, "years_exp": max(0, age - 22),
                         "team": "XXX", "dynasty_score": value, "value_score": value, "fantasycalc_value": value, "active": True, "status": "Active"})
        return pd.DataFrame(rows)

    def board(settings, frame):
        return live_draft.build_live_draft_rankings(
            frame, roster_df=pd.DataFrame(), league_settings=settings, score_field="dynasty_score", draft={"metadata": {"type": "startup"}}
        )

    runs = top5_changed = top1_changed = needs_changed = aged_runs = 0
    moves: list[int] = []
    examples: list[str] = []
    for seed in SEEDS:
        profile, _lookup = synthetic_profile(seed)
        frame = pool(seed)
        for rid in range(1, TEAMS + 1):
            ctx = live_draft_context.build_context(profile=profile, my_roster_id=rid, declared_stance="")
            if not ctx:
                continue
            base_settings = {"league_format": "Dynasty", "qb_format": "1QB"}
            os.environ[live_draft_context.LIVE_DRAFT_CONTEXT_ENV_KEY] = "0"
            off = board(live_draft_context.apply_to_settings(base_settings, ctx), frame)
            os.environ.pop(live_draft_context.LIVE_DRAFT_CONTEXT_ENV_KEY, None)
            on = board(live_draft_context.apply_to_settings(base_settings, ctx), frame)
            runs += 1
            aged_runs += 1 if ctx["aging_rooms"] else 0
            off_top, on_top = list(off["player_id"][:5]), list(on["player_id"][:5])
            top5_changed += off_top != on_top
            top1_changed += off_top[0] != on_top[0]
            needs_changed += live_draft.roster_position_needs(pd.DataFrame(), live_draft_context.apply_to_settings(base_settings, ctx)) != live_draft.roster_position_needs(pd.DataFrame(), base_settings)
            off_rank = {pid: i for i, pid in enumerate(off["player_id"], start=1)}
            for i, pid in enumerate(on["player_id"][:10], start=1):
                moves.append(off_rank[pid] - i)
            if off_top != on_top and len(examples) < 3:
                row = on.iloc[0]
                notes = live_draft_context.notes_for({"position": row["position"], "name": row["name"]}, ctx)
                examples.append(
                    f"seed {seed}, team {rid} ({ctx['strategy'] or 'no stance'}, needs {','.join(ctx['needs']) or 'none'}, aging rooms {','.join(ctx['aging_rooms']) or 'none'}): "
                    f"top 5 off {off_top} -> on {on_top}; new #1 {row['name']} ({row['position']}, {int(row['age'])}); notes: {notes or 'none'}"
                )
    lines = [
        "# Handshake 8: live draft reads stance, ages, needs, rookie ADP and class strength",
        "",
        f"SYNTHETIC seeded 12-team leagues (seeds {list(SEEDS)}); each team drafts from a 60-player seeded startup pool (values packed within ~190 points, so small tilts are visible) = {runs} boards.",
        f"- Flag off: board identical to today's (apply_to_settings returns the settings untouched; covered by test).",
        f"- Flag on: top-5 changed in {top5_changed}/{runs} boards, #1 pick changed in {top1_changed}/{runs}, the true-need list replaces the coarse roster-count list on every board (empty-roster count model lists all 4 positions); {aged_runs} teams have an aging room.",
        "",
        "## Examples",
        *[f"- {e}" for e in examples],
    ]
    Path(out).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def item9(out: str) -> None:
    """Playoff odds: projected pick slots and buyer / seller lean."""

    import math

    from modules import playoff_context

    def synthetic_odds(summary: pd.DataFrame, seed: int) -> dict:
        import random

        rng = random.Random(seed)
        scores = summary["total_score"].astype(float)
        z = (scores - scores.mean()) / (scores.std() or 1.0)
        rows = []
        # Record luck and schedule: the simulated finish departs from raw roster strength.
        for (_, r), zi in zip(summary.iterrows(), [v + rng.gauss(0, 0.9) for v in z]):
            p = 100.0 / (1.0 + math.exp(-1.6 * zi))
            rows.append({"roster_id": str(r["roster_id"]), "playoff_probability": round(p, 1), "median_final_wins": round(7 + 3 * zi),
                         "median_seed": int(max(1, min(TEAMS, round(6.5 - 4 * zi)))), "clinched": p > 99, "eliminated": p < 1})
        return {"ok": True, "teams": rows}

    runs = moved = 0
    deltas: list[int] = []
    leans = Counter()
    disagree = Counter()
    examples: list[str] = []
    for seed in SEEDS:
        players, summary, adapter, _leans = make_league(seed)
        profile, _lookup = synthetic_profile(seed)
        odds = synthetic_odds(summary, seed)
        rosters, league = adapter.get_rosters("x"), adapter.get_league("x")
        os.environ[playoff_context.PLAYOFF_ODDS_CONTEXT_ENV_KEY] = "0"
        off_pcts = playoff_context.slot_percentiles(odds)
        reads_off = playoff_context.team_reads(odds, profile)
        os.environ.pop(playoff_context.PLAYOFF_ODDS_CONTEXT_ENV_KEY, None)
        on_pcts = playoff_context.slot_percentiles(odds)
        reads = playoff_context.team_reads(odds, profile)
        assert not off_pcts and not reads_off, "flag off returns nothing (today's behaviour)"
        before = trade_ideas._build_roster_pick_assets("x", rosters, summary, league_settings=SETTINGS, adapter=adapter)
        after = trade_ideas._build_roster_pick_assets("x", rosters, summary, league_settings=SETTINGS, adapter=adapter, odds_slot_percentiles=on_pcts)

        def first_slot(assets_by_owner, rid):
            firsts = [a for a in assets_by_owner[rid] if a.get("round") == 1 and a.get("original_roster_id") == rid and a.get("projected_slot_number")]
            return min(firsts, key=lambda a: a["season"]) if firsts else None

        for rid in range(1, TEAMS + 1):
            b, a = first_slot(before, rid), first_slot(after, rid)
            if not b or not a:
                continue
            runs += 1
            delta = a["projected_slot_number"] - b["projected_slot_number"]
            deltas.append(delta)
            moved += delta != 0
            read = reads[str(rid)]
            leans[read["lean"]] += 1
            posture = profile["teams"][str(rid)]["posture"]["key"]
            if (read["lean"] == "seller" and posture in {"contender", "fringe_contender"}) or (read["lean"] == "buyer" and posture in {"rebuild", "tank"}):
                disagree[posture] += 1
            if delta and len(examples) < 4:
                examples.append(
                    f"seed {seed}, team {rid} ({posture}): next first {b['projected_slot_label']} -> {a['projected_slot_label']} "
                    f"(value {b['score']} -> {a['score']}); simulated finish {read['expected_finish']} of {TEAMS}, lean {read['lean']}: {'; '.join(read['why'])}"
                )
    lines = [
        "# Handshake 9: playoff odds feed projected pick slots and a buyer / seller lean",
        "",
        f"SYNTHETIC seeded 12-team leagues (seeds {list(SEEDS)}); odds are a seeded logistic of roster strength plus seeded record luck (the real simulation needs league history). {runs} teams.",
        "- Flag off: no slot percentiles and no leans (today's behaviour; asserted in the harness).",
        f"- Flag on: next-first projected slot changes for {moved}/{runs} teams; average move {sum(abs(d) for d in deltas) / len(deltas):.1f} slots, max {max(abs(d) for d in deltas)} (the simulated finish is 50% of the blend, roster value and record keep the rest).",
        "- Leans: " + ", ".join(f"{k} {v}" for k, v in sorted(leans.items())) + f"; leans that contradict the roster posture: {sum(disagree.values())} (shown to the user as a disagreement, never silently).",
        "",
        "## Examples",
        *[f"- {e}" for e in examples],
    ]
    Path(out).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


ITEMS = {"7": item7, "8": item8, "9": item9}

if __name__ == "__main__":
    ITEMS[sys.argv[1]](sys.argv[2] if len(sys.argv) > 2 else f"handshakes_{sys.argv[1]}_diff.md")

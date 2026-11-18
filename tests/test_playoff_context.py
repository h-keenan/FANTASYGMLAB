"""Playoff odds as the pick-slot and buyer / seller engine (handshake item 9)."""

from __future__ import annotations

import pandas as pd

from modules import gm_plan_outlook, playoff_context, trade_ideas


def odds(rows):
    return {"ok": True, "teams": rows}


def row(rid, p, wins=7, seed=6, **kw):
    return {"roster_id": str(rid), "playoff_probability": p, "median_final_wins": wins, "median_seed": seed, **kw}


ODDS = odds([row(1, 92, 10, 1), row(2, 61, 8, 4), row(3, 31, 7, 7), row(4, 4, 4, 11, eliminated=False)])


def test_slot_percentiles_follow_the_simulated_finish():
    pcts = playoff_context.slot_percentiles(ODDS)
    assert pcts[1] == 0.0 and pcts[4] == 1.0, "best team picks last (0), worst picks first (1)"
    assert pcts[2] < pcts[3]
    assert playoff_context.slot_percentiles({"ok": False, "teams": []}) == {}, "off-season: nothing"


def test_blend_keeps_roster_value_and_record_in_the_mix():
    assert playoff_context.blend_slot_percentile(0.2, 0.8) == 0.5
    assert playoff_context.blend_slot_percentile(0.2, None) == 0.2


def test_lean_needs_two_points_and_lists_reasons():
    strong = playoff_context.lean(row(1, 92), posture_key="contender")
    assert strong["lean"] == "buyer" and len(strong["why"]) == 2
    doomed = playoff_context.lean(row(4, 4), posture_key="retool", core_age_delta=2.0)
    assert doomed["lean"] == "seller"
    assert any("older than the league" in w for w in doomed["why"])
    bubble = playoff_context.lean(row(2, 55), posture_key="retool")
    assert bubble["lean"] == "hold", "one factor alone never leaves hold"
    assert playoff_context.lean(None)["lean"] == ""


def profile():
    mk = lambda core, key: {"age": {"core_avg": core}, "posture": {"key": key}}  # noqa: E731
    return {"teams": {"1": mk(26, "contender"), "2": mk(26, "retool"), "3": mk(27, "retool"), "4": mk(29, "rebuild")}}


def test_team_reads_assembles_slot_and_lean_per_team():
    reads = playoff_context.team_reads(ODDS, profile())
    assert reads["1"]["lean"] == "buyer" and reads["1"]["expected_finish"] == 1
    assert reads["4"]["lean"] == "seller" and reads["4"]["slot_percentile"] == 1.0
    assert reads["4"]["team_count"] == 4


def test_flag_off_returns_nothing(monkeypatch):
    monkeypatch.setenv(playoff_context.PLAYOFF_ODDS_CONTEXT_ENV_KEY, "0")
    assert playoff_context.slot_percentiles(ODDS) == {}
    assert playoff_context.team_reads(ODDS, profile()) == {}


def test_pick_team_context_moves_only_with_an_odds_percentile():
    summary = pd.DataFrame({"roster_id": [1, 2, 3, 4], "total_score": [100, 80, 60, 40]})
    base = trade_ideas._pick_team_context(2, summary)
    same = trade_ideas._pick_team_context(2, summary, odds_percentile=None)
    assert base == same
    nudged = trade_ideas._pick_team_context(2, summary, odds_percentile=1.0)
    assert nudged["slot_percentile"] > base["slot_percentile"]
    assert nudged["slot_percentile"] == 0.5 * base["slot_percentile"] + 0.5


def team(core, key, needs=(), surplus=None, firsts=1):
    return {
        "team_name": f"T{key}{core}",
        "posture": {"key": key, "label": key.title()},
        "age": {"avg": core, "core_avg": core, "cliff_ids": [], "rising_ids": [], "phase_counts": {"prime": 8}, "by_position": {}},
        "needs": {"needs": list(needs), "surplus_ids": surplus or {}},
        "picks": {"count": 2, "firsts": firsts, "capital": 3000, "tier": "middle", "assets": [{"round": 1, "slot": "1.04", "slot_number": 4, "season": "2027"}], "flow": {}},
        "tendency": {},
    }


def test_outlook_adds_lean_item_and_odds_aware_pick_slot():
    teams = {"1": team(27, "retool", ["TE"], {"WR": ["w1"]}), "2": team(26, "contender", ["WR"], {"TE": ["t1"]})}
    reads = {
        "1": {"lean": "seller", "points": -3, "why": ["only 4% playoff odds", "roster reads as a rebuild"], "expected_finish": 11, "team_count": 12},
        "2": {"lean": "buyer", "points": 3, "why": ["92% playoff odds"], "expected_finish": 1, "team_count": 12},
    }
    odds_block = {"assets": [{"round": 1, "slot": "1.02", "slot_number": 2, "season": "2027"}]}
    items = gm_plan_outlook.build_outlook(
        my_roster_id=1, profile={"teams": teams}, players_by_id={"t1": {"name": "Tee Hawk", "position": "TE"}},
        declared_stance="competing", odds_reads=reads, odds_picks_block=odds_block,
    )
    topics = [i["outlook_topic"] for i in items]
    assert "lean" in topics
    lean = next(i for i in items if i["outlook_topic"] == "lean")
    assert lean["headline"] == "Lean: seller"
    assert any("disagrees with your declared win-now stance" in w for w in lean["why"])
    picks = next(i for i in items if i["outlook_topic"] == "picks")
    assert any("projects at 1.02, not 1.04" in w for w in picks["why"])
    call = next(i for i in items if i["outlook_topic"] == "call")
    assert call["headline"].startswith("T")
    # Without odds the plan has no lean item and the pick lines are unchanged.
    plain = gm_plan_outlook.build_outlook(my_roster_id=1, profile={"teams": teams}, players_by_id={})
    assert "lean" not in [i["outlook_topic"] for i in plain]

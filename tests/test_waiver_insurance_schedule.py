"""Late-season waiver quality: injury cover and handcuffs tied to YOUR roster, the real NFL
schedule (byes, playoff weeks), this league's own FAAB bid history, and drop safety."""

from __future__ import annotations

import pandas as pd
import pytest

from modules import faab, waiver_context, waivers_logic
from modules import drop_candidates as dc

SCORE = "dynasty_score"


def _fa(pid, pos, team, score, **extra):
    row = {
        "player_id": pid, "name": pid, "position": pos, "team": team, SCORE: score, "score": score,
        "stale_free_agent": False, "status": "Active", "injury_status": "", "age": 25,
    }
    row.update(extra)
    return row


def _mine(pid, pos, team, score, **extra):
    return _fa(pid, pos, team, score, **extra)


def _rank(wire, roster, *, fmt="Dynasty", posture="", needed=(), **kw):
    ranked = waivers_logic.rank_priority_add_candidates(
        pd.DataFrame(wire),
        score_field=SCORE,
        needed_positions=list(needed),
        league_settings={"league_format": fmt, "qb_format": "1QB", "k_count": 0},
        roster_df=pd.DataFrame(roster),
        max_items=6,
        posture=posture,
        **kw,
    )
    return ranked


def _verdict(ranked, pid):
    row = ranked[ranked["player_id"] == pid].iloc[0]
    return waivers_logic.waiver_recommendation(row, 1)


# --- an injured starter's replacement rises -----------------------------------------------


def test_the_backup_behind_my_injured_starter_outranks_a_better_unrelated_player():
    roster = [_mine("stud", "RB", "HOU", 9000, status="Out", injury_status="Out"), _mine("wr", "WR", "DAL", 5000)]
    wire = [_fa("other_rb", "RB", "SEA", 5200), _fa("backup", "RB", "HOU", 3000)]
    ranked = _rank(wire, roster)
    assert ranked.iloc[0]["player_id"] == "backup"
    label, _tone, _conf, reason = _verdict(ranked, "backup")
    assert label == "Add" and "Direct backup to your injured stud" in reason


def test_a_healthy_starter_does_not_create_an_injury_cover_add():
    roster = [_mine("stud", "RB", "HOU", 9000)]
    wire = [_fa("backup", "RB", "HOU", 3000, opportunity_label="Handcuff")]
    ranked = _rank(wire, roster)
    row = ranked[ranked["player_id"] == "backup"].iloc[0]
    assert not row["injury_cover_for"] and row["handcuff_of"] == "stud"


def test_the_backup_is_not_an_add_if_he_is_out_himself():
    roster = [_mine("stud", "RB", "HOU", 9000, status="Out", injury_status="Out")]
    wire = [_fa("backup", "RB", "HOU", 3000, injury_status="Out")]
    ranked = _rank(wire, roster)
    assert ranked.empty or _verdict(ranked, "backup")[0] != "Add"


# --- handcuffs: dynasty vs redraft ----------------------------------------------------------


def test_a_studs_handcuff_is_a_dynasty_stash_that_names_the_asset():
    roster = [_mine("stud", "RB", "HOU", 9000)]
    wire = [_fa("cuff", "RB", "HOU", 2500, opportunity_label="Handcuff"), _fa("rando", "RB", "SEA", 2500)]
    ranked = _rank(wire, roster, fmt="Dynasty")
    flags = dict(zip(ranked["player_id"], ranked["priority_insurance"]))
    assert flags["cuff"] and not flags.get("rando", False)
    label, _t, conf, reason = _verdict(ranked, "cuff")
    assert label == "Stash" and conf == "Medium"
    assert "Handcuff to your stud" in reason and "dynasty asset" in reason


def test_redraft_handcuff_is_insurance_late_and_skipped_for_a_rebuild():
    roster = [_mine("stud", "RB", "HOU", 9000)]
    wire = [_fa("cuff", "RB", "HOU", 2500, opportunity_label="Handcuff", late_season=True)]
    contender = _rank(wire, roster, fmt="Redraft", posture="contender")
    assert "insurance for the playoff run" in _verdict(contender, "cuff")[3]
    rebuild = _rank(wire, roster, fmt="Redraft", posture="rebuild")
    assert rebuild.empty or not bool(rebuild.iloc[0]["priority_insurance"])


def test_a_backup_behind_a_non_stud_is_not_a_handcuff():
    roster = [_mine("s1", "RB", "KC", 9000), _mine("s2", "RB", "SF", 8500), _mine("scrub", "RB", "HOU", 1500)]
    wire = [_fa("cuff", "RB", "HOU", 900, opportunity_label="Handcuff")]
    assert waiver_context.insurance_links(pd.DataFrame(wire), pd.DataFrame(roster), SCORE) == {}


# --- schedule -------------------------------------------------------------------------------


def _sched(bye=None, opps=None):
    rows = [{"week": w, "bye": w == bye, "opponent": None if w == bye else "AAA"} for w in range(1, 19)]
    for w, opp in (opps or {}).items():
        rows[w - 1]["opponent"] = opp
    return rows


def test_schedule_facts_name_a_bye_this_week_and_next():
    now = waiver_context.schedule_facts(_sched(bye=11), week=11, playoff_start=15)
    assert now["on_bye_now"] and "on bye in week 11" in now["schedule_note"]
    nxt = waiver_context.schedule_facts(_sched(bye=12), week=11, playoff_start=15)
    assert not nxt["on_bye_now"] and nxt["schedule_note"] == "bye in week 12"
    assert waiver_context.schedule_facts(_sched(bye=5), week=11, playoff_start=15)["schedule_note"] == ""


def test_playoff_stretch_is_scored_from_real_opponent_tiers_only_late_in_the_season():
    tiers = {t: {"RB": {"tier": tier}} for t, tier in (("SOFT1", "weak"), ("SOFT2", "weak"), ("TOUGH1", "tough"), ("TOUGH2", "tough"))}
    soft = _sched(bye=6, opps={15: "SOFT1", 16: "SOFT2"})
    hard = _sched(bye=6, opps={15: "TOUGH1", 16: "TOUGH2"})
    s = waiver_context.schedule_facts(soft, week=12, playoff_start=15, position="RB", defense_strength=tiers)
    h = waiver_context.schedule_facts(hard, week=12, playoff_start=15, position="RB", defense_strength=tiers)
    assert s["playoff_edge"] == 2 and "soft playoff-week matchups" in s["schedule_note"]
    assert h["playoff_edge"] == -2 and "tough run" in h["schedule_note"]
    early = waiver_context.schedule_facts(_sched(bye=9, opps={15: "SOFT1", 16: "SOFT2"}), week=5, playoff_start=15, position="RB", defense_strength=tiers)
    assert early["playoff_edge"] == 0 and early["schedule_note"] == ""
    assert waiver_context.schedule_facts(soft, week=12, playoff_start=15, position="RB")["playoff_edge"] == 0


def test_a_better_playoff_stretch_breaks_a_near_tie_but_never_beats_a_clearly_better_player():
    roster = [_mine("wr", "WR", "DAL", 5000)]
    wire = [
        _fa("flat", "RB", "SEA", 5000, playoff_edge=0),
        _fa("soft", "RB", "MIA", 4900, playoff_edge=2),
        _fa("tough_but_better", "RB", "NYJ", 7000, playoff_edge=-2),
    ]
    ranked = _rank(wire, roster, needed=["RB"])
    order = list(ranked["player_id"])
    assert order.index("tough_but_better") < order.index("soft") < order.index("flat")


def test_a_player_on_bye_this_week_is_an_add_at_lower_confidence_and_says_so():
    row = {
        "position": "RB", "priority_need_fit": True, "priority_value_opportunity": False, "score": 5000, "age": 26,
        "on_bye_now": True, "schedule_note": "on bye in week 11, so no points until week 12",
    }
    label, _t, conf, reason = waivers_logic.waiver_recommendation(row, 1)
    assert (label, conf) == ("Add", "Medium") and "on bye in week 11" in reason
    row2 = dict(row, on_bye_now=False, schedule_note="")
    assert waivers_logic.waiver_recommendation(row2, 1)[2] == "High"


# --- FAAB bid history -----------------------------------------------------------------------


def _tx(pid, bid, **kw):
    return {"type": "waiver", "status": "complete", "adds": {pid: 1}, "settings": {"waiver_bid": bid}, **kw}


def test_bid_history_reads_only_completed_waiver_claims_by_position():
    txs = [_tx("a", 12), _tx("b", 20), _tx("c", 8), _tx("d", 5, status="failed"), {"type": "free_agent", "adds": {"a": 1}}]
    hist = faab.build_bid_history(txs, {"a": "RB", "b": "RB", "c": "RB", "d": "RB"})
    assert hist == {"RB": (8, 12, 20)}


def _guide(history):
    return faab.recommend_faab_guidance(
        6000, "RB", is_starter=True, budget=100, remaining_budget=100, week=11, roster_need=True,
        bid_history=history,
    )


def test_bid_history_pulls_the_bid_toward_what_this_league_pays_and_says_so():
    base = _guide(None)
    high = _guide([40, 45, 50, 60])
    low = _guide([1, 1, 2, 2])
    assert low.point_bid < base.point_bid < high.point_bid
    assert any("Winning RB bids in this league" in r for r in high.reasons)
    assert not any("Winning RB bids" in r for r in _guide([40, 45]).reasons)  # too few claims
    assert _guide([40, 45]).point_bid == base.point_bid


# --- drop safety ----------------------------------------------------------------------------


def test_a_top_starter_or_young_dynasty_asset_is_never_the_suggested_drop():
    from tests.test_drop_candidates import _core, _make, _pool, _row

    bench = [_row(f"B{i}", "WR", 600 + 40 * i, ppg=3, age=30) for i in range(5)]
    roster = _core() + bench + [_row("YOUNG", "WR", 9400, ppg=4, age=21)]
    rvc = _make(roster, _pool(("RB", 8000, 18)), limit=len(roster))
    assert rvc.limits.is_full
    result = dc.suggest_drop_for_add(rvc, rvc.pool.iloc[0].to_dict(), untouchable=set(), usage={})
    protected = {"QB1", "RB1", "RB2", "WR1", "WR2", "WR3", "TE1", "FLX", "YOUNG"}
    assert result["drop"] is not None
    assert result["drop"]["player_id"] not in protected
    assert all(a["player_id"] not in protected for a in result["alternatives"])

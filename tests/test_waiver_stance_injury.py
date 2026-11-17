"""Realism P1 (2026-11 audit 2): Add / Stash / Watch weighs the team's stance, the league
format and the candidate's own injury, and every waiver surface reads ONE source."""

from pathlib import Path

import pandas as pd
import pytest

from modules import waivers_logic as wl

ROOT = Path(__file__).resolve().parents[1]


def _need_row(**extra):
    row = {
        "position": "RB", "priority_need_fit": True, "priority_value_opportunity": False,
        "score": 5000, "age": 26, "status": "Active", "injury_status": "",
    }
    row.update(extra)
    return row


def test_a_candidate_who_is_out_is_never_an_add():
    label, _tone, conf, reason = wl.waiver_recommendation(_need_row(injury_status="Out"), 1)
    assert label != "Add" and conf != "High"
    assert "Out" in reason and "cannot fill a lineup hole" in reason


def test_out_candidate_is_held_only_where_holding_makes_sense():
    dynasty_rebuild = _need_row(injury_status="IR", roster_posture="rebuild", league_format="Dynasty")
    assert wl.waiver_recommendation(dynasty_rebuild, 1)[0] == "Stash"
    redraft_contender = _need_row(injury_status="IR", roster_posture="contender", league_format="Redraft", age=30)
    label, _t, _c, reason = wl.waiver_recommendation(redraft_contender, 1)
    assert label == "Watch" and "check back" in reason
    # a contender in dynasty can still hold a young player, and the text says it gets nothing now
    dynasty_contender = _need_row(injury_status="Out", roster_posture="contender", league_format="Dynasty", age=23)
    label, _t, _c, reason = wl.waiver_recommendation(dynasty_contender, 1)
    assert label == "Stash" and "contender gets nothing" in reason


def test_a_questionable_candidate_keeps_the_add_at_lower_confidence():
    label, _tone, conf, reason = wl.waiver_recommendation(_need_row(injury_status="Questionable"), 1)
    assert (label, conf) == ("Add", "Medium")
    assert "Questionable" in reason and "may not play" in reason
    assert wl.waiver_recommendation(_need_row(), 1)[2] == "High"


def test_stance_changes_the_verdict_and_says_why():
    contend = wl.waiver_recommendation(_need_row(roster_posture="contender", age=27), 2)
    assert contend[0] == "Add" and "contending team" in contend[3]
    old_rebuild = wl.waiver_recommendation(_need_row(roster_posture="rebuild", age=31), 2)
    assert old_rebuild[0] == "Add" and old_rebuild[2] == "Medium" and "rebuild" in old_rebuild[3]
    young_rebuild = wl.waiver_recommendation(
        {"position": "WR", "age": 22, "score": 900, "priority_need_fit": False,
         "priority_value_opportunity": False, "roster_posture": "rebuild", "league_format": "Dynasty"}, 4)
    assert young_rebuild[:3] == ("Stash", "information", "Medium")


def test_age_alone_is_not_a_stash_in_redraft():
    row = {"position": "WR", "age": 22, "score": 900, "priority_need_fit": False,
           "priority_value_opportunity": False}
    assert wl.waiver_recommendation({**row, "league_format": "Dynasty"}, 5)[0] == "Stash"
    assert wl.waiver_recommendation({**row, "league_format": "Redraft"}, 5)[0] == "Watch"


def _frame():
    return pd.DataFrame([
        {"player_id": "out_rb", "name": "Out Back", "position": "RB", "score": 9000, "status": "Active",
         "injury_status": "Out", "age": 25, "waiver_actionable": True},
        {"player_id": "ok_rb", "name": "Healthy Back", "position": "RB", "score": 4000, "status": "Active",
         "injury_status": "", "age": 25, "waiver_actionable": True},
        {"player_id": "wr", "name": "Wideout", "position": "WR", "score": 3000, "status": "Active",
         "injury_status": "", "age": 25, "waiver_actionable": True},
    ])


def test_ranker_never_lists_an_out_candidate_as_filling_a_need():
    ranked = wl.rank_priority_add_candidates(
        _frame(), score_field="score", needed_positions=["RB"], league_settings={"league_format": "Redraft"},
        roster_df=pd.DataFrame(), max_items=5, posture="contender",
    )
    assert "out_rb" not in ranked["player_id"].tolist()
    assert ranked.iloc[0]["player_id"] == "ok_rb"
    assert set(ranked["roster_posture"]) == {"contender"} and set(ranked["league_format"]) == {"Redraft"}


def test_out_candidate_stays_a_stash_only_in_a_long_term_format():
    ranked = wl.rank_priority_add_candidates(
        _frame(), score_field="score", needed_positions=["RB"], league_settings={"league_format": "Dynasty"},
        roster_df=pd.DataFrame(), max_items=5, posture="rebuild",
    )
    out = ranked[ranked["player_id"] == "out_rb"]
    if not out.empty:
        assert not bool(out.iloc[0]["priority_need_fit"])
        assert wl.waiver_recommendation(out.iloc[0], 1)[0] != "Add"


# --- one source for every waiver surface -------------------------------------


def test_top_pick_and_page_ranking_are_the_same_source():
    kwargs = dict(
        score_field="score", needed_positions=["RB"], league_settings={"league_format": "Dynasty"},
        played_ids=None, posture="contender",
    )
    top = wl.select_top_waiver_opportunity(_frame(), pd.DataFrame(), kwargs["league_settings"], "score",
                                           needed_positions=["RB"], posture="contender", played_ids=set(_frame()["player_id"]))
    page = wl.shared_waiver_adds(_frame(), pd.DataFrame(), kwargs["league_settings"], "score",
                                 needed_positions=["RB"], posture="contender", played_ids=set(_frame()["player_id"]),
                                 max_items=6)
    assert top["player_id"] == page.iloc[0]["player_id"]
    assert wl.waiver_recommendation(top, 1) == wl.waiver_recommendation(page.iloc[0], 1)


def test_every_surface_ranks_through_the_shared_source():
    # No surface may call the ranker directly; each goes through waivers_logic.shared_waiver_adds
    # (the Waivers page directly, the rest through select_top_waiver_opportunity).
    for rel in ("modules/dashboard_engine.py", "modules/league_glance.py", "modules/push_triggers.py",
                "modules/trade_ideas.py", "services/mobile_api_service.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "rank_priority_add_candidates(" not in text, rel
    assert "shared_waiver_adds(" in (ROOT / "services/mobile_api_service.py").read_text(encoding="utf-8")
    for rel in ("modules/dashboard_engine.py", "modules/league_glance.py", "modules/push_triggers.py", "modules/trade_ideas.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "select_top_waiver_opportunity(" in text, rel
        assert "valued=" in text and "roster_id=" in text, rel


def test_trade_card_guardrail_passes_the_waiver_page_inputs(monkeypatch):
    from modules import trade_ideas

    seen = {}

    def fake(free_agents, roster, settings, score_field, **kw):
        seen.update(kw)
        return pd.Series(dtype="object")

    monkeypatch.setattr(trade_ideas, "select_top_waiver_opportunity", fake)
    ctx = {"free_agents": _frame(), "my_team_df": pd.DataFrame(), "league_settings": {}, "score_field": "score",
           "valued": _frame(), "rosters": [{"roster_id": 1}], "roster_id": 1, "posture": "rebuild"}
    trade_ideas._waiver_alternative_for_need("RB", ctx)
    assert seen["posture"] == "rebuild" and seen["roster_id"] == 1 and seen["valued"] is ctx["valued"]

"""Lineup-aware trade evaluation (coridian_, 2026-10-27 screenshot).

A manager with a shaky RB room traded away a Questionable RB for a 2027 R2
and the analyzer said "Starter lineup stays close to neutral", "Injury risk
improves from Injury Crisis to Injury Crisis", and headlined a -379 balance
"Why this works". The evaluator must now see that no RB can start this week.
"""

from __future__ import annotations

import pandas as pd
import pytest

from modules import nfl_schedule, trade_analyzer_fit, trade_lineup_impact, trade_offer_analyzer

SETTINGS = {
    "league_format": "Dynasty",
    "qb_format": "1QB",
    "qb_count": 1,
    "rb_count": 2,
    "wr_count": 3,
    "te_count": 1,
    "k_count": 0,
    "def_count": 0,
    "flex_count": 1,
    "superflex_count": 0,
    "current_week": 8,
}


@pytest.fixture(autouse=True)
def _no_bye(monkeypatch):
    monkeypatch.setattr(nfl_schedule, "team_bye_week", lambda team, season, **kw: 99)


def _row(pid, pos, score, *, team="T", status="Active", injury="", age=26):
    return {
        "player_id": pid, "name": pid, "position": pos, "team": team, "status": status,
        "injury_status": injury, "age": age, "value_score": score, "dynasty_score": score, "score": score,
    }


def _roster(rows):
    return pd.DataFrame(rows)


def _asset(row):
    return {"asset_type": "player", **row, "label": row["name"]}


def _pick(score=900):
    return {"asset_type": "pick", "label": "2027 Round 2", "season": 2027, "round": 2, "score": score,
            "value_score": score, "owner_roster_id": "1"}


def _shaky_rb_roster(extra_rb=None):
    rows = [
        _row("QB1", "QB", 6000),
        _row("Jones", "RB", 5200, injury="Questionable"),
        _row("RBout", "RB", 2500, status="Injured Reserve", injury="IR"),
        _row("WR1", "WR", 7000), _row("WR2", "WR", 5000), _row("WR3", "WR", 4800), _row("WR4", "WR", 2000),
        _row("TE1", "TE", 4000),
    ]
    if extra_rb:
        rows.append(extra_rb)
    return _roster(rows)


def _stat_row(pid, pos, value, ppg):
    return {**_row(pid, pos, value), "ppg": ppg, "games_played": 7, "receptions": 0}


def _universe():
    """A league-wide pool with real season PPG, so the model can calibrate."""

    rows = []
    for pos, n, top, bottom in (("QB", 20, 24, 12), ("RB", 50, 24, 3), ("WR", 70, 22, 3), ("TE", 25, 14, 2)):
        for i in range(n):
            rows.append(_stat_row(f"U_{pos}{i}", pos, 9000 * (1 - i / n) + 200, top - (top - bottom) * i / (n - 1)))
    return pd.DataFrame(rows)


def _free_agents(*items):
    """Real free agents: (position, ppg) pairs."""

    return pd.DataFrame([_stat_row(f"FA_{pos}{i}", pos, 300, ppg) for i, (pos, ppg) in enumerate(items)])


def _grade(roster, send, receive, strategy="retool", partner=None, waiver=None, waiver_df=None):
    pool = pd.concat([roster, _universe()], ignore_index=True)
    fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
        roster, pool, send, receive, None, strategy, SETTINGS, "dynasty_score", waiver_df=waiver_df
    )
    verdict = trade_offer_analyzer.decide_offer_verdict(
        fit, send_assets=send, receive_assets=receive, partner_assets=partner, waiver_options=waiver
    )
    return fit, verdict


def test_screenshot_scenario_flags_no_startable_rb():
    roster = _shaky_rb_roster()
    send = [_asset(roster.set_index("player_id").loc["Jones"].to_dict() | {"player_id": "Jones"})]
    # Real waiver pool: the best free-agent RB is a 3-point scrap, so the open
    # RB slot costs far more than the market's replacement-level assumption.
    fit, verdict = _grade(
        roster, send, [_pick(4800)], waiver_df=_free_agents(("RB", 3.5), ("RB", 3.0), ("WR", 5.0), ("TE", 3.0))
    )

    warning = next(w for w in fit["lineup_warnings"] if w["position"] == "RB")
    assert warning["severity"] == "critical"
    assert warning["startable_before"] == 1 and warning["startable_after"] == 0
    assert "without a startable RB" in warning["headline"]
    assert "RB" in "".join(fit["weekly_lineup"]["new_open_slots"])
    assert "stays close to neutral" not in fit["lineup_summary"] or "without a startable RB" in fit["lineup_summary"]
    assert "without a startable RB" in verdict.roster_summary
    assert verdict.lineup_warnings and verdict.lineup_warnings[0]["position"] == "RB"
    # Never accept-as-offered / coin flip with an empty starting slot.
    assert verdict.tone in {"counter", "decline"}
    assert verdict.confidence != "High confidence" or verdict.tone == "decline"
    assert verdict.rationale_label in {"Why it needs changes", "Why it doesn't work"}
    assert "without a startable RB" in verdict.to_public_dict()["lineup_warnings"][0]["headline"]


def test_fix_guidance_names_partner_rb_and_waiver_options():
    roster = _shaky_rb_roster()
    send = [_asset(roster.set_index("player_id").loc["Jones"].to_dict() | {"player_id": "Jones"})]
    partner = [
        {**_asset(_row("PartnerRB", "RB", 3000)), "owner_roster_id": "2"},
        {**_asset(_row("PartnerInjRB", "RB", 3500, injury="Questionable")), "owner_roster_id": "2"},
    ]
    _fit, verdict = _grade(
        roster, send, [_pick(4800)], partner=partner, waiver={"RB": ["Free Agent RB"]},
        waiver_df=_free_agents(("RB", 3.5), ("RB", 3.0)),
    )
    assert "PartnerRB" in verdict.counter_guidance
    assert "PartnerInjRB" not in verdict.counter_guidance  # an injured RB is not a fix
    assert "Free Agent RB" in verdict.counter_guidance
    assert verdict.counter_action and verdict.counter_action["player_id"] == "PartnerRB"


def test_receiving_a_startable_rb_clears_the_warning():
    roster = _shaky_rb_roster()
    send = [_asset(roster.set_index("player_id").loc["Jones"].to_dict() | {"player_id": "Jones"})]
    incoming = _row("NewRB", "RB", 5000)
    pool_roster = roster
    fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
        pool_roster, pd.concat([roster, _roster([incoming])]), send, [_asset(incoming)], None, "retool", SETTINGS, "dynasty_score"
    )
    assert not [w for w in fit["lineup_warnings"] if w["severity"] == "critical"]


def test_bye_week_rb_does_not_count_as_startable(monkeypatch):
    monkeypatch.setattr(nfl_schedule, "team_bye_week", lambda team, season, **kw: 8 if team == "BYE" else 99)
    roster = _roster([
        _row("QB1", "QB", 6000), _row("Jones", "RB", 5200), _row("ByeRB", "RB", 4000, team="BYE"),
        _row("WR1", "WR", 7000), _row("WR2", "WR", 5000), _row("WR3", "WR", 4800), _row("TE1", "TE", 4000),
    ])
    send = [_asset(roster.set_index("player_id").loc["Jones"].to_dict() | {"player_id": "Jones"})]
    fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
        roster, roster, send, [_pick()], None, "contender", SETTINGS, "dynasty_score"
    )
    rb = next(w for w in fit["lineup_warnings"] if w["position"] == "RB")
    assert rb["severity"] == "critical"


def test_healthy_depth_trade_has_no_warning_and_normal_label():
    roster = _roster([
        _row("QB1", "QB", 6000), _row("RB1", "RB", 6000), _row("RB2", "RB", 5000), _row("RB3", "RB", 3000),
        _row("WR1", "WR", 7000), _row("WR2", "WR", 5000), _row("WR3", "WR", 4800), _row("TE1", "TE", 4000),
    ])
    send = [_asset(roster.set_index("player_id").loc["RB3"].to_dict() | {"player_id": "RB3"})]
    fit, verdict = _grade(roster, send, [_pick(3000)])
    assert fit["lineup_warnings"] == []
    assert verdict.lineup_warnings == ()


def test_offseason_makes_no_weekly_claims():
    roster = _shaky_rb_roster()
    send = [_asset(roster.set_index("player_id").loc["Jones"].to_dict() | {"player_id": "Jones"})]
    fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
        roster, roster, send, [_pick()], None, "retool", dict(SETTINGS, current_week=0), "dynasty_score"
    )
    assert fit["lineup_warnings"] == []
    assert fit["weekly_lineup"]["available"] is False


def test_unchanged_injury_flag_never_reads_x_to_x():
    roster = _shaky_rb_roster()
    send = [_asset(roster.set_index("player_id").loc["Jones"].to_dict() | {"player_id": "Jones"})]
    fit, _ = _grade(roster, send, [_pick(4800)])
    text = fit["injury_summary"]
    import re
    m = re.search(r"from (\w[\w ]*?) to (\w[\w ]*?)\.", text)
    assert not m or m.group(1) != m.group(2)
    assert ".." not in text


def test_rationale_label_follows_direction():
    assert trade_offer_analyzer._rationale_label("accept", 400) == "Why this works"
    assert trade_offer_analyzer._rationale_label("accept", -50) == "Why it still works"
    assert trade_offer_analyzer._rationale_label("fair", -379) == "Why it's close"
    assert trade_offer_analyzer._rationale_label("counter", -379) == "Why it needs changes"
    assert trade_offer_analyzer._rationale_label("decline", -2000) == "Why it doesn't work"


def test_negative_balance_never_headlined_helps_because():
    fit = {"value_delta": -379, "raw_value_delta": -379, "component_scores": {"value": -1}, "explanation": "Falls short: it x."}
    verdict = trade_offer_analyzer.decide_offer_verdict(fit)
    assert verdict.rationale_label != "Why this works"

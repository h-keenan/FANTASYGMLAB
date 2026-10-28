"""Trade engine v2: expected lineup points and the one trade score.

Scenarios are built from synthetic league-wide frames with real-looking season
PPG so the model calibrates the same way it does in production
(docs/trade-engine-v2.md).
"""

from __future__ import annotations

import json
from dataclasses import replace

import pandas as pd
import pytest

from modules import nfl_schedule, trade_analyzer_fit, trade_grade, trade_lineup_model as model, trade_offer_analyzer

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

BYES: dict[str, int] = {}


@pytest.fixture(autouse=True)
def _byes(monkeypatch):
    BYES.clear()
    monkeypatch.setattr(nfl_schedule, "team_bye_week", lambda team, season, **kw: BYES.get(team, 99))


def _row(pid, pos, value, *, ppg=None, team="T", status="Active", injury="", age=26, **extra):
    row = {
        "player_id": pid, "name": pid, "position": pos, "team": team, "status": status,
        "injury_status": injury, "age": age, "value_score": value, "dynasty_score": value, "score": value,
        "ppg": ppg, "games_played": 7 if ppg is not None else 0, "receptions": 0 if ppg is not None else None,
    }
    row.update(extra)
    return row


def _universe():
    rows = []
    for pos, n, top, bottom in (("QB", 20, 25, 12), ("RB", 50, 24, 3), ("WR", 70, 22, 3), ("TE", 25, 14, 2)):
        for i in range(n):
            rows.append(_row(f"U_{pos}{i}", pos, 9000 * (1 - i / n) + 200, ppg=top - (top - bottom) * i / (n - 1), team="U"))
    return pd.DataFrame(rows)


def _fas(*items):
    return pd.DataFrame([_row(f"FA_{pos}{i}", pos, 300, ppg=ppg, team="F") for i, (pos, ppg) in enumerate(items)])


def _asset(row):
    return {"asset_type": "player", **row, "label": row["name"]}


def _pick(score=4800):
    return {"asset_type": "pick", "label": "2027 Round 2", "season": 2027, "round": 2, "score": score,
            "value_score": score, "owner_roster_id": "1"}


def _evaluate(roster, send_ids, receive_rows, *, strategy="retool", waiver=None, settings=None, receive_assets=None):
    roster = pd.DataFrame(roster)
    by_id = roster.set_index("player_id", drop=False)
    send = [_asset(by_id.loc[i].to_dict()) for i in send_ids]
    receive = receive_assets if receive_assets is not None else [_asset(r) for r in receive_rows]
    universe = pd.concat([roster, _universe(), pd.DataFrame(receive_rows or [])], ignore_index=True)
    fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
        roster, universe, send, receive, None, strategy, settings or SETTINGS, "dynasty_score", waiver_df=waiver
    )
    verdict = trade_offer_analyzer.decide_offer_verdict(fit, send_assets=send, receive_assets=receive)
    return fit, verdict


def _thin_roster():
    return [
        _row("QB1", "QB", 6000, ppg=20), _row("Jones", "RB", 5200, ppg=14, injury="Questionable"),
        _row("RBout", "RB", 2500, ppg=8, status="Injured Reserve", injury="IR"),
        _row("WR1", "WR", 7000, ppg=18), _row("WR2", "WR", 5000, ppg=14), _row("WR3", "WR", 4800, ppg=13),
        _row("WR4", "WR", 2000, ppg=7), _row("TE1", "TE", 4000, ppg=9),
    ]


def _deep_roster():
    return [
        _row("QB1", "QB", 6000, ppg=20), _row("RB1", "RB", 6000, ppg=16), _row("RB2", "RB", 5200, ppg=14),
        _row("RB3", "RB", 4800, ppg=12), _row("RB4", "RB", 4400, ppg=11),
        _row("WR1", "WR", 7000, ppg=18), _row("WR2", "WR", 5000, ppg=14), _row("WR3", "WR", 4800, ppg=13),
        _row("WR4", "WR", 2000, ppg=7), _row("TE1", "TE", 4000, ppg=9),
    ]


# --- 1. the owner's RB scenario ----------------------------------------------


def test_owner_rb_scenario_empty_rb_slot_costs_a_lot_and_is_explained_with_numbers():
    waiver = _fas(("RB", 3.5), ("RB", 3.0), ("WR", 5), ("TE", 3))
    fit, verdict = _evaluate(_thin_roster(), ["Jones"], [], receive_assets=[_pick(4800)], waiver=waiver)
    m = fit["lineup_model"]

    assert m["available"] and m["worst_position"] == "RB"
    assert m["positions"]["RB"]["ros_delta"] < -60
    assert m["positions"]["RB"]["per_week_delta"] < -5
    assert m["positions"]["WR"]["ros_delta"] == 0
    # The pickup is named, with what it recovers and its expected points.
    assert m["pickup"]["position"] == "RB" and m["pickup"]["name"].startswith("FA_RB")
    assert 0 < m["pickup"]["points_recovered_ros"] < abs(m["positions"]["RB"]["ros_delta"])
    # The text cites the numbers the structured response carries.
    assert f"{abs(m['positions']['RB']['per_week_delta']):.1f} pts/week at RB" in m["explanation"]
    assert "FA_RB" in m["explanation"]  # the pickup is named, with what it recovers
    assert f"{abs(m['points']['ros_delta']):.0f} lineup pts" in m["explanation"]
    # Verdict, confidence, risk text and counter all derive from the one score.
    assert verdict.trade_score == fit["trade_score"] == m["trade_score"]
    assert verdict.tone in {"counter", "decline"}
    assert verdict.confidence == m["confidence_label"] and verdict.confidence_pct == m["confidence_pct"]
    assert "lineup points" in verdict.risk_summary and "sure of the direction" in verdict.risk_summary
    assert verdict.lineup_model["points"]["ros_delta"] == m["points"]["ros_delta"]
    # The market's value balance is kept separate from the combined score.
    assert fit["value_delta"] == fit["raw_value_delta"] == -400
    assert fit["trade_score"] < fit["value_delta"] - 1000


def test_same_trade_with_no_waiver_data_assumes_market_replacement_and_says_so():
    fit, _ = _evaluate(_thin_roster(), ["Jones"], [], receive_assets=[_pick(4800)], waiver=None)
    m = fit["lineup_model"]
    assert m["waiver_pool_used"] is False
    assert "no waiver data" in m["explanation"]


# --- 2. bye-week stacking ----------------------------------------------------


def test_bye_week_stacking_costs_points_in_the_bye_week():
    BYES.update({"STK": 9, "OTH": 12})
    base = [_row("QB1", "QB", 6000, ppg=20), _row("RB1", "RB", 6000, ppg=16), _row("RB2", "RB", 5000, ppg=13),
            _row("WR1", "WR", 7000, ppg=18, team="STK"), _row("WR2", "WR", 6500, ppg=17, team="STK"),
            _row("WRsend", "WR", 6000, ppg=15, team="X"), _row("WR4", "WR", 3000, ppg=9, team="OTH"),
            _row("WR5", "WR", 2000, ppg=7, team="OTH"), _row("TE1", "TE", 4000, ppg=9)]
    stack_in = _row("WRin_stack", "WR", 6000, ppg=15, team="STK")
    spread_in = _row("WRin_spread", "WR", 6000, ppg=15, team="Y")
    waiver = _fas(("WR", 4), ("RB", 4), ("TE", 3), ("QB", 8))
    stacked, _ = _evaluate(base, ["WRsend"], [stack_in], waiver=waiver)
    spread, _ = _evaluate(base, ["WRsend"], [spread_in], waiver=waiver)
    # Identical player quality, but three WRs idle in week 9 instead of two.
    assert stacked["lineup_model"]["points"]["ros_delta"] < spread["lineup_model"]["points"]["ros_delta"] - 5
    assert stacked["trade_score"] < spread["trade_score"]


# --- 3. injured starter ------------------------------------------------------


def test_injured_starter_prices_missed_weeks_in_points():
    roster = _deep_roster()
    healthy = _row("InHealthy", "RB", 5000, ppg=15)
    out_ir = _row("InIR", "RB", 5000, ppg=15, status="Injured Reserve", injury="IR")
    out_acl = _row("InACL", "RB", 5000, ppg=15, injury="Out", injury_body_part="ACL")
    waiver = _fas(("RB", 4), ("WR", 5))
    f_h, _ = _evaluate(roster, ["RB4"], [healthy], waiver=waiver)
    f_ir, _ = _evaluate(roster, ["RB4"], [out_ir], waiver=waiver)
    f_acl, _ = _evaluate(roster, ["RB4"], [out_acl], waiver=waiver)
    assert f_h["lineup_model"]["points"]["ros_delta"] > f_ir["lineup_model"]["points"]["ros_delta"] > f_acl["lineup_model"]["points"]["ros_delta"]
    assert f_h["trade_score"] > f_ir["trade_score"] > f_acl["trade_score"]
    # Same market value on all three: only the lineup model separates them.
    assert f_h["raw_value_delta"] == f_ir["raw_value_delta"]


def test_questionable_starter_is_enumerated_exactly_not_rounded():
    # One Questionable RB (0.25 expected weeks missed => 75% to play Week 8).
    roster = [_row("QB1", "QB", 6000, ppg=20), _row("RBq", "RB", 5000, ppg=15, injury="Questionable"),
              _row("RBb", "RB", 3000, ppg=9), _row("WR1", "WR", 6000, ppg=16), _row("WR2", "WR", 5000, ppg=13),
              _row("WR3", "WR", 4000, ppg=11), _row("TE1", "TE", 4000, ppg=9)]
    df = pd.DataFrame(roster)
    ctx = model.get_context(pd.concat([df, _universe()], ignore_index=True), SETTINGS, "dynasty_score",
                            window=trade_grade.season_window(SETTINGS), strategy="retool",
                            waiver_df=pd.DataFrame())
    players = model.profile_roster(df, ctx)
    b, _a, meta = model.run_weeks(players, players, ctx, weeks=[8])
    rbq = next(p for p in players if p.player_id == "RBq")
    assert rbq.availability(8, 8) == pytest.approx(0.75)
    healthy = [replace(p, absence=None) for p in players]
    plays = model.run_weeks(healthy, healthy, ctx, weeks=[8])[0].expected
    sits_roster = [p for p in players if p.player_id != "RBq"]
    sits = model.run_weeks(sits_roster, sits_roster, ctx, weeks=[8])[0].expected
    assert sits < plays
    # Exactly the probability-weighted mix of the two real lineups.
    assert b.expected == pytest.approx(0.75 * plays + 0.25 * sits)
    # Identical rosters: the delta is exactly 0 in every scenario.
    assert meta["avail_variance"] == pytest.approx(0.0)


# --- 4. deep vs thin ----------------------------------------------------------


def test_depth_insures_a_traded_starter():
    waiver = _fas(("RB", 3.5), ("RB", 3.0), ("WR", 5), ("TE", 3))
    deep, _ = _evaluate(_deep_roster(), ["RB1"], [], receive_assets=[_pick(6000)], waiver=waiver)
    thin_roster = [r for r in _deep_roster() if r["player_id"] not in {"RB3", "RB4"}]
    thin, _ = _evaluate(thin_roster, ["RB1"], [], receive_assets=[_pick(6000)], waiver=waiver)
    assert deep["lineup_model"]["positions"]["RB"]["ros_delta"] > thin["lineup_model"]["positions"]["RB"]["ros_delta"] + 20
    assert deep["trade_score"] > thin["trade_score"] + 500


# --- 5. waiver replacement availability --------------------------------------


def test_better_waiver_replacement_shrinks_the_cost_monotonically():
    scores = []
    for fa_ppg in (3.0, 6.0, 9.0, 12.0):
        waiver = _fas(("RB", fa_ppg), ("RB", fa_ppg - 0.5), ("WR", 5), ("TE", 3))
        fit, _ = _evaluate(_thin_roster(), ["Jones"], [], receive_assets=[_pick(4800)], waiver=waiver)
        scores.append((fit["lineup_model"]["points"]["ros_delta"], fit["trade_score"]))
    assert [s[0] for s in scores] == sorted(s[0] for s in scores)
    assert [s[1] for s in scores] == sorted(s[1] for s in scores)
    assert scores[-1][1] - scores[0][1] > 1500


# --- 6. superflex QB ----------------------------------------------------------


def test_superflex_slot_makes_the_second_qb_start():
    qbs = [_row("QB1", "QB", 6000, ppg=22), _row("QB2", "QB", 5500, ppg=19)]
    rest = [_row("RB1", "RB", 6000, ppg=16), _row("RB2", "RB", 5000, ppg=13), _row("WR1", "WR", 7000, ppg=18),
            _row("WR2", "WR", 6000, ppg=16), _row("WR3", "WR", 5000, ppg=13), _row("WR4", "WR", 3000, ppg=9),
            _row("TE1", "TE", 4000, ppg=9)]
    waiver = _fas(("QB", 9), ("WR", 6), ("RB", 4), ("TE", 3))
    one_qb, _ = _evaluate(qbs + rest, ["QB2"], [], receive_assets=[_pick(5500)], waiver=waiver)
    sf_settings = dict(SETTINGS, superflex_count=1, qb_format="Superflex")
    sf, _ = _evaluate(qbs + rest, ["QB2"], [], receive_assets=[_pick(5500)], waiver=waiver, settings=sf_settings)
    # In 1QB a second QB is a bench piece; in superflex he fills a lineup slot.
    assert one_qb["lineup_model"]["positions"]["QB"]["ros_delta"] == 0
    assert sf["lineup_model"]["positions"]["QB"]["ros_delta"] < -40
    assert sf["trade_score"] < one_qb["trade_score"] - 500


# --- 7. TE premium -------------------------------------------------------------


def test_te_premium_scores_receptions_and_lifts_te_points():
    row = {"games_played": 8, "receptions": 48}
    ppr = model.scoring_profile({"scoring_format": "PPR", "te_premium": False})
    prem = model.scoring_profile({"scoring_format": "PPR", "te_premium": True})
    half = model.scoring_profile({"scoring_format": "Half-PPR"})
    base = model._league_scored(12.0, row, "TE", ppr)
    assert base == pytest.approx(12.0)
    assert model._league_scored(12.0, row, "TE", prem) == pytest.approx(12.0 + 0.5 * 6)
    assert model._league_scored(12.0, row, "WR", prem) == pytest.approx(12.0)  # premium is TE only
    assert model._league_scored(12.0, row, "TE", half) == pytest.approx(12.0 - 0.5 * 6)
    # Detected scoring wins over the label, including the bonus size.
    detected = model.scoring_profile({"_detected_scoring": {"rec": 1.0, "te_premium_keys": {"bonus_rec_te": 1.0}}, "te_premium": True})
    assert detected["te_bonus"] == 1.0


def test_te_premium_changes_the_trade_score_for_a_te_swap():
    roster = _deep_roster()
    roster[-1] = _row("TE1", "TE", 4000, ppg=9, receptions=56, games_played=8)
    waiver = _fas(("TE", 3), ("RB", 4), ("WR", 5))
    plain, _ = _evaluate(roster, ["TE1"], [], receive_assets=[_pick(4000)], waiver=waiver)
    prem, _ = _evaluate(roster, ["TE1"], [], receive_assets=[_pick(4000)], waiver=waiver,
                        settings=dict(SETTINGS, te_premium=True))
    assert prem["lineup_model"]["positions"]["TE"]["ros_delta"] < plain["lineup_model"]["positions"]["TE"]["ros_delta"]


# --- 8. contender vs rebuilder weighting --------------------------------------


def test_posture_weights_flip_a_vet_for_pick_trade():
    waiver = _fas(("RB", 6), ("RB", 5), ("WR", 5), ("TE", 3))
    # Sell a starter for a pick of equal value: contenders resist, rebuilders take it.
    c, vc = _evaluate(_deep_roster(), ["RB1"], [], receive_assets=[_pick(6000)], strategy="contender", waiver=waiver)
    r, vr = _evaluate(_deep_roster(), ["RB1"], [], receive_assets=[_pick(6000)], strategy="rebuild", waiver=waiver)
    assert c["trade_score"] < r["trade_score"]
    # And the mirror: buying a vet with a pick is a contender move.
    vet = _row("VET", "RB", 6000, ppg=20)
    roster = _deep_roster()
    universe = pd.concat([pd.DataFrame(roster), _universe(), pd.DataFrame([vet])], ignore_index=True)

    def buy(strategy):
        return trade_analyzer_fit.evaluate_trade_analyzer_fit(
            pd.DataFrame(roster), universe, [_pick(6000)], [_asset(vet)], None, strategy, SETTINGS,
            "dynasty_score", waiver_df=waiver,
        )

    assert buy("contender")["trade_score"] > buy("rebuild")["trade_score"]
    assert c["lineup_model"]["weights"]["now"] > r["lineup_model"]["weights"]["now"]


# --- 9. offseason --------------------------------------------------------------


def test_offseason_has_no_weekly_claims_and_keeps_legacy_pricing():
    fit, verdict = _evaluate(_thin_roster(), ["Jones"], [], receive_assets=[_pick(4800)],
                             waiver=_fas(("RB", 3.5)), settings=dict(SETTINGS, current_week=0))
    assert fit["lineup_model"] is None
    assert fit["lineup_warnings"] == []
    assert fit["trade_score"] == fit["value_delta"]
    assert verdict.lineup_model is None and verdict.confidence_pct is None
    assert "this week" not in verdict.roster_summary.lower()


# --- 10. determinism -----------------------------------------------------------


def test_same_inputs_same_numbers_regardless_of_row_order():
    waiver = _fas(("RB", 3.5), ("RB", 3.0), ("WR", 5), ("TE", 3))
    a, _ = _evaluate(_thin_roster(), ["Jones"], [], receive_assets=[_pick(4800)], waiver=waiver)
    shuffled = list(reversed(_thin_roster()))
    b, _ = _evaluate(shuffled, ["Jones"], [], receive_assets=[_pick(4800)], waiver=waiver.iloc[::-1].reset_index(drop=True))
    c, _ = _evaluate(_thin_roster(), ["Jones"], [], receive_assets=[_pick(4800)], waiver=waiver)
    assert json.dumps(a["lineup_model"], sort_keys=True, default=str) == json.dumps(c["lineup_model"], sort_keys=True, default=str)
    assert a["trade_score"] == b["trade_score"]
    assert a["lineup_model"]["confidence_pct"] == b["lineup_model"]["confidence_pct"]
    assert a["lineup_model"]["points"] == b["lineup_model"]["points"]


# --- confidence is computed, not stepped --------------------------------------


def test_confidence_is_a_continuous_function_of_the_score_and_its_uncertainty():
    waiver = _fas(("RB", 6), ("RB", 5), ("WR", 5), ("TE", 3))
    pcts = []
    for pick in (3200, 3800, 4400, 5000, 5600, 6400, 7600):
        fit, _ = _evaluate(_deep_roster(), ["RB3"], [], receive_assets=[_pick(pick)], waiver=waiver)
        pcts.append((fit["trade_score"], fit["lineup_model"]["confidence_pct"]))
    pcts.sort()
    # More lopsided => more sure, and the numbers are not a handful of fixed steps.
    assert len({p for _, p in pcts}) >= 5
    assert all(50.0 <= p <= 99.0 for _, p in pcts)  # never claims certainty
    # Confidence tracks |score| / uncertainty: farther from zero is never less sure.
    by_distance = sorted(pcts, key=lambda t: abs(t[0]))
    assert [p for _, p in by_distance] == sorted(p for _, p in by_distance)


# --- points sources: documented fallbacks, never invented ----------------------


def test_point_sources_fall_back_in_order_and_never_invent():
    df = pd.DataFrame([
        _row("PROJ", "WR", 5000, ppg=10, proj_ppg=17.0, proj_sd=4.0),
        _row("SEASON", "WR", 5000, ppg=12),
        _row("VALUE", "WR", 5000),
        {**_row("DEF1", "DEF", 500), "ppg": None},
    ])
    ctx = model.build_context(pd.concat([df, _universe()], ignore_index=True), SETTINGS, "dynasty_score",
                              window=trade_grade.season_window(SETTINGS), strategy="retool")
    by_id = {p.player_id: p for p in model.profile_roster(df, ctx)}
    assert by_id["PROJ"].basis == "projection" and by_id["PROJ"].ppg == pytest.approx(17.0) and by_id["PROJ"].sd == pytest.approx(4.0)
    # Season average is shrunk toward the value-derived prior by games played.
    assert by_id["SEASON"].basis == "season_average"
    assert 10 < by_id["SEASON"].ppg < 14
    assert by_id["VALUE"].basis == "value_estimate" and by_id["VALUE"].ppg > 0
    # A defense has no points data: no estimate, never a made-up number.
    assert by_id["DEF1"].ppg is None and by_id["DEF1"].basis == "none"
    # Value-derived estimates carry wider spread than projections of the same size.
    assert by_id["VALUE"].sd > by_id["SEASON"].sd


def test_value_derived_ppg_rank_matches_the_position_distribution():
    ctx = model.build_context(_universe(), SETTINGS, "dynasty_score",
                              window=trade_grade.season_window(SETTINGS), strategy="retool")
    top, _ = model._value_curve_ppg(ctx.curves, "RB", 9300)
    mid, _ = model._value_curve_ppg(ctx.curves, "RB", 4500)
    low, _ = model._value_curve_ppg(ctx.curves, "RB", 300)
    assert top > mid > low
    assert top == pytest.approx(24.0, abs=0.01)
    assert ctx.calibration["value_per_point_source"] == "calibrated"


# --- lineup solver ---------------------------------------------------------------


def test_solver_fills_nested_flex_slots_optimally():
    slots = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "SUPER_FLEX": 1}
    cands = [("q1", "QB", 20), ("q2", "QB", 18), ("r1", "RB", 15), ("r2", "RB", 14), ("r3", "RB", 13),
             ("w1", "WR", 16), ("w2", "WR", 12), ("w3", "WR", 11), ("t1", "TE", 8), ("t2", "TE", 10)]
    total, starters, open_slots = model.solve_lineup(cands, slots)
    # TE slot takes t2 (10), FLEX the best leftover RB/WR/TE (r3 13), SUPER_FLEX the best left (q2 18).
    assert total == pytest.approx(20 + 15 + 14 + 16 + 12 + 10 + 13 + 18)
    assert open_slots == {}
    _, _, open_slots = model.solve_lineup([("r1", "RB", 15)], {"RB": 2})
    assert open_slots == {"RB": 1}


# --- counter-offer search optimizes the same score -----------------------------


def test_counter_search_asks_for_the_player_that_fills_the_hole():
    waiver = _fas(("RB", 3.5), ("RB", 3.0), ("WR", 5), ("TE", 3))
    roster = pd.DataFrame(_thin_roster())
    partner = [
        {**_asset(_row("PartnerRB", "RB", 3500, ppg=11, team="P")), "owner_roster_id": "2"},
        {**_asset(_row("PartnerWR", "WR", 3500, ppg=11, team="P")), "owner_roster_id": "2"},
    ]
    send = [_asset(roster.set_index("player_id", drop=False).loc["Jones"].to_dict())]
    receive = [_pick(3000)]
    universe = pd.concat([roster, _universe(), pd.DataFrame([{k: v for k, v in p.items() if k not in {"asset_type", "label", "owner_roster_id"}} for p in partner])], ignore_index=True)

    def regrade(cand_send, cand_receive):
        fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
            roster, universe, cand_send, cand_receive, None, "retool", SETTINGS, "dynasty_score", waiver_df=waiver
        )
        return trade_offer_analyzer.decide_offer_verdict(fit, send_assets=cand_send, receive_assets=cand_receive, partner_assets=partner)

    base = regrade(send, receive)
    assert base.tone in {"counter", "decline"}
    packages = trade_offer_analyzer.build_counter_offer_packages(
        band=base.band, value_delta=base.trade_score, send_assets=send, receive_assets=receive,
        my_asset_pool=[], partner_asset_pool=partner, regrade=regrade, my_needs=["RB"],
    )
    # Whatever clears the bar is ranked by the same score, best first.
    scores = [p["trade_score"] for p in packages]
    assert scores == sorted(scores, reverse=True)
    for package in packages:
        assert package["lineup_points_delta"] is not None
    # Asking for the RB beats asking for an equal-value WR.
    wr_only = regrade(send, receive + [partner[1]])
    rb_only = regrade(send, receive + [partner[0]])
    assert rb_only.trade_score > wr_only.trade_score + 500


# --- Trade Hub gate uses the same number; schema is additive ------------------


def test_hub_grade_uses_the_trade_score_and_passes_the_waiver_pool():
    roster = pd.DataFrame(_thin_roster())
    send = [_asset(roster.set_index("player_id", drop=False).loc["Jones"].to_dict())]
    universe = pd.concat([roster, _universe()], ignore_index=True)
    waiver = _fas(("RB", 3.5), ("RB", 3.0))
    fit, verdict = trade_grade.grade_trade_for_user(
        my_team_df=roster, all_players_df=universe, send_assets=send, receive_assets=[_pick(4800)],
        strategy="retool", lineup_settings=SETTINGS, score_field="dynasty_score", waiver_df=waiver,
    )
    assert fit["lineup_model"]["waiver_pool_used"] is True
    assert verdict.trade_score == fit["trade_score"]
    assert verdict.ui_verdict not in trade_grade.PASSING_UI_VERDICTS  # the hole keeps it off Hub


def test_public_schema_is_additive_for_old_app_builds():
    fit, verdict = _evaluate(_thin_roster(), ["Jones"], [], receive_assets=[_pick(4800)], waiver=_fas(("RB", 3.5)))
    public = verdict.to_public_dict()
    for legacy in ("band", "ui_verdict", "confidence", "rationale", "value_summary", "roster_summary", "strategy_summary",
                   "risk_summary", "counter_guidance", "fit_total", "value_delta", "tone", "counter_action",
                   "alternate_packages", "lineup_warnings", "rationale_label"):
        assert legacy in public
    for new in ("trade_score", "confidence_pct", "lineup_model"):
        assert new in public
    for key in ("points", "positions", "uncertainty", "components", "weights", "pickup", "explanation", "trade_score"):
        assert key in public["lineup_model"]
    json.dumps(public, default=str)  # serializable


def test_model_failure_falls_back_to_the_legacy_pricing(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(model, "evaluate_trade", boom)
    fit, verdict = _evaluate(_thin_roster(), ["Jones"], [], receive_assets=[_pick(4800)])
    assert fit["lineup_model"] is None and fit["trade_score"] == fit["value_delta"]
    assert verdict.lineup_model is None

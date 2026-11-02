"""Team-posture-aware trade verdicts (modules.trade_posture, docs/trade-engine-v2.md).

coridian_ 2026-11-01: a contender sending Tee Higgins for an IR rookie WR plus
a 2028 R1 got SMASH ACCEPT next to "-90 lineup pts" ("it must know team
status"). These tests pin the model, not the single case.
"""

from __future__ import annotations

import pandas as pd
import pytest

from modules import nfl_schedule, trade_analyzer_fit, trade_offer_analyzer, trade_posture, trade_value_bands
from tests import test_trade_lineup_model as T

ACCEPT_UI = "ACCEPT"
POSTURES = ("contender", "fringe_contender", "retool", "rebuild", "tank")


@pytest.fixture(autouse=True)
def _byes(monkeypatch):
    monkeypatch.setattr(nfl_schedule, "team_bye_week", lambda team, season, **kw: 99)


def _pick(score, rnd=1, season=2028):
    return {"asset_type": "pick", "label": f"{season} Round {rnd}", "season": season, "round": rnd,
            "score": score, "value_score": score, "value": score, "owner_roster_id": "1"}


def _contender_roster():
    r = T._row
    return [
        r("QB1", "QB", 6000, ppg=20, age=29), r("RB1", "RB", 6000, ppg=16, age=25), r("RB2", "RB", 5200, ppg=14, age=26),
        r("RB3", "RB", 3000, ppg=9), r("Higgins", "WR", 5913, ppg=16, age=27), r("WR2", "WR", 5000, ppg=14, age=28),
        r("WR3", "WR", 4800, ppg=13, age=28), r("WR4", "WR", 2000, ppg=7, age=30), r("TE1", "TE", 4000, ppg=9, age=27),
    ]


def _noel():
    return T._row("Noel", "WR", 2048, ppg=8, age=24, status="Injured Reserve", injury="IR")


def _grade(roster, send_ids, receive_players, *, strategy, send_picks=(), receive_picks=(), posture=None):
    roster = pd.DataFrame(roster)
    by_id = roster.set_index("player_id", drop=False)
    send = [T._asset(by_id.loc[i].to_dict()) for i in send_ids] + list(send_picks)
    receive = [T._asset(p) for p in receive_players] + list(receive_picks)
    universe = pd.concat([roster, T._universe(), pd.DataFrame(receive_players or [])], ignore_index=True)
    fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
        roster, universe, send, receive, None, strategy, T.SETTINGS, "dynasty_score",
        waiver_df=T._fas(("RB", 3.5), ("WR", 5), ("TE", 3)), posture=posture,
    )
    return fit, trade_offer_analyzer.decide_offer_verdict(fit, send_assets=send, receive_assets=receive)


def _higgins(strategy, posture=None):
    return _grade(_contender_roster(), ["Higgins"], [_noel()], strategy=strategy,
                  receive_picks=[_pick(7400)], posture=posture)


# --- the owner's scenario -----------------------------------------------------


def test_contender_is_not_told_smash_accept_for_a_lineup_costing_value_win():
    fit, verdict = _higgins("contender")
    assert fit["value_delta"] >= 3000  # the market really says "you win"
    assert fit["lineup_model"]["points"]["ros_delta"] < -60
    assert verdict.band == trade_value_bands.VERDICT_VALUE_COSTS_LINEUP
    assert verdict.ui_verdict != "ACCEPT" and verdict.tone != "accept"
    assert verdict.score_band in {"COUNTER", "FAIR / PREFERENCE"}
    # The line under the verdict still states the market value honestly.
    assert verdict.value_summary == "You win big on value"
    # The card names the posture and the trade-off with numbers, never "Helps".
    assert verdict.posture["key"] == "contender"
    assert "You're a contender" in verdict.posture_note and "lineup points" in verdict.posture_note
    assert "step toward a rebuild" in verdict.posture_note
    assert verdict.rationale_label == "The trade-off"
    assert "Helps because" not in verdict.rationale
    assert verdict.posture_assessment["lineup_costly"] and verdict.posture_assessment["adjustment"] < -1000


def test_same_trade_for_a_rebuilding_team_stays_an_accept_and_says_lineup_matters_little():
    _, verdict = _higgins("rebuild")
    assert verdict.ui_verdict == ACCEPT_UI and verdict.band in {"ACCEPT", "SMASH ACCEPT"}
    assert "matter little to your timeline" in verdict.posture_note
    assert verdict.posture_assessment["window_term"] == 0 and verdict.posture_assessment["present_term"] > 0


def test_posture_is_a_gradient_not_a_switch():
    scores = {s: _higgins(s)[0]["trade_score"] for s in POSTURES}
    assert scores["contender"] < scores["fringe_contender"] < scores["retool"] < scores["rebuild"] < scores["tank"]
    # Retool keeps this an accept: it is a mild lineup lens, not a contender.
    assert _higgins("retool")[1].ui_verdict == ACCEPT_UI


def test_components_are_inspectable_and_sum_to_the_score():
    fit, verdict = _higgins("contender")
    m = fit["lineup_model"]
    c = m["components"]
    assert m["trade_score_before_posture"] + c["posture_window"] + c["posture_direction"] + c["posture_present"] == m["trade_score"]
    assert verdict.trade_score == fit["trade_score"] == m["trade_score"]
    # Confidence is recomputed for the score the verdict actually uses.
    assert verdict.confidence_pct == m["confidence_pct"]


# --- symmetric: rebuilding team spending future on old players ---------------


def test_rebuilder_paying_picks_for_old_vets_is_not_a_smash_accept():
    r = T._row
    roster = [
        r("QB1", "QB", 3000, ppg=14, age=24), r("RB1", "RB", 3000, ppg=9, age=23), r("RB2", "RB", 2500, ppg=8, age=23),
        r("WR1", "WR", 4000, ppg=12, age=23), r("WR2", "WR", 3500, ppg=11, age=22), r("WR3", "WR", 3000, ppg=10, age=22),
        r("TE1", "TE", 2000, ppg=6, age=23), r("WR4", "WR", 1500, ppg=6, age=22),
    ]
    vets = [r("OldQB", "QB", 7000, ppg=22, age=34), r("OldRB", "RB", 6000, ppg=17, age=31)]
    picks = [_pick(8000), _pick(6000, rnd=2)]
    out = {s: _grade(roster, [], vets, strategy=s, send_picks=picks) for s in ("contender", "rebuild", "tank")}
    assert out["contender"][1].ui_verdict == ACCEPT_UI  # win-now fits a contender
    assert out["rebuild"][1].ui_verdict != ACCEPT_UI
    assert out["tank"][1].ui_verdict in {"DECLINE", "COUNTER"}
    note = out["rebuild"][1].posture_note
    assert "rebuilding" in note and "away from your rebuild" in note


# --- posture resolution -------------------------------------------------------


def test_declared_beats_auto_beats_client():
    p = trade_posture.resolve_posture(declared_strategy="rebuild", auto_strategy="contender", client_strategy="contender")
    assert (p["key"], p["source"], p["confidence"]) == ("rebuild", "declared", 1.0)
    p = trade_posture.resolve_posture(auto_strategy="contender", client_strategy="retool", power_rank=2, league_size=12,
                                      record={"wins": 4, "losses": 2})
    assert p["key"] == "contender" and p["source"] == "auto" and p["record"] == "4-2"
    assert "#2 of 12" in p["standing"] and "4-2" in p["why"]
    p = trade_posture.resolve_posture(client_strategy="rebuild")
    assert (p["key"], p["source"]) == ("rebuild", "client")
    assert trade_posture.resolve_posture()["key"] == "retool"


def test_auto_confidence_grows_with_standing_and_games_and_retool_is_never_sure():
    sure = trade_posture.resolve_posture(auto_strategy="contender", power_rank=1, league_size=12, record={"wins": 6, "losses": 0})
    unsure = trade_posture.resolve_posture(auto_strategy="contender", power_rank=6, league_size=12, record={"wins": 1, "losses": 0})
    mid = trade_posture.resolve_posture(auto_strategy="retool", power_rank=1, league_size=12, record={"wins": 6, "losses": 0})
    assert sure["confidence"] > unsure["confidence"] and sure["confidence_label"] == "high"
    assert mid["confidence"] <= 0.65


def test_supplied_posture_drives_the_verdict_over_the_strategy_key():
    posture = trade_posture.resolve_posture(auto_strategy="contender", power_rank=2, league_size=12,
                                            record={"wins": 4, "losses": 2})
    fit, verdict = _higgins("retool", posture=posture)
    assert verdict.posture["source"] == "auto"
    assert "You're a contender (#2 of 12, 4-2)" in verdict.posture_note
    assert verdict.band == trade_value_bands.VERDICT_VALUE_COSTS_LINEUP


# --- the model itself ---------------------------------------------------------


def _model(ros_delta, present, future, ros_before=1200.0, k=22.0):
    return {"available": True, "points": {"ros_delta": ros_delta, "ros_before": ros_before},
            "win_now_delta": present, "future_delta": future, "value_per_point": k}


def test_window_term_is_zero_for_rebuilders_and_gains_are_credited_at_a_discount():
    loss = trade_posture.assess({"key": "contender"}, _model(-90, -2000, 2000))
    gain = trade_posture.assess({"key": "contender"}, _model(90, 2000, -2000))
    assert loss["window_term"] < 0 < gain["window_term"]
    assert gain["window_term"] == pytest.approx(-loss["window_term"] * trade_posture.GAIN_CREDIT, abs=2)
    assert trade_posture.assess({"key": "rebuild"}, _model(-90, -2000, 2000))["window_term"] == 0
    assert trade_posture.assess({"key": "contender"}, _model(0, 0, 0))["adjustment"] == 0


def test_direction_penalty_only_for_misaligned_conversions_above_the_deadband():
    small = trade_posture.assess({"key": "contender"}, _model(0, -800, 800))
    big = trade_posture.assess({"key": "contender"}, _model(0, -4000, 4000))
    toward_present = trade_posture.assess({"key": "contender"}, _model(0, 4000, -4000))
    assert small["direction_term"] == 0 and not small["direction_misaligned"]
    assert big["direction_term"] < 0 and big["direction"] == "toward_future"
    assert toward_present["direction_term"] == 0
    assert trade_posture.assess({"key": "retool"}, _model(0, -4000, 4000))["direction_term"] == 0
    assert trade_posture.assess({"key": "rebuild"}, _model(0, 4000, -4000))["direction_term"] < 0


def test_materiality_is_relative_to_the_margin():
    thin = trade_posture.assess({"key": "contender"}, _model(-40, 0, 0, ros_before=500.0))
    deep = trade_posture.assess({"key": "contender"}, _model(-20, 0, 0, ros_before=3000.0))
    assert thin["lineup_costly"] and not deep["lineup_costly"]


def test_no_lineup_model_means_no_adjustment():
    out = trade_posture.assess({"key": "contender"}, None)
    assert out["available"] is False and out["adjustment"] == 0


# --- calibration over the existing synthetic league fixtures ------------------


def _grid():
    r = T._row

    def P(score, rnd=1):
        return _pick(score, rnd)

    trades = {
        "star-for-picks": (["WR1"], [], [P(7000)]),
        "star-for-young-IR+pick": (["WR1"], [r("Noel", "WR", 2048, ppg=8, age=24, status="Injured Reserve", injury="IR")], [P(6500)]),
        "vet-for-pick": (["RB2"], [], [P(5200, 2)]),
        "pick-for-starter": ([], [r("NewWR", "WR", 5500, ppg=16, age=27)], []),
        "even-swap": (["WR2"], [r("SwapWR", "WR", 5000, ppg=14, age=26)], []),
        "2for1 up": (["WR2", "WR3"], [r("Star", "WR", 9500, ppg=21, age=25)], []),
        "1for2 down": (["WR1"], [r("A", "WR", 3500, ppg=11, age=23), r("B", "WR", 3400, ppg=10, age=22)], []),
        "bench-for-pick": (["WR4"], [], [P(2500, 3)]),
        "overpay": (["WR1"], [r("Meh", "WR", 2500, ppg=9, age=30)], []),
        "TE swap young": (["TE1"], [r("YTE", "TE", 4300, ppg=8, age=22)], []),
        "sell RB for bust+pick": (["RB1"], [r("Bust", "RB", 1500, ppg=5, age=23)], [P(6500)]),
    }
    return {"deep": (T._deep_roster(), trades), "thin": (T._thin_roster(), trades)}


def _run_grid(monkeypatch, enabled):
    if not enabled:
        real = trade_posture.assess

        def neutral(posture, model):
            out = dict(real(posture, model))
            out.update(adjustment=0, window_term=0, direction_term=0, present_term=0,
                       lineup_costly=False, direction_misaligned=False)
            return out

        monkeypatch.setattr(trade_posture, "assess", neutral)
    results = {}
    for rn, (roster, trades) in _grid().items():
        ids = {x["player_id"] for x in roster}
        for tn, (send, recv, picks) in trades.items():
            if any(s not in ids for s in send):
                continue
            for strat in POSTURES:
                _, v = _grade(roster, send, recv, strategy=strat, receive_picks=picks)
                results[(rn, tn, strat)] = v
    return results


def test_calibration_grid_verdict_changes_are_few_directional_and_explained(monkeypatch):
    with monkeypatch.context() as m:
        before = _run_grid(m, enabled=False)
    after = _run_grid(monkeypatch, enabled=True)
    assert before.keys() == after.keys() and len(after) >= 100

    ui_changed = {k for k in after if after[k].ui_verdict != before[k].ui_verdict}
    label_changed = {k for k in after if after[k].band != before[k].band}
    # Most verdicts are untouched: only trades with a real lineup or direction effect move.
    win_now = {k for k in after if k[2] in {"contender", "fringe_contender", "retool"}}
    # Win-now side (where the owner's report lives): few verdicts move.
    assert len(ui_changed & win_now) / len(win_now) <= 0.15
    # Rebuild/tank move more by design: their lineup weight drops (PRESENT_ADJUST).
    assert len(ui_changed) / len(after) <= 0.25
    assert len(label_changed) / len(after) <= 0.30
    for key in ui_changed:
        _, name, strat = key
        a, b = after[key], before[key]
        # Every change is explained by the posture assessment's own numbers.
        assert a.posture_assessment["adjustment"] != 0, key
        if strat in {"contender", "fringe_contender", "retool"}:
            # Win-now teams only ever lose standing from a lineup loss in this grid.
            assert a.trade_score <= b.trade_score, key
        else:
            assert a.posture_assessment["present_term"] != 0 or a.posture_assessment["direction_term"] != 0, key
    # Win-now teams never read "ACCEPT" on a trade whose market value is an accept
    # but whose lineup cost is material.
    for key, v in after.items():
        if key[2] == "contender" and v.posture_assessment["lineup_costly"]:
            assert v.ui_verdict != ACCEPT_UI or v.trade_score >= 1500, key
    # Sensible trades keep their verdicts: even swaps and upgrades are untouched for every posture.
    for strat in POSTURES:
        for name in ("even-swap", "pick-for-starter", "2for1 up", "overpay"):
            for rn in ("deep", "thin"):
                k = (rn, name, strat)
                if strat in {"contender", "fringe_contender", "retool"}:
                    assert after[k].ui_verdict == before[k].ui_verdict, k


# --- the endpoint helper ------------------------------------------------------


def _svc():
    from services import mobile_api_service as svc

    return svc


def _rankings(strategy="contender"):
    return pd.DataFrame([
        {"roster_id": 1, "strategy": strategy, "power_rank": 2},
        {"roster_id": 2, "strategy": "rebuild", "power_rank": 9},
    ] + [{"roster_id": 10 + i, "strategy": "retool", "power_rank": 3 + i} for i in range(10)])


def test_endpoint_resolves_auto_posture_when_nothing_declared_and_ignores_the_web_default(monkeypatch):
    svc = _svc()
    monkeypatch.setattr(svc, "_fetch_team_stance", lambda *a, **k: "")
    monkeypatch.setattr(svc.league_rankings, "build_league_rankings_frame_cached", lambda **k: _rankings())
    p = svc._resolve_trade_posture({"id": "u"}, "L", {}, {"roster_id": 1, "settings": {"wins": 4, "losses": 2}},
                                   lens="Dynasty", client_strategy="retool")
    assert (p["key"], p["source"], p["record"], p["rank"], p["league_size"]) == ("contender", "auto", "4-2", 2, 12)


def test_endpoint_declared_stance_wins_and_failures_fall_back(monkeypatch):
    svc = _svc()
    monkeypatch.setattr(svc, "_fetch_team_stance", lambda *a, **k: "rebuilding")
    monkeypatch.setattr(svc.league_rankings, "build_league_rankings_frame_cached", lambda **k: _rankings())
    p = svc._resolve_trade_posture({"id": "u"}, "L", {}, {"roster_id": 1}, lens="Dynasty", client_strategy="contender")
    assert (p["key"], p["source"]) == ("rebuild", "declared")

    def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(svc, "_fetch_team_stance", boom)
    monkeypatch.setattr(svc.league_rankings, "build_league_rankings_frame_cached", boom)
    p = svc._resolve_trade_posture({"id": "u"}, "L", {}, {"roster_id": 1}, lens="Dynasty", client_strategy="rebuild")
    assert (p["key"], p["source"]) == ("rebuild", "client")

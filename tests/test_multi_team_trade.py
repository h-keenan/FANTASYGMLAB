"""Multi-team trade analyzer: transfer model, validation, engine, veto N-team, API."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pandas as pd
import pytest
from freezegun import freeze_time

from modules import (
    admission,
    league_rankings,
    league_value_settings,
    nfl_schedule,
    sleeper,
    trade_hub_engine,
    trade_ideas,
    trade_veto,
)
from modules import multi_team_trade as mt
from modules import multi_team_trade_engine as engine
from scripts.profile_trade_hub import FixtureSpec, build_fixture
from tests.test_mobile_api_service import _client

T = mt.Transfer
ROSTERS = {"1": ["a1", "a2"], "2": ["b1", "b2"], "3": ["c1", "c2"], "4": ["d1"], "5": ["e1"], "6": ["f1"], "7": ["g1"]}


def _ids(errors):
    return [e["code"] for e in errors]


# --- transfer model + validation --------------------------------------------


def test_valid_three_team_cycle():
    ts = [T("player", "a1", "1", "2"), T("player", "b1", "2", "3"), T("player", "c1", "3", "1")]
    assert mt.validate_transfers(ts, roster_players=ROSTERS) == []
    assert mt.participants(ts) == ["1", "2", "3"]
    assert [t.asset_id for t in mt.outgoing(ts, "2")] == ["b1"]
    assert [t.asset_id for t in mt.incoming(ts, "1")] == ["c1"]


def test_team_that_only_receives_is_legal():
    ts = [T("player", "a1", "1", "3"), T("player", "b1", "2", "3"), T("player", "a2", "1", "2")]
    assert mt.validate_transfers(ts, roster_players=ROSTERS) == []


def test_ownership_violation_and_double_move():
    ts = [T("player", "a1", "2", "3"), T("player", "b1", "2", "1"), T("player", "b1", "2", "3")]
    codes = _ids(mt.validate_transfers(ts, roster_players=ROSTERS))
    assert mt.ERR_NOT_OWNED in codes and mt.ERR_DUPLICATE in codes


def test_same_team_unknown_roster_and_team_caps():
    assert mt.ERR_SAME_TEAM in _ids(mt.validate_transfers([T("player", "a1", "1", "1")], roster_players=ROSTERS))
    assert mt.ERR_UNKNOWN_ROSTER in _ids(
        mt.validate_transfers([T("player", "a1", "1", "99"), T("player", "b1", "2", "1")], roster_players=ROSTERS)
    )
    two = [T("player", "a1", "1", "2"), T("player", "b1", "2", "1")]
    assert mt.ERR_TOO_FEW in _ids(mt.validate_transfers(two, roster_players=ROSTERS))
    assert mt.validate_transfers(two, roster_players=ROSTERS, min_teams=2) == []
    seven = [T("player", f"{c}1", str(i), str(i % 7 + 1)) for i, c in enumerate("abcdefg", start=1)]
    assert mt.ERR_TOO_MANY in _ids(mt.validate_transfers(seven, roster_players=ROSTERS))
    six = [T("player", f"{c}1", str(i), str(i % 6 + 1)) for i, c in enumerate("abcdef", start=1)]
    assert mt.ERR_TOO_MANY not in _ids(mt.validate_transfers(six, roster_players=ROSTERS))


def test_pick_ownership():
    ts = [T("pick", "2027:1:2", "2", "1"), T("player", "a1", "1", "3"), T("player", "c1", "3", "2")]
    assert mt.validate_transfers(ts, roster_players=ROSTERS, pick_owners={"2027:1:2": "2"}) == []
    assert mt.ERR_NOT_OWNED in _ids(mt.validate_transfers(ts, roster_players=ROSTERS, pick_owners={"2027:1:2": "3"}))
    assert mt.ERR_UNKNOWN_PICK in _ids(mt.validate_transfers(ts, roster_players=ROSTERS, pick_owners={}))


def test_parse_rejects_malformed_rows_loudly():
    ts, errs = mt.parse_transfers([{"type": "player", "id": "a1", "from_roster_id": 1, "to_roster_id": 2}, {"type": "bad"}, "x"])
    assert [t.to_public() for t in ts] == [{"type": "player", "id": "a1", "from_roster_id": "1", "to_roster_id": "2"}]
    assert len(errs) == 2 and all(e["code"] == mt.ERR_SHAPE for e in errs)


def test_legacy_two_team_round_trip():
    ts = mt.from_two_team("1", "2", send_player_ids=["a1"], receive_player_ids=["b1"], send_pick_ids=["2027:1:1"])
    assert mt.to_two_team(ts, "1") == {
        "send_player_ids": ["a1"], "receive_player_ids": ["b1"],
        "send_pick_ids": ["2027:1:1"], "receive_pick_ids": [],
    }
    assert mt.to_two_team([*ts, T("player", "c1", "3", "1")], "1") is None


def _row(rid, score, market, tone):
    return {"roster_id": rid, "team_name": f"T{rid}", "trade_score": score, "market_delta": market,
            "outcome": mt.outcome_for_tone(tone)}


def test_summary_names_most_hurt_and_spread():
    rows = [_row("1", 900, 800, "accept"), _row("2", -50, -40, "fair"), _row("3", -1500, -1200, "decline")]
    s = mt.summarize(rows, "2")
    assert s["most_hurt_roster_id"] == "3" and s["best_off_roster_id"] == "1"
    assert s["balance"]["spread"] == 2400 and s["balance"]["id"] == "lopsided"
    assert s["outcomes"] == {"wins": ["1"], "even": ["2"], "gives_up": [], "loses": ["3"]}
    assert s["perspective"] == {"roster_id": "2", "outcome": "even", "rank": 2, "of": 3}
    assert [r["roster_id"] for r in s["ranking"]] == ["1", "2", "3"]
    balanced = mt.summarize([_row("1", 60, 50, "fair"), _row("2", -20, -30, "fair"), _row("3", 0, -20, "fair")])
    assert balanced["balance"]["id"] == "balanced" and balanced["perspective"] is None


# --- veto generalisation + 2-team regression ---------------------------------


def _old_assess(sides, prior_lopsided_wins=None):
    """Verbatim pre-change two-side implementation, kept as the byte-identical reference."""
    from modules import trade_value_bands as bands

    if len(sides) != 2:
        raise ValueError("a veto check needs exactly two sides")
    prior = {str(k): int(v) for k, v in (prior_lopsided_wins or {}).items()}
    loser = min(sides, key=lambda s: (float(s["team_score"]), float(s["market_delta"])))
    winner = next(s for s in sides if s is not loser)
    market_gap = trade_veto._gap_norm(float(loser["market_delta"]))
    team_gap = trade_veto._gap_norm(float(loser["team_score"]))
    explained = float(loser["team_score"]) >= -bands.EDGE
    if explained:
        base = 100.0 * trade_veto.EXPLAINABLE_MARKET_WEIGHT * market_gap
    else:
        base = 100.0 * (trade_veto.MARKET_WEIGHT * market_gap + trade_veto.TEAM_WEIGHT * team_gap)
    history = 0.0
    prior_wins = prior.get(str(winner["roster_id"]), 0)
    if base >= trade_veto.HISTORY_MIN_BASE and not explained:
        history = trade_veto.history_bonus(prior_wins)
    outrage = round(trade_veto._clamp(base + history, 0.0, 100.0), 1)
    band = trade_veto.band_for(outrage)
    reasons = trade_veto.side_reasons(loser)
    if history > 0:
        reasons.append(
            f"{winner.get('team_name') or 'The other team'} also won {prior_wins} earlier lopsided "
            f"trade{'s' if prior_wins != 1 else ''} from {loser.get('team_name') or 'this team'} this season."
        )
    if not reasons:
        reasons = ["Both rosters come out close to even on value and lineup points."]
    return {
        "outrage": outrage, "band": band, "label": trade_veto.BAND_LABELS[band],
        "advice": trade_veto.BAND_ADVICE[band], "explained_by_roster": bool(explained and market_gap > 0),
        "hurt_roster_id": str(loser["roster_id"]), "reasons": reasons[:5], "history_points": round(history, 1),
        "limits": list(trade_veto.LIMITS),
    }


def _side(rid, market, score, ppw=0.0, posture="retool"):
    return {"roster_id": rid, "team_name": f"Team {rid}", "market_delta": market, "team_score": score,
            "points_per_week": ppw, "posture": posture, "worst_position": None}


@pytest.mark.parametrize("market,score,wins", [
    (0, 0, {}), (2400, -2300, {}), (1500, 80, {}), (1300, -1000, {"1": 2}), (60, -70, {"1": 5}),
    (3000, -2600, {"1": 9}), (-500, 300, {"2": 1}),
])
def test_two_team_assess_is_byte_identical_to_the_old_implementation(market, score, wins):
    sides = [_side("1", market, -score), _side("2", -market, score, ppw=-2.5)]
    assert trade_veto.assess(sides, prior_lopsided_wins=wins) == _old_assess(sides, wins)


def test_assess_still_rejects_fewer_than_two_sides():
    with pytest.raises(ValueError):
        trade_veto.assess([_side("1", 0, 0)])


def test_three_team_assess_reads_the_worst_team_against_the_best():
    sides = [_side("1", 2000, 1800), _side("2", 100, 50), _side("3", -2100, -2000, ppw=-3.0)]
    out = trade_veto.assess(sides)
    assert out["hurt_roster_id"] == "3" and out["band"] in (trade_veto.BAND_LOPSIDED, trade_veto.BAND_OUTRAGE)
    each = trade_veto.assess_each(sides)
    assert set(each) == {"1", "2", "3"} and each["3"]["outrage"] == out["outrage"]
    assert each["1"]["outrage"] < each["3"]["outrage"] and each["1"]["hurt_roster_id"] == "1"
    # History credits the best-off side among the others.
    boosted = trade_veto.assess(sides, prior_lopsided_wins={"1": 2})
    assert boosted["history_points"] == 12.0


# --- engine on the fixture league -------------------------------------------


@pytest.fixture()
def league(monkeypatch):
    trade_ideas.clear_team_shape_memos()
    nfl_schedule.clear_load_games_cache()
    fx = build_fixture(FixtureSpec("multi", 8, 22, "1QB", strategy="contender"))
    fx["settings"] = dict(fx["settings"], current_week=8, max_roster_size=26, bench_count=17)
    monkeypatch.setattr(nfl_schedule, "load_games", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(sleeper, "get_league", lambda lid: {"league_id": lid, "total_rosters": len(fx["rosters"])})
    monkeypatch.setattr(sleeper, "get_rosters", lambda lid: fx["rosters"])
    monkeypatch.setattr(sleeper, "get_league_roster_profiles", lambda lid: {})
    monkeypatch.setattr(league_value_settings, "detect_league_value_settings_from_payload", lambda league: fx["settings"])
    monkeypatch.setattr(league_value_settings, "build_valued_players_frame_cached", lambda **k: fx["players"])
    monkeypatch.setattr(league_rankings, "build_league_summary_and_draft_capital_cached", lambda **k: (fx["summary"], None))
    monkeypatch.setattr(league_rankings, "build_league_rankings_frame_cached", lambda **k: pd.DataFrame())
    monkeypatch.setattr(trade_ideas, "get_sleeper_adapter", lambda *a, **k: fx["adapter"])
    with freeze_time("2026-10-28T12:00:00"):
        yield fx
    trade_ideas.clear_team_shape_memos()
    nfl_schedule.clear_load_games_cache()


def _top(fx, idx, n=1, skip=0):
    ids = [str(p) for p in fx["rosters"][idx]["players"]]
    rows = fx["players"][fx["players"]["player_id"].astype(str).isin(ids)].sort_values("value_score", ascending=False)
    return [str(p) for p in rows["player_id"].iloc[skip:skip + n]]


def _tr(pid, src, dst, kind="player"):
    return {"type": kind, "id": pid, "from_roster_id": str(src), "to_roster_id": str(dst)}


def _run(fx, transfers, **kw):
    return engine.analyze_multi_team_trade(
        league_id="fixture-league", transfers=transfers, lens="Dynasty", players_db_path=":memory:", **kw
    )


def test_three_team_cycle_grades_every_team(league):
    fx = league
    transfers = [_tr(_top(fx, 0)[0], 1, 2), _tr(_top(fx, 1)[0], 2, 3), _tr(_top(fx, 2)[0], 3, 1)]
    out = _run(fx, transfers, perspective_roster_id="2", include_veto=True)
    assert out["status"] == "ok", out
    assert [t["roster_id"] for t in out["teams"]][0] == "2"  # requester's seat first
    assert {t["roster_id"] for t in out["teams"]} == {"1", "2", "3"}
    for team in out["teams"]:
        assert len(team["sends"]) == 1 and len(team["receives"]) == 1
        assert team["verdict"]["band"] and team["tone"] in {"accept", "fair", "counter", "decline"}
        assert team["posture"]["group"] in {"contender", "retool", "rebuild"}
        assert {w["factor"] for w in team["why"]} >= {"flows", "market"}
        assert team["veto_risk"]["band"]
    summary = out["summary"]
    assert summary["team_count"] == 3 and summary["most_hurt_roster_id"] in {"1", "2", "3"}
    hurt = min(out["teams"], key=lambda t: t["trade_score"])
    assert summary["most_hurt_roster_id"] == hurt["roster_id"]
    assert len(out["flows"]) == 3 and out["veto_summary"]["hurt_roster_id"] == hurt["roster_id"]


def test_free_caller_gets_no_veto_detail(league):
    fx = league
    out = _run(fx, [_tr(_top(fx, 0)[0], 1, 2), _tr(_top(fx, 1)[0], 2, 3), _tr(_top(fx, 2)[0], 3, 1)])
    assert out["status"] == "ok" and all(t["veto_risk"] is None for t in out["teams"]) and out["veto_summary"] is None


def test_six_team_trade_with_a_receive_only_team(league):
    fx = league
    transfers = [
        _tr(_top(fx, 0)[0], 1, 2), _tr(_top(fx, 1)[0], 2, 3), _tr(_top(fx, 2)[0], 3, 4),
        _tr(_top(fx, 3)[0], 4, 5), _tr(_top(fx, 4)[0], 5, 6), _tr(_top(fx, 0, 1, skip=1)[0], 1, 6),
    ]
    out = _run(fx, transfers, perspective_roster_id="1", include_veto=True)
    assert out["status"] == "ok", out
    assert out["team_count"] == 6
    assert len(out["summary"]["ranking"]) == 6
    six = {t["roster_id"]: t for t in out["teams"]}
    assert six["6"]["sends"] == [] and len(six["6"]["receives"]) == 2
    assert six["1"]["sends"][0]["to_roster_id"] in {"2", "6"} and six["1"]["sends"][0]["to_team_name"]
    # Every flow is accounted for exactly once on each end.
    assert sum(len(t["sends"]) for t in out["teams"]) == sum(len(t["receives"]) for t in out["teams"]) == 6


def test_seven_teams_rejected_before_any_engine_work(league):
    fx = league
    transfers = [_tr(_top(fx, i)[0], i + 1, (i + 1) % 7 + 1) for i in range(7)]
    with patch.object(engine, "apply_strategy_age_curve", side_effect=AssertionError("engine ran")):
        out = _run(fx, transfers)
    assert out["status"] == "invalid" and out["errors"][0]["code"] == mt.ERR_TOO_MANY


def test_ownership_violations_are_reported_not_graded(league):
    fx = league
    stolen = _top(fx, 3)[0]  # roster 4's player, claimed by roster 1
    out = _run(fx, [_tr(stolen, 1, 2), _tr(_top(fx, 1)[0], 2, 3), _tr(_top(fx, 2)[0], 3, 1)])
    assert out["status"] == "invalid" and out["errors"][0]["code"] == mt.ERR_NOT_OWNED
    dup = _top(fx, 0)[0]
    out = _run(fx, [_tr(dup, 1, 2), _tr(dup, 1, 3), _tr(_top(fx, 1)[0], 2, 1)])
    assert out["status"] == "invalid" and mt.ERR_DUPLICATE in [e["code"] for e in out["errors"]]


def test_robbery_names_the_victim_as_most_hurt(league):
    fx = league
    stars = _top(fx, 0, 3)
    out = _run(fx, [_tr(stars[0], 1, 2), _tr(stars[1], 1, 3), _tr(stars[2], 1, 4), _tr(_top(fx, 1)[0], 2, 3)])
    assert out["status"] == "ok", out
    assert out["summary"]["most_hurt_roster_id"] == "1"
    assert out["summary"]["balance"]["id"] != "balanced"
    team1 = next(t for t in out["teams"] if t["roster_id"] == "1")
    assert team1["market_delta"] < 0 and team1["lineup_delta"]["per_week"] < 0


def test_two_team_matrix_is_the_mirror_of_the_legacy_package(league):
    fx = league
    a, b = _top(fx, 0)[0], _top(fx, 1)[0]
    out = _run(fx, [_tr(a, 1, 2), _tr(b, 2, 1)], min_teams=2, perspective_roster_id="1")
    assert out["status"] == "ok", out
    one, two = out["teams"]
    assert one["sends"][0]["id"] == a == two["receives"][0]["id"]
    assert two["sends"][0]["id"] == b == one["receives"][0]["id"]
    assert one["verdict"]["value_delta"] == one["market_delta"]
    assert one["verdict"]["trade_score"] == one["trade_score"]


def test_picks_move_between_teams_and_are_priced(league):
    fx = league
    picks = trade_ideas.list_draft_pick_assets("fixture-league", fx["summary"], league_settings=dict(fx["settings"]))
    mine = next(p for p in picks if str(p.get("owner_roster_id")) == "1")
    pid = f"{mine['season']}:{mine['round']}:{mine['original_roster_id']}"
    out = _run(fx, [_tr(pid, 1, 3, "pick"), _tr(_top(fx, 1)[0], 2, 1), _tr(_top(fx, 2)[0], 3, 2)])
    assert out["status"] == "ok", out
    team3 = next(t for t in out["teams"] if t["roster_id"] == "3")
    assert team3["receives"][0]["type"] == "pick" and team3["receives"][0]["score"] > 0
    bad = _run(fx, [_tr(pid, 2, 3, "pick"), _tr(_top(fx, 1)[0], 2, 1), _tr(_top(fx, 2)[0], 3, 2)])
    assert bad["status"] == "invalid" and bad["errors"][0]["code"] == mt.ERR_NOT_OWNED


# --- API / admission ---------------------------------------------------------


def test_admission_gates_the_multi_route_on_the_heavy_lane():
    assert admission.lane_for("/v1/leagues/1/trade-analyzer/multi") == "heavy"
    assert admission.lane_for("/v1/leagues/1/trade-analyzer") == "heavy"
    assert admission.lane_for("/v1/leagues/1/trade-analyzer/other") is None


def test_endpoint_requires_auth_and_validates(monkeypatch):
    client = _client(monkeypatch)
    body = {"transfers": [_tr("a1", 1, 2)]}
    assert client.post("/v1/leagues/abc/trade-analyzer/multi", json=body).status_code == 401


def _auth(entitlement="free"):
    auth = Mock(status_code=200)
    auth.json.return_value = {"id": "user-1", "email": "u@example.com"}
    profile = Mock(status_code=200)
    profile.json.return_value = [{"entitlement": entitlement, "sleeper_username": "gm_dynasty"}]
    return [auth, profile, profile, profile]


def test_endpoint_rejects_bad_lens_and_empty_transfers(monkeypatch):
    client = _client(monkeypatch)
    for payload in ({"transfers": [_tr("a", 1, 2)], "lens": "Nope"}, {"transfers": []}):
        with patch("requests.get", side_effect=_auth()):
            r = client.post("/v1/leagues/abc/trade-analyzer/multi", json=payload, headers={"Authorization": "Bearer t"})
        assert r.status_code == 422


def test_endpoint_is_not_metered_and_gates_veto_by_tier(monkeypatch):
    import services.mobile_api_service as svc

    client = _client(monkeypatch)
    fake = {"ok": True, "reason": "", "status": "ok", "teams": [], "summary": {}, "flows": []}
    monkeypatch.setattr(svc, "_resolve_my_roster", lambda user, lid: ({"roster_id": 1, "players": []}, ""))
    monkeypatch.setattr(svc, "_compute_multi_team_trade", lambda *a, **k: dict(fake))
    consume = Mock(return_value=True)
    refund = Mock()
    monkeypatch.setattr(svc.free_tier_ledger, "consume_weekly_trade_eval", consume)
    monkeypatch.setattr(svc.free_tier_ledger, "refund_weekly_trade_eval", refund)
    for pro, locked in ((False, True), (True, False)):
        monkeypatch.setattr(svc, "_is_pro_caller", lambda user, _p=pro: _p)
        body = {"transfers": [_tr("a1", 1, 2), _tr("b1", 2, 3), _tr("c1", 3, 1)], "perspective_roster_id": f"{int(pro)}"}
        with patch("requests.get", side_effect=_auth("pro" if pro else "free")):
            r = client.post("/v1/leagues/abc/trade-analyzer/multi", json=body, headers={"Authorization": "Bearer t"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["counts_against_free_limit"] is False and data["veto_locked"] is locked
        assert (data["veto_upsell"] is None) is (not locked)
    consume.assert_not_called()
    refund.assert_not_called()

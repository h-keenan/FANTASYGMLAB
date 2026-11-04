"""Commissioner trade veto calculator: scoring (modules.trade_veto) and endpoint gating."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from modules import trade_veto
from tests.test_mobile_api_service import _client


def _side(rid, market, score, ppw=0.0, posture="retool", name=None, worst=None):
    return {
        "roster_id": rid, "team_name": name or f"Team {rid}", "market_delta": market, "team_score": score,
        "points_per_week": ppw, "posture": posture, "worst_position": worst,
    }


def test_even_trade_is_fair():
    out = trade_veto.assess([_side("1", 40, 60), _side("2", -40, -50)])
    assert out["band"] == trade_veto.BAND_FAIR and out["outrage"] < 20


def test_market_robbery_that_also_hurts_the_roster_is_outrage_level():
    out = trade_veto.assess([_side("1", 2400, 2100), _side("2", -2400, -2300, ppw=-3.2, posture="contend")])
    assert out["band"] == trade_veto.BAND_OUTRAGE
    assert out["hurt_roster_id"] == "2"
    assert any("whole roster" in r or "lineup loses" in r for r in out["reasons"])


def test_rebuilder_selling_a_vet_for_youth_and_picks_is_explainable_not_outrage():
    # Market says they lose a lot, but their own (rebuild-weighted) score is fine.
    out = trade_veto.assess([
        _side("1", 1500, 400, posture="contend"),
        _side("2", -1500, 80, ppw=-2.0, posture="rebuild", name="Tank FC"),
    ])
    assert out["band"] in (trade_veto.BAND_FAIR, trade_veto.BAND_EXPLAINABLE)
    assert out["explained_by_roster"] is True
    assert any("rebuilding" in r for r in out["reasons"])


def test_same_market_gap_scores_worse_when_the_team_read_is_also_bad():
    explained = trade_veto.assess([_side("1", 1500, 400), _side("2", -1500, 0)])
    unexplained = trade_veto.assess([_side("1", 1500, 400), _side("2", -1500, -1300)])
    assert unexplained["outrage"] > explained["outrage"] + 15


def test_history_adds_points_but_never_turns_a_fair_trade_into_a_flag():
    fair = [_side("1", 60, 90), _side("2", -60, -70)]
    assert trade_veto.assess(fair, prior_lopsided_wins={"1": 5})["band"] == trade_veto.BAND_FAIR
    bad = [_side("1", 1300, 1000), _side("2", -1300, -1000)]
    base = trade_veto.assess(bad)["outrage"]
    boosted = trade_veto.assess(bad, prior_lopsided_wins={"1": 2})
    assert boosted["outrage"] == pytest.approx(base + 12, abs=0.2)
    assert boosted["history_points"] == 12.0
    assert any("earlier lopsided" in r for r in boosted["reasons"])


def test_history_is_capped_and_scores_stay_in_range():
    out = trade_veto.assess([_side("1", 5000, 4000), _side("2", -5000, -4000)], prior_lopsided_wins={"1": 9})
    assert out["history_points"] == trade_veto.HISTORY_MAX and out["outrage"] <= 100


def test_every_result_carries_the_limits_and_never_says_collusion():
    out = trade_veto.assess([_side("1", 2400, 2100), _side("2", -2400, -2300)])
    assert out["limits"] and "collusion" in " ".join(out["limits"]).lower()
    assert "collu" not in (out["advice"] + " ".join(out["reasons"])).lower()


def test_needs_two_sides():
    with pytest.raises(ValueError):
        trade_veto.assess([_side("1", 0, 0)])


def _auth(entitlement):
    auth = Mock(status_code=200)
    auth.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile = Mock(status_code=200)
    profile.json.return_value = [{"entitlement": entitlement, "sleeper_username": "gm_dynasty"}]
    return [auth, profile]


_BODY = {"roster_a": 1, "roster_b": 2, "a_sends_player_ids": ["p1"], "b_sends_player_ids": ["p2"]}


def test_endpoint_requires_auth(monkeypatch):
    assert _client(monkeypatch).post("/v1/leagues/abc/commissioner/veto-check", json=_BODY).status_code == 401


def test_endpoint_rejects_bad_lens(monkeypatch):
    client = _client(monkeypatch)
    with patch("requests.get", side_effect=_auth("pro")):
        r = client.post(
            "/v1/leagues/abc/commissioner/veto-check", json={**_BODY, "lens": "Nope"},
            headers={"Authorization": "Bearer t"},
        )
    assert r.status_code == 422


# --- whole-roster engine on the fixture league ------------------------------

import pandas as pd  # noqa: E402
from freezegun import freeze_time  # noqa: E402

from modules import league_rankings, league_value_settings, nfl_schedule, sleeper, trade_hub_engine, trade_ideas  # noqa: E402
from scripts.profile_trade_hub import FixtureSpec, build_fixture  # noqa: E402


@pytest.fixture()
def fixture_league(monkeypatch):
    trade_ideas.clear_team_shape_memos()
    nfl_schedule.clear_load_games_cache()
    fx = build_fixture(FixtureSpec("veto", 8, 22, "1QB", strategy="contender"))
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
    monkeypatch.setattr(trade_hub_engine, "_veto_prior_lopsided_wins", lambda *a, **k: {})
    with freeze_time("2026-10-28T12:00:00"):
        yield fx
    trade_ideas.clear_team_shape_memos()
    nfl_schedule.clear_load_games_cache()


def _top(fx, roster_index, n=1):
    ids = [str(p) for p in fx["rosters"][roster_index]["players"]]
    rows = fx["players"][fx["players"]["player_id"].astype(str).isin(ids)].sort_values("value_score", ascending=False)
    return [str(p) for p in rows["player_id"].head(n)]


def _check(fx, a_send, b_send, **extra):
    return trade_hub_engine.generate_veto_check(
        league_id="fixture-league", roster_a=1, roster_b=2, a_sends_player_ids=a_send,
        b_sends_player_ids=b_send, a_sends_pick_ids=extra.get("a_picks", []),
        b_sends_pick_ids=extra.get("b_picks", []), lens="Dynasty", players_db_path=":memory:",
    )


def test_even_swap_reads_fair_and_robbery_reads_worse(fixture_league):
    fx = fixture_league
    a_top, b_top = _top(fx, 0)[0], _top(fx, 1)[0]
    swap = _check(fx, [a_top], [b_top])
    assert swap["status"] == "ok", swap
    assert {s["roster_id"] for s in swap["sides"]} == {"1", "2"}
    # Roster 1 gives away its best player and two starters for nothing.
    robbery = _check(fx, _top(fx, 0, 3), [])
    assert robbery["status"] == "ok", robbery
    assert robbery["outrage"] > swap["outrage"]
    assert robbery["hurt_roster_id"] == "1"
    sides = {s["roster_id"]: s for s in robbery["sides"]}
    assert sides["1"]["market_delta"] < 0 < sides["2"]["market_delta"]
    assert sides["1"]["points_per_week"] < 0


def test_a_player_the_team_does_not_own_is_rejected(fixture_league):
    fx = fixture_league
    out = _check(fx, _top(fx, 1)[:1], [])
    assert out["status"] == "invalid"


def test_empty_trade_and_same_team_are_rejected(fixture_league):
    fx = fixture_league
    assert _check(fx, [], [])["status"] == "invalid"
    out = trade_hub_engine.generate_veto_check(
        league_id="x", roster_a=1, roster_b=1, a_sends_player_ids=_top(fx, 0), b_sends_player_ids=[],
        a_sends_pick_ids=[], b_sends_pick_ids=[], lens="Dynasty", players_db_path=":memory:",
    )
    assert out["status"] == "invalid"


def test_reasons_do_not_call_a_tiny_gap_a_loss():
    out = trade_veto.assess([_side("1", 49, 49), _side("2", -49, -49)])
    assert out["reasons"] == ["Both rosters come out close to even on value and lineup points."]

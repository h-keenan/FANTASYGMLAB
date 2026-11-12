"""One-tap season forecast: engine-only aggregation plus the /v1/sim/forecast route."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient

from modules.sim import api as sim_api
from modules.sim import forecast as fc
from modules.sim.forecast import build_forecast
from modules.sim.store import InMemoryBackend
from modules.sim.synthetic import build_synthetic_snapshot
from modules.sim.types import SimInputsError

SNAP = build_synthetic_snapshot(7)
SMALL = {"samples": 12, "scenario_samples": 6}


def test_forecast_shape_and_ranges():
    f = build_forecast(SNAP, **SMALL)
    assert f["samples"] == 12
    assert f["team"]["team_id"] == SNAP.user_team.tid
    odds = f["odds"]
    assert 0 <= odds["title"] <= odds["finals"] <= odds["playoffs"] <= 1
    rec = f["record"]
    assert rec["wins_low"] <= rec["wins"] <= rec["wins_high"]
    w, l = rec["projected"].split("-")
    assert int(w) + int(l) == int(rec["games"])
    fin = f["finish"]
    assert 1 <= fin["low"] <= fin["median"] <= fin["high"] <= fin["teams"]
    assert len(fin["distribution"]) == fin["teams"]
    assert abs(sum(d["probability"] for d in fin["distribution"]) - 1) < 0.02
    assert len(f["swing_factors"]) <= fc.MAX_FACTORS
    for factor in f["swing_factors"]:
        assert factor["kind"] in ("game", "waiver", "trade")
        assert factor["title"] and factor["detail"]


def test_forecast_is_deterministic():
    assert build_forecast(SNAP, **SMALL) == build_forecast(SNAP, **SMALL)


def test_forecast_never_runs_user_transactions():
    # Baseline strategy: the user's own trades and waivers are off ("current rosters").
    assert fc.BASELINE.trade_aggressiveness == 0 and fc.BASELINE.waiver_aggressiveness == 0
    assert fc.BASELINE.lineup_auto_set is True
    outcome = fc.simulate_season(SNAP, fc.BASELINE, 1)
    assert not [e for e in outcome.events if e.get("involves_user")]


def test_game_swing_is_conditional_odds():
    outcomes = [fc.simulate_season(SNAP, fc.BASELINE, s) for s in range(1, 41)]
    scores = [fc._score(o) for o in outcomes]
    factors = fc._game_factors(SNAP, outcomes, scores)
    for factor in factors:
        assert factor["kind"] == "game" and factor["playoff_delta"] >= fc.MIN_GAME_SWING
        assert "playoff odds" in factor["detail"]


def test_move_factor_needs_a_real_gain(monkeypatch):
    base = [fc._score(fc.simulate_season(SNAP, fc.BASELINE, s)) for s in range(1, 9)]
    scenario = [fc.simulate_season(SNAP, fc.WIRE, s) for s in range(1, 9)]
    monkeypatch.setattr(fc, "MIN_MOVE_PLAYOFF_GAIN", 2.0)
    monkeypatch.setattr(fc, "MIN_MOVE_TITLE_GAIN", 2.0)
    assert fc._move_factor("waiver", base, scenario, SNAP.user_team.tid) is None


class FakeInputs:
    def __init__(self):
        self.calls = 0

    def league_snapshot(self, league_id, *, mode="remaining", username="", roster_id=""):
        self.calls += 1
        if league_id == "missing":
            raise SimInputsError("league_unavailable")
        if league_id == "over":
            raise SimInputsError("season_complete")
        return SNAP


@pytest.fixture
def client(monkeypatch):
    sim_api._FORECAST_CACHE.clear()
    monkeypatch.setattr(sim_api, "build_forecast", lambda snap: build_forecast(snap, **SMALL))
    inputs = FakeInputs()

    def require_user(authorization: str | None = Header(default=None)):
        return {"id": authorization or "u1", "_access_token": "tok"}

    app = FastAPI()
    sim_api.mount(
        app,
        sim_api.SimApiDeps(
            require_user=require_user, is_pro=lambda u: u["id"] == "u1",
            sleeper_username=lambda u: "user1", backend_for=lambda u: InMemoryBackend(), inputs=inputs,
        ),
        environ={"SIM_ENABLED": "1"},
    )
    yield TestClient(app), inputs
    sim_api._FORECAST_CACHE.clear()


def test_route_free_user_gets_upsell_and_no_work(client):
    c, inputs = client
    body = c.get("/v1/sim/forecast?league_id=L1", headers={"Authorization": "free"}).json()
    assert body["reason"] == "premium_required" and body["upsell"]["title"]
    assert inputs.calls == 0


def test_route_pro_gets_forecast_and_it_is_cached(client):
    c, inputs = client
    body = c.get("/v1/sim/forecast?league_id=L1", headers={"Authorization": "u1"}).json()
    assert body["reason"] == "" and body["forecast"]["odds"]["playoffs"] >= 0
    assert body["as_of"] and body["mode"] == "full" and isinstance(body["notes"], list)
    again = c.get("/v1/sim/forecast?league_id=L1", headers={"Authorization": "u1"}).json()
    assert again == body and inputs.calls == 1


@pytest.mark.parametrize("league,reason", [("missing", "league_unavailable"), ("over", "season_complete")])
def test_route_not_ready_reasons(client, league, reason):
    c, _ = client
    assert c.get(f"/v1/sim/forecast?league_id={league}", headers={"Authorization": "u1"}).json()["reason"] == reason


def test_route_requires_league_id(client):
    c, _ = client
    assert c.get("/v1/sim/forecast", headers={"Authorization": "u1"}).status_code == 422

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


def test_single_flight_computes_once_for_concurrent_requests(client, monkeypatch):
    import threading
    import time

    c, inputs = client
    started = threading.Event()
    release = threading.Event()
    calls = []

    def slow(snap):
        calls.append(1)
        started.set()
        release.wait(5)
        return build_forecast(snap, **SMALL)

    monkeypatch.setattr(sim_api, "build_forecast", slow)
    results = []

    def hit():
        results.append(c.get("/v1/sim/forecast?league_id=L1", headers={"Authorization": "u1"}).json())

    first = threading.Thread(target=hit)
    first.start()
    assert started.wait(5)
    others = [threading.Thread(target=hit) for _ in range(3)]
    for t in others:
        t.start()
    time.sleep(0.3)  # followers are parked on the in-flight computation
    release.set()
    for t in [first, *others]:
        t.join(10)
    assert len(calls) == 1 and inputs.calls == 1
    assert len(results) == 4 and all(r["reason"] == "" and r["forecast"] for r in results)
    assert not sim_api._FLIGHTS


def test_single_flight_is_per_user_and_league(client):
    c, inputs = client
    c.get("/v1/sim/forecast?league_id=L1", headers={"Authorization": "u1"})
    c.get("/v1/sim/forecast?league_id=L2", headers={"Authorization": "u1"})
    assert inputs.calls == 2


def test_failed_compute_is_not_cached_and_clears_the_flight(client, monkeypatch):
    c, inputs = client

    def boom(snap):
        raise RuntimeError("engine blew up")

    monkeypatch.setattr(sim_api, "build_forecast", boom)
    with pytest.raises(RuntimeError):
        c.get("/v1/sim/forecast?league_id=L1", headers={"Authorization": "u1"})
    assert not sim_api._FLIGHTS and not sim_api._FORECAST_CACHE
    monkeypatch.setattr(sim_api, "build_forecast", lambda snap: build_forecast(snap, **SMALL))
    assert c.get("/v1/sim/forecast?league_id=L1", headers={"Authorization": "u1"}).json()["forecast"]


def test_full_compute_pool_answers_503_server_busy_and_is_not_cached(client, monkeypatch):
    c, inputs = client
    monkeypatch.setattr(sim_api, "_COMPUTE_WAIT_SECONDS", 0.05)
    held = [sim_api._COMPUTE.acquire() for _ in range(sim_api.MAX_CONCURRENT_COMPUTE)]
    try:
        r = c.get("/v1/sim/forecast?league_id=L1", headers={"Authorization": "u1"})
    finally:
        for _ in held:
            sim_api._COMPUTE.release()
    assert r.status_code == 503 and r.json()["code"] == "server_busy" and r.headers["retry-after"] == "5"
    assert inputs.calls == 0 and not sim_api._FORECAST_CACHE
    assert c.get("/v1/sim/forecast?league_id=L1", headers={"Authorization": "u1"}).status_code == 200


def test_sample_plan_shrinks_for_long_horizons_but_keeps_a_floor():
    assert fc.sample_plan(5) == (fc.BASE_SAMPLES, fc.SCENARIO_SAMPLES)
    mid, mid_s = fc.sample_plan(10)
    assert fc.MIN_BASE_SAMPLES < mid < fc.BASE_SAMPLES and mid_s < fc.SCENARIO_SAMPLES
    assert fc.sample_plan(14) == (fc.MIN_BASE_SAMPLES, fc.MIN_SCENARIO_SAMPLES) == fc.sample_plan(40)

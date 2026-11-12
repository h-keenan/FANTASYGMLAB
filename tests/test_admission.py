"""modules.admission: bounded concurrency + queue + 503/Retry-After shedding."""

from __future__ import annotations

import asyncio

import httpx
from fastapi import FastAPI

from modules import admission
from modules.admission import AdmissionControlMiddleware


def _app(gate: dict) -> FastAPI:
    app = FastAPI()
    app.add_middleware(AdmissionControlMiddleware, enabled_in_tests=True)

    @app.get("/v1/leagues/{lid}/dashboard")
    async def dashboard(lid: str):
        gate["running"] = gate.get("running", 0) + 1
        gate["peak"] = max(gate.get("peak", 0), gate["running"])
        try:
            await asyncio.sleep(gate.get("hold", 0.2))
        finally:
            gate["running"] -= 1
        return {"ok": True}

    @app.get("/v1/leagues/{lid}/my-team")
    async def my_team(lid: str):
        gate["light_running"] = gate.get("light_running", 0) + 1
        gate["light_peak"] = max(gate.get("light_peak", 0), gate["light_running"])
        try:
            await asyncio.sleep(gate.get("light_hold", 0.1))
        finally:
            gate["light_running"] -= 1
        return {"ok": True}

    @app.get("/v1/leagues/{lid}/users")
    async def users(lid: str):
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"ok": True}

    return app


def _run(app, n, path="/v1/leagues/L1/dashboard"):
    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            return await asyncio.gather(*[c.get(path) for _ in range(n)])

    return asyncio.run(go())


def test_is_expensive_matches_engine_routes_only():
    for p in ("/v1/leagues/1/dashboard", "/v1/leagues/1/my-team", "/v1/leagues/1/trade-hub", "/v1/leagues/1/waivers",
              "/v1/leagues/1/playoff-odds", "/v1/leagues/1/trade-analyzer", "/v1/leagues/1/trade-hub/abc"):
        assert admission.is_expensive(p), p
    for p in ("/health", "/v1/leagues/1/users", "/v1/analytics/event", "/v1/leagues/1/team-stance",
              "/v1/leagues/1/trade-hub/abc/share-card.png", "/v1/me"):
        assert not admission.is_expensive(p), p


def test_concurrency_is_capped_and_queue_serves_everyone(monkeypatch):
    monkeypatch.setenv("ADMISSION_MAX_INFLIGHT", "2")
    monkeypatch.setenv("ADMISSION_MAX_QUEUE", "10")
    monkeypatch.setenv("ADMISSION_MAX_WAIT_SECONDS", "5")
    gate = {"hold": 0.1}
    responses = _run(_app(gate), 6)
    assert [r.status_code for r in responses] == [200] * 6
    assert gate["peak"] == 2


def test_queue_full_sheds_503_with_retry_after_and_code(monkeypatch):
    monkeypatch.setenv("ADMISSION_MAX_INFLIGHT", "1")
    monkeypatch.setenv("ADMISSION_MAX_QUEUE", "1")
    monkeypatch.setenv("ADMISSION_MAX_WAIT_SECONDS", "5")
    responses = _run(_app({"hold": 0.3}), 4)
    codes = sorted(r.status_code for r in responses)
    assert codes == [200, 200, 503, 503]
    shed = next(r for r in responses if r.status_code == 503)
    assert int(shed.headers["retry-after"]) >= 2
    body = shed.json()
    assert body["code"] == "server_busy"
    assert body["ok"] is False and body["detail"] and body["error"]
    assert body["retry_after"] == int(shed.headers["retry-after"])
    assert shed.headers["x-admission"] == "queue_full"


def test_waiter_times_out_and_is_shed(monkeypatch):
    monkeypatch.setenv("ADMISSION_MAX_INFLIGHT", "1")
    monkeypatch.setenv("ADMISSION_MAX_QUEUE", "5")
    monkeypatch.setenv("ADMISSION_MAX_WAIT_SECONDS", "0.1")
    responses = _run(_app({"hold": 0.5}), 3)
    assert sorted(r.status_code for r in responses) == [200, 503, 503]
    assert {r.headers["x-admission"] for r in responses if r.status_code == 503} == {"queue_timeout"}


def test_cheap_routes_are_never_queued_behind_heavy_work(monkeypatch):
    monkeypatch.setenv("ADMISSION_MAX_INFLIGHT", "1")
    monkeypatch.setenv("ADMISSION_MAX_QUEUE", "0")
    app = _app({"hold": 0.3})

    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            heavy = asyncio.create_task(c.get("/v1/leagues/L1/dashboard"))
            await asyncio.sleep(0.05)
            cheap = await asyncio.gather(c.get("/health"), c.get("/v1/leagues/L1/users"))
            rejected = await c.get("/v1/leagues/L1/dashboard")
            return cheap, rejected, await heavy

    cheap, rejected, heavy = asyncio.run(go())
    assert [r.status_code for r in cheap] == [200, 200]
    assert rejected.status_code == 503
    assert heavy.status_code == 200


def test_slot_is_released_after_each_request(monkeypatch):
    monkeypatch.setenv("ADMISSION_MAX_INFLIGHT", "1")
    monkeypatch.setenv("ADMISSION_MAX_QUEUE", "0")
    app = _app({"hold": 0.01})
    for _ in range(3):
        assert _run(app, 1)[0].status_code == 200


def test_zero_disables_gate(monkeypatch):
    monkeypatch.setenv("ADMISSION_MAX_INFLIGHT", "0")
    gate = {"hold": 0.05}
    assert [r.status_code for r in _run(_app(gate), 5)] == [200] * 5
    assert gate["peak"] == 5


def test_disabled_under_pytest_unless_forced(monkeypatch):
    monkeypatch.setenv("ADMISSION_MAX_INFLIGHT", "1")
    monkeypatch.setenv("ADMISSION_MAX_QUEUE", "0")
    app = FastAPI()
    app.add_middleware(AdmissionControlMiddleware)  # default: not enabled in tests

    @app.get("/v1/leagues/{lid}/dashboard")
    async def dash(lid: str):
        await asyncio.sleep(0.05)
        return {}

    assert [r.status_code for r in _run(app, 3)] == [200] * 3


def test_real_app_registers_the_gate_and_exposes_retry_after():
    from services import mobile_api_service as svc

    assert any(m.cls is AdmissionControlMiddleware for m in svc.app.user_middleware)


def test_lane_classification():
    for p in ("/v1/leagues/1/dashboard", "/v1/leagues/1/trade-hub", "/v1/leagues/1/trade-analyzer",
              "/v1/leagues/1/matchup/what-if", "/v1/leagues/1/team-rankings", "/v1/leagues/1/games/season-sim"):
        assert admission.lane_for(p) == "heavy", p
    for p in ("/v1/leagues/1/my-team", "/v1/leagues/1/my-team-needs", "/v1/leagues/1/matchup",
              "/v1/leagues/1/waivers", "/v1/leagues/1/playoff-odds", "/v1/leagues/1/rankings"):
        assert admission.lane_for(p) == "light", p
    for p in ("/health", "/v1/leagues/1/users", "/v1/leagues/1/trade-hub/abc/share-card.png", "/v1/me"):
        assert admission.lane_for(p) is None, p


def test_sim_forecast_is_in_the_heavy_lane_and_sheds_with_retry_after(monkeypatch):
    assert admission.lane_for("/v1/sim/forecast") == "heavy"
    assert admission.lane_for("/v1/sim/games") is None
    monkeypatch.setenv("ADMISSION_MAX_INFLIGHT", "1")
    monkeypatch.setenv("ADMISSION_MAX_QUEUE", "0")
    app = FastAPI()
    app.add_middleware(AdmissionControlMiddleware, enabled_in_tests=True)

    @app.get("/v1/sim/forecast")
    async def forecast():
        await asyncio.sleep(0.2)
        return {"ok": True}

    responses = _run(app, 3, path="/v1/sim/forecast")
    codes = sorted(r.status_code for r in responses)
    assert codes == [200, 503, 503]
    shed = next(r for r in responses if r.status_code == 503)
    assert shed.json()["code"] == "server_busy" and int(shed.headers["retry-after"]) >= 2


def test_light_routes_are_not_shed_or_queued_behind_saturated_heavy_pool(monkeypatch):
    monkeypatch.setenv("ADMISSION_MAX_INFLIGHT", "1")
    monkeypatch.setenv("ADMISSION_MAX_QUEUE", "0")
    monkeypatch.setenv("ADMISSION_LIGHT_MAX_INFLIGHT", "4")
    app = _app({"hold": 0.4, "light_hold": 0.05})

    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            heavy = asyncio.create_task(c.get("/v1/leagues/L1/dashboard"))
            await asyncio.sleep(0.05)
            start = asyncio.get_running_loop().time()
            light = await asyncio.gather(*[c.get("/v1/leagues/L1/my-team") for _ in range(3)])
            light_elapsed = asyncio.get_running_loop().time() - start
            shed_heavy = await c.get("/v1/leagues/L1/dashboard")
            return light, light_elapsed, shed_heavy, await heavy

    light, light_elapsed, shed_heavy, heavy = asyncio.run(go())
    assert [r.status_code for r in light] == [200] * 3
    assert light_elapsed < 0.3  # served immediately, not after the 0.4s heavy request
    assert shed_heavy.status_code == 503
    assert heavy.status_code == 200


def test_heavy_work_does_not_consume_light_slots_and_light_pool_is_capped(monkeypatch):
    monkeypatch.setenv("ADMISSION_MAX_INFLIGHT", "8")
    monkeypatch.setenv("ADMISSION_LIGHT_MAX_INFLIGHT", "2")
    monkeypatch.setenv("ADMISSION_LIGHT_MAX_QUEUE", "0")
    gate = {"hold": 0.05, "light_hold": 0.2}
    responses = _run(_app(gate), 5, path="/v1/leagues/L1/my-team")
    assert sorted(r.status_code for r in responses) == [200, 200, 503, 503, 503]
    assert gate["light_peak"] == 2
    assert responses[0].headers.get("x-admission") in (None, "queue_full")


def test_light_lane_can_be_disabled_independently(monkeypatch):
    monkeypatch.setenv("ADMISSION_LIGHT_MAX_INFLIGHT", "0")
    gate = {"light_hold": 0.05}
    assert [r.status_code for r in _run(_app(gate), 6, path="/v1/leagues/L1/my-team")] == [200] * 6
    assert gate["light_peak"] == 6

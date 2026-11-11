"""/v1/sim/* router and sim_* storage, with stubbed auth/Pro/data (no network)."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from modules.sim import api as sim_api
from modules.sim.store import MAX_WORLDS_PER_USER, InMemoryBackend, SimStore
from modules.sim.synthetic import build_synthetic_snapshot
from modules.sim.types import SimInputsError, Strategy

SNAP = build_synthetic_snapshot(7)


class FakeInputs:
    def __init__(self):
        self.calls = []

    def league_snapshot(self, league_id, *, mode="remaining", username="", roster_id=""):
        self.calls.append((league_id, mode, username, roster_id))
        if league_id == "missing":
            raise SimInputsError("league_unavailable")
        return SNAP


def make_app(*, pro=("u1", "u2"), backend=None, inputs=None):
    backend = backend if backend is not None else InMemoryBackend()
    inputs = inputs or FakeInputs()

    def require_user(authorization: str | None = Header(default=None)):
        if not authorization:
            raise HTTPException(status_code=401, detail="no")
        return {"id": authorization, "_access_token": "tok"}

    app = FastAPI()
    sim_api.mount(
        app,
        sim_api.SimApiDeps(
            require_user=require_user, is_pro=lambda u: u["id"] in pro,
            sleeper_username=lambda u: "user1", backend_for=lambda u: backend, inputs=inputs,
        ),
        environ={"SIM_ENABLED": "1"},
    )
    return app, backend, inputs


def hdr(user="u1"):
    return {"Authorization": user}


def create(client, **body):
    return client.post("/v1/sim/worlds", json={"league_id": "L1", **body}, headers=hdr()).json()


def test_flag_off_mounts_nothing():
    app = FastAPI()
    deps = sim_api.SimApiDeps(
        require_user=lambda: {}, is_pro=lambda u: True, sleeper_username=lambda u: "", backend_for=lambda u: None
    )
    for env in ({}, {"SIM_ENABLED": "0"}, {"SIM_ENABLED": ""}, {"SIM_ENABLED": "nope"}):
        assert sim_api.mount(app, deps, environ=env) is False
    assert TestClient(app).get("/v1/sim/status").status_code == 404
    assert sim_api.mount(app, deps, environ={"SIM_ENABLED": "true"}) is True


def test_requires_auth():
    app, _, _ = make_app()
    assert TestClient(app).get("/v1/sim/worlds").status_code == 401


def test_free_users_get_premium_required_and_nothing_runs():
    app, backend, inputs = make_app(pro=())
    client = TestClient(app)
    for method, path, body in [
        ("get", "/v1/sim/status", None), ("get", "/v1/sim/worlds", None),
        ("post", "/v1/sim/worlds", {"league_id": "L1"}),
        ("get", "/v1/sim/worlds/00000000-0000-0000-0000-000000000000", None),
        ("post", "/v1/sim/worlds/00000000-0000-0000-0000-000000000000/run", None),
        ("delete", "/v1/sim/worlds/00000000-0000-0000-0000-000000000000", None),
    ]:
        res = getattr(client, method)(path, headers=hdr(), **({"json": body} if body else {}))
        assert res.status_code == 200
        data = res.json()
        assert data["reason"] == "premium_required" and data["is_premium"] is False and data["upsell"]
    assert inputs.calls == [] and backend.tables == {}


def test_status_describes_options():
    app, _, _ = make_app()
    data = TestClient(app).get("/v1/sim/status", headers=hdr()).json()
    assert data["ok"] and data["enabled"] and data["reason"] == ""
    assert {p["id"] for p in data["personas"]} >= {"contender", "rebuilder", "value_shark"}
    assert data["strategy_options"]["posture"]["values"] == ["win_now", "balanced", "rebuild"]


def test_create_run_get_delete_flow():
    app, backend, inputs = make_app()
    client = TestClient(app)
    created = create(client, strategy={"posture": "rebuild", "trade_aggressiveness": 0.8})
    assert created["reason"] == "" and created["team"]["team_id"] == "1"
    world = created["world"]
    assert world["status"] == "ready" and world["strategy"]["posture"] == "rebuild"
    assert isinstance(world["seed"], int) and "user_id" not in world
    assert inputs.calls == [("L1", "remaining", "user1", "")]

    assert client.get(f"/v1/sim/worlds/{world['id']}/result", headers=hdr()).json()["reason"] == "not_simulated"

    ran = client.post(f"/v1/sim/worlds/{world['id']}/run", headers=hdr()).json()
    assert ran["reason"] == "" and ran["world"]["status"] == "simulated"
    result = ran["result"]
    assert result["grade"]["letter"] and len(result["decisions_that_mattered"]) >= 3
    assert result["seed"] == world["seed"] and result["strategy"]["posture"] == "rebuild"
    assert ran["world"]["grade_letter"] == result["grade"]["letter"]

    # idempotent: a second run returns the stored result, identical
    again = client.post(f"/v1/sim/worlds/{world['id']}/run", headers=hdr()).json()
    assert again["result"] == result
    fetched = client.get(f"/v1/sim/worlds/{world['id']}/result", headers=hdr()).json()
    assert fetched["result"] == result
    listed = client.get("/v1/sim/worlds", headers=hdr()).json()
    assert [w["id"] for w in listed["worlds"]] == [world["id"]]

    assert client.delete(f"/v1/sim/worlds/{world['id']}", headers=hdr()).json()["reason"] == ""
    assert client.get(f"/v1/sim/worlds/{world['id']}", headers=hdr()).status_code == 404
    assert all(not rows for rows in backend.tables.values())


def test_changing_strategy_invalidates_result_and_changes_outcome():
    app, _, _ = make_app()
    client = TestClient(app)
    wid = create(client)["world"]["id"]
    first = client.post(f"/v1/sim/worlds/{wid}/run", headers=hdr()).json()["result"]
    put = client.put(
        f"/v1/sim/worlds/{wid}/strategy", headers=hdr(),
        json={"strategy": {"posture": "win_now", "trade_aggressiveness": 0.0, "lineup_auto_set": False}},
    ).json()
    assert put["world"]["status"] == "ready" and put["world"]["grade_letter"] is None
    assert client.get(f"/v1/sim/worlds/{wid}/result", headers=hdr()).json()["reason"] == "not_simulated"
    second = client.post(f"/v1/sim/worlds/{wid}/run", headers=hdr()).json()["result"]
    assert second["seed"] == first["seed"] and second["strategy"]["lineup_auto_set"] is False
    assert second != first


def test_validation_errors_are_422():
    app, _, _ = make_app()
    client = TestClient(app)
    bad = [
        {"strategy": {"posture": "yolo"}}, {"strategy": {"trade_aggressiveness": 2}},
        {"strategy": {"waiver_aggressiveness": "lots"}}, {"strategy": {"lineup_auto_set": "yes"}},
        {"mode": "dynasty"}, {"league_id": " "}, {"strategy": {"protected_player_ids": ["nobody"]}},
    ]
    for extra in bad:
        body = {"league_id": "L1", **extra}
        assert client.post("/v1/sim/worlds", json=body, headers=hdr()).status_code == 422, extra
    wid = create(client)["world"]["id"]
    res = client.put(f"/v1/sim/worlds/{wid}/strategy", json={"strategy": {"posture": "x"}}, headers=hdr())
    assert res.status_code == 422


def test_protected_players_accepted_when_on_roster():
    app, _, _ = make_app()
    client = TestClient(app)
    roster = list(SNAP.user_team.roster)
    created = create(client, strategy={"protected_player_ids": roster[:2]})
    assert created["world"]["strategy"]["protected_player_ids"] == sorted(roster[:2])


def test_input_failures_pass_through_as_reasons():
    app, _, _ = make_app()
    data = create(TestClient(app), league_id="missing")
    assert data["ok"] and data["reason"] == "league_unavailable" and "world" not in data


def test_bad_world_ids_are_404_not_queries():
    app, _, _ = make_app()
    client = TestClient(app)
    for bad in ("nope", "1; drop table", "..%2F..", "x" * 80):
        assert client.get(f"/v1/sim/worlds/{bad}", headers=hdr()).status_code == 404


def test_users_cannot_see_each_others_worlds():
    app, backend, _ = make_app()
    client = TestClient(app)
    wid = create(client)["world"]["id"]
    assert client.get(f"/v1/sim/worlds/{wid}", headers=hdr("u2")).status_code == 404
    assert client.post(f"/v1/sim/worlds/{wid}/run", headers=hdr("u2")).status_code == 404
    assert client.get("/v1/sim/worlds", headers=hdr("u2")).json()["worlds"] == []
    client.delete(f"/v1/sim/worlds/{wid}", headers=hdr("u2"))
    assert client.get(f"/v1/sim/worlds/{wid}", headers=hdr("u1")).status_code == 200


def test_world_limit():
    app, _, _ = make_app()
    client = TestClient(app)
    for _ in range(MAX_WORLDS_PER_USER):
        assert create(client)["reason"] == ""
    assert create(client)["reason"] == "world_limit_reached"


def test_missing_tables_degrade_gracefully():
    app, _, inputs = make_app(backend=InMemoryBackend(fail=True))
    client = TestClient(app)
    for res in (
        client.post("/v1/sim/worlds", json={"league_id": "L1"}, headers=hdr()),
        client.get("/v1/sim/worlds", headers=hdr()),
        client.get("/v1/sim/worlds/00000000-0000-0000-0000-000000000000", headers=hdr()),
        client.post("/v1/sim/worlds/00000000-0000-0000-0000-000000000000/run", headers=hdr()),
        client.delete("/v1/sim/worlds/00000000-0000-0000-0000-000000000000", headers=hdr()),
    ):
        assert res.status_code == 200 and res.json()["reason"] == "sim_storage_unavailable"
    assert inputs.calls == []  # never fetched real data when there is nowhere to store it


def test_busy_simulator_sheds_load(monkeypatch):
    app, _, _ = make_app()
    client = TestClient(app)
    wid = create(client)["world"]["id"]
    monkeypatch.setattr(sim_api, "_COMPUTE_WAIT_SECONDS", 0.01)
    held = [sim_api._COMPUTE.acquire() for _ in range(sim_api.MAX_CONCURRENT_COMPUTE)]
    try:
        res = client.post(f"/v1/sim/worlds/{wid}/run", headers=hdr())
        assert res.status_code == 503 and res.headers["Retry-After"] == "5"
        assert res.json()["code"] == "server_busy"
    finally:
        for _ in held:
            sim_api._COMPUTE.release()


def test_store_snapshot_round_trip_and_failed_snapshot_write_rolls_back():
    backend = InMemoryBackend()
    store = SimStore(backend)
    world = store.create_world("u1", league_id="L1", snapshot=SNAP, strategy=Strategy(), seed=5)
    restored = store.get_snapshot("u1", world["id"])
    assert restored.to_dict() == SNAP.to_dict()

    class FailSnapshots(InMemoryBackend):
        def upsert(self, table, row, *, on_conflict):
            if table == "sim_snapshots":
                return False, "boom"
            return super().upsert(table, row, on_conflict=on_conflict)

    broken = FailSnapshots()
    with pytest.raises(Exception):
        SimStore(broken).create_world("u1", league_id="L1", snapshot=SNAP, strategy=Strategy(), seed=5)
    assert broken.tables["sim_worlds"] == []


def test_supabase_backend_only_touches_sim_tables_as_the_user(monkeypatch):
    from modules import account_store
    from modules.sim.backend import SupabaseSimBackend

    calls = []
    monkeypatch.setattr(account_store, "fetch_rows", lambda cfg, tok, table, **kw: calls.append(("select", table, tok, kw)) or ([], ""))
    monkeypatch.setattr(account_store, "upsert_row", lambda cfg, tok, table, row, **kw: calls.append(("upsert", table, tok, kw)) or (True, ""))
    monkeypatch.setattr(account_store, "delete_rows", lambda cfg, tok, table, **kw: calls.append(("delete", table, tok, kw)) or (True, ""))
    backend = SupabaseSimBackend({"url": "https://x.supabase.co", "anon_key": "k"}, "user-jwt")
    backend.select("sim_worlds", user_id="u1", filters={"id": "abc"}, columns="id", limit=3)
    backend.upsert("sim_results", {"world_id": "w", "user_id": "u1", "payload": {}}, on_conflict="world_id")
    backend.delete("sim_snapshots", user_id="u1", filters={"world_id": "w"})
    assert [c[:3] for c in calls] == [
        ("select", "sim_worlds", "user-jwt"), ("upsert", "sim_results", "user-jwt"), ("delete", "sim_snapshots", "user-jwt"),
    ]
    assert calls[0][3]["extra_query"] == "id=eq.abc&select=id&limit=3"
    assert calls[2][3]["query"] == "user_id=eq.u1&world_id=eq.w"
    for table in ("profiles", "saved_leagues", "gm_targets", "sim_worlds; drop table x"):
        with pytest.raises(ValueError):
            backend.select(table, user_id="u1")
        with pytest.raises(ValueError):
            backend.upsert(table, {}, on_conflict="id")
        with pytest.raises(ValueError):
            backend.delete(table, user_id="u1", filters={})
        with pytest.raises(ValueError):
            backend.update(table, user_id="u1", filters={}, values={})


def test_supabase_backend_update_uses_patch_with_user_jwt(monkeypatch):
    import requests

    from modules.sim.backend import SupabaseSimBackend

    seen = {}

    class Resp:
        status_code = 204

    def fake_patch(url, headers=None, json=None, timeout=None):
        seen.update(url=url, headers=headers, json=json)
        return Resp()

    monkeypatch.setattr(requests, "patch", fake_patch)
    backend = SupabaseSimBackend({"enabled": True, "url": "https://x.supabase.co", "anon_key": "sb_publishable_k"}, "user-jwt")
    ok, err = backend.update("sim_worlds", user_id="u1", filters={"id": "w"}, values={"status": "ready", "grade_letter": None})
    assert (ok, err) == (True, "")
    assert seen["url"].endswith("/rest/v1/sim_worlds?user_id=eq.u1&id=eq.w")
    assert seen["json"] == {"status": "ready", "grade_letter": None}
    assert "user-jwt" in str(seen["headers"])


def test_status_reports_unavailable_storage_for_pro_but_upsells_free():
    app, _, _ = make_app(backend=InMemoryBackend(fail=True))
    client = TestClient(app)
    body = client.get("/v1/sim/status", headers=hdr()).json()
    assert body["reason"] == "sim_storage_unavailable" and body["enabled"] is True
    free = client.get("/v1/sim/status", headers=hdr("u3")).json()
    assert free["reason"] == "premium_required"

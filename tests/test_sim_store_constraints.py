"""The sim game store against the REAL table constraints (docs/supabase_sim_game.sql).

The default in-memory backend has no schema, which is how a status the CHECK
constraint rejects ("offseason") passed every test while production answered
sim_storage_unavailable after every dynasty pick. ``StrictBackend`` enforces the
SQL's NOT NULL / CHECK / integer / jsonb rules; the failure-mode tests cover
batching, the single transient retry and idempotent conflicts."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient

from modules.sim import api as sim_api, game_api
from modules.sim import game_store as gs
from modules.sim.game_store import GameConflict, GameStore
from modules.sim.store import InMemoryBackend, SimStoreError, classify_store_error
from tests.test_sim_dynasty import H, PoolInputs

STATUSES = ("drafting", "in_season", "playoffs", "complete")
NOT_NULL = {
    "sim_games": ("id", "user_id", "seed", "engine_version", "status", "current_week", "event_count"),
    "sim_events": ("game_id", "user_id", "seq", "week", "actor", "type", "payload"),
    "sim_week_checkpoints": ("game_id", "user_id", "week", "event_seq", "state"),
}
INTS = {"sim_events": ("seq", "week"), "sim_week_checkpoints": ("week", "event_seq"), "sim_games": ("current_week", "event_count")}


def _check(table, row, *, partial=False):
    for col in NOT_NULL.get(table, ()):
        if col in row and row[col] is None:
            return f"pg=23502: null value in column {col}"
        if not partial and col not in row:
            return f"pg=23502: missing {col}"
    for col in INTS.get(table, ()):
        if col in row and (isinstance(row[col], bool) or not isinstance(row[col], int) or abs(row[col]) > 2**31 - 1):
            return f"pg=22P02: bad integer for {col}"
    if "status" in row and table == "sim_games" and row["status"] not in STATUSES:
        return "pg=23514: violates check constraint sim_games_status_check"
    try:
        json.dumps(dict(row), allow_nan=False)
    except ValueError:
        return "payload is not valid JSON"
    return ""


class StrictBackend(InMemoryBackend):
    def upsert(self, table, row, *, on_conflict):
        err = _check(table, row)
        return (False, f"Supabase upsert failed (400). {err}") if err else super().upsert(table, row, on_conflict=on_conflict)

    def update(self, table, *, user_id, filters, values):
        err = _check(table, values, partial=True)
        return (False, f"Supabase update failed (400). {err}") if err else super().update(table, user_id=user_id, filters=filters, values=values)

    def insert_many(self, table, rows):
        for row in rows:
            err = _check(table, row)
            if err:
                return False, f"Supabase insert failed (400). {err}"
        return super().insert_many(table, rows)


def client(backend):
    def require_user(authorization: str | None = Header(default=None)):
        return {"id": authorization or "pro", "_access_token": "t"}

    app = FastAPI()
    sim_api.mount(app, sim_api.SimApiDeps(require_user=require_user, is_pro=lambda u: True, sleeper_username=lambda u: "",
                                           backend_for=lambda u: backend, inputs=PoolInputs()), environ={"SIM_ENABLED": "1"})
    return TestClient(app)


@pytest.fixture(autouse=True)
def _pool(monkeypatch):
    monkeypatch.setattr(gs, "RETRY_DELAY", 0)
    game_api.clear_pool_cache()
    yield
    game_api.clear_pool_cache()


def test_dynasty_offseason_draft_pick_and_taxi_move_satisfy_the_real_schema():
    backend = StrictBackend()
    c = client(backend)
    gid = c.post("/v1/sim/games", json={"mode": "dynasty", "teams": 8, "seasons": 3, "rookie_rounds": 2, "user_slot": 3}, headers=H).json()["game"]["id"]
    assert c.post(f"/v1/sim/games/{gid}/draft/auto", headers=H).json()["completed"] is True
    while True:
        out = c.post(f"/v1/sim/games/{gid}/advance", headers=H).json()
        assert out["reason"] == "", out
        if out["game"]["status"] == "offseason":
            break
    started = c.post(f"/v1/sim/games/{gid}/offseason/rookie-draft/start", headers=H).json()
    assert started["reason"] == "", started
    draft = started["offseason"]["draft"]
    if draft["your_turn"]:
        picked = c.post(f"/v1/sim/games/{gid}/offseason/rookie-draft/pick", json={"player_id": draft["available"][0]["id"]}, headers=H).json()
        assert picked["reason"] == "", picked
    auto = c.post(f"/v1/sim/games/{gid}/offseason/rookie-draft/auto", headers=H).json()
    assert auto["reason"] == "", auto
    assert {g["status"] for g in backend.tables["sim_games"]} <= set(STATUSES)
    lineup = c.get(f"/v1/sim/games/{gid}/lineup", headers=H).json()
    bench = lineup["bench"][0]["id"] if lineup["bench"] else None
    if bench:
        moved = c.post(f"/v1/sim/games/{gid}/roster/move", json={"player_id": bench, "to": "taxi"}, headers=H).json()
        assert moved["reason"] != "sim_storage_unavailable", moved


def test_touch_maps_statuses_the_check_constraint_rejects():
    backend = StrictBackend()
    store = GameStore(backend)
    backend.upsert("sim_games", {"id": "g", "user_id": "u", "seed": 1, "engine_version": "x", "status": "drafting",
                                 "current_week": 0, "event_count": 0}, on_conflict="id")
    store.touch("u", "g", status="offseason", week=0, event_count=3)
    assert backend.tables["sim_games"][0]["status"] == "in_season"


class Flaky(InMemoryBackend):
    def __init__(self, failures):
        super().__init__()
        self.failures = list(failures)
        self.insert_calls = []

    def insert_many(self, table, rows):
        self.insert_calls.append(len(rows))
        if self.failures:
            return False, self.failures.pop(0)
        return super().insert_many(table, rows)


def events(start, n):
    return [{"seq": start + i, "week": 0, "actor": "ai", "type": "draft_pick", "payload": {"pick_no": start + i}} for i in range(n)]


def test_many_ai_picks_are_one_batched_request():
    b = Flaky([])
    GameStore(b).append_events("u", "g", events(0, 12))
    assert b.insert_calls == [12] and len(b.tables["sim_events"]) == 12


def test_transient_failure_retries_once_then_succeeds():
    b = Flaky(["Supabase insert failed (503)."])
    GameStore(b).append_events("u", "g", events(0, 5))
    assert b.insert_calls == [5, 5] and len(b.tables["sim_events"]) == 5


def test_persistent_failure_writes_nothing_and_carries_a_code():
    b = Flaky(["Supabase insert failed (503).", "Supabase insert failed (503)."])
    with pytest.raises(SimStoreError) as err:
        GameStore(b).append_events("u", "g", events(0, 5))
    assert err.value.code == "http_5xx" and b.tables.get("sim_events", []) == []


def test_constraint_failure_is_not_retried():
    b = Flaky(["Supabase insert failed (400). pg=23514: bad"])
    with pytest.raises(SimStoreError) as err:
        GameStore(b).append_events("u", "g", events(0, 2))
    assert err.value.code == "constraint" and b.insert_calls == [2]


def test_conflict_when_our_events_already_landed_is_success():
    store = GameStore(Flaky([]))
    store.append_events("u", "g", events(0, 3))
    store.append_events("u", "g", events(0, 3))  # double tap / retry after a timeout that committed


def test_conflict_with_different_events_raises():
    store = GameStore(Flaky([]))
    store.append_events("u", "g", events(0, 3))
    other = events(0, 3)
    other[1]["payload"] = {"pick_no": 99}
    with pytest.raises(GameConflict):
        store.append_events("u", "g", other)


def test_error_classification():
    assert classify_store_error("Supabase insert failed (400). pg=23514: x") == "constraint"
    assert classify_store_error("Supabase insert failed (403).") == "rls"
    assert classify_store_error("Supabase insert failed (413).") == "payload_too_large"
    assert classify_store_error("Could not reach Supabase table storage (timed out or network error).") == "timeout"
    assert classify_store_error("event log has a gap") == "log_inconsistent"

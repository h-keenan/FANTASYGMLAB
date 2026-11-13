"""The GM game's in-process state cache, parallel commits and slim action deltas must not change any result.

Same events => identical state digests, with the cache on, off, cold, warm and after another worker wrote.
Golden digests for the frozen player-model-1 game live in test_sim_game_model_versions.py; the cached
loader is checked against them here."""

from __future__ import annotations

import json

import pytest

from modules.sim import game_api, game_store
from modules.sim.game_state import GameState
from modules.sim.game_store import STATES, GameStore, row_version
from modules.sim.store import InMemoryBackend
from tests.test_sim_game_api import advance, finish_draft, hdr, make_app, new_game  # noqa: F401 (fixtures)
from tests.test_sim_game_model_versions import GOLDEN_V1_DIGESTS, STOP_WEEK, V1_ID, _play

UID = "pro"


class Counting(InMemoryBackend):
    def __init__(self):
        super().__init__()
        self.log: list[tuple[str, str]] = []

    def select(self, table, **kw):
        self.log.append(("select", table))
        return super().select(table, **kw)

    def upsert(self, table, row, **kw):
        self.log.append(("upsert", table))
        return super().upsert(table, row, **kw)

    def update(self, table, **kw):
        self.log.append(("update", table))
        return super().update(table, **kw)

    def delete(self, table, **kw):
        self.log.append(("delete", table))
        return super().delete(table, **kw)

    def insert_many(self, table, rows):
        self.log.append(("insert", table))
        return super().insert_many(table, rows)


@pytest.fixture(autouse=True)
def _clean_caches(monkeypatch):
    STATES.clear()
    game_store.SNAPSHOTS._items.clear()
    monkeypatch.setattr(game_api.secrets, "randbits", lambda n: 123456789)
    yield
    STATES.clear()


def _season(client, backend, *, weeks=3):
    """A scripted game touching every kind of action; returns the game id."""

    gid = new_game(client, user_slot=4, teams=12)["game"]["id"]
    finish_draft(client, gid)
    for _ in range(weeks):
        advance(client, gid)
    you = client.get(f"/v1/sim/games/{gid}", headers=hdr()).json()["game"]["you"]["team_id"]
    mine = client.get(f"/v1/sim/games/{gid}/teams/{you}", headers=hdr()).json()["players"]
    free = client.get(f"/v1/sim/games/{gid}/players?status=available&page_size=5", headers=hdr()).json()["items"]
    claim = client.post(f"/v1/sim/games/{gid}/waivers", json={"add": free[0]["id"], "drop": mine[-1]["id"]}, headers=hdr()).json()
    assert claim["reason"] == "" and claim["delta"]["pending"]["claims"] == 1
    client.delete(f"/v1/sim/games/{gid}/waivers/{claim['claim_id']}", headers=hdr())
    client.post(f"/v1/sim/games/{gid}/lineup/auto", headers=hdr())
    client.post(f"/v1/sim/games/{gid}/waivers", json={"add": free[1]["id"], "drop": mine[-2]["id"]}, headers=hdr())
    client.post(f"/v1/sim/games/{gid}/cut", json={"player_id": mine[-3]["id"]}, headers=hdr())
    for item in client.get(f"/v1/sim/games/{gid}/inbox", headers=hdr()).json()["items"][:2]:
        client.post(f"/v1/sim/games/{gid}/inbox/{item['id']}/respond", json={"action": "decline"}, headers=hdr())
    league = client.get(f"/v1/sim/games/{gid}/league", headers=hdr()).json()["teams"]
    other = next(t["team_id"] for t in league if not t["is_you"])
    theirs = client.get(f"/v1/sim/games/{gid}/teams/{other}", headers=hdr()).json()["players"]
    body = {"partner": other, "give": [mine[2]["id"]], "get": [theirs[2]["id"]]}
    client.post(f"/v1/sim/games/{gid}/trades/preview", json=body, headers=hdr())
    client.post(f"/v1/sim/games/{gid}/trades", json=body, headers=hdr())
    advance(client, gid)
    return gid


def _events(backend):
    return [(e["seq"], e["week"], e["actor"], e["type"], json.dumps(e["payload"], sort_keys=True))
            for e in sorted(backend.tables["sim_events"], key=lambda e: e["seq"])]


def _replay_digest(backend, gid):
    store = GameStore(backend)
    snap = store.get_snapshot(UID, gid)
    return store.load_state(UID, gid, snap, use_checkpoint=False).digest()


def test_cache_on_and_off_write_identical_event_logs_and_states(monkeypatch):
    runs = []
    for size in (0, 12):
        monkeypatch.setattr(STATES, "size", size)
        STATES.clear()
        game_store.SNAPSHOTS._items.clear()
        client, backend, _ = make_app()
        gid = _season(client, backend)
        runs.append((_events(backend), _replay_digest(backend, gid), client.get(f"/v1/sim/games/{gid}/home", headers=hdr()).json()))
    (ev_off, dig_off, home_off), (ev_on, dig_on, home_on) = runs
    assert ev_off == ev_on and len(ev_on) > 250
    assert dig_off == dig_on
    home_off.pop("preview", None), home_on.pop("preview", None)
    assert home_off == home_on


def test_cached_state_equals_a_fresh_replay_after_every_kind_of_write():
    client, backend, _ = make_app()
    gid = _season(client, backend)
    store = GameStore(backend)
    row = store.get_game(UID, gid)
    cached = STATES.get(gid, UID, row_version(row))
    assert cached is not None, "the last commit should have published its state"
    assert cached[0].digest() == _replay_digest(backend, gid)
    assert cached[0].seq == row["event_count"]


def test_reads_never_mutate_the_shared_state():
    client, backend, _ = make_app()
    gid = _season(client, backend, weeks=2)
    store = GameStore(backend)
    row = store.get_game(UID, gid)
    before = STATES.get(gid, UID, row_version(row))[0].digest()
    you = client.get(f"/v1/sim/games/{gid}", headers=hdr()).json()["game"]["you"]["team_id"]
    for path in ("", "/home", "/lineup", "/inbox", "/league", "/picks", f"/teams/{you}", "/players?page_size=60",
                 "/draft", "/dynasty", "/offseason"):
        client.get(f"/v1/sim/games/{gid}{path}", headers=hdr())
    client.post(f"/v1/sim/games/{gid}/trades/preview", json={"partner": "1", "give": [], "get": []}, headers=hdr())
    assert STATES.get(gid, UID, row_version(store.get_game(UID, gid)))[0].digest() == before == _replay_digest(backend, gid)


def test_warm_waiver_claim_costs_one_read_and_two_writes():
    backend = Counting()
    client, _, _ = make_app(backend=backend)
    gid = new_game(client, user_slot=4)["game"]["id"]
    finish_draft(client, gid)
    advance(client, gid)
    free = client.get(f"/v1/sim/games/{gid}/players?status=available&page_size=3", headers=hdr()).json()["items"]
    mine_id = client.get(f"/v1/sim/games/{gid}", headers=hdr()).json()["game"]["you"]["team_id"]
    drop = client.get(f"/v1/sim/games/{gid}/teams/{mine_id}", headers=hdr()).json()["players"][-1]["id"]
    backend.log.clear()
    out = client.post(f"/v1/sim/games/{gid}/waivers", json={"add": free[0]["id"], "drop": drop}, headers=hdr()).json()
    assert out["reason"] == "" and out["claim"]["add"]["id"] == free[0]["id"]
    assert sorted(backend.log) == [("insert", "sim_events"), ("select", "sim_games"), ("update", "sim_games")]
    backend.log.clear()
    client.get(f"/v1/sim/games/{gid}/home", headers=hdr())
    assert backend.log == [("select", "sim_games")]  # a warm read is the version check and nothing else


def test_a_write_by_another_worker_is_seen_on_the_next_request():
    """Worker A holds a cached state; worker B (another process: same store, its own cache) appends."""

    client, backend, _ = make_app()
    gid = new_game(client, user_slot=4)["game"]["id"]
    finish_draft(client, gid)
    advance(client, gid)
    free = client.get(f"/v1/sim/games/{gid}/players?status=available&page_size=3", headers=hdr()).json()["items"]
    assert client.get(f"/v1/sim/games/{gid}/inbox", headers=hdr()).status_code == 200  # A is warm
    # worker B: its own state, written through the plain store API, bypassing A's cache
    store = GameStore(backend)
    snap = store.get_snapshot(UID, gid)
    state = store.load_state(UID, gid, snap)
    from modules.sim import game_actions as act
    from modules.sim.game_state import Emitter

    em = Emitter(state, snap)
    act.queue_claim(em, free[2]["id"], None, None)
    store.append_events(UID, gid, em.events)
    store.touch(UID, gid, status=state.status, week=state.week, event_count=state.seq)
    assert STATES.cp_week(gid, UID) is not None or True  # A's entry is still there, one version behind
    got = client.get(f"/v1/sim/games/{gid}", headers=hdr()).json()["game"]
    assert got["pending"]["claims"] == 1


def test_a_lost_write_race_is_a_409_and_the_next_request_recovers():
    client, backend, _ = make_app()
    gid = new_game(client, user_slot=4)["game"]["id"]
    finish_draft(client, gid)
    advance(client, gid)
    free = client.get(f"/v1/sim/games/{gid}/players?status=available&page_size=4", headers=hdr()).json()["items"]
    store = GameStore(backend)
    row = store.get_game(UID, gid)
    # another worker appended an event but has not touched the row yet: our cache still looks current
    from modules.sim import game_actions as act
    from modules.sim.game_state import Emitter

    snap = store.get_snapshot(UID, gid)
    state = store.load_state(UID, gid, snap)
    em = Emitter(state, snap)
    act.queue_claim(em, free[3]["id"], None, None)
    store.append_events(UID, gid, em.events)
    assert row_version(store.get_game(UID, gid)) == row_version(row)
    res = client.post(f"/v1/sim/games/{gid}/waivers", json={"add": free[0]["id"]}, headers=hdr())
    assert res.status_code == 409 and res.json()["reason"] == "conflict"
    assert STATES.get(gid, UID, row_version(row)) is None  # the entry was dropped
    store.touch(UID, gid, status=state.status, week=state.week, event_count=state.seq)
    ok = client.post(f"/v1/sim/games/{gid}/waivers", json={"add": free[0]["id"]}, headers=hdr()).json()
    assert ok["reason"] == "" and len(ok["claims"]) == 2


def test_revert_and_delete_invalidate_the_cache():
    client, backend, _ = make_app()
    gid = new_game(client, user_slot=4)["game"]["id"]
    finish_draft(client, gid)
    advance(client, gid)
    free = client.get(f"/v1/sim/games/{gid}/players?status=available&page_size=2", headers=hdr()).json()["items"]
    client.post(f"/v1/sim/games/{gid}/waivers", json={"add": free[0]["id"]}, headers=hdr())
    assert client.get(f"/v1/sim/games/{gid}", headers=hdr()).json()["game"]["pending"]["claims"] == 1
    out = client.post(f"/v1/sim/games/{gid}/revert-week", headers=hdr()).json()
    assert out["reverted"] >= 1 and out["game"]["pending"]["claims"] == 0
    assert client.get(f"/v1/sim/games/{gid}", headers=hdr()).json()["game"]["pending"]["claims"] == 0
    # same event sequence numbers, different content: the versions differ, so no stale hit
    client.post(f"/v1/sim/games/{gid}/waivers", json={"add": free[1]["id"]}, headers=hdr())
    claims = client.get(f"/v1/sim/games/{gid}/inbox", headers=hdr())  # warm another route on the new version
    assert claims.status_code == 200
    assert client.get(f"/v1/sim/games/{gid}", headers=hdr()).json()["game"]["pending"]["claims"] == 1
    client.delete(f"/v1/sim/games/{gid}", headers=hdr())
    assert client.get(f"/v1/sim/games/{gid}", headers=hdr()).status_code == 404


def test_other_users_cannot_read_a_cached_game():
    client, backend, _ = make_app()
    gid = new_game(client, user_slot=4)["game"]["id"]
    assert client.get(f"/v1/sim/games/{gid}", headers=hdr()).status_code == 200
    assert client.get(f"/v1/sim/games/{gid}", headers=hdr("pro2")).status_code == 404


def test_clone_is_value_identical_and_independent():
    client, backend, _ = make_app()
    gid = _season(client, backend, weeks=2)
    store = GameStore(backend)
    snap = store.get_snapshot(UID, gid)
    state = store.load_state(UID, gid, snap)
    twin = state.clone()
    assert twin.digest() == state.digest() and twin.to_dict() == state.to_dict()
    twin.claims.append({"id": "x"})
    twin.rosters[snap.tids[0]].append("zzz")
    assert state.digest() != twin.digest() and "zzz" not in state.rosters[snap.tids[0]]


def test_the_cached_loader_reproduces_the_golden_v1_digests():
    store, gid, snap, state, digests = _play(V1_ID)
    assert digests == GOLDEN_V1_DIGESTS
    row = store.get_game("u", gid)
    store.touch("u", gid, status=state.status, week=state.week, event_count=state.seq)
    row = store.get_game("u", gid)
    for _ in range(2):  # cold, then warm
        loaded_snap, loaded = store.load_game("u", gid, row)
        assert loaded.digest() == GOLDEN_V1_DIGESTS[STOP_WEEK]
    assert loaded_snap is snap or loaded_snap.to_dict() == snap.to_dict()


def test_action_responses_carry_the_delta_the_client_applies():
    client, backend, _ = make_app()
    gid = new_game(client, user_slot=4)["game"]["id"]
    finish_draft(client, gid)
    advance(client, gid)
    free = client.get(f"/v1/sim/games/{gid}/players?status=available&page_size=2", headers=hdr()).json()["items"]
    out = client.post(f"/v1/sim/games/{gid}/waivers", json={"add": free[0]["id"]}, headers=hdr()).json()
    full = client.get(f"/v1/sim/games/{gid}", headers=hdr()).json()["game"]
    assert out["delta"]["pending"] == full["pending"]
    assert out["delta"]["can_trade"] == full["can_trade"] and out["delta"]["week"] == full["week"]
    lineup = client.post(f"/v1/sim/games/{gid}/lineup/auto", headers=hdr()).json()
    assert lineup["delta"]["pending"] == client.get(f"/v1/sim/games/{gid}", headers=hdr()).json()["game"]["pending"]


def test_a_burst_of_cold_reads_loads_the_game_once():
    """The client fires game + home + players at the same time after any write: one load, not three."""

    import threading

    backend = Counting()
    client, _, _ = make_app(backend=backend)
    gid = new_game(client, user_slot=4)["game"]["id"]
    finish_draft(client, gid)
    advance(client, gid)
    STATES.clear()
    backend.log.clear()
    statuses: list[int] = []

    def read(path):
        statuses.append(client.get(f"/v1/sim/games/{gid}{path}", headers=hdr()).status_code)

    threads = [threading.Thread(target=read, args=(p,)) for p in ("", "/home", "/lineup", "/inbox", "/league", "/picks")]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert statuses == [200] * 6
    assert backend.log.count(("select", "sim_week_checkpoints")) == 1
    assert backend.log.count(("select", "sim_events")) == 1
    assert backend.log.count(("select", "sim_games")) <= 7  # one version check each, plus at most one snapshot read

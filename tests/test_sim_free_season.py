"""Fantasy Sim: ONE free season per account, and the game cap enforced atomically.

Owner decision 2026-11-15: Free plays a full season (draft, every week, playoffs, final grade). More seasons,
dynasty and a start from the league's current week are Pro. The allowance is per account, not per game.
"""

from __future__ import annotations

import threading

import pytest

from modules.sim import game_store as gs
from modules.sim.game_store import GameLimitReached, GameStore
from modules.sim.store import InMemoryBackend
from tests.test_sim_game_api import advance, finish_draft, hdr, make_app, new_game


def test_free_user_plays_the_whole_season_including_playoffs():
    client, _, _ = make_app(pro=set())
    data = new_game(client, user="free")
    assert data["preview"]["free_season"] is True and data["preview"]["paywalled"] is False
    gid = data["game"]["id"]
    finish_draft(client, gid, "free")
    weeks = 0
    for _ in range(40):
        res = advance(client, gid, "free")
        if res["reason"] == "season_complete":
            break
        assert res["reason"] == "", res
        assert res["preview"]["paywalled"] is False  # never paused mid-season (old rule: week 4)
        weeks += 1
    assert weeks >= 14  # regular season plus playoff rounds
    game = client.get(f"/v1/sim/games/{gid}", headers=hdr("free")).json()
    assert game["game"]["status"] == "complete"
    assert client.get(f"/v1/sim/games/{gid}/result", headers=hdr("free")).json()["reason"] == ""


def test_dynasty_starts_need_pro_and_create_nothing():
    client, backend, _ = make_app(pro=set())
    for body in ({"mode": "dynasty", "seasons": 3, "rookie_rounds": 2}, {"mode": "dynasty"}):
        out = client.post("/v1/sim/games", json=body, headers=hdr("free")).json()
        assert out["reason"] == "premium_required" and out["upsell"]["title"]
    assert not backend.tables.get("sim_games")


def _dynasty_to_offseason(client, pro):
    gid = new_game(client, user="free", mode="dynasty", teams=8, seasons=3, rookie_rounds=2)["game"]["id"]
    finish_draft(client, gid, "free")
    for _ in range(40):
        res = advance(client, gid, "free")
        if res["game"]["status"] == "offseason":
            break
    pro.clear()  # the account lapsed to Free
    return gid


def test_a_dynasty_save_is_paused_at_the_offseason_for_free_and_pro_resumes():
    pro = {"free"}
    client, _, _ = make_app(pro=pro)
    gid = _dynasty_to_offseason(client, pro)
    assert client.get(f"/v1/sim/games/{gid}", headers=hdr("free")).json()["game"]["status"] == "offseason"
    out = client.post(f"/v1/sim/games/{gid}/advance", headers=hdr("free")).json()
    assert out["reason"] == "premium_required" and out["preview"]["paywalled"] is True
    pro.add("free")
    assert client.post(f"/v1/sim/games/{gid}/advance", headers=hdr("free")).json()["reason"] != "premium_required"


def test_undo_sim_and_trade_preview_are_gated_like_every_other_write():
    pro = {"free"}
    client, _, _ = make_app(pro=pro)
    gid = _dynasty_to_offseason(client, pro)
    undo = client.post(f"/v1/sim/games/{gid}/undo-sim", json={"from_seq": 1}, headers=hdr("free")).json()
    assert undo["reason"] == "premium_required"
    body = {"partner": "2", "give": ["a"], "get": ["b"]}
    assert client.post(f"/v1/sim/games/{gid}/trades/preview", json=body, headers=hdr("free")).json()["reason"] == "premium_required"


def test_trade_preview_still_works_inside_the_free_season():
    client, _, _ = make_app(pro=set())
    gid = new_game(client, user="free")["game"]["id"]
    finish_draft(client, gid, "free")
    advance(client, gid, "free")
    body = {"partner": "2", "give": ["a"], "get": ["b"]}
    out = client.post(f"/v1/sim/games/{gid}/trades/preview", json=body, headers=hdr("free"))
    assert "premium_required" not in out.text  # bogus ids may 4xx, but it is not paywalled


def test_deleting_the_game_does_not_restart_the_free_season():
    client, _, _ = make_app(pro=set())
    gid = new_game(client, user="free")["game"]["id"]
    assert client.get("/v1/sim/games/options", headers=hdr("free")).json()["free_season_used"] is True
    assert client.delete(f"/v1/sim/games/{gid}", headers=hdr("free")).json()["reason"] == ""
    again = client.post("/v1/sim/games", json={}, headers=hdr("free")).json()
    assert again["reason"] == "premium_required" and "free season" in again["upsell"]["title"].lower()
    assert client.get("/v1/sim/games", headers=hdr("free")).json()["games"] == []
    assert new_game(client, user="free2")["reason"] == ""  # another account has its own free season


def test_pro_is_not_limited_by_the_free_season_claim():
    client, backend, _ = make_app(pro=set())
    new_game(client, user="u1")
    assert backend.tables["sim_free_season_claims"][0]["user_id"] == "u1"
    client2, _, _ = make_app(pro={"p"})
    for _ in range(3):
        assert new_game(client2, user="p")["reason"] == ""
    assert not client2.get("/v1/sim/games/options", headers=hdr("p")).json()["free_season_used"]


# ----------------------------------------------------------- atomic cap


def _snapshot():
    client, _, _ = make_app()
    gid = new_game(client)["game"]["id"]
    return gs.SNAPSHOTS.get(gid)


def test_simultaneous_creates_cannot_both_fit_under_the_cap():
    snap = _snapshot()
    backend = InMemoryBackend()
    store = GameStore(backend)
    barrier = threading.Barrier(8)
    results = []
    seen = threading.local()
    real_select = backend.select

    def slow_select(*a, **k):
        # Every thread reads "0 games" before any inserts: the old count-then-insert race.
        out = real_select(*a, **k)
        if not getattr(seen, "done", False):
            seen.done = True
            try:
                barrier.wait(timeout=5)
            except threading.BrokenBarrierError:
                pass
        return out

    backend.select = slow_select

    def create():
        try:
            store.create_game("u", snapshot=snap, seed=1, max_games=1)
            results.append("ok")
        except GameLimitReached:
            results.append("limit")

    threads = [threading.Thread(target=create) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(15)
    backend.select = real_select
    assert results.count("ok") == 1 and results.count("limit") == 7, results
    assert len(backend.tables["sim_games"]) == 1


def test_pro_cap_of_three_holds_under_concurrency_and_slots_are_reused_after_delete():
    snap = _snapshot()
    backend = InMemoryBackend()
    store = GameStore(backend)
    outcomes = []

    def create():
        try:
            outcomes.append(store.create_game("u", snapshot=snap, seed=1, max_games=3)["id"])
        except GameLimitReached:
            outcomes.append(None)

    threads = [threading.Thread(target=create) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(15)
    made = [o for o in outcomes if o]
    assert len(made) == 3 and len(backend.tables["sim_games"]) == 3
    assert sorted(r["slot"] for r in backend.tables["sim_games"]) == [1, 2, 3]
    store.delete_game("u", made[0])
    assert store.create_game("u", snapshot=snap, seed=1, max_games=3)["id"]
    with pytest.raises(GameLimitReached):
        store.create_game("u", snapshot=snap, seed=1, max_games=3)


def test_missing_slot_column_falls_back_to_the_old_insert():
    snap = _snapshot()

    class NoSlotColumn(InMemoryBackend):
        def insert_many(self, table, rows):
            if table == "sim_games":
                return False, "Supabase insert failed (400). pg=PGRST204: Could not find the 'slot' column of 'sim_games'"
            return super().insert_many(table, rows)

    backend = NoSlotColumn()
    GameStore(backend).create_game("u", snapshot=snap, seed=1, max_games=1)
    assert len(backend.tables["sim_games"]) == 1


class _PreMigrationBackend(InMemoryBackend):
    """A database where docs/supabase_sim_game.sql has NOT been applied, with the error strings the real
    Supabase backend returns: selects that name ``slot`` fail, inserts with ``slot`` fail, and the
    ``sim_free_season_claims`` table does not exist."""

    def select(self, table, *, user_id, columns="*", **kwargs):
        if table == "sim_free_season_claims":
            return [], "Supabase tables are not set up yet. Run docs/supabase_accounts.sql in your Supabase SQL editor."
        if table == "sim_games" and "slot" in columns.split(","):
            return [], "column sim_games.slot does not exist"
        return super().select(table, user_id=user_id, columns=columns, **kwargs)

    def insert_many(self, table, rows):
        if table == "sim_free_season_claims":
            return False, "Supabase tables are not set up yet. Run docs/supabase_accounts.sql in your Supabase SQL editor."
        if table == "sim_games" and any("slot" in r for r in rows):
            return False, "Supabase insert failed (400). pg=PGRST204: Could not find the 'slot' column of 'sim_games'"
        return super().insert_many(table, rows)


def test_games_can_still_be_created_before_the_migration_is_applied():
    """Production regression 2026-11-16: every new game failed with store_error because the cap read
    ``id,slot`` and the free-season check read a table that did not exist yet."""

    backend = _PreMigrationBackend()
    store = GameStore(backend)
    assert store.free_season_claim("u") is None
    store.create_game("u", snapshot=_snapshot(), seed=1, max_games=1)
    assert store.claim_free_season("u", backend.tables["sim_games"][0]["id"]) is True
    assert len(backend.tables["sim_games"]) == 1
    with pytest.raises(GameLimitReached):  # the old count-then-insert cap still holds
        store.create_game("u", snapshot=_snapshot(), seed=2, max_games=1)


def test_real_outages_are_not_mistaken_for_a_missing_migration():
    class Down(InMemoryBackend):
        def select(self, table, **kwargs):
            return [], "Could not reach Supabase table storage."

    with pytest.raises(gs.SimStoreError):
        GameStore(Down()).free_season_claim("u")
    with pytest.raises(gs.SimStoreError):
        GameStore(Down()).create_game("u", snapshot=_snapshot(), seed=1, max_games=1)

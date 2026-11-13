"""The notification center is derived from the event log: replay-safe, capped, with a client-held read cursor."""

from __future__ import annotations

import pytest

from modules.sim import game_api, game_notifications as notif
from tests.test_sim_dynasty import H
from tests.test_sim_store_constraints import StrictBackend, client


@pytest.fixture(autouse=True)
def _fresh():
    game_api.clear_pool_cache()
    yield
    game_api.clear_pool_cache()


def _game(c):
    gid = c.post("/v1/sim/games", json={"mode": "dynasty", "teams": 8, "seasons": 3, "rookie_rounds": 2, "user_slot": 3}, headers=H).json()["game"]["id"]
    c.post(f"/v1/sim/games/{gid}/draft/auto", headers=H)
    return gid


def _get(c, gid, since=0):
    r = c.get(f"/v1/sim/games/{gid}/notifications", params={"since": since}, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def test_recap_and_offers_appear_newest_first_and_the_read_cursor_clears_unread():
    c = client(StrictBackend())
    gid = _game(c)
    c.post(f"/v1/sim/games/{gid}/advance", headers=H)
    c.post(f"/v1/sim/games/{gid}/advance", headers=H)
    body = _get(c, gid)
    kinds = [i["kind"] for i in body["items"]]
    assert "recap" in kinds
    assert [i["seq"] for i in body["items"]] == sorted((i["seq"] for i in body["items"]), reverse=True)
    assert len(body["items"]) <= notif.MAX_ITEMS
    recaps = [i for i in body["items"] if i["kind"] == "recap"]
    assert {i["headline"] for i in recaps} >= {"Week 1 recap is ready", "Week 2 recap is ready"}
    assert body["unread"] == len(body["items"])
    # marking all read = since the latest seq: nothing is unread, including the state-derived ones (stable synthetic seq)
    again = _get(c, gid, since=body["seq"])
    assert again["unread"] == 0
    assert [i["id"] for i in again["items"]] == [i["id"] for i in body["items"]]  # ids are stable (replay-safe)
    # a new week makes new items unread again
    c.post(f"/v1/sim/games/{gid}/advance", headers=H)
    after = _get(c, gid, since=body["seq"])
    assert after["unread"] >= 1
    assert any(i["headline"] == "Week 3 recap is ready" and i["seq"] > body["seq"] for i in after["items"])


def test_items_have_a_screen_to_open_and_a_week():
    c = client(StrictBackend())
    gid = _game(c)
    c.post(f"/v1/sim/games/{gid}/advance", headers=H)
    for item in _get(c, gid)["items"]:
        assert item["target"]["screen"] in ("trades", "team", "home", "players", "league", "draft")
        assert isinstance(item["week"], int) and item["icon"] and item["headline"]


def test_the_endpoint_is_replay_safe_the_same_log_gives_the_same_items():
    c = client(StrictBackend())
    gid = _game(c)
    c.post(f"/v1/sim/games/{gid}/advance", headers=H)
    a = _get(c, gid)
    b = _get(c, gid)
    assert a["items"] == b["items"] and a["seq"] == b["seq"]


def test_derivation_from_a_played_season_covers_offers_expiries_injuries_and_the_title():
    from tests.test_sim_dynasty import Run

    run = Run()
    run.play_season()
    snap, state = run.snap, run.state
    events = [{"seq": e["seq"], "week": e["week"], "actor": e["actor"], "type": e["type"], "payload": e["payload"]} for e in run.em.events]
    out = notif.derive(snap, state, events, since=0, limit=500)
    by_kind: dict[str, list[dict]] = {}
    for item in out["items"]:
        by_kind.setdefault(item["kind"], []).append(item)
    assert len(by_kind["recap"]) >= 14
    assert by_kind["offer"], "AI offers reach the user"
    # only proposals that actually reached the inbox, worded as what they offer for what they ask
    inbox_ids = {e["payload"]["id"] for e in events if e["type"] == "inbox_offer"}
    assert {i["target"]["offer_id"] for i in by_kind["offer"]} == inbox_ids
    assert all(" offers " in i["headline"] and " for " in i["headline"] for i in by_kind["offer"])
    assert by_kind.get("offer_expired"), "unanswered offers expire at a week boundary"
    for item in by_kind.get("injury", []):
        pid = item["target"]["player_id"]
        assert state.where(snap.user_team.tid, pid) is not None  # only your own players
    assert "title" in by_kind
    # the cap and the unread count
    capped = notif.derive(snap, state, events, since=0, limit=10)
    assert len(capped["items"]) == 10 and capped["unread"] == 10
    assert notif.derive(snap, state, events, since=out["seq"])["unread"] == 0

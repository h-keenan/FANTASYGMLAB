import hashlib
import os
import time
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from services import fantasy_content as content

TOKEN = "test-content-token-" + "a" * 48


def test_content_endpoint_uses_separate_read_only_credential(monkeypatch):
    app = FastAPI()
    monkeypatch.setattr(content, "build_feed", lambda *a: {"schema_version": 1, "rankings": {}, "waiver_watch": [], "news": []})
    app.include_router(content.content_router("not-read", lambda: None, lambda: []))
    client = TestClient(app)
    monkeypatch.delenv("FGL_CONTENT_TOKEN_SHA256", raising=False)
    assert client.get("/v1/content/feed").status_code == 503
    monkeypatch.setenv("FGL_CONTENT_TOKEN_SHA256", hashlib.sha256(TOKEN.encode()).hexdigest())
    assert client.get("/v1/content/feed", headers={"Authorization": "Bearer user-session"}).status_code == 401
    assert client.get("/v1/content/feed", headers={"Authorization": "Bearer " + TOKEN}).status_code == 200
    assert client.post("/v1/content/feed", headers={"Authorization": "Bearer " + TOKEN}).status_code == 405


def test_public_export_uses_entire_position_pool_and_never_account_data(tmp_path, monkeypatch):
    path = tmp_path / "players.db"
    path.touch()
    frame = pd.DataFrame([{"player_id": str(i + 1), "name": "Player " + str(i), "position": "QB", "team": "BUF", "dynasty_score": i + 1, "owner_id": "PRIVATE"} for i in range(30)])
    monkeypatch.setattr(content.rankings, "load_players", lambda *_: frame)
    monkeypatch.setattr(content, "roster_percentages", lambda *a: {})
    monkeypatch.setattr(content.player_eligibility, "filter_current_fantasy_players", lambda f, **kw: f)
    monkeypatch.setattr(content.sleeper, "trending_add_rank_map", lambda **kw: {"30": {"count": 100, "rank": 1}})
    feed = content.build_feed(str(path), lambda: [])
    assert len(feed["rankings"]["players"]) == 30
    assert feed["rankings"]["players"][0]["overall_rating"] is not None
    assert all("owner_id" not in p for p in feed["rankings"]["players"])
    assert feed["waiver_watch"][0]["rostered"] is None
    assert "100 adds" in feed["waiver_watch"][0]["reason"]
    os.utime(path, (time.time() - 90000, time.time() - 90000))
    with pytest.raises(Exception) as held:
        content.build_feed(str(path), lambda: [])
    assert held.value.status_code == 503


def _value_history_frame(player_id, dynasty_score, market_score):
    return pd.DataFrame([{
        "player_id": player_id, "name": "Player One", "position": "RB", "team": "BUF",
        "dynasty_score": dynasty_score, "market_score": market_score, "age_curve_score": 400.0,
        "role_score": 100.0, "scarcity_score": 50.0, "opportunity_score": 300.0,
        "production_score": 200.0, "owner_id": "PRIVATE",
    }])


def test_value_changes_field_reports_delta_and_reason_only_after_a_real_refresh(tmp_path, monkeypatch):
    path = tmp_path / "players.db"
    path.write_bytes(b"v1")
    monkeypatch.setattr(content, "roster_percentages", lambda *a: {})
    monkeypatch.setattr(content.player_eligibility, "filter_current_fantasy_players", lambda f, **kw: f)
    monkeypatch.setattr(content.sleeper, "trending_add_rank_map", lambda **kw: {})

    monkeypatch.setattr(content.rankings, "load_players", lambda *_: _value_history_frame("1", 500, 500.0))
    first = content.build_feed(str(path), lambda: [])
    assert first["value_changes"] == []  # no prior snapshot to diff against yet

    # Re-reading the same, unrefreshed source must not erase the baseline or
    # fabricate a diff against itself.
    second = content.build_feed(str(path), lambda: [])
    assert second["value_changes"] == []

    # A real refresh: the source file changes (new size + mtime) and the
    # player's market score — and therefore overall score — rises.
    path.write_bytes(b"v2-longer-content")
    os.utime(path, (time.time() + 10, time.time() + 10))
    # market_score rises by 400 (500 -> 900); at the real COMPOSITE_WEIGHT_MARKET
    # (0.44) that is a +176 contribution, so dynasty_score is set to match
    # (500 + 176 = 676) and leave no unexplained residual for "risk" to win.
    monkeypatch.setattr(content.rankings, "load_players", lambda *_: _value_history_frame("1", 676, 900.0))
    third = content.build_feed(str(path), lambda: [])
    assert len(third["value_changes"]) == 1
    change = third["value_changes"][0]
    assert change["player_id"] == "1"
    assert change["previous_score"] == 500
    assert change["current_score"] == 676
    assert change["delta"] == 176
    assert change["driver_factor"] == "market_score"
    assert "Market value increased" in change["reason"]
    assert change["name"] == "Player One" and change["team"] == "BUF" and change["position"] == "RB"

    # Re-reading again before the next refresh returns the same cached diff.
    fourth = content.build_feed(str(path), lambda: [])
    assert fourth["value_changes"] == third["value_changes"]


def test_trending_adds_week_field_is_distinct_from_24h_waiver_watch(tmp_path, monkeypatch):
    path = tmp_path / "players.db"
    path.touch()
    frame = pd.DataFrame([{"player_id": str(i + 1), "name": "Player " + str(i), "position": "WR",
                           "team": "BUF", "dynasty_score": 100 - i} for i in range(5)])
    monkeypatch.setattr(content.rankings, "load_players", lambda *_: frame)
    monkeypatch.setattr(content, "roster_percentages", lambda *a: {})
    monkeypatch.setattr(content.player_eligibility, "filter_current_fantasy_players", lambda f, **kw: f)

    calls = []

    def fake_trending(**kwargs):
        calls.append(kwargs.get("lookback_hours"))
        return {"3": {"count": 77, "rank": 1}}

    monkeypatch.setattr(content.sleeper, "trending_add_rank_map", fake_trending)
    feed = content.build_feed(str(path), lambda: [])
    assert feed["trending_adds_week"] == [{"player_id": "3", "name": "Player 2", "team": "BUF",
                                           "position": "WR", "add_count": 77, "rank": 1, "lookback_hours": 168}]
    # Both the 24h waiver-watch lookup and the new weekly lookup happened,
    # with distinct lookback windows — this never adds an uncached hot path.
    assert 24 in calls and 24 * 7 in calls

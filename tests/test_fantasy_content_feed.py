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

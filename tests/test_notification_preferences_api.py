"""GET/POST /v1/notifications/preferences and POST /v1/notifications/opened."""

from __future__ import annotations

from unittest.mock import Mock, patch

from tests.test_mobile_api_service import _client

AUTH = {"Authorization": "Bearer good-token"}


def _auth():
    return Mock(status_code=200, json=lambda: {"id": "user-123", "email": "gm@example.com"})


def _settings(settings):
    return Mock(status_code=200, json=lambda: [{"user_id": "user-123", "settings": settings}])


def test_get_returns_defaults_and_catalog(monkeypatch):
    client = _client(monkeypatch)
    with patch("requests.get", side_effect=[_auth(), Mock(status_code=200, json=lambda: [])]):
        body = client.get("/v1/notifications/preferences", headers=AUTH).json()
    assert body["ok"] is True
    assert body["prefs"]["quiet_start"] == 22 and body["prefs"]["quiet_end"] == 8
    assert body["prefs"]["league_overrides"] == {} and body["prefs"]["weekly_cap"] is None
    assert body["default_weekly_cap"] >= 1
    assert [p["key"] for p in body["cap_presets"]] == ["light", "standard", "frequent"]
    assert "injury" in body["critical_categories"]
    assert body["categories"]["injury"] is True


def test_post_merges_prefs_and_categories_without_clobbering(monkeypatch):
    client = _client(monkeypatch)
    existing = {
        "push_categories": {"watch": False},
        "notification_prefs": {"league_overrides": {"L1": "mute"}, "weekly_cap": 2},
        "ui_density": "compact",
    }
    with patch("requests.get", side_effect=[_auth(), _settings(existing)]):
        with patch("requests.post", return_value=Mock(status_code=200)) as post:
            response = client.post(
                "/v1/notifications/preferences",
                json={
                    "prefs": {"quiet_start": 23, "quiet_end": 6, "league_overrides": {"L2": "critical", "L1": "all"}},
                    "categories": {"injury": False},
                },
                headers=AUTH,
            )
    assert response.status_code == 200 and response.json()["ok"] is True
    saved = post.call_args.kwargs["json"]["settings"]
    assert saved["ui_density"] == "compact"  # unrelated settings preserved
    assert saved["push_categories"]["watch"] is False and saved["push_categories"]["injury"] is False
    assert saved["notification_prefs"]["league_overrides"] == {"L2": "critical"}
    assert saved["notification_prefs"]["weekly_cap"] == 2
    assert (saved["notification_prefs"]["quiet_start"], saved["notification_prefs"]["quiet_end"]) == (23, 6)


def test_post_rejects_invalid_values(monkeypatch):
    client = _client(monkeypatch)
    bad_bodies = [
        {"prefs": {"quiet_start": 30}},
        {"prefs": {"weekly_cap": 100}},
        {"prefs": {"league_overrides": {"L1": "loud"}}},
        {"prefs": {"category_modes": {"injury": "digest"}}},
        {"categories": {"nope": True}},
    ]
    for body in bad_bodies:
        with patch("requests.get", return_value=_auth()):
            response = client.post("/v1/notifications/preferences", json=body, headers=AUTH)
        assert response.status_code == 422, body


def test_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/v1/notifications/preferences").status_code == 401
    assert client.post("/v1/notifications/preferences", json={}).status_code == 401
    assert client.post("/v1/notifications/opened", json={"notification_id": "x"}).status_code == 401


def test_opened_is_always_ok_even_without_the_table(monkeypatch):
    client = _client(monkeypatch)
    with patch("requests.get", return_value=_auth()):
        with patch("modules.notification_events.mark_opened", return_value=False) as mark:
            response = client.post(
                "/v1/notifications/opened", json={"notification_id": "123e4567-e89b-12d3-a456-426614174000"}, headers=AUTH
            )
    assert response.json() == {"ok": True}
    assert mark.call_args.kwargs["user_id"] == "user-123"

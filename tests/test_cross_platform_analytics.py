"""feature_use / platform split across the ingest endpoint and founder report."""

from __future__ import annotations

import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from modules import founder_analytics
from modules import launch_analytics as la


def _client(monkeypatch):
    from services import mobile_api_service

    return TestClient(mobile_api_service.app)


def test_analytics_event_accepts_feature_use_and_defaults_platform_to_web(monkeypatch):
    client = _client(monkeypatch)
    from services import mobile_api_service

    with patch.object(mobile_api_service.launch_analytics, "track_event") as mock_track:
        response = client.post(
            "/v1/analytics/event",
            json={"event": "feature_use", "anon_id": "anon_abc123", "props": {"feature": "x", "action": "opened"}},
        )
        client.post(
            "/v1/analytics/event",
            json={"event": "feature_use", "anon_id": "anon_abc123", "props": {"platform": "ios", "feature": "x"}},
        )
        client.post(
            "/v1/analytics/event",
            json={"event": "feature_use", "anon_id": "anon_abc123", "props": {"platform": "evil"}},
        )

    assert response.json() == {"ok": True}
    platforms = [c.kwargs["props"]["platform"] for c in mock_track.call_args_list]
    assert platforms == ["web", "ios", "web"]


def test_analytics_event_page_view_passes_platform(monkeypatch):
    client = _client(monkeypatch)
    from services import mobile_api_service

    with patch.object(mobile_api_service.launch_analytics, "track_page_view") as mock_pv:
        client.post(
            "/v1/analytics/event",
            json={
                "event": "page_view",
                "anon_id": "anon_abc123",
                "props": {"route": "mobile/Home", "platform": "android"},
            },
        )
    # account_kind is derived server-side (no bearer token here -> "visitor"), never read from client props.
    assert mock_pv.call_args.kwargs["extra"] == {"platform": "android", "account_kind": "visitor"}


def test_report_splits_platforms_and_feature_use(tmp_path):
    path = tmp_path / "e.jsonl"
    rows = [
        {"event": "feature_use", "ts": 1, "props": {"feature": "player_exposure", "action": "viewed", "tier": "pro"}},
        {
            "event": "feature_use",
            "ts": 2,
            "props": {"feature": "player_exposure", "action": "viewed", "tier": "free", "platform": "ios"},
        },
        {"event": "pqv_opened", "ts": 3, "props": {"platform": "android"}},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    report = founder_analytics.build_report(window_key="all", path=path, writes_enabled=True)
    assert report["platforms"] == {"android": 1, "ios": 1, "web": 1}
    (row,) = report["feature_use"]
    assert (row["feature"], row["action"], row["total"]) == ("player_exposure", "viewed", 2)
    assert (row["web"], row["ios"], row["pro"], row["free"]) == (1, 1, 1, 1)


def test_feature_use_event_is_tracked_and_keeps_allowlisted_props_only(tmp_path, monkeypatch):
    path = tmp_path / "e.jsonl"
    monkeypatch.setattr(la, "ENABLED", True)
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(path))
    assert la.track_event(
        "feature_use",
        props={"feature": "f", "action": "a", "platform": "ios", "email": "a@b.com", "player_name": "X"},
        state={},
    )
    blob = path.read_text(encoding="utf-8")
    assert "a@b.com" not in blob and "player_name" not in blob
    assert '"platform":"ios"' in blob


def test_ingest_derives_account_kind_server_side_and_ignores_client_value(monkeypatch):
    client = _client(monkeypatch)
    from services import mobile_api_service

    app = mobile_api_service.app
    guest = {"id": "u-guest", "is_anonymous": True}
    app.dependency_overrides[mobile_api_service.optional_user] = lambda: guest
    try:
        with patch.object(mobile_api_service.launch_analytics, "track_event") as mock_track, patch.object(
            mobile_api_service.account_acquisition, "record_account_acquisition"
        ) as mock_acq:
            client.post(
                "/v1/analytics/event",
                json={"event": "feature_use", "anon_id": "anon_abc123", "props": {"feature": "x", "account_kind": "registered"}},
            )
    finally:
        app.dependency_overrides.pop(mobile_api_service.optional_user, None)
    assert mock_track.call_args.kwargs["props"]["account_kind"] == "guest"
    assert mock_acq.call_args.args[0] == guest


def test_ingest_accepts_android_okhttp_user_agent_but_still_drops_it_for_web(monkeypatch):
    client = _client(monkeypatch)
    from services import mobile_api_service

    headers = {"user-agent": "okhttp/4.12.0"}
    with patch.object(mobile_api_service.launch_analytics, "track_event") as mock_track:
        ok = client.post(
            "/v1/analytics/event",
            headers=headers,
            json={"event": "feature_use", "anon_id": "anon_abc123", "props": {"platform": "android", "feature": "x"}},
        )
        dropped = client.post(
            "/v1/analytics/event",
            headers=headers,
            json={"event": "feature_use", "anon_id": "anon_abc123", "props": {"feature": "x"}},
        )
    assert ok.json() == {"ok": True}
    assert dropped.json() == {"ok": False}
    assert mock_track.call_count == 1

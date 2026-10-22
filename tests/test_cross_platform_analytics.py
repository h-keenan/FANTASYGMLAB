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
    assert mock_pv.call_args.kwargs["extra"] == {"platform": "android"}


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

"""Durable Supabase storage migration for launch analytics.

Covers the write-through (modules.launch_analytics.track_event -> Supabase,
best-effort, never blocking / never raising) and the read-through
(modules.launch_analytics.read_events_with_source /
modules.founder_analytics.build_report -> Supabase-first, local JSONL
fallback). Mocks `requests` — never a real network call — matching the
convention already used for modules/push_triggers.py's own Supabase tests.
"""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pytest

from modules import founder_analytics
from modules import launch_analytics as la


def _config() -> la.AnalyticsSupabaseConfig:
    return la.AnalyticsSupabaseConfig(url="https://example.supabase.co", service_role_key="service-role-key")


def _run_inline(monkeypatch) -> None:
    """Make the fire-and-forget write-through run synchronously for tests."""
    monkeypatch.setattr(la, "_spawn_background", lambda fn: fn())


# --- config -----------------------------------------------------------------


def test_load_analytics_supabase_config_reads_expected_env_vars():
    config = la.load_analytics_supabase_config(
        environ={"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    )
    assert config.configured
    assert config.url == "https://x.supabase.co"
    assert config.service_role_key == "srk"


def test_load_analytics_supabase_config_not_configured_without_service_role_key():
    config = la.load_analytics_supabase_config(environ={"SUPABASE_URL": "https://x.supabase.co"})
    assert not config.configured


def test_analytics_supabase_config_not_configured_when_empty():
    assert not la.AnalyticsSupabaseConfig().configured


# --- row mapping --------------------------------------------------------------


def test_supabase_row_from_payload_maps_fields_and_derives_occurred_at():
    payload = {
        "event": "pqv_opened",
        "event_version": 2,
        "ts": 1_700_000_000.0,
        "build": "abc123",
        "environment": "production",
        "session_key": "anon_a",
        "anon_id": "anon_a",
        "user_key": "acct_1",
        "account_hash": "acct_1",
        "props": {"route": "pqv"},
    }
    row = la._supabase_row_from_payload(payload)
    assert row["event"] == "pqv_opened"
    assert row["ts"] == 1_700_000_000.0
    assert row["props"] == {"route": "pqv"}
    assert row["user_key"] == "acct_1"
    assert row["occurred_at"].startswith("2023-")


def test_supabase_row_from_payload_tolerates_bad_ts():
    row = la._supabase_row_from_payload({"event": "pqv_opened", "ts": "not-a-number"})
    assert "occurred_at" not in row


# --- write-through ------------------------------------------------------------


def test_write_event_supabase_posts_row_and_returns_true_on_success():
    response = Mock(status_code=200)
    with patch("requests.post", return_value=response) as mock_post:
        ok = la._write_event_supabase(_config(), {"event": "pqv_opened", "ts": 1.0})
    assert ok is True
    args, kwargs = mock_post.call_args
    assert args[0] == "https://example.supabase.co/rest/v1/analytics_events"
    assert kwargs["headers"]["apikey"] == "service-role-key"
    assert kwargs["headers"]["Authorization"] == "Bearer service-role-key"
    assert kwargs["json"] == {"event": "pqv_opened", "ts": 1.0}


def test_write_event_supabase_returns_false_on_http_error():
    response = Mock(status_code=500)
    with patch("requests.post", return_value=response):
        ok = la._write_event_supabase(_config(), {"event": "pqv_opened"})
    assert ok is False


def test_write_event_supabase_returns_false_on_exception_never_raises():
    with patch("requests.post", side_effect=Exception("network down")):
        ok = la._write_event_supabase(_config(), {"event": "pqv_opened"})
    assert ok is False


def test_write_event_supabase_returns_false_when_not_configured():
    with patch("requests.post") as mock_post:
        ok = la._write_event_supabase(la.AnalyticsSupabaseConfig(), {"event": "pqv_opened"})
    assert ok is False
    mock_post.assert_not_called()


def test_track_event_writes_local_jsonl_and_queues_supabase_write(tmp_path, monkeypatch):
    path = tmp_path / "analytics.jsonl"
    monkeypatch.setattr(la, "ENABLED", True)
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(path))
    monkeypatch.setattr(la, "load_analytics_supabase_config", lambda: _config())
    _run_inline(monkeypatch)
    la.clear_emitted()

    response = Mock(status_code=200)
    with patch("requests.post", return_value=response) as mock_post:
        ok = la.track_event("pqv_opened", props={}, state={})

    assert ok is True
    assert path.is_file()
    line = json.loads(path.read_text(encoding="utf-8").strip())
    assert line["event"] == "pqv_opened"

    mock_post.assert_called_once()
    _args, kwargs = mock_post.call_args
    assert kwargs["json"]["event"] == "pqv_opened"


def test_track_event_never_raises_when_supabase_write_fails(tmp_path, monkeypatch):
    path = tmp_path / "analytics.jsonl"
    monkeypatch.setattr(la, "ENABLED", True)
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(path))
    monkeypatch.setattr(la, "load_analytics_supabase_config", lambda: _config())
    _run_inline(monkeypatch)
    la.clear_emitted()

    with patch("requests.post", side_effect=Exception("network down")):
        ok = la.track_event("pqv_opened", props={}, state={})

    # Local write still succeeded; Supabase outage never surfaces here.
    assert ok is True
    assert path.is_file()


def test_track_event_skips_supabase_entirely_when_not_configured(tmp_path, monkeypatch):
    path = tmp_path / "analytics.jsonl"
    monkeypatch.setattr(la, "ENABLED", True)
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(path))
    monkeypatch.setattr(la, "load_analytics_supabase_config", lambda: la.AnalyticsSupabaseConfig())
    _run_inline(monkeypatch)
    la.clear_emitted()

    with patch("requests.post") as mock_post:
        ok = la.track_event("pqv_opened", props={}, state={})

    assert ok is True
    mock_post.assert_not_called()


def test_track_event_never_raises_when_config_loader_itself_fails(tmp_path, monkeypatch):
    path = tmp_path / "analytics.jsonl"
    monkeypatch.setattr(la, "ENABLED", True)
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(path))

    def _boom():
        raise RuntimeError("secrets backend unavailable")

    monkeypatch.setattr(la, "load_analytics_supabase_config", _boom)
    la.clear_emitted()

    ok = la.track_event("pqv_opened", props={}, state={})
    assert ok is True
    assert path.is_file()


# --- read-through --------------------------------------------------------------


def test_fetch_events_supabase_returns_rows_and_ok_true():
    response = Mock(status_code=200)
    response.json.return_value = [
        {"event": "pqv_opened", "ts": 10.0, "anon_id": "anon_a", "session_key": "anon_a", "props": {}},
    ]
    with patch("requests.get", return_value=response) as mock_get:
        rows, ok = la._fetch_events_supabase(_config(), since_ts=5.0)
    assert ok is True
    assert rows[0]["event"] == "pqv_opened"
    _args, kwargs = mock_get.call_args
    assert kwargs["params"]["ts"] == "gte.5.0"


def test_fetch_events_supabase_fails_open_on_http_error():
    response = Mock(status_code=503)
    with patch("requests.get", return_value=response):
        rows, ok = la._fetch_events_supabase(_config())
    assert rows == []
    assert ok is False


def test_fetch_events_supabase_fails_open_on_exception():
    with patch("requests.get", side_effect=Exception("network down")):
        rows, ok = la._fetch_events_supabase(_config())
    assert rows == []
    assert ok is False


def test_fetch_events_supabase_not_configured_returns_ok_false():
    rows, ok = la._fetch_events_supabase(la.AnalyticsSupabaseConfig())
    assert rows == []
    assert ok is False


def test_read_events_with_source_uses_supabase_when_configured(monkeypatch):
    monkeypatch.setattr(la, "load_analytics_supabase_config", lambda: _config())
    fake_rows = [{"event": "pqv_opened", "ts": 10.0}]
    with patch("requests.get") as mock_get:
        response = Mock(status_code=200)
        response.json.return_value = fake_rows
        mock_get.return_value = response
        rows, source = la.read_events_with_source(path=None, since_ts=5.0)
    assert source == "supabase"
    assert rows == fake_rows


def test_read_events_with_source_falls_back_to_local_jsonl_on_supabase_failure(tmp_path, monkeypatch):
    path = tmp_path / "analytics.jsonl"
    path.write_text(json.dumps({"event": "pqv_opened", "ts": 10.0}) + "\n", encoding="utf-8")
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(path))
    monkeypatch.setattr(la, "load_analytics_supabase_config", lambda: _config())
    with patch("requests.get", side_effect=Exception("network down")):
        rows, source = la.read_events_with_source(path=None)
    assert source == "local_jsonl"
    assert rows[0]["event"] == "pqv_opened"


def test_read_events_with_source_skips_supabase_when_path_explicit(tmp_path, monkeypatch):
    path = tmp_path / "analytics.jsonl"
    path.write_text(json.dumps({"event": "pqv_opened", "ts": 10.0}) + "\n", encoding="utf-8")
    monkeypatch.setattr(la, "load_analytics_supabase_config", lambda: _config())
    with patch("requests.get") as mock_get:
        rows, source = la.read_events_with_source(path=path)
    mock_get.assert_not_called()
    assert source == "local_jsonl"
    assert rows[0]["event"] == "pqv_opened"


def test_read_events_with_source_local_jsonl_when_supabase_unconfigured(tmp_path, monkeypatch):
    path = tmp_path / "analytics.jsonl"
    path.write_text(json.dumps({"event": "pqv_opened", "ts": 10.0}) + "\n", encoding="utf-8")
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(path))
    monkeypatch.setattr(la, "load_analytics_supabase_config", lambda: la.AnalyticsSupabaseConfig())
    rows, source = la.read_events_with_source(path=None)
    assert source == "local_jsonl"
    assert rows[0]["event"] == "pqv_opened"


# --- founder_analytics.build_report ---------------------------------------------


def test_build_report_uses_supabase_rows_and_labels_storage(monkeypatch):
    now = 1_700_000_000.0
    supabase_rows = [
        {"event": "pqv_opened", "ts": now - 10, "anon_id": "anon_a", "session_key": "anon_a", "props": {}},
        {"event": "checkout_started", "ts": now - 5, "anon_id": "anon_a", "session_key": "anon_a", "props": {"interval": "monthly"}},
    ]
    monkeypatch.setattr(la, "load_analytics_supabase_config", lambda: _config())
    response = Mock(status_code=200)
    response.json.return_value = supabase_rows
    with patch("requests.get", return_value=response):
        report = founder_analytics.build_report(window_key="all", now=now, writes_enabled=True)

    assert report["event_count"] == 2
    assert report["storage"]["kind"] == "supabase"
    assert "all app instances" in report["storage"]["scope_label"].casefold()
    assert report["checkout_intervals"]["monthly"] == 1


def test_build_report_falls_back_to_local_jsonl_when_supabase_unreachable(tmp_path, monkeypatch):
    path = tmp_path / "e.jsonl"
    now = 1_700_000_000.0
    rows = [
        {"event": "pqv_opened", "ts": now - 10, "anon_id": "anon_a", "session_key": "anon_a", "props": {}},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(path))
    monkeypatch.setattr(la, "load_analytics_supabase_config", lambda: _config())
    with patch("requests.get", side_effect=Exception("network down")):
        report = founder_analytics.build_report(window_key="all", now=now, writes_enabled=True)

    assert report["event_count"] == 1
    assert report["storage"]["kind"] == "host_local_jsonl"


def test_build_report_with_explicit_path_never_contacts_supabase(tmp_path, monkeypatch):
    path = tmp_path / "e.jsonl"
    now = 1_700_000_000.0
    path.write_text(
        json.dumps({"event": "pqv_opened", "ts": now - 10, "anon_id": "anon_a"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(la, "load_analytics_supabase_config", lambda: _config())
    with patch("requests.get") as mock_get:
        report = founder_analytics.build_report(window_key="all", path=path, now=now, writes_enabled=True)
    mock_get.assert_not_called()
    assert report["storage"]["kind"] == "host_local_jsonl"
    assert report["event_count"] == 1

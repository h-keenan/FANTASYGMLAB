"""modules.sleeper._request_json: retry-with-backoff for transient failures.

Before this fix, a single Sleeper timeout/5xx/network blip meant every
caller (get_league, get_rosters, ...) immediately failed for that request,
even though every caller already wraps _request_json in try/except and
degrades gracefully — a retry inside _request_json itself is a strict
improvement with no contract change: None on failure, same as before. Only
genuine 4xx client errors should still fail fast without retrying.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import requests

from modules import sleeper


def _ok_response(payload):
    response = Mock()
    response.status_code = 200
    response.json.return_value = payload
    return response


def _status_response(status_code):
    response = Mock()
    response.status_code = status_code
    response.json.return_value = {}
    return response


def test_transient_timeout_then_success_retries_and_returns_data(monkeypatch):
    monkeypatch.setattr(sleeper.time, "sleep", lambda _seconds: None)
    with patch(
        "modules.sleeper.requests.get",
        side_effect=[requests.Timeout("boom"), _ok_response({"league_id": "L1"})],
    ) as mock_get:
        result = sleeper._request_json("sleeper_league", "https://example.test/league/L1")
    assert result == {"league_id": "L1"}
    assert mock_get.call_count == 2


def test_transient_5xx_then_success_retries_and_returns_data(monkeypatch):
    monkeypatch.setattr(sleeper.time, "sleep", lambda _seconds: None)
    with patch(
        "modules.sleeper.requests.get",
        side_effect=[_status_response(503), _ok_response({"ok": True})],
    ) as mock_get:
        result = sleeper._request_json("sleeper_league", "https://example.test/league/L1")
    assert result == {"ok": True}
    assert mock_get.call_count == 2


def test_persistent_timeout_exhausts_retries_and_returns_none(monkeypatch):
    monkeypatch.setattr(sleeper.time, "sleep", lambda _seconds: None)
    with patch(
        "modules.sleeper.requests.get",
        side_effect=requests.Timeout("boom"),
    ) as mock_get:
        result = sleeper._request_json(
            "sleeper_league", "https://example.test/league/L1", max_retries=2
        )
    assert result is None
    # Initial attempt + 2 retries = 3 total calls.
    assert mock_get.call_count == 3


def test_persistent_network_error_exhausts_retries_and_returns_none(monkeypatch):
    monkeypatch.setattr(sleeper.time, "sleep", lambda _seconds: None)
    with patch(
        "modules.sleeper.requests.get",
        side_effect=requests.ConnectionError("boom"),
    ) as mock_get:
        result = sleeper._request_json(
            "sleeper_league", "https://example.test/league/L1", max_retries=2
        )
    assert result is None
    assert mock_get.call_count == 3


def test_persistent_5xx_exhausts_retries_and_returns_none(monkeypatch):
    monkeypatch.setattr(sleeper.time, "sleep", lambda _seconds: None)
    with patch(
        "modules.sleeper.requests.get",
        return_value=_status_response(500),
    ) as mock_get:
        result = sleeper._request_json(
            "sleeper_league", "https://example.test/league/L1", max_retries=2
        )
    assert result is None
    assert mock_get.call_count == 3


def test_genuine_4xx_fails_fast_without_retrying(monkeypatch):
    monkeypatch.setattr(sleeper.time, "sleep", lambda _seconds: None)
    with patch(
        "modules.sleeper.requests.get",
        return_value=_status_response(404),
    ) as mock_get:
        result = sleeper._request_json(
            "sleeper_league", "https://example.test/league/L1", max_retries=2
        )
    assert result is None
    assert mock_get.call_count == 1


def test_genuine_400_fails_fast_without_retrying(monkeypatch):
    monkeypatch.setattr(sleeper.time, "sleep", lambda _seconds: None)
    with patch(
        "modules.sleeper.requests.get",
        return_value=_status_response(400),
    ) as mock_get:
        result = sleeper._request_json(
            "sleeper_league", "https://example.test/league/L1", max_retries=2
        )
    assert result is None
    assert mock_get.call_count == 1

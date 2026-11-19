"""Silent-failure audit (docs/audits/2026-11-silent-failures.md): a failed Sleeper read is logged with context, not swallowed."""

from __future__ import annotations

import logging
from unittest.mock import Mock, patch

import pytest
import requests

from modules import sleeper


@pytest.fixture(autouse=True)
def _reset_throttle():
    sleeper._failure_log_last.clear()
    yield
    sleeper._failure_log_last.clear()


def _status(code):
    response = Mock()
    response.status_code = code
    response.json.return_value = {}
    return response


def test_request_json_logs_a_final_http_failure_with_label(monkeypatch, caplog):
    monkeypatch.setattr(sleeper.time, "sleep", lambda _s: None)
    with caplog.at_level(logging.WARNING, logger="fantasygm.sleeper"):
        with patch("modules.sleeper.requests.get", return_value=_status(404)):
            assert sleeper._request_json("sleeper_league", "https://example.test/league/L1?token=secret", allow_defer=False) is None
    assert "label=sleeper_league" in caplog.text and "http_404" in caplog.text
    assert "secret" not in caplog.text and "example.test" not in caplog.text


def test_request_json_logs_timeout_once_per_interval(monkeypatch, caplog):
    monkeypatch.setattr(sleeper.time, "sleep", lambda _s: None)
    with caplog.at_level(logging.WARNING, logger="fantasygm.sleeper"):
        with patch("modules.sleeper.requests.get", side_effect=requests.Timeout("slow")):
            for _ in range(3):
                sleeper._request_json("sleeper_league_rosters", "https://example.test/x", max_retries=0, allow_defer=False)
    assert caplog.text.count("reason=timeout") == 1


def test_rosters_getter_logs_league_id_and_still_returns_empty(caplog):
    sleeper._get_rosters_cached.cache_clear()
    with caplog.at_level(logging.WARNING, logger="fantasygm.sleeper"):
        with patch("modules.sleeper._live_league_json", side_effect=RuntimeError("boom")):
            assert sleeper._get_rosters_cached("L9", 1) == []
    sleeper._get_rosters_cached.cache_clear()
    assert "league_id=L9" in caplog.text and "RuntimeError" in caplog.text


def test_weekly_stats_says_unavailable_instead_of_no_games(monkeypatch, caplog):
    from tests.test_mobile_api_service import _client

    client = _client(monkeypatch)
    auth = Mock(status_code=200)
    auth.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    log = logging.getLogger("fantasygm.mobile_api")
    log.addHandler(caplog.handler)  # that logger does not propagate to root
    caplog.set_level(logging.WARNING, logger="fantasygm.mobile_api")
    try:
        with patch("requests.get", return_value=auth):
            with patch("modules.sleeper.default_player_stats_season", return_value=2026):
                with patch("modules.sleeper.get_season_player_stats", return_value={}):
                    body = client.get("/v1/players/9001/weekly-stats", headers={"Authorization": "Bearer good-token"}).json()
    finally:
        log.removeHandler(caplog.handler)
    assert body["ok"] is True and body["weeks"] == [] and body["stats_available"] is False
    assert "weekly_stats_unavailable" in caplog.text

def _capture(caplog, name="fantasygm.mobile_api"):
    log = logging.getLogger(name)
    log.addHandler(caplog.handler)  # that logger does not propagate to root
    caplog.set_level(logging.WARNING, logger=name)
    return log


def test_referral_comp_check_failure_is_logged_and_still_fails_closed(caplog):
    from services import mobile_api_service as svc

    log = _capture(caplog)
    try:
        with patch("modules.account_store.fetch_user_settings", side_effect=RuntimeError("down")):
            assert svc._referral_comp_active({}, "secret-user", "secret-token") is False
    finally:
        log.removeHandler(caplog.handler)
    assert "referral_comp_check_failed" in caplog.text and "RuntimeError" in caplog.text
    assert "secret" not in caplog.text


def test_decision_log_write_failure_is_logged_and_surfaced(monkeypatch, caplog):
    from tests.test_mobile_api_service import _client

    client = _client(monkeypatch)
    auth = Mock(status_code=200)
    auth.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    log = _capture(caplog)
    try:
        with patch("requests.get", return_value=auth), patch("requests.post", return_value=Mock(status_code=500)):
            body = client.post("/v1/decisions", headers={"Authorization": "Bearer good-token"}, json={"kind": "waiver_add", "rec_key": "w:1"}).json()
    finally:
        log.removeHandler(caplog.handler)
    assert body == {"ok": False, "reason": "not_available"}
    assert "decision_log_write_failed" in caplog.text and "status=500" in caplog.text

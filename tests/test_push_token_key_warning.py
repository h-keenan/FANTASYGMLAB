"""Startup visibility for the push-token handoff's missing service key."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

from services import mobile_api_service as svc

NAME = svc.DEGRADED_PUSH_TOKEN_KEY_MISSING


def _run(monkeypatch, caplog, *, flag, key):
    monkeypatch.setattr(svc.push_tokens, "handoff_enabled", lambda: flag)
    if key:
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-placeholder")
    else:
        monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    sentry = MagicMock()
    monkeypatch.setattr(svc, "SENTRY_DSN", "https://example.invalid/1")
    monkeypatch.setitem(__import__("sys").modules, "sentry_sdk", sentry)
    with caplog.at_level(logging.WARNING, logger="fantasygm.mobile_api"):
        svc._check_push_token_handoff_key()
    warns = [r for r in caplog.records if NAME in r.getMessage()]
    return warns, sentry


def test_key_present_no_warning(monkeypatch, caplog):
    warns, sentry = _run(monkeypatch, caplog, flag=True, key=True)
    assert warns == []
    sentry.capture_message.assert_not_called()
    assert NAME not in svc._degraded_flags
    assert "test-placeholder" not in caplog.text


def test_key_absent_one_warning_and_alert(monkeypatch, caplog):
    warns, sentry = _run(monkeypatch, caplog, flag=True, key=False)
    assert len(warns) == 1
    sentry.capture_message.assert_called_once()
    assert svc.health().get("degraded") == [NAME]
    svc._degraded_flags.clear()


def test_flag_off_no_warning(monkeypatch, caplog):
    warns, sentry = _run(monkeypatch, caplog, flag=False, key=False)
    assert warns == []
    sentry.capture_message.assert_not_called()
    assert "degraded" not in svc.health()

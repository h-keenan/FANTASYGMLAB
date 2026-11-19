"""modules/sentry_scrub.py: backend Sentry events must never carry credentials, emails or request bodies."""

from __future__ import annotations

from modules import sentry_scrub


def _event():
    return {
        "request": {
            "url": "https://api.example.com/v1/espn/credentials?access_token=abc12345",
            "method": "POST",
            "data": {"espn_s2": "AEB-SECRET-COOKIE", "swid": "{ABC-123}"},
            "cookies": {"sb": "x"},
            "query_string": "token=zzz",
            "headers": {"Authorization": "Bearer abc", "User-Agent": "ua", "X-Forwarded-For": "198.51.100.9"},
        },
        "user": {"id": "uid-1", "email": "a@b.com", "ip_address": "198.51.100.9", "username": "bob"},
        "extra": {"espn_s2": "AEB-SECRET-COOKIE", "league_id": "123", "note": "contact a@b.com now"},
        "exception": {"values": [{"type": "ValueError", "value": "bad Bearer eyJhbGciOi.eyJzdWIiOiJ4.abcdefghijk for a@b.com"}]},
        "breadcrumbs": {"values": [{"category": "http", "data": {"url": "https://x/y?token=abcdef", "swid": "{S}"}}]},
    }


def test_request_body_cookies_query_and_sensitive_headers_are_dropped():
    out = sentry_scrub.scrub_event(_event())
    request = out["request"]
    assert "data" not in request and "cookies" not in request and "query_string" not in request
    assert request["headers"]["Authorization"] == sentry_scrub.FILTERED
    assert request["headers"]["X-Forwarded-For"] == sentry_scrub.FILTERED
    assert request["headers"]["User-Agent"] == "ua"
    assert "abc12345" not in request["url"]


def test_user_keeps_only_opaque_id():
    assert sentry_scrub.scrub_event(_event())["user"] == {"id": "uid-1"}


def test_credential_keys_and_values_are_redacted_everywhere():
    out = sentry_scrub.scrub_event(_event())
    assert out["extra"]["espn_s2"] == sentry_scrub.FILTERED
    assert out["extra"]["league_id"] == "123"
    assert "a@b.com" not in out["extra"]["note"]
    message = out["exception"]["values"][0]["value"]
    assert "a@b.com" not in message and "eyJhbGciOi" not in message
    crumb = out["breadcrumbs"]["values"][0]["data"]
    assert crumb["swid"] == sentry_scrub.FILTERED and "abcdef" not in crumb["url"]


def test_scrubber_never_raises_or_drops_an_event():
    weird = {"request": "not-a-dict", "user": None, "extra": object()}
    assert sentry_scrub.scrub_event(weird) is weird


def test_breadcrumb_scrubber_redacts_tokens():
    crumb = sentry_scrub.scrub_breadcrumb({"message": "GET /x?token=abcdef12", "data": {"Authorization": "Bearer x"}})
    assert "abcdef12" not in crumb["message"]
    assert crumb["data"]["Authorization"] == sentry_scrub.FILTERED


def test_init_options_disable_pii_and_bodies():
    opts = sentry_scrub.sentry_init_options()
    assert opts["send_default_pii"] is False
    assert opts["max_request_body_size"] == "never"
    assert opts["before_send"] is sentry_scrub.scrub_event

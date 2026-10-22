"""Sleeper call-rate budget, priority deferral, and last-known fallback."""

from __future__ import annotations

import time
from unittest.mock import Mock, patch

import pytest
import requests

from modules import league_warmup, sleeper, sleeper_budget

URL = "https://example.test/league/L1/rosters"


def _resp(status, payload=None):
    r = Mock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    return r


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    sleeper_budget.reset_for_tests()
    monkeypatch.setattr(sleeper.time, "sleep", lambda _s: None)
    yield
    sleeper_budget.reset_for_tests()


def _fill(n):
    for _ in range(n):
        sleeper_budget.record_call()


def test_soft_threshold_is_70_percent_of_1000():
    assert sleeper_budget.SOFT_THRESHOLD == 700
    _fill(699)
    assert not sleeper_budget.over_soft_threshold()
    _fill(1)
    assert sleeper_budget.over_soft_threshold()


def test_counter_is_shared_through_redis_across_workers(_fake_redis_for_tests):
    # Another worker's calls (written straight to Redis) count toward ours.
    _fake_redis_for_tests.set(sleeper_budget._redis_key(time.time()), 800)
    assert sleeper_budget.over_soft_threshold()


def test_request_json_records_one_call_per_attempt():
    with patch("modules.sleeper.requests.get", side_effect=[_resp(503), _resp(200, [1])]):
        assert sleeper._request_json("x", URL) == [1]
    assert sleeper_budget._local_count(time.time()) == 2


def test_free_tier_over_threshold_serves_last_known_with_as_of_and_no_call():
    with patch("modules.sleeper.requests.get", return_value=_resp(200, [{"roster_id": 1}])):
        sleeper._request_json("x", URL)
    _fill(750)
    sleeper_budget.begin_request()
    sleeper_budget.set_request_tier("free")
    with patch("modules.sleeper.requests.get") as get:
        result = sleeper._request_json("x", URL)
    get.assert_not_called()
    assert result == [{"roster_id": 1}]
    assert sleeper_budget.stale_as_of()


def test_paid_tier_over_threshold_still_goes_live():
    with patch("modules.sleeper.requests.get", return_value=_resp(200, ["old"])):
        sleeper._request_json("x", URL)
    _fill(750)
    sleeper_budget.begin_request()
    sleeper_budget.set_request_tier("premium")
    with patch("modules.sleeper.requests.get", return_value=_resp(200, ["fresh"])) as get:
        assert sleeper._request_json("x", URL) == ["fresh"]
    get.assert_called_once()
    assert sleeper_budget.stale_as_of() is None


def test_free_tier_with_nothing_cached_still_fetches_live():
    _fill(750)
    sleeper_budget.set_request_tier("free")
    with patch("modules.sleeper.requests.get", return_value=_resp(200, ["live"])):
        assert sleeper._request_json("x", URL) == ["live"]


def test_low_priority_with_nothing_cached_skips_without_calling():
    _fill(750)
    with sleeper_budget.low_priority(), patch("modules.sleeper.requests.get") as get:
        assert sleeper._request_json("x", URL) is None
    get.assert_not_called()


def test_low_priority_proceeds_under_threshold():
    with sleeper_budget.low_priority(), patch(
        "modules.sleeper.requests.get", return_value=_resp(200, ["ok"])
    ):
        assert sleeper._request_json("x", URL) == ["ok"]


def test_429_after_retries_serves_last_known_with_as_of():
    with patch("modules.sleeper.requests.get", return_value=_resp(200, ["good"])):
        sleeper._request_json("x", URL)
    sleeper_budget.begin_request()
    with patch("modules.sleeper.requests.get", return_value=_resp(429)):
        assert sleeper._request_json("x", URL) == ["good"]
    assert sleeper_budget.stale_as_of()


def test_timeout_serves_last_known():
    with patch("modules.sleeper.requests.get", return_value=_resp(200, ["good"])):
        sleeper._request_json("x", URL)
    with patch("modules.sleeper.requests.get", side_effect=requests.Timeout("t")):
        assert sleeper._request_json("x", URL) == ["good"]


def test_failure_with_no_last_known_returns_none_never_fabricates():
    sleeper_budget.begin_request()
    with patch("modules.sleeper.requests.get", return_value=_resp(429)):
        assert sleeper._request_json("x", URL) is None
    assert sleeper_budget.stale_as_of() is None


def test_plain_404_does_not_fall_back_to_last_known():
    with patch("modules.sleeper.requests.get", return_value=_resp(200, ["good"])):
        sleeper._request_json("x", URL)
    with patch("modules.sleeper.requests.get", return_value=_resp(404)):
        assert sleeper._request_json("x", URL) is None


def test_warmup_is_skipped_over_threshold():
    _fill(750)
    assert league_warmup.start_warmup(user_id="u", league_id="L", steps={}) is False


def test_only_free_tier_is_deferred():
    sleeper_budget.set_request_tier("premium")
    _fill(750)
    assert not sleeper_budget.should_defer()
    sleeper_budget.set_request_tier("free")
    sleeper_budget._priority.set("free")
    assert sleeper_budget.should_defer()


def test_last_known_cache_is_bounded():
    cap = sleeper_budget.LAST_KNOWN_MAX_ENTRIES
    for i in range(cap + 10):
        sleeper_budget.remember(f"u{i}", i)
    assert sleeper_budget.last_known("u0") is None
    assert sleeper_budget.last_known(f"u{cap + 9}") is not None


def test_endpoint_wrapper_adds_as_of_only_when_stale_served():
    from services import mobile_api_service as svc

    def live():
        return {"ok": True}

    def stale():
        sleeper_budget.note_stale_served("u", time.time() - 90)
        return {"ok": True}

    assert svc._with_sleeper_as_of(live)() == {"ok": True}
    out = svc._with_sleeper_as_of(stale)()
    assert out["ok"] is True and out["sleeper_data_as_of"]


def test_free_profile_tags_request_but_failed_profile_read_does_not(monkeypatch):
    from services import mobile_api_service as svc

    ok = {"entitlement": "free", "sleeper_username": "", "status": "ok"}
    monkeypatch.setattr(svc, "_fetch_profile_fields_uncached", lambda *_a: ok)
    svc._fetch_profile_fields({}, "free-user", "tok")
    assert sleeper_budget.current_priority() == "free"
    sleeper_budget.reset_for_tests()
    err = {"entitlement": "free", "sleeper_username": "", "status": "error"}
    monkeypatch.setattr(svc, "_fetch_profile_fields_uncached", lambda *_a: err)
    svc._fetch_profile_fields({}, "err-user", "tok")
    assert sleeper_budget.current_priority() == ""

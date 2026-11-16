"""A Pro account must never read as Free because a profile lookup failed."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient

from modules.sim import api as sim_api
from modules.sim import game_view
from modules.sim.store import InMemoryBackend
from services import mobile_api_service as svc

ERROR = {"entitlement": "free", "sleeper_username": "", "status": "error"}
PRO_OK = {"entitlement": "premium", "sleeper_username": "x", "status": "ok"}


@pytest.fixture
def fake_cache(monkeypatch):
    """Dict-backed stand-in for redis_single_flight_cache that caches whatever compute returns."""

    store: dict = {}

    def fake(*, cache_key, ttl_seconds, compute, **_k):
        if cache_key in store:
            return store[cache_key]
        result = compute()
        store[cache_key] = result
        return result

    monkeypatch.setattr(svc.redis_cache, "redis_single_flight_cache", fake)
    return store


def script_reads(monkeypatch, results):
    calls = []

    def fake(config, user_id, token):
        calls.append(1)
        return results[min(len(calls) - 1, len(results) - 1)]

    monkeypatch.setattr(svc, "_fetch_profile_fields_uncached", fake)
    return calls


def test_failed_read_is_never_cached(monkeypatch, fake_cache):
    calls = script_reads(monkeypatch, [ERROR, ERROR, PRO_OK])
    assert svc._fetch_profile_fields({}, "u1", "t")["status"] == "error"
    assert fake_cache == {}  # nothing pinned for the TTL
    assert svc._fetch_profile_fields({}, "u1", "t")["entitlement"] == "premium"
    assert len(calls) == 3


def test_one_transient_failure_is_retried_within_the_call(monkeypatch, fake_cache):
    calls = script_reads(monkeypatch, [ERROR, PRO_OK])
    assert svc._fetch_profile_fields({}, "u1", "t")["entitlement"] == "premium"
    assert len(calls) == 2


def test_caller_plan_unknown_on_error_and_not_memoized(monkeypatch):
    monkeypatch.setattr(svc, "_fetch_profile_fields", lambda *a, **k: ERROR)
    user = {"id": "u1", "_access_token": "t"}
    assert svc._caller_plan(user) == "unknown"
    assert "_plan" not in user
    assert svc._manager_tendencies_gate(user) is False  # other Pro gates stay closed
    monkeypatch.setattr(svc, "_fetch_profile_fields", lambda *a, **k: PRO_OK)
    assert svc._caller_plan(user) == "pro"


def test_plan_resolved_once_per_request(monkeypatch):
    calls = []
    monkeypatch.setattr(svc, "_fetch_profile_fields", lambda *a, **k: calls.append(1) or PRO_OK)
    user = {"id": "u1", "_access_token": "t"}
    assert all(svc._is_pro_caller(user) for _ in range(5))
    assert len(calls) == 1


def test_genuine_free_user_is_free(monkeypatch):
    monkeypatch.setattr(svc, "_fetch_profile_fields", lambda *a, **k: {"entitlement": "free", "status": "ok"})
    assert svc._caller_plan({"id": "u1"}) == "free"


class _Resp:
    def __init__(self, status, rows=None):
        self.status_code = status
        self._rows = rows or []

    def json(self):
        return self._rows


@pytest.mark.parametrize("status", [401, 500, 503])
def test_transient_status_does_not_flip_trial_column_flag(monkeypatch, status):
    monkeypatch.setattr(svc, "_TRIAL_COLUMN_MISSING", False)
    monkeypatch.setattr(svc.requests, "get", lambda *a, **k: _Resp(status))
    assert svc._fetch_profile_fields_uncached({"url": "x"}, "u1", "t")["status"] == "error"
    assert svc._TRIAL_COLUMN_MISSING is False


def test_missing_column_flips_flag_only_when_fallback_works(monkeypatch):
    monkeypatch.setattr(svc, "_TRIAL_COLUMN_MISSING", False)
    seq = [_Resp(400), _Resp(200, [{"entitlement": "pro", "sleeper_username": "x"}])]
    monkeypatch.setattr(svc.requests, "get", lambda *a, **k: seq.pop(0))
    out = svc._fetch_profile_fields_uncached({"url": "x"}, "u1", "t")
    assert out["status"] == "ok" and out["entitlement"] == "premium"
    assert svc._TRIAL_COLUMN_MISSING is True
    monkeypatch.setattr(svc, "_TRIAL_COLUMN_MISSING", False)


def test_service_sim_is_pro_raises_on_unknown_plan(monkeypatch):
    monkeypatch.setattr(svc, "_fetch_profile_fields", lambda *a, **k: ERROR)
    with pytest.raises(svc._PlanUnverified):
        svc._sim_is_pro({"id": "u1"})
    monkeypatch.setattr(svc, "_fetch_profile_fields", lambda *a, **k: PRO_OK)
    assert svc._sim_is_pro({"id": "u2"}) is True


def make_client(is_pro):
    def require_user(authorization: str | None = Header(default=None)):
        return {"id": "owner", "_access_token": "tok"}

    app = FastAPI()
    sim_api.mount(
        app,
        sim_api.SimApiDeps(require_user=require_user, is_pro=is_pro, sleeper_username=lambda u: "",
                           backend_for=lambda u: InMemoryBackend()),
        environ={"SIM_ENABLED": "1"},
    )
    return TestClient(app)


def test_unverified_plan_answers_retryable_reason_not_paywall():
    def unverified(user):
        raise sim_api.PlanUnverified()

    client = make_client(unverified)
    for method, path in (("get", "/v1/sim/games/options"), ("get", "/v1/sim/games"), ("post", "/v1/sim/games")):
        kwargs = {"json": {}} if method == "post" else {}
        res = getattr(client, method)(path, headers={"Authorization": "x"}, **kwargs)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["reason"] == "plan_unverified"
        assert body["preview"] is None and body["upsell"] is None
        assert body["is_premium"] is None


def test_verified_pro_is_never_paywalled_in_season_two():
    state = SimpleNamespace(status="offseason", season_no=2, week=4)
    assert game_view.paywalled(True, state) is False
    assert game_view.preview_block(True, state) is None
    # A verified Free user still is (revenue protection unchanged).
    assert game_view.paywalled(False, state) is True

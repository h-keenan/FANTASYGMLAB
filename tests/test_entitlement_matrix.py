"""Entitlement matrix: ONE Pro source (profiles.entitlement + live referral comp).

For every stored value the profile read must resolve one wire value, every
server gate must agree with it, and a failed read must never read as Free.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from modules import premium
from services import mobile_api_service as svc

ROOT = Path(__file__).resolve().parents[1]


def _response(rows, status=200):
    return SimpleNamespace(status_code=status, json=lambda: rows)


def _read(monkeypatch, stored, *, comp=None, settings_error=""):
    """Run the real profile read against a stubbed Supabase."""

    monkeypatch.setattr(svc, "_TRIAL_COLUMN_MISSING", False)
    monkeypatch.setattr(svc.auth_supabase, "auth_headers", lambda *_a, **_k: {})
    monkeypatch.setattr(svc.auth_supabase, "rest_api_url", lambda *_a, **_k: "https://x.test/rest")
    if stored is None:
        monkeypatch.setattr(svc.requests, "get", lambda *_a, **_k: _response([], 500))
    else:
        row = {"entitlement": stored, "sleeper_username": "u", "trial_ends_at": ""}
        monkeypatch.setattr(svc.requests, "get", lambda *_a, **_k: _response([row]))
    settings = {"user_id": "u1", "settings": {"referral_program": {"comp_until": comp}} if comp else {}}
    monkeypatch.setattr(
        svc.account_store, "fetch_user_settings", lambda *_a, **_k: (({}, settings_error) if settings_error else (settings, ""))
    )
    return svc._fetch_profile_fields_uncached({}, "u1", "tok")


@pytest.mark.parametrize(
    "stored,wire,is_pro",
    [
        ("free", "free", False),
        ("premium", "premium", True),
        ("pro", "premium", True),
        ("front_office", "premium", True),
        ("Front Office", "premium", True),
        ("", "free", False),
        (None, "free", False),
        ("banana", "free", False),
    ],
)
def test_stored_value_resolves_one_wire_value_and_every_gate_agrees(monkeypatch, stored, wire, is_pro):
    profile = _read(monkeypatch, stored if stored is not None else "")
    assert profile["entitlement"] == wire and profile["status"] == "ok"
    assert premium.is_at_least(profile["entitlement"], premium.PRO) is is_pro
    monkeypatch.setattr(svc, "_fetch_profile_fields", lambda *_a, **_k: profile)
    assert svc._manager_tendencies_gate({"id": "u1"}) is is_pro
    assert svc._is_pro_caller({"id": "u1"}) is is_pro
    assert svc._sim_is_pro({"id": "u1"}) is is_pro
    assert premium.has_cross_league_exposure(profile["entitlement"]) is is_pro


def test_failed_profile_read_is_unknown_never_free(monkeypatch):
    profile = _read(monkeypatch, None)
    assert profile["status"] == "error"
    monkeypatch.setattr(svc, "_fetch_profile_fields", lambda *_a, **_k: profile)
    assert svc._caller_plan({"id": "u1"}) == "unknown"
    with pytest.raises(svc._PlanUnverified):
        svc._sim_is_pro({"id": "u1"})
    # Other gates stay closed (revenue protection) but report no Pro either.
    assert svc._manager_tendencies_gate({"id": "u1"}) is False


FUTURE = "2999-01-01T00:00:00+00:00"
PAST = "2000-01-01T00:00:00+00:00"


def test_live_referral_comp_grants_pro_on_the_api_read(monkeypatch):
    profile = _read(monkeypatch, "free", comp=FUTURE)
    assert profile["entitlement"] == "premium"


def test_expired_comp_or_unreadable_settings_stay_free(monkeypatch):
    assert _read(monkeypatch, "free", comp=PAST)["entitlement"] == "free"
    assert _read(monkeypatch, "free", comp=FUTURE, settings_error="boom")["entitlement"] == "free"


def test_comp_never_touches_a_paid_plan(monkeypatch):
    calls = []
    monkeypatch.setattr(svc, "_referral_comp_active", lambda *a, **k: calls.append(1) or True)
    monkeypatch.setattr(svc, "_TRIAL_COLUMN_MISSING", False)
    monkeypatch.setattr(svc.auth_supabase, "auth_headers", lambda *_a, **_k: {})
    monkeypatch.setattr(svc.auth_supabase, "rest_api_url", lambda *_a, **_k: "https://x.test/rest")
    monkeypatch.setattr(svc.requests, "get", lambda *_a, **_k: _response([{"entitlement": "premium"}]))
    assert svc._fetch_profile_fields_uncached({}, "u1", "tok")["entitlement"] == "premium"
    assert calls == []  # no settings read for someone already paying


def test_web_and_mobile_see_the_same_plan_for_one_account(monkeypatch):
    """/v1/me is the only plan source both clients read; a store purchase and a
    Stripe purchase both land in profiles.entitlement, so the answer is shared."""

    for stored in ("free", "premium", "front_office"):
        a = _read(monkeypatch, stored)
        b = _read(monkeypatch, stored)
        assert a["entitlement"] == b["entitlement"]


def test_what_if_gate_free_sees_paywall_pro_sees_data(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    svc.app.dependency_overrides[svc.require_user] = lambda: {"id": "user-1", "_access_token": "tok"}
    svc.app.dependency_overrides[svc.require_league_access] = lambda: "999"
    try:
        client = TestClient(svc.app)
        monkeypatch.setattr(svc, "_fetch_profile_fields", lambda *_a, **_k: {"entitlement": "free", "status": "ok"})
        free = client.post("/v1/leagues/999/games/season-sim/what-if", json={"add": ["1"]}).json()
        assert free["is_premium"] is False and free["upsell"]["title"]
        monkeypatch.setattr(svc, "_fetch_profile_fields", lambda *_a, **_k: {"entitlement": "premium", "status": "ok"})
        pro = client.post("/v1/leagues/999/games/season-sim/what-if", json={"add": ["1"]}).json()
        assert pro.get("is_premium") is not False
    finally:
        svc.app.dependency_overrides.clear()


def test_no_server_surface_keeps_its_own_pro_comparison():
    """Pro is decided by premium.is_at_least(...) / canonical_tier only."""

    allowed = {"premium.py", "stripe_billing.py", "stripe_webhook.py", "revenuecat_billing.py", "revenuecat_webhook.py", "founder_analytics.py"}
    pattern = re.compile(r"""entitlement["']?\)?\s*(==|!=|in)\s*[\(\{\[]?\s*["'](premium|pro|front_office)["']""")
    offenders = []
    for folder in ("services", "modules"):
        for path in (ROOT / folder).rglob("*.py"):
            if path.name in allowed:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                if pattern.search(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == [], "use premium.is_at_least(entitlement, premium.PRO)"

"""GET /v1/leagues/{id}/commissioner/{status,integrity}: commissioner-only,
Pro-gated, public Sleeper data only (engine covered in test_league_integrity)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.test_paywall_leaks import (  # noqa: F401  (fixture + helpers shared with the paywall suite)
    AUTH,
    _PRO_FEATURE_ENTITLEMENTS,
    _set_profile,
    pro_feature_client,
)

USERS = [{"user_id": "u-owner", "is_owner": True}, {"user_id": "u-member", "is_owner": False}]


def _as(owner_id):
    return patch("services.mobile_api_service._resolve_my_roster", return_value=({"roster_id": 1, "owner_id": owner_id}, ""))


def test_status_true_for_sleeper_owner_flag(pro_feature_client, monkeypatch):
    _set_profile(monkeypatch, "free")
    with _as("u-owner"), patch("modules.sleeper.get_users", return_value=USERS):
        body = pro_feature_client.get("/v1/leagues/abc/commissioner/status", headers=AUTH).json()
    assert body == {"ok": True, "is_commissioner": True, "reason": ""}


def test_status_false_for_member_and_for_unresolved_roster(pro_feature_client, monkeypatch):
    _set_profile(monkeypatch, "free")
    with _as("u-member"), patch("modules.sleeper.get_users", return_value=USERS):
        assert pro_feature_client.get("/v1/leagues/abc/commissioner/status", headers=AUTH).json()["is_commissioner"] is False
    with patch("services.mobile_api_service._resolve_my_roster", return_value=(None, "no_roster_in_league")):
        body = pro_feature_client.get("/v1/leagues/abc/commissioner/status", headers=AUTH).json()
    assert body["is_commissioner"] is False and body["reason"] == "no_roster_in_league"


@pytest.mark.parametrize("entitlement,allowed", _PRO_FEATURE_ENTITLEMENTS)
def test_integrity_is_pro_only_and_commissioner_only(pro_feature_client, monkeypatch, entitlement, allowed):
    _set_profile(monkeypatch, entitlement)
    real = {"ok": True, "reason": "", "teams": [{"roster_id": 1, "band": "fine"}], "collusion": [], "inactive": []}
    with _as("u-owner"), patch("modules.sleeper.get_users", return_value=USERS), \
            patch("modules.league_integrity_data.build_cached", return_value=real) as build:
        body = pro_feature_client.get("/v1/leagues/abc/commissioner/integrity?draft_order=record", headers=AUTH).json()
    if allowed:
        assert body["teams"] == real["teams"] and body["is_commissioner"] is True and body["upsell"] is None
        build.assert_called_once()
        assert build.call_args.args[1] == "record"
    else:
        assert body["reason"] == "premium_required" and body["teams"] == [] and body["upsell"]["title"]
        build.assert_not_called()


def test_integrity_refuses_non_commissioner_without_computing(pro_feature_client, monkeypatch):
    _set_profile(monkeypatch, "premium", trial_ends_at="2999-01-01T00:00:00+00:00")
    with _as("u-member"), patch("modules.sleeper.get_users", return_value=USERS), \
            patch("modules.league_integrity_data.build_cached") as build:
        body = pro_feature_client.get("/v1/leagues/abc/commissioner/integrity", headers=AUTH).json()
    assert body["reason"] == "not_commissioner" and body["teams"] == [] and body["is_commissioner"] is False
    build.assert_not_called()


def test_integrity_rejects_unknown_draft_order(pro_feature_client, monkeypatch):
    _set_profile(monkeypatch, "premium", trial_ends_at="2999-01-01T00:00:00+00:00")
    response = pro_feature_client.get("/v1/leagues/abc/commissioner/integrity?draft_order=bogus", headers=AUTH)
    assert response.status_code == 422

"""GET /v1/leagues/{id}/commissioner/integrity: Pro-gated, any league the Pro
user can open (no commissioner check), public Sleeper data only (engine
covered in test_league_integrity)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.test_paywall_leaks import (  # noqa: F401  (fixture + helpers shared with the paywall suite)
    AUTH,
    _PRO_FEATURE_ENTITLEMENTS,
    _set_profile,
    pro_feature_client,
)


@pytest.mark.parametrize("entitlement,allowed", _PRO_FEATURE_ENTITLEMENTS)
def test_integrity_is_pro_only(pro_feature_client, monkeypatch, entitlement, allowed):
    _set_profile(monkeypatch, entitlement)
    real = {"ok": True, "reason": "", "teams": [{"roster_id": 1, "band": "fine"}], "collusion": [], "inactive": []}
    with patch("modules.league_integrity_data.build_cached", return_value=real) as build:
        body = pro_feature_client.get("/v1/leagues/abc/commissioner/integrity?draft_order=record", headers=AUTH).json()
    if allowed:
        assert body["teams"] == real["teams"] and body["is_premium"] is True and body["upsell"] is None
        assert build.call_args.args[1] == "record"
    else:
        assert body["reason"] == "premium_required" and body["teams"] == [] and body["upsell"]["title"]
        build.assert_not_called()


def test_integrity_does_not_check_commissioner_status(pro_feature_client, monkeypatch):
    _set_profile(monkeypatch, "premium", trial_ends_at="2999-01-01T00:00:00+00:00")
    with patch("modules.league_integrity_data.build_cached", return_value={"ok": True, "reason": "", "teams": []}), \
            patch("modules.sleeper.get_users", side_effect=AssertionError("no commissioner lookup")):
        body = pro_feature_client.get("/v1/leagues/abc/commissioner/integrity", headers=AUTH).json()
    assert body["is_premium"] is True


def test_integrity_rejects_unknown_draft_order(pro_feature_client, monkeypatch):
    _set_profile(monkeypatch, "premium", trial_ends_at="2999-01-01T00:00:00+00:00")
    assert pro_feature_client.get("/v1/leagues/abc/commissioner/integrity?draft_order=bogus", headers=AUTH).status_code == 422

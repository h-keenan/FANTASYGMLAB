"""Founder Beta launch readiness: customer-safe error messaging contracts."""

from __future__ import annotations

from unittest.mock import Mock, patch

from modules import account_store
from modules.sleeper_leagues import (
    LeagueLookupResult,
    league_lookup_customer_message,
    lookup_user_leagues,
)


def test_league_lookup_customer_messages_cover_failure_modes():
    assert "username" in league_lookup_customer_message("empty_username").casefold()
    assert "no sleeper account" in league_lookup_customer_message("user_not_found").casefold()
    assert "unreachable" in league_lookup_customer_message("unavailable").casefold()
    assert "no leagues were found" in league_lookup_customer_message("no_leagues").casefold()
    assert league_lookup_customer_message("ok") == ""


def test_lookup_user_leagues_distinguishes_user_not_found_from_unavailable():
    with patch("modules.sleeper_leagues.requests.get") as mock_get:
        mock_get.return_value = Mock(status_code=404, json=lambda: {})
        result = lookup_user_leagues("missing_user")
    assert result == LeagueLookupResult([], "user_not_found")

    with patch("modules.sleeper_leagues.requests.get") as mock_get:
        mock_get.side_effect = TimeoutError("timed out")
        result = lookup_user_leagues("any_user")
    assert result == LeagueLookupResult([], "unavailable")


def test_lookup_user_leagues_returns_leagues_on_success():
    user_response = Mock(status_code=200, json=lambda: {"user_id": "user-1"})
    league_response = Mock(
        status_code=200,
        json=lambda: [{"league_id": "lg-1", "name": "Test League"}],
    )
    prior_response = Mock(status_code=200, json=lambda: [])

    with patch(
        "modules.sleeper_leagues.requests.get",
        side_effect=[user_response, league_response, prior_response],
    ):
        result = lookup_user_leagues("founder")

    assert result.status == "ok"
    assert result.leagues[0]["league_id"] == "lg-1"
    assert result.leagues[0]["season"] is not None


def test_lookup_user_leagues_merges_current_and_prior_season():
    user_response = Mock(status_code=200, json=lambda: {"user_id": "user-1"})
    current = Mock(
        status_code=200,
        json=lambda: [{"league_id": "lg-2026", "name": "New Year"}],
    )
    prior = Mock(
        status_code=200,
        json=lambda: [{"league_id": "lg-2025", "name": "Dynasty Home"}],
    )
    with patch(
        "modules.sleeper_leagues.requests.get",
        side_effect=[user_response, current, prior],
    ):
        result = lookup_user_leagues("founder", season=2026)
    assert result.status == "ok"
    ids = [row["league_id"] for row in result.leagues]
    assert ids == ["lg-2026", "lg-2025"]


def test_customer_safe_error_sanitizes_profile_and_saved_league_failures():
    assert "session expired" in account_store.customer_safe_error(
        "JWT expired",
        context="profile",
    ).casefold()
    assert "premium stays locked" in account_store.customer_safe_error(
        "RLS blocked profile fetch.",
        context="profile",
    ).casefold()
    assert account_store.customer_safe_error(
        "permission denied for relation saved_leagues",
        context="saved_leagues",
    ) == "Saved leagues could not be loaded right now. Please try again in a moment."


def test_launch_readiness_report_exists():
    from pathlib import Path

    doc = (Path(__file__).resolve().parents[1] / "docs/founder-beta-launch-readiness-report.md").read_text(
        encoding="utf-8"
    )
    assert "READY AFTER OPS" in doc
    assert "a65881a70a3445b4322d8bca04cb490f990a69f8" in doc
    assert "Ship Founder Beta" in doc or "Delay" in doc

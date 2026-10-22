"""Portfolio perf audit, 2026-10-21.

Covers the progressive Portfolio endpoints (GET /v1/portfolio/leagues and
GET /v1/portfolio/leagues/{league_id}), the concurrent saved-league
rollover resolution, and league_rankings' reuse of the shared
summary/draft-capital cache entry.
"""

import threading
import time
from unittest.mock import patch

import pandas as pd
import pytest

from modules import league_rankings
from services import mobile_api_service

AUTH_USER = ({"id": "user-123", "email": "gm@example.com"}, "")
PREMIUM_PROFILE = {"entitlement": "premium", "sleeper_username": "gm_dynasty", "status": "ok"}
FREE_PROFILE = {"entitlement": "free", "sleeper_username": "gm_dynasty", "status": "ok"}
SAVED_ROWS = [
    {"league_id": "league-ok", "league_name": "The Ok League"},
    {"league_id": "league-skip", "league_name": "The Skip League"},
]
HEADERS = {"Authorization": "Bearer good-token"}


def _client(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    return TestClient(mobile_api_service.app)


def _ok_summary():
    return {
        "ok": True,
        "team_name": "Ok Team",
        "team_avatar_url": "",
        "wins": 7,
        "losses": 3,
        "ties": 0,
        "health_flag": "Stable",
        "power_rank": 2,
        "power_rank_tied": False,
        "franchise_rank": 3,
        "franchise_rank_tied": False,
        "roster_value_rank": 1,
        "roster_value_rank_tied": False,
        "archetype": "juggernaut",
        "archetype_label": "Juggernaut",
        "top_asset": None,
        "top_item": {"category": "need", "headline": "Add RB2 depth", "reason": "Thin.", "destination": "my_team"},
    }


@pytest.fixture
def premium_portfolio(monkeypatch):
    monkeypatch.setattr(mobile_api_service.auth_supabase, "fetch_auth_user", lambda *a, **k: AUTH_USER)
    monkeypatch.setattr(mobile_api_service, "_fetch_profile_fields", lambda *a, **k: dict(PREMIUM_PROFILE))
    monkeypatch.setattr(
        mobile_api_service.account_store, "fetch_saved_leagues", lambda *a, **k: (list(SAVED_ROWS), "")
    )
    monkeypatch.setattr(mobile_api_service, "_fetch_team_stance", lambda *a, **k: "")
    monkeypatch.setattr(mobile_api_service, "_fetch_gm_target_player_ids", lambda *a, **k: ((), ()))
    calls: list[str] = []

    def _fake_build_league_summary(*, league_id, **_kwargs):
        calls.append(league_id)
        if league_id == "league-ok":
            return _ok_summary()
        return {"ok": False, "reason": "not_a_member_of_league"}

    monkeypatch.setattr(mobile_api_service.dashboard_engine, "build_league_summary", _fake_build_league_summary)
    return calls


def test_portfolio_index_lists_saved_leagues_without_building_any_summary(monkeypatch, premium_portfolio):
    client = _client(monkeypatch)
    response = client.get("/v1/portfolio/leagues", headers=HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["is_premium"] is True
    assert body["saved_leagues"] == [
        {"league_id": "league-ok", "league_name": "The Ok League"},
        {"league_id": "league-skip", "league_name": "The Skip League"},
    ]
    assert body["leagues"] == [] and body["failed_leagues"] == []
    assert premium_portfolio == []


def test_portfolio_league_row_matches_the_full_portfolio_row(monkeypatch, premium_portfolio):
    client = _client(monkeypatch)
    full = client.get("/v1/portfolio", headers=HEADERS).json()
    one = client.get("/v1/portfolio/leagues/league-ok", headers=HEADERS).json()

    assert one["is_premium"] is True
    assert one["failed_league"] is None
    assert one["league"] == full["leagues"][0]


def test_portfolio_league_reports_a_skip_state_as_a_failed_league(monkeypatch, premium_portfolio):
    client = _client(monkeypatch)
    body = client.get("/v1/portfolio/leagues/league-skip", headers=HEADERS).json()

    assert body["league"] is None
    assert body["failed_league"] == {
        "league_id": "league-skip",
        "league_name": "The Skip League",
        "reason": "not_a_member_of_league",
    }


def test_portfolio_league_reports_an_unexpected_error_as_unavailable(monkeypatch, premium_portfolio):
    def _boom(*_a, **_k):
        raise RuntimeError("Sleeper is unreachable")

    monkeypatch.setattr(mobile_api_service.dashboard_engine, "build_league_summary", _boom)
    client = _client(monkeypatch)
    body = client.get("/v1/portfolio/leagues/league-ok", headers=HEADERS).json()

    assert body["league"] is None
    assert body["failed_league"]["reason"] == "unavailable"


def test_portfolio_league_refuses_a_league_the_caller_never_saved(monkeypatch, premium_portfolio):
    client = _client(monkeypatch)
    response = client.get("/v1/portfolio/leagues/someone-elses-league", headers=HEADERS)

    assert response.status_code == 404
    assert premium_portfolio == []


def test_portfolio_league_times_out_a_hung_league(monkeypatch, premium_portfolio):
    release = threading.Event()

    def _hang(**_kwargs):
        release.wait(5)
        return _ok_summary()

    monkeypatch.setattr(mobile_api_service.dashboard_engine, "build_league_summary", _hang)
    monkeypatch.setattr(mobile_api_service, "_PORTFOLIO_FANOUT_TIMEOUT_SECONDS", 0.2)
    client = _client(monkeypatch)
    try:
        body = client.get("/v1/portfolio/leagues/league-ok", headers=HEADERS).json()
    finally:
        release.set()

    assert body["league"] is None
    assert body["failed_league"]["reason"] == "timed_out"


def test_portfolio_progressive_endpoints_gate_free_callers(monkeypatch, premium_portfolio):
    monkeypatch.setattr(mobile_api_service, "_fetch_profile_fields", lambda *a, **k: dict(FREE_PROFILE))
    client = _client(monkeypatch)

    index = client.get("/v1/portfolio/leagues", headers=HEADERS).json()
    one = client.get("/v1/portfolio/leagues/league-ok", headers=HEADERS).json()

    assert index["is_premium"] is False and index["saved_leagues"] == []
    assert index["upsell"]["title"]
    assert one["is_premium"] is False and one["league"] is None and one["failed_league"] is None
    assert premium_portfolio == []


def test_portfolio_progressive_endpoints_require_auth(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/v1/portfolio/leagues").status_code == 401
    assert client.get("/v1/portfolio/leagues/league-ok").status_code == 401


def test_portfolio_reports_saved_leagues_unavailable_when_the_read_raises(monkeypatch, premium_portfolio):
    def _raise(*_a, **_k):
        raise RuntimeError("supabase down")

    monkeypatch.setattr(mobile_api_service, "_fetch_saved_leagues_cached", _raise)
    client = _client(monkeypatch)
    body = client.get("/v1/portfolio", headers=HEADERS).json()

    assert body["reason"] == "saved_leagues_unavailable"
    assert body["leagues"] == []


def test_rollover_resolution_runs_rows_concurrently_and_keeps_order(monkeypatch):
    rows = [
        {"league_id": f"league-{i}", "league_name": f"L{i}", "sleeper_username": "gm_dynasty"} for i in range(5)
    ]

    def _slow_resolve(league_id, _username):
        time.sleep(0.2)
        return "league-3-next" if league_id == "league-3" else league_id

    monkeypatch.setattr(mobile_api_service, "_resolve_league_rollover_cached", _slow_resolve)
    monkeypatch.setattr(mobile_api_service.account_store, "migrate_saved_league", lambda *a, **k: (True, ""))

    started = time.perf_counter()
    resolved = mobile_api_service._apply_league_rollover_resolution({}, "token", "user-123", rows)
    elapsed = time.perf_counter() - started

    assert [row["league_id"] for row in resolved] == ["league-0", "league-1", "league-2", "league-3-next", "league-4"]
    # Sequential would be ~1.0s; concurrent is ~one row's worth.
    assert elapsed < 0.7


def test_league_rankings_frame_reuses_the_cached_summary_and_draft_capital(monkeypatch):
    summary = pd.DataFrame([{"roster_id": 1}])
    draft_capital = pd.DataFrame([{"roster_id": 1}])
    seen: dict = {}

    monkeypatch.setattr(league_rankings.sleeper, "get_league", lambda _league_id: {"league_id": "abc"})
    monkeypatch.setattr(
        league_rankings.league_value_settings,
        "detect_league_value_settings_from_payload",
        lambda _league: {},
    )
    monkeypatch.setattr(
        league_rankings.league_value_settings,
        "build_valued_players_frame_cached",
        lambda **_kwargs: pd.DataFrame([{"player_id": "p1"}]),
    )
    monkeypatch.setattr(
        league_rankings,
        "build_league_summary_and_draft_capital_cached",
        lambda **_kwargs: (summary, draft_capital),
    )

    def _no_recompute(*_a, **_k):
        raise AssertionError("the summary pass must come from the shared cache entry")

    monkeypatch.setattr(league_rankings, "build_league_summary_and_draft_capital", _no_recompute)

    def _display(df_summary, draft_capital_summary, include_picks):
        seen["summary"] = df_summary
        seen["draft_capital"] = draft_capital_summary
        return df_summary

    monkeypatch.setattr(league_rankings, "build_league_display_frame", _display)
    monkeypatch.setattr(league_rankings, "add_league_detail_ranks", lambda df: df)

    frame = league_rankings._build_league_rankings_frame_cached("abc", "Dynasty", "unused.db", 0)

    assert seen["summary"] is summary and seen["draft_capital"] is draft_capital
    assert not frame.empty


def test_build_league_rankings_frame_still_computes_the_summary_when_not_given_one(monkeypatch):
    calls = []

    def _summary(*_a, **_k):
        calls.append(1)
        return pd.DataFrame(), pd.DataFrame()

    monkeypatch.setattr(league_rankings, "build_league_summary_and_draft_capital", _summary)
    result = league_rankings.build_league_rankings_frame(pd.DataFrame(), "abc")

    assert calls == [1]
    assert result.empty

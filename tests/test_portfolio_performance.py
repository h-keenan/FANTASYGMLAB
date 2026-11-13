"""Portfolio load-time audit, 2026-11 (docs/performance-audit-portfolio-2026-11.md).

Equivalence and behaviour tests for:

* modules.portfolio_cache (stale-while-revalidate finished rows keyed on a
  fingerprint of every per-user input),
* GET /v1/portfolio/leagues/{id} (cached rows, `signals=defer` headline-first),
* dashboard_engine.build_league_summary(defer_signals=True).

The invariant everywhere: a response built from the cache, or headline-first
followed by the full request, equals the row the pre-optimisation code built
from scratch.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from modules import dashboard_engine, portfolio_cache, redis_cache
from services import mobile_api_service

AUTH_USER = ({"id": "user-123", "email": "gm@example.com"}, "")
PREMIUM_PROFILE = {"entitlement": "premium", "sleeper_username": "gm_dynasty", "status": "ok"}
SAVED_ROWS = [
    {"league_id": "league-a", "league_name": "League A"},
    {"league_id": "league-b", "league_name": "League B"},
]
HEADERS = {"Authorization": "Bearer good-token"}


def _client(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    return TestClient(mobile_api_service.app)


def _summary(league_id: str, *, with_signals: bool = True) -> dict:
    item = {"category": "need", "headline": f"Add depth {league_id}", "reason": "Thin.", "destination": "my_team"}
    return {
        "ok": True,
        "team_name": f"Team {league_id}",
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
        "top_item": item if with_signals else None,
        "top_items": [item] if with_signals else [],
    }


@pytest.fixture
def env(monkeypatch):
    state = {"stance": "", "targets": (), "calls": []}
    monkeypatch.setattr(mobile_api_service.auth_supabase, "fetch_auth_user", lambda *a, **k: AUTH_USER)
    monkeypatch.setattr(mobile_api_service, "_fetch_profile_fields", lambda *a, **k: dict(PREMIUM_PROFILE))
    monkeypatch.setattr(
        mobile_api_service.account_store, "fetch_saved_leagues", lambda *a, **k: (list(SAVED_ROWS), "")
    )
    monkeypatch.setattr(mobile_api_service, "_fetch_team_stance", lambda *a, **k: state["stance"])
    monkeypatch.setattr(mobile_api_service, "_fetch_gm_target_player_ids", lambda *a, **k: (state["targets"], ()))

    def _fake_summary(*, league_id, defer_signals=False, **_kwargs):
        state["calls"].append((league_id, defer_signals))
        return _summary(league_id, with_signals=not defer_signals)

    monkeypatch.setattr(mobile_api_service.dashboard_engine, "build_league_summary", _fake_summary)
    return state


def _row(client, league_id, query=""):
    return client.get(f"/v1/portfolio/leagues/{league_id}{query}", headers=HEADERS).json()


# --- cached rows ----------------------------------------------------------------


def test_second_request_is_served_from_the_cache_and_is_identical(monkeypatch, env):
    client = _client(monkeypatch)
    first = _row(client, "league-a")
    second = _row(client, "league-a")

    assert first["league"] is not None
    assert second == first
    assert [c for c in env["calls"] if c[0] == "league-a"] == [("league-a", False)]


def test_cached_row_equals_the_legacy_single_shot_row(monkeypatch, env):
    client = _client(monkeypatch)
    legacy = client.get("/v1/portfolio", headers=HEADERS).json()  # builds + caches both rows
    per_league = [_row(client, "league-a")["league"], _row(client, "league-b")["league"]]
    assert per_league == legacy["leagues"]
    assert len(env["calls"]) == 2  # legacy built each once; per-league requests were cache hits


def test_changing_a_per_user_input_misses_the_cache(monkeypatch, env):
    client = _client(monkeypatch)
    _row(client, "league-a")
    env["stance"] = "rebuilding"
    _row(client, "league-a")
    env["targets"] = ("123",)
    _row(client, "league-a")
    assert len(env["calls"]) == 3


def test_failed_rows_are_never_cached(monkeypatch, env):
    outcomes = iter([{"ok": False, "reason": "not_a_member_of_league"}, _summary("league-a")])
    monkeypatch.setattr(
        mobile_api_service.dashboard_engine, "build_league_summary", lambda **_k: next(outcomes)
    )
    client = _client(monkeypatch)
    assert _row(client, "league-a")["failed_league"]["reason"] == "not_a_member_of_league"
    assert _row(client, "league-a")["league"] is not None


def test_cached_row_serializes_like_a_freshly_built_one(monkeypatch, env):
    """numpy scalars in a summary must not change shape once they round-trip the cache."""

    import numpy as np

    summary = _summary("league-a")
    summary["wins"] = np.int64(7)
    summary["power_rank"] = np.int64(2)
    monkeypatch.setattr(mobile_api_service.dashboard_engine, "build_league_summary", lambda **_k: dict(summary))
    client = _client(monkeypatch)
    first = _row(client, "league-a")
    second = _row(client, "league-a")
    assert first == second
    assert second["league"]["wins"] == 7 and second["league"]["power_rank"] == 2


# --- stale-while-revalidate ---------------------------------------------------------


def _key_and_age(redis_client, seconds: float) -> str:
    keys = [k for k in redis_client.keys("*portfolio_row*") if b"lock:" not in k]
    assert len(keys) == 1
    import json

    envelope = json.loads(redis_client.get(keys[0]))
    envelope["ts"] = time.time() - seconds
    redis_client.set(keys[0], json.dumps(envelope))
    return keys[0].decode()


def test_stale_row_is_served_immediately_then_refreshed_in_the_background(monkeypatch, env):
    client = _client(monkeypatch)
    _row(client, "league-a")
    redis_client = redis_cache.get_redis_client()
    key = _key_and_age(redis_client, portfolio_cache.FRESH_SECONDS + 5)
    env["calls"].clear()

    served = _row(client, "league-a")
    assert served["league"] is not None  # the stale row, no waiting

    deadline = time.time() + 5
    while time.time() < deadline and not env["calls"]:
        time.sleep(0.02)
    assert env["calls"] == [("league-a", False)]  # exactly one background rebuild
    deadline = time.time() + 5
    import json

    while time.time() < deadline and time.time() - json.loads(redis_client.get(key))["ts"] > 5:
        time.sleep(0.02)
    assert time.time() - json.loads(redis_client.get(key))["ts"] < 5  # refreshed in place


def test_row_older_than_the_stale_window_is_rebuilt_in_the_request(monkeypatch, env):
    client = _client(monkeypatch)
    _row(client, "league-a")
    _key_and_age(redis_cache.get_redis_client(), portfolio_cache.STALE_SECONDS + 5)
    env["calls"].clear()
    assert _row(client, "league-a")["league"] is not None
    assert env["calls"] == [("league-a", False)]


def test_unreachable_redis_just_computes(monkeypatch, env):
    class Down:
        def get(self, *_a, **_k):
            raise ConnectionError("redis down")

        set = delete = get

    monkeypatch.setattr(portfolio_cache.redis_cache, "get_redis_client", lambda: Down())
    client = _client(monkeypatch)
    assert _row(client, "league-a")["league"] is not None


def test_get_row_is_single_flight_across_threads():
    import threading

    key = "portfolio_row:test-single-flight"
    builds = []

    def build():
        builds.append(1)
        time.sleep(0.2)
        return {"league_id": "x"}

    results = []
    threads = [
        threading.Thread(target=lambda: results.append(portfolio_cache.get_row(key, build)[0])) for _ in range(5)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(builds) == 1
    assert results == [{"league_id": "x"}] * 5


# --- headline first ---------------------------------------------------------------------


def test_defer_returns_headline_then_full_row_matches_the_legacy_row(monkeypatch, env):
    client = _client(monkeypatch)
    headline = _row(client, "league-a", "?signals=defer")
    assert headline["signals_pending"] is True
    assert headline["league"]["top_item"] is None and headline["league"]["top_items"] == []
    assert env["calls"] == [("league-a", True)]

    full = _row(client, "league-a")
    assert "signals_pending" not in full
    assert full["league"]["top_items"]  # signals filled in
    headline_fields = {k: v for k, v in headline["league"].items() if k not in ("top_item", "top_items")}
    assert {k: v for k, v in full["league"].items() if k in headline_fields} == headline_fields

    legacy = client.get("/v1/portfolio", headers=HEADERS).json()
    assert full["league"] == legacy["leagues"][0]

    # With the full row cached, a deferred request is answered complete.
    again = _row(client, "league-a", "?signals=defer")
    assert "signals_pending" not in again and again["league"] == full["league"]


def test_defer_does_not_cache_the_headline(monkeypatch, env):
    client = _client(monkeypatch)
    _row(client, "league-a", "?signals=defer")
    _row(client, "league-a", "?signals=defer")
    assert env["calls"] == [("league-a", True), ("league-a", True)]


def test_defer_failure_has_no_signals_pending(monkeypatch, env):
    monkeypatch.setattr(
        mobile_api_service.dashboard_engine,
        "build_league_summary",
        lambda **_k: {"ok": False, "reason": "empty_roster"},
    )
    client = _client(monkeypatch)
    body = _row(client, "league-a", "?signals=defer")
    assert body["failed_league"]["reason"] == "empty_roster"
    assert "signals_pending" not in body


# --- the engine: defer_signals skips the heavy work, changes nothing else -------------------


def _engine_run(defer: bool):
    roster = {"roster_id": 1, "owner_id": "me", "players": ["1", "2"], "settings": {"wins": 5, "losses": 2, "ties": 0}}
    valued = pd.DataFrame(
        {"player_id": ["1", "2", "3"], "name": ["A", "B", "C"], "position": ["QB", "RB", "WR"], "team": ["X"] * 3,
         "player_tier": ["t"] * 3, "dynasty_score": [900, 800, 700]}
    )
    rankings = pd.DataFrame(
        {"roster_id": [1], "power_rank": [3], "power_rank_tied": [False], "franchise_rank": [2],
         "franchise_rank_tied": [False], "roster_value_rank": [4], "roster_value_rank_tied": [False],
         "archetype": ["contender"], "archetype_label": ["Contender"], "strategy": ["contend"], "strategy_label": ["Contend"]}
    )
    briefing = MagicMock()
    item = MagicMock()
    item.to_dict.return_value = {"headline": "h"}
    briefing.items = [item]
    de = dashboard_engine
    mocks = {
        "ideas": MagicMock(return_value=[{"idea": 1}]),
        "posture": MagicMock(return_value={"key": "contend"}),
        "compose": MagicMock(return_value=briefing),
    }
    patches = [
        patch.object(de, "_resolve_sleeper_user_id_for_league_summary", return_value="me"),
        patch.object(de, "_get_league_for_league_summary", return_value={"season": "2026", "league_id": "L"}),
        patch.object(de.sleeper, "default_player_stats_season", return_value=2026),
        patch.object(de, "_get_rosters_for_league_summary", return_value=[roster]),
        patch.object(de.league_value_settings, "detect_league_value_settings_from_payload", return_value={}),
        patch.object(de.league_value_settings, "build_valued_players_frame_cached", return_value=valued),
        patch.object(de.league_value_settings, "valuation_score_field", return_value="dynasty_score"),
        patch.object(de.trade_hub_engine, "roster_posture", mocks["posture"]),
        patch.object(de.trade_hub_engine, "generate_trade_idea_records_cached", mocks["ideas"]),
        patch.object(de.league_calendar, "trade_deadline_passed", return_value=False),
        patch.object(de, "suggest_optimal_lineup", return_value=valued.iloc[:2]),
        patch.object(de, "roster_injury_context", return_value={}),
        patch.object(de.league_rankings, "build_league_rankings_frame_cached", return_value=rankings),
        patch.object(de, "refine_team_directions", side_effect=lambda f: f),
        patch.object(de, "compose_next_move_briefing", mocks["compose"]),
        patch.object(de.injury_ui, "resolve_team_injury_context", return_value={}),
        patch.object(de.injury_ui, "team_injury_display_label", return_value="Stable"),
        patch.object(de, "_get_league_roster_profiles_for_league_summary", return_value={"1": {"team_name": "T"}}),
        patch.object(de.record_signal, "season_progress_fraction", return_value=0.5),
    ]
    for p in patches:
        p.start()
    try:
        result = de.build_league_summary(
            league_id="L", lens="Dynasty", sleeper_username="me", players_db_path="x", defer_signals=defer
        )
    finally:
        for p in reversed(patches):
            p.stop()
    return result, mocks


def test_defer_signals_skips_trade_ideas_posture_and_briefing_but_nothing_else():
    full, full_mocks = _engine_run(defer=False)
    quick, quick_mocks = _engine_run(defer=True)

    assert full["ok"] and quick["ok"]
    assert full_mocks["ideas"].called and full_mocks["compose"].called and full_mocks["posture"].called
    assert not quick_mocks["ideas"].called
    assert not quick_mocks["compose"].called
    assert not quick_mocks["posture"].called

    assert full["top_item"] == {"headline": "h"}
    assert quick["top_item"] is None and quick["top_items"] == []
    strip = lambda d: {k: v for k, v in d.items() if k not in ("top_item", "top_items")}  # noqa: E731
    assert strip(quick) == strip(full)

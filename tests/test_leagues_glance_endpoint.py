"""GET /v1/leagues-glance ("All leagues at a glance") endpoint contracts.

The per-league composition itself (record / waiver / trade / news / need)
is pinned in tests/test_league_glance.py; these pin the endpoint's Premium
gate, aggregation, failure isolation, and short-TTL Redis caching.
Redis is tests/conftest.py's autouse fakeredis, fresh per test.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest


def _client(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")

    from services import mobile_api_service

    return TestClient(mobile_api_service.app)


def _glance_ok(league_id: str) -> dict:
    return {
        "ok": True,
        "reason": "",
        "roster_id": "1",
        "team_name": f"Team {league_id}",
        "record": {
            "wins": 6,
            "losses": 2,
            "ties": 0,
            "record_label": "6-2",
            "standing_rank": 1,
            "team_count": 12,
            "playoff_status": "Playoff seed #1",
            "standings_available": True,
        },
        "waiver": {"player_id": "w1", "name": "Waiver Guy", "position": "WR", "team": "KC", "reason": "Fills WR3."},
        "trade": {"headline": "Get Star Back", "partner_team_name": "Rivals"},
        "news": {"news_count": 3, "injury_count": 1},
        "need": {"category": "true_need", "label": "Biggest Team Need", "value": "TE", "tier_label": "Need"},
    }


def _glance_request(client, *, entitlement="premium", lens="Dynasty"):
    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": entitlement, "sleeper_username": "gm_dynasty"}]
    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        return client.get(f"/v1/leagues-glance?lens={lens}", headers={"Authorization": "Bearer good-token"})


def _stub_supabase_and_news(monkeypatch, mobile_api_service, saved_rows):
    monkeypatch.setattr(mobile_api_service.account_store, "fetch_saved_leagues", lambda *a, **k: (saved_rows, ""))
    monkeypatch.setattr(mobile_api_service, "_fetch_team_stance", lambda *a, **k: "")
    monkeypatch.setattr(mobile_api_service, "_fetch_gm_target_player_ids", lambda *a, **k: ((), ()))
    monkeypatch.setattr(mobile_api_service.news_cache, "schedule_news_cache_refresh", lambda: None)
    monkeypatch.setattr(mobile_api_service.news_cache, "load_cached_news_pool", lambda: [])


def test_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/v1/leagues-glance").status_code == 401


def test_rejects_an_invalid_lens(monkeypatch):
    client = _client(monkeypatch)
    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    with patch("requests.get", return_value=auth_user_response):
        response = client.get("/v1/leagues-glance?lens=Nope", headers={"Authorization": "Bearer good-token"})
    assert response.status_code == 422


def test_free_user_gets_upsell_and_no_league_work_runs(monkeypatch):
    from services import mobile_api_service

    def _must_not_run(*_a, **_k):
        raise AssertionError("no per-league glance work may run for a Free caller")

    monkeypatch.setattr(mobile_api_service.league_glance, "build_league_glance", _must_not_run)
    monkeypatch.setattr(mobile_api_service.account_store, "fetch_saved_leagues", _must_not_run)

    response = _glance_request(_client(monkeypatch), entitlement="free")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["is_premium"] is False
    assert body["leagues"] == []
    assert body["failed_leagues"] == []
    assert body["upsell"]["title"]
    assert body["upsell"]["body"]


def test_free_tier_cap_is_one_league_which_is_why_this_is_premium_only():
    from modules import saved_leagues

    assert saved_leagues.MAX_LEAGUES_FREE == 1


def test_premium_aggregates_in_saved_order_and_isolates_failures(monkeypatch):
    from services import mobile_api_service

    _stub_supabase_and_news(
        monkeypatch,
        mobile_api_service,
        [
            {"league_id": "L-ok-1", "league_name": "First League"},
            {"league_id": "L-skip", "league_name": "Skip League"},
            {"league_id": "L-ok-2", "league_name": "Second League"},
            {"league_id": "L-boom", "league_name": "Boom League"},
        ],
    )

    def _fake_glance(*, league_id, **_k):
        if league_id.startswith("L-ok"):
            return _glance_ok(league_id)
        if league_id == "L-skip":
            return {"ok": False, "reason": "not_a_member_of_league"}
        raise RuntimeError("Sleeper is down")

    monkeypatch.setattr(mobile_api_service.league_glance, "build_league_glance", _fake_glance)

    response = _glance_request(_client(monkeypatch))

    assert response.status_code == 200
    body = response.json()
    assert body["is_premium"] is True
    assert body["upsell"] is None
    assert body["cache_ttl_seconds"] == mobile_api_service.LEAGUE_GLANCE_TTL_SECONDS
    assert [league["league_id"] for league in body["leagues"]] == ["L-ok-1", "L-ok-2"]
    first = body["leagues"][0]
    assert first["league_name"] == "First League"
    assert first["team_name"] == "Team L-ok-1"
    assert first["record"]["record_label"] == "6-2"
    assert first["record"]["standing_rank"] == 1
    assert first["record"]["playoff_status"] == "Playoff seed #1"
    assert first["waiver"] == {
        "player_id": "w1",
        "name": "Waiver Guy",
        "position": "WR",
        "team": "KC",
        "reason": "Fills WR3.",
    }
    assert first["trade"] == {"headline": "Get Star Back", "partner_team_name": "Rivals"}
    assert first["news"] == {"news_count": 3, "injury_count": 1}
    assert first["need"]["value"] == "TE"
    # Trimmed: none of the heavy Dashboard payload leaks into a card.
    assert set(first) == {"league_id", "league_name", "team_name", "record", "waiver", "trade", "news", "need"}

    failed = {row["league_id"]: row["reason"] for row in body["failed_leagues"]}
    assert failed == {"L-skip": "not_a_member_of_league", "L-boom": "unavailable"}


def test_premium_with_no_saved_leagues_is_empty_not_broken(monkeypatch):
    from services import mobile_api_service

    _stub_supabase_and_news(monkeypatch, mobile_api_service, [])
    body = _glance_request(_client(monkeypatch)).json()
    assert body["ok"] is True
    assert body["is_premium"] is True
    assert body["leagues"] == []
    assert body["failed_leagues"] == []


def test_caches_per_league_within_the_ttl(monkeypatch):
    from services import mobile_api_service

    _stub_supabase_and_news(
        monkeypatch,
        mobile_api_service,
        [{"league_id": "L1", "league_name": "One"}, {"league_id": "L2", "league_name": "Two"}],
    )
    stance_reads: list[str] = []
    monkeypatch.setattr(
        mobile_api_service, "_fetch_team_stance", lambda *a, **k: stance_reads.append(a[3]) or ""
    )
    computed: list[tuple[str, str]] = []

    def _fake_glance(*, league_id, lens, **_k):
        computed.append((league_id, lens))
        return _glance_ok(league_id)

    monkeypatch.setattr(mobile_api_service.league_glance, "build_league_glance", _fake_glance)
    client = _client(monkeypatch)

    first = _glance_request(client).json()
    second = _glance_request(client).json()

    assert sorted(computed) == [("L1", "Dynasty"), ("L2", "Dynasty")]
    # The cache wraps the whole per-league compute, so a repeat visit inside
    # the TTL doesn't even re-read Team Situation from Supabase.
    assert sorted(stance_reads) == ["L1", "L2"]
    assert first["leagues"] == second["leagues"]

    # A different lens is a different question: its own cache entries.
    _glance_request(client, lens="Rebuild")
    assert sorted(computed) == [("L1", "Dynasty"), ("L1", "Rebuild"), ("L2", "Dynasty"), ("L2", "Rebuild")]


def test_cache_is_scoped_per_user(monkeypatch):
    from services import mobile_api_service

    assert mobile_api_service._league_glance_cache_key(
        "user-a", "L1", "Dynasty"
    ) != mobile_api_service._league_glance_cache_key("user-b", "L1", "Dynasty")


def test_cache_entry_uses_the_short_ttl(monkeypatch):
    from modules import redis_cache
    from services import mobile_api_service

    assert 60 <= mobile_api_service.LEAGUE_GLANCE_TTL_SECONDS <= 600

    _stub_supabase_and_news(monkeypatch, mobile_api_service, [{"league_id": "L1", "league_name": "One"}])
    monkeypatch.setattr(mobile_api_service.league_glance, "build_league_glance", lambda **k: _glance_ok("L1"))
    _glance_request(_client(monkeypatch))

    key = mobile_api_service._league_glance_cache_key("user-123", "L1", "Dynasty")
    ttl = redis_cache.get_redis_client().ttl(key)
    assert 0 < ttl <= mobile_api_service.LEAGUE_GLANCE_TTL_SECONDS


def test_never_caches_a_failure(monkeypatch):
    from services import mobile_api_service

    _stub_supabase_and_news(monkeypatch, mobile_api_service, [{"league_id": "L1", "league_name": "One"}])
    attempts = {"n": 0}

    def _flaky(**_k):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("transient Sleeper outage")
        return _glance_ok("L1")

    monkeypatch.setattr(mobile_api_service.league_glance, "build_league_glance", _flaky)
    client = _client(monkeypatch)

    first = _glance_request(client).json()
    assert first["leagues"] == []
    assert first["failed_leagues"] == [{"league_id": "L1", "league_name": "One", "reason": "unavailable"}]

    second = _glance_request(client).json()
    assert [league["league_id"] for league in second["leagues"]] == ["L1"]
    assert attempts["n"] == 2


def test_loads_the_news_pool_once_and_only_on_a_cache_miss(monkeypatch):
    from services import mobile_api_service

    _stub_supabase_and_news(
        monkeypatch,
        mobile_api_service,
        [{"league_id": f"L{i}", "league_name": f"League {i}"} for i in range(4)],
    )
    loads = {"n": 0}

    def _load_pool():
        loads["n"] += 1
        return [{"title": "news"}]

    monkeypatch.setattr(mobile_api_service.news_cache, "load_cached_news_pool", _load_pool)
    seen_pools: list = []
    monkeypatch.setattr(
        mobile_api_service.league_glance,
        "build_league_glance",
        lambda *, league_id, news_pool, **_k: seen_pools.append(news_pool) or _glance_ok(league_id),
    )
    client = _client(monkeypatch)

    _glance_request(client)
    assert loads["n"] == 1
    assert seen_pools == [[{"title": "news"}]] * 4

    _glance_request(client)  # every league is a cache hit now
    assert loads["n"] == 1


def test_adds_a_new_route_alongside_dashboard_and_portfolio():
    from services import mobile_api_service

    paths = {route.path for route in mobile_api_service.app.routes}
    assert "/v1/leagues-glance" in paths
    assert "/v1/leagues/{league_id}/dashboard" in paths
    assert "/v1/portfolio" in paths

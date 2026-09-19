"""Mobile API FastAPI service contracts."""

from __future__ import annotations

import contextlib
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _client(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")

    from services import mobile_api_service

    return TestClient(mobile_api_service.app)


@pytest.fixture(autouse=True)
def _clear_trade_hub_ideas_cache():
    # trade_hub_engine._generate_trade_idea_records_cached is keyed by
    # (league_id, roster_id, strategy, lens, players_db_path, time-bucket) —
    # tests reusing the same league_id/roster combo within the same 30s
    # wall-clock bucket would otherwise see a PRIOR test's mocked
    # modules.trade_hub_engine.generate_trade_idea_records result instead of
    # their own, since the cache sits between the caller (both the Trade Hub
    # endpoint and Dashboard's trade tile) and that mockable call.
    from modules import trade_hub_engine

    trade_hub_engine._generate_trade_idea_records_cached.cache_clear()
    yield
    trade_hub_engine._generate_trade_idea_records_cached.cache_clear()


def test_render_yaml_documents_mobile_api_service():
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "fantasygm-lab-mobile-api" in text
    assert "uvicorn services.mobile_api_service:app --host 0.0.0.0 --port $PORT" in text
    assert "healthCheckPath: /health" in text.split("fantasygm-lab-mobile-api", 1)[1]


def test_maybe_schedule_players_refresh_noop_under_pytest(monkeypatch):
    """The guard itself: this test runs under pytest, so PYTEST_CURRENT_TEST
    is genuinely set (not simulated) — confirms the function never even
    reaches the staleness check, let alone schedules a real background
    refresh that would collide with every other test's requests.get mock.
    """

    from services import mobile_api_service

    checked = {"hit": False}
    monkeypatch.setattr(
        mobile_api_service.startup_cold_path,
        "sleeper_players_cache_stale",
        lambda **kwargs: checked.__setitem__("hit", True) or True,
    )
    mobile_api_service._maybe_schedule_players_refresh()
    assert checked["hit"] is False


def test_maybe_schedule_players_refresh_schedules_when_stale(monkeypatch):
    from services import mobile_api_service

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("DYNASTYGM_TEST_MODE", raising=False)
    monkeypatch.setattr(mobile_api_service.startup_cold_path, "sleeper_players_cache_stale", lambda **kwargs: True)
    called: dict = {}

    def fake_schedule(**kwargs):
        called.update(kwargs)
        return {"scheduled": True}

    monkeypatch.setattr(mobile_api_service.players_refresh_flight, "schedule_deferred_players_refresh", fake_schedule)

    mobile_api_service._maybe_schedule_players_refresh()

    assert called["db_path"] == mobile_api_service.PLAYERS_DB_PATH
    assert called["build_players_table_fn"] is mobile_api_service.rankings.build_players_table
    assert called["background"] is True
    assert called["session_state"][mobile_api_service.startup_cold_path.PLAYERS_REFRESH_PENDING_KEY] is True


def test_maybe_schedule_players_refresh_noop_when_fresh(monkeypatch):
    from services import mobile_api_service

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("DYNASTYGM_TEST_MODE", raising=False)
    monkeypatch.setattr(mobile_api_service.startup_cold_path, "sleeper_players_cache_stale", lambda **kwargs: False)
    called = {"hit": False}

    def fake_schedule(**kwargs):
        called["hit"] = True
        return {"scheduled": False}

    monkeypatch.setattr(mobile_api_service.players_refresh_flight, "schedule_deferred_players_refresh", fake_schedule)

    mobile_api_service._maybe_schedule_players_refresh()

    assert called["hit"] is False


def test_health_root_and_ready(monkeypatch):
    client = _client(monkeypatch)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["me"] == "/v1/me"

    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


def test_health_triggers_players_refresh_check_without_auth(monkeypatch):
    # /health needs no Authorization header, unlike every endpoint behind
    # require_user — it's the only route the keep-alive cron actually pings
    # (.github/workflows/keep-alive.yml), so it's also the only reliable,
    # traffic-independent place to catch a stale players cache when no real
    # user has hit an authenticated endpoint in the last hour.
    client = _client(monkeypatch)
    from services import mobile_api_service

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("DYNASTYGM_TEST_MODE", raising=False)
    monkeypatch.setattr(mobile_api_service.startup_cold_path, "sleeper_players_cache_stale", lambda **kwargs: True)
    called: dict = {}

    def fake_schedule(**kwargs):
        called.update(kwargs)
        return {"scheduled": True}

    monkeypatch.setattr(mobile_api_service.players_refresh_flight, "schedule_deferred_players_refresh", fake_schedule)

    response = client.get("/health")

    assert response.status_code == 200
    assert called["db_path"] == mobile_api_service.PLAYERS_DB_PATH


def test_ready_reports_not_ready_without_supabase_config(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

    from services import mobile_api_service

    client = TestClient(mobile_api_service.app)
    ready = client.get("/ready")
    assert ready.status_code == 503
    assert "supabase_not_configured" in ready.json()["issues"]


def test_protected_endpoints_require_bearer_token(monkeypatch):
    client = _client(monkeypatch)

    missing = client.get("/v1/me")
    assert missing.status_code == 401

    malformed = client.get("/v1/me", headers={"Authorization": "Token abc"})
    assert malformed.status_code == 401

    league = client.get("/v1/leagues/123")
    assert league.status_code == 401


def test_me_rejects_invalid_session(monkeypatch):
    client = _client(monkeypatch)

    error_response = Mock(status_code=401)
    error_response.json.return_value = {"error": "invalid token"}
    with patch("requests.get", return_value=error_response):
        response = client.get("/v1/me", headers={"Authorization": "Bearer bad-token"})

    assert response.status_code == 401


def test_me_returns_user_and_entitlement(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "premium"}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get("/v1/me", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["user"]["id"] == "user-123"
    assert body["user"]["email"] == "gm@example.com"
    assert body["user"]["entitlement"] == "premium"
    assert body["user"]["sleeper_username"] == ""
    assert body["user"]["profile_status"] == "ok"


def test_me_returns_linked_sleeper_username(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get("/v1/me", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    assert response.json()["user"]["sleeper_username"] == "gm_dynasty"


def test_me_defaults_to_free_when_profile_lookup_fails(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    profile_response = Mock(status_code=500)

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get("/v1/me", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["entitlement"] == "free"
    # A profile-lookup failure must be distinguishable from a genuine free
    # user — otherwise a paying user hitting a transient error looks and
    # behaves exactly like a non-payer with no signal anything is wrong.
    assert body["user"]["profile_status"] == "error"


def test_me_reports_ok_status_for_a_new_user_with_no_profile_row_yet(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    profile_response = Mock(status_code=200)
    profile_response.json.return_value = []

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get("/v1/me", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["entitlement"] == "free"
    assert body["user"]["profile_status"] == "ok"


def test_league_endpoints_wrap_sleeper_module(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value={"name": "Dynasty League"}):
            league = client.get("/v1/leagues/abc", headers={"Authorization": "Bearer good-token"})
        assert league.status_code == 200
        assert league.json()["league"]["name"] == "Dynasty League"

        with patch("modules.sleeper.get_league", return_value={}):
            missing = client.get("/v1/leagues/abc", headers={"Authorization": "Bearer good-token"})
        assert missing.status_code == 404

        with patch("modules.sleeper.get_users", return_value=[{"user_id": "u1"}]):
            users = client.get("/v1/leagues/abc/users", headers={"Authorization": "Bearer good-token"})
        assert users.status_code == 200
        assert users.json()["users"] == [{"user_id": "u1"}]

        with patch("modules.sleeper.get_rosters", return_value=[{"roster_id": 1}]):
            rosters = client.get("/v1/leagues/abc/rosters", headers={"Authorization": "Bearer good-token"})
        assert rosters.status_code == 200
        assert rosters.json()["rosters"] == [{"roster_id": 1}]

        with patch(
            "modules.sleeper.get_rosters",
            return_value=[{"roster_id": 1, "owner_id": "u1", "metadata": {}}],
        ):
            with patch(
                "modules.sleeper.get_users",
                return_value=[{"user_id": "u1", "display_name": "Alice", "avatar": "abc123"}],
            ):
                profiles = client.get(
                    "/v1/leagues/abc/team-profiles",
                    headers={"Authorization": "Bearer good-token"},
                )
        assert profiles.status_code == 200
        body = profiles.json()["profiles"]
        # Real modules.sleeper.get_league_roster_profiles engine, not a mocked
        # result — exercises the actual team_name/avatar fallback chain.
        assert body["1"]["team_name"] == "Alice"
        assert body["1"]["avatar_url"].endswith("abc123")


def test_my_roster_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/my-roster")
    assert response.status_code == 401


def test_my_roster_reports_no_linked_username(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get("/v1/leagues/abc/my-roster", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["roster"] is None
    assert body["reason"] == "no_sleeper_username_linked"


def test_my_roster_reports_sleeper_user_not_found(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "ghost_gm"}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value=None):
            response = client.get("/v1/leagues/abc/my-roster", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["roster"] is None
    assert body["reason"] == "sleeper_user_not_found"


def test_my_roster_reports_not_a_member(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch("modules.sleeper.get_rosters", return_value=[{"roster_id": 1, "owner_id": "someone-else"}]):
                response = client.get("/v1/leagues/abc/my-roster", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["roster"] is None
    assert body["reason"] == "not_a_member_of_league"


def test_my_roster_returns_matching_roster(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[
                    {"roster_id": 1, "owner_id": "someone-else"},
                    {"roster_id": 2, "owner_id": "sleeper-user-1", "players": ["p1", "p2"]},
                ],
            ):
                response = client.get("/v1/leagues/abc/my-roster", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["reason"] == ""
    assert body["roster"]["roster_id"] == 2
    assert body["roster"]["players"] == ["p1", "p2"]


def _fake_roster_frame():
    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "RB", "WR"]
    rows = []
    for i, position in enumerate(positions, start=1):
        rows.append(
            {
                "player_id": f"my{i}",
                "name": f"My Player {i}",
                "position": position,
                "team": "KC",
                "age": 26,
                "years_exp": 4,
                "status": "Active",
                "injury_status": None,
                "score": 2000,
                "dynasty_score": 2000,
                "value_score": 2000,
                "rebuild_score": 2000,
            }
        )
    # A clearly-weaker bench RB to trade away.
    rows.append(
        {
            "player_id": "my_bench_rb",
            "name": "Bench Runner",
            "position": "RB",
            "team": "KC",
            "age": 30,
            "years_exp": 8,
            "status": "Active",
            "injury_status": None,
            "score": 300,
            "dynasty_score": 300,
            "value_score": 300,
            "rebuild_score": 300,
        }
    )
    # A clearly-better available RB to trade for.
    rows.append(
        {
            "player_id": "target_rb",
            "name": "Target Runner",
            "position": "RB",
            "team": "SF",
            "age": 25,
            "years_exp": 3,
            "status": "Active",
            "injury_status": None,
            "score": 6000,
            "dynasty_score": 6000,
            "value_score": 6000,
            "rebuild_score": 6000,
        }
    )
    return pd.DataFrame(rows)


_TRADE_ANALYZER_LEAGUE = {
    "scoring_settings": {"rec": 1.0},
    "settings": {"type": 2},
    "roster_positions": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "BN", "BN"],
    "total_rosters": 12,
}


def test_trade_analyzer_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.post("/v1/leagues/abc/trade-analyzer", json={"send_player_ids": ["p1"]})
    assert response.status_code == 401


def test_trade_analyzer_rejects_empty_package(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.post(
            "/v1/leagues/abc/trade-analyzer",
            json={},
            headers={"Authorization": "Bearer good-token"},
        )
    assert response.status_code == 422


def test_trade_analyzer_reports_no_linked_username(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.post(
            "/v1/leagues/abc/trade-analyzer",
            json={"send_player_ids": ["my_bench_rb"], "receive_player_ids": ["target_rb"]},
            headers={"Authorization": "Bearer good-token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] is None
    assert body["reason"] == "no_sleeper_username_linked"


def test_trade_analyzer_returns_real_verdict_for_lopsided_upgrade(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids}],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                        with patch(
                            "modules.player_eligibility.filter_current_fantasy_players",
                            side_effect=lambda df, **kwargs: df,
                        ):
                            response = client.post(
                                "/v1/leagues/abc/trade-analyzer",
                                json={
                                    "send_player_ids": ["my_bench_rb"],
                                    "receive_player_ids": ["target_rb"],
                                    "strategy": "contender",
                                },
                                headers={"Authorization": "Bearer good-token"},
                            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    verdict = body["verdict"]
    # A clearly better RB (6000) for a clearly worse one (300) on a
    # contender roster should land as a real accept, not a mocked stub —
    # this exercises the actual fit engine + verdict logic end to end.
    assert verdict["tone"] == "accept"
    assert verdict["value_delta"] > 0
    for key in ("band", "ui_verdict", "confidence", "rationale", "value_summary", "roster_summary"):
        assert key in verdict


def test_trade_analyzer_passes_partner_roster_assets_when_given(monkeypatch):
    """partner_roster_id should resolve to that roster's real players and
    reach decide_offer_verdict as partner_assets — the input
    build_counter_guidance needs to suggest a specific verified asset
    instead of only generic counter text (see modules.trade_offer_analyzer).
    """

    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]
    fake_verdict = SimpleNamespace(to_public_dict=lambda: {"ok": "stub"})

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[
                    {"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids},
                    {"roster_id": 2, "owner_id": "other-user", "players": ["target_rb"]},
                ],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                        with patch(
                            "modules.player_eligibility.filter_current_fantasy_players",
                            side_effect=lambda df, **kwargs: df,
                        ):
                            with patch(
                                "modules.trade_offer_analyzer.decide_offer_verdict",
                                return_value=fake_verdict,
                            ) as mock_decide:
                                response = client.post(
                                    "/v1/leagues/abc/trade-analyzer",
                                    json={
                                        "send_player_ids": ["my_bench_rb"],
                                        "receive_player_ids": [],
                                        "strategy": "contender",
                                        "partner_roster_id": "2",
                                    },
                                    headers={"Authorization": "Bearer good-token"},
                                )

    assert response.status_code == 200
    assert response.json()["verdict"] == {"ok": "stub"}
    partner_assets = mock_decide.call_args.kwargs["partner_assets"]
    assert len(partner_assets) == 1
    assert partner_assets[0]["player_id"] == "target_rb"
    assert partner_assets[0]["owner_roster_id"] == "2"


def test_draft_picks_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/draft-picks")
    assert response.status_code == 401


def _draft_picks_fixture_context():
    """(rosters, users) for a 2-team league whose draft-capital chain is
    already proven to produce real, non-empty pick assets — the exact
    fixture test_team_rankings_returns_power_and_franchise_ranks already
    exercises for the same league (_TRADE_ANALYZER_LEAGUE)."""

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]
    rosters = [
        {"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids},
        {"roster_id": 2, "owner_id": "sleeper-user-2", "players": ["target_rb"]},
    ]
    users = [
        {"user_id": "sleeper-user-1", "display_name": "GM One"},
        {"user_id": "sleeper-user-2", "display_name": "GM Two"},
    ]
    return rosters, users


def test_draft_picks_returns_real_pick_assets(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    fake_rosters, fake_users = _draft_picks_fixture_context()

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
            with patch("modules.sleeper.get_rosters", return_value=fake_rosters):
                with patch("modules.sleeper.get_users", return_value=fake_users):
                    with patch("modules.sleeper.get_traded_picks", return_value=[]):
                        with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                            with patch(
                                "modules.player_eligibility.filter_current_fantasy_players",
                                side_effect=lambda df, **kwargs: df,
                            ):
                                response = client.get(
                                    "/v1/leagues/abc/draft-picks",
                                    headers={"Authorization": "Bearer good-token"},
                                )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    picks = body["picks"]
    # Real modules.trade_ideas.list_draft_pick_assets output, not mocked —
    # a 2-roster dynasty league with no traded picks should generate real
    # future-pick assets for both rosters.
    assert picks
    for pick in picks:
        assert pick["pick_id"] == f"{pick['season']}:{pick['round']}:{pick['original_roster_id']}"
        assert pick["owner_roster_id"] in {"1", "2"}
        assert isinstance(pick["score"], (int, float))


def test_draft_picks_forward_the_full_valuation_breakdown(monkeypatch):
    """The Pick Detail ("PQV for a draft pick") screen renders the model's own
    multipliers and projected-range distribution, so the endpoint must forward
    them rather than dropping everything but the headline score."""

    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    fake_rosters, fake_users = _draft_picks_fixture_context()

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
            with patch("modules.sleeper.get_rosters", return_value=fake_rosters):
                with patch("modules.sleeper.get_users", return_value=fake_users):
                    with patch("modules.sleeper.get_traded_picks", return_value=[]):
                        with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                            with patch(
                                "modules.player_eligibility.filter_current_fantasy_players",
                                side_effect=lambda df, **kwargs: df,
                            ):
                                response = client.get(
                                    "/v1/leagues/abc/draft-picks",
                                    headers={"Authorization": "Bearer good-token"},
                                )

    assert response.status_code == 200
    picks = response.json()["picks"]
    assert picks

    breakdown_fields = (
        "base_score",
        "years_out",
        "future_discount",
        "team_modifier",
        "format_multiplier",
        "class_strength_multiplier",
        "prospect_strength_multiplier",
        "slot_percentile",
        "projected_slot_percentile",
        "early_probability",
        "mid_probability",
        "late_probability",
        "projection_confidence",
    )
    for pick in picks:
        for field in breakdown_fields:
            assert isinstance(pick[field], (int, float)), f"{field} missing/non-numeric"
        assert pick["tier_bucket"] in {"early", "mid", "late"}
        assert pick["projection_source"] == "team_strength_model"
        assert isinstance(pick["is_current_year_pick"], bool)
        # Bucket probabilities are a distribution over the three round slots.
        total = pick["early_probability"] + pick["mid_probability"] + pick["late_probability"]
        assert total == pytest.approx(1.0, abs=1e-6)
        assert 0.0 <= pick["projection_confidence"] <= 1.0


def test_draft_picks_degrade_confidence_for_further_out_seasons(monkeypatch):
    """coridian_'s literal ask — "the further in the future the pics are, it's
    harder" — has to survive the endpoint, not just live in the model: a later
    season's pick must discount harder and project less confidently than the
    same round of the same original roster a year nearer.

    The league fixture only ever emits two pick years (the current draft year
    and the one after it), and `years_out` is 0 for both, so this drives a
    league whose `season` is several years out — that makes the comparison
    deterministic regardless of the wall-clock year the suite runs in.
    """

    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    fake_rosters, fake_users = _draft_picks_fixture_context()
    far_future_league = {**_TRADE_ANALYZER_LEAGUE, "season": "2035"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value=far_future_league):
            with patch("modules.sleeper.get_rosters", return_value=fake_rosters):
                with patch("modules.sleeper.get_users", return_value=fake_users):
                    with patch("modules.sleeper.get_traded_picks", return_value=[]):
                        with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                            with patch(
                                "modules.player_eligibility.filter_current_fantasy_players",
                                side_effect=lambda df, **kwargs: df,
                            ):
                                response = client.get(
                                    "/v1/leagues/abc/draft-picks",
                                    headers={"Authorization": "Bearer good-token"},
                                )

    assert response.status_code == 200
    picks = response.json()["picks"]
    assert picks

    by_key: dict[tuple[str, int], list[dict]] = {}
    for pick in picks:
        by_key.setdefault((pick["original_roster_id"], pick["round"]), []).append(pick)

    compared = 0
    for series in by_key.values():
        series.sort(key=lambda p: p["season"])
        for nearer, further in zip(series, series[1:]):
            assert further["years_out"] > nearer["years_out"]
            assert further["future_discount"] < nearer["future_discount"]
            assert further["projection_confidence"] <= nearer["projection_confidence"]
            compared += 1
    assert compared, "fixture produced no further-out pick to compare"


def test_trade_analyzer_includes_a_real_pick_asset_when_pick_ids_given(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]
    fake_rosters, fake_users = _draft_picks_fixture_context()

    with patch("requests.get", side_effect=[auth_user_response, auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                with patch("modules.sleeper.get_rosters", return_value=fake_rosters):
                    with patch("modules.sleeper.get_users", return_value=fake_users):
                        with patch("modules.sleeper.get_traded_picks", return_value=[]):
                            with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                                with patch(
                                    "modules.player_eligibility.filter_current_fantasy_players",
                                    side_effect=lambda df, **kwargs: df,
                                ):
                                    picks_response = client.get(
                                        "/v1/leagues/abc/draft-picks",
                                        headers={"Authorization": "Bearer good-token"},
                                    )
                                    assert picks_response.status_code == 200
                                    a_pick_id = picks_response.json()["picks"][0]["pick_id"]

                                    response = client.post(
                                        "/v1/leagues/abc/trade-analyzer",
                                        json={
                                            "send_player_ids": ["my_bench_rb"],
                                            "receive_pick_ids": [a_pick_id],
                                            "strategy": "contender",
                                        },
                                        headers={"Authorization": "Bearer good-token"},
                                    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    # A real verdict came back at all — proves the pick_id round-tripped
    # through list_draft_pick_assets -> pick_asset_from_mapping ->
    # trade_analyzer_fit without crashing on a mixed player+pick package.
    assert body["verdict"] is not None


def test_trade_analyzer_reports_assets_not_found_for_an_unknown_pick_id(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]
    fake_rosters, fake_users = _draft_picks_fixture_context()

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch("modules.sleeper.get_rosters", return_value=fake_rosters):
                with patch("modules.sleeper.get_users", return_value=fake_users):
                    with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                        with patch("modules.sleeper.get_traded_picks", return_value=[]):
                            with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                                with patch(
                                    "modules.player_eligibility.filter_current_fantasy_players",
                                    side_effect=lambda df, **kwargs: df,
                                ):
                                    response = client.post(
                                        "/v1/leagues/abc/trade-analyzer",
                                        json={"receive_pick_ids": ["9999:9:999"]},
                                        headers={"Authorization": "Bearer good-token"},
                                    )

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] is None
    assert body["reason"] == "assets_not_found"


def _fake_players_dataset():
    return {
        "1001": {
            "full_name": "Test Player",
            "first_name": "Test",
            "last_name": "Player",
            "position": "WR",
            "team": "KC",
            "status": "Active",
            "injury_status": None,
            "age": 26,
            "number": 10,
            "years_exp": 4,
            "espn_id": "should-not-leak",
            "sportradar_id": "should-not-leak",
        },
    }


def test_players_endpoint_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/players?ids=1001")
    assert response.status_code == 401


def test_players_endpoint_projects_minimal_fields(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_players", return_value=_fake_players_dataset()):
            response = client.get(
                "/v1/players?ids=1001,9999",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    body = response.json()
    assert set(body["players"].keys()) == {"1001"}
    player = body["players"]["1001"]
    assert player["full_name"] == "Test Player"
    assert player["position"] == "WR"
    assert "espn_id" not in player
    assert "sportradar_id" not in player


def test_players_endpoint_rejects_empty_or_oversized_id_list(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        empty = client.get("/v1/players?ids=", headers={"Authorization": "Bearer good-token"})
        assert empty.status_code == 422

        too_many_ids = ",".join(str(i) for i in range(301))
        oversized = client.get(
            f"/v1/players?ids={too_many_ids}",
            headers={"Authorization": "Bearer good-token"},
        )
        assert oversized.status_code == 422


def _fake_players_frame():
    return pd.DataFrame(
        [
            {
                "player_id": "9001",
                "name": "Star Wideout",
                "position": "WR",
                "team": "KC",
                "age": 24,
                "years_exp": 3,
                "status": "Active",
                "injury_status": None,
                "search_rank": 10,
                "score": 8000,
                "dynasty_score": 8000,
                "value_score": 7000,
                "market_score": 8000,
                "role_score": 7500,
                "opportunity_score": 7500,
                "scarcity_score": 7000,
                "risk_multiplier": 1.0,
            },
            {
                "player_id": "9002",
                "name": "Backup Runner",
                "position": "RB",
                "team": "NYJ",
                "age": 29,
                "years_exp": 7,
                "status": "Active",
                "injury_status": None,
                "search_rank": 400,
                "score": 1200,
                "dynasty_score": 1200,
                "value_score": 1500,
                "market_score": 1200,
                "role_score": 1000,
                "opportunity_score": 900,
                "scarcity_score": 800,
                "risk_multiplier": 1.0,
            },
        ]
    )


def test_rankings_endpoint_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/rankings")
    assert response.status_code == 401


def test_rankings_endpoint_rejects_unknown_lens(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.get(
            "/v1/leagues/abc/rankings?lens=Nonsense",
            headers={"Authorization": "Bearer good-token"},
        )
    assert response.status_code == 422


def test_rankings_endpoint_returns_ranked_players_for_real_league_settings(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    fake_league = {
        "scoring_settings": {"rec": 1.0},
        "settings": {"type": 2},
        "roster_positions": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "BN"],
        "total_rosters": 12,
    }

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value=fake_league):
            with patch("modules.rankings.load_players", return_value=_fake_players_frame()):
                with patch(
                    "modules.player_eligibility.filter_current_fantasy_players",
                    side_effect=lambda df, **kwargs: df,
                ):
                    response = client.get(
                        "/v1/leagues/abc/rankings?lens=Dynasty",
                        headers={"Authorization": "Bearer good-token"},
                    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    players = body["players"]
    assert len(players) == 2
    # The genuinely more valuable player ranks first — this exercises the
    # real valuation/ranking engine (modules.league_value_settings), not a
    # mocked result, so a wiring mistake would actually change this order.
    assert players[0]["name"] == "Star Wideout"
    assert players[0]["overall_rank"] == 1
    assert players[1]["name"] == "Backup Runner"
    assert players[1]["overall_rank"] == 2
    for player in players:
        assert "score" in player
        assert "tier" in player
        assert "opportunity_label" in player


def test_rankings_endpoint_returns_404_for_missing_league(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value={}):
            response = client.get(
                "/v1/leagues/missing/rankings",
                headers={"Authorization": "Bearer good-token"},
            )
    assert response.status_code == 404


def test_rankings_endpoint_rejects_bad_limit(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.get(
            "/v1/leagues/abc/rankings?limit=0",
            headers={"Authorization": "Bearer good-token"},
        )
        assert response.status_code == 422

        response = client.get(
            "/v1/leagues/abc/rankings?limit=9999",
            headers={"Authorization": "Bearer good-token"},
        )
        assert response.status_code == 422


def test_player_rank_in_league_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/players/9001/rank")
    assert response.status_code == 401


def test_player_rank_in_league_returns_404_for_missing_league(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value={}):
            response = client.get(
                "/v1/leagues/missing/players/9001/rank",
                headers={"Authorization": "Bearer good-token"},
            )
    assert response.status_code == 404


def test_player_rank_in_league_returns_the_players_real_rank(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    fake_league = {
        "scoring_settings": {"rec": 1.0},
        "settings": {"type": 2},
        "roster_positions": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "BN"],
        "total_rosters": 12,
    }

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value=fake_league):
            with patch("modules.rankings.load_players", return_value=_fake_players_frame()):
                with patch(
                    "modules.player_eligibility.filter_current_fantasy_players",
                    side_effect=lambda df, **kwargs: df,
                ):
                    response = client.get(
                        "/v1/leagues/abc/players/9002/rank?lens=Dynasty",
                        headers={"Authorization": "Bearer good-token"},
                    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    # 9002 ("Backup Runner") is the weaker of the two fake players, so this
    # exercises the real ranking engine landing it at #2, not #1 by accident.
    assert body["player"]["name"] == "Backup Runner"
    assert body["player"]["overall_rank"] == 2


def test_player_rank_in_league_returns_none_for_unknown_player(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    fake_league = {
        "scoring_settings": {"rec": 1.0},
        "settings": {"type": 2},
        "roster_positions": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "BN"],
        "total_rosters": 12,
    }

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value=fake_league):
            with patch("modules.rankings.load_players", return_value=_fake_players_frame()):
                with patch(
                    "modules.player_eligibility.filter_current_fantasy_players",
                    side_effect=lambda df, **kwargs: df,
                ):
                    response = client.get(
                        "/v1/leagues/abc/players/nonexistent/rank",
                        headers={"Authorization": "Bearer good-token"},
                    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "player": None}


def test_news_endpoint_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/news")
    assert response.status_code == 401


def test_news_endpoint_rejects_bad_limit(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.get(
            "/v1/news?limit=0",
            headers={"Authorization": "Bearer good-token"},
        )
        assert response.status_code == 422

        response = client.get(
            "/v1/news?limit=9999",
            headers={"Authorization": "Bearer good-token"},
        )
        assert response.status_code == 422


def test_news_endpoint_filters_to_actionable_signal_and_dedupes(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    fake_pool = [
        {
            "title": "Star RB (knee) questionable for Sunday",
            "summary": "The team's RB1 was limited in practice with a knee issue.",
            "link": "https://example.com/injury-1",
            "source": "https://www.espn.com/espn/rss/nfl/news",
            "published_ts": 1000.0,
        },
        # Off-topic — no injury/role/transaction/off-field signal, should be dropped.
        {
            "title": "Celebrity attends game, wears fun hat",
            "summary": "A celebrity wore a hat at the game.",
            "link": "https://example.com/celebrity",
            "source": "https://www.espn.com/espn/rss/nfl/news",
            "published_ts": 2000.0,
        },
        # Duplicate link of the injury item above (different casing) — deduped.
        {
            "title": "Star RB (knee) questionable for Sunday",
            "summary": "The team's RB1 was limited in practice with a knee issue.",
            "link": "HTTPS://EXAMPLE.COM/injury-1",
            "source": "https://www.espn.com/espn/rss/nfl/news",
            "published_ts": 1000.0,
        },
        {
            "title": "Team trades WR to division rival",
            "summary": "A trade sends a wide receiver across the division.",
            "link": "https://example.com/trade-1",
            "source": "https://www.espn.com/espn/rss/nfl/news",
            "published_ts": 3000.0,
        },
    ]

    from modules import news as news_module

    news_module.clear_enriched_news_pool_cache()
    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.news.schedule_news_cache_refresh", return_value=False):
            with patch("modules.news.load_cached_news_pool", return_value=fake_pool):
                response = client.get(
                    "/v1/news",
                    headers={"Authorization": "Bearer good-token"},
                )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    items = body["items"]
    # Celebrity item dropped (no actionable signal); injury duplicate deduped;
    # most-recent-first ordering (trade at 3000 before injury at 1000).
    assert len(items) == 2
    assert items[0]["title"] == "Team trades WR to division rival"
    assert items[0]["event_type"] == "transaction"
    assert items[0]["source"] == "ESPN"
    assert items[1]["title"] == "Star RB (knee) questionable for Sunday"
    assert items[1]["event_type"] == "injury/status"
    for item in items:
        assert "summary" in item
        assert "speculative" in item


def test_friendly_news_source_maps_known_feed_domains(monkeypatch):
    from services.mobile_api_service import _friendly_news_source

    assert _friendly_news_source("https://www.rotowire.com/rss/news.php?sport=NFL") == "RotoWire"
    assert _friendly_news_source("https://www.espn.com/espn/rss/nfl/news") == "ESPN"
    assert _friendly_news_source("https://www.cbssports.com/rss/headlines/nfl/") == "CBS Sports"
    assert _friendly_news_source("https://sports.yahoo.com/nfl/rss/") == "Yahoo Sports"
    assert _friendly_news_source("https://www.nbcsports.com/profootballtalk.rss") == "Pro Football Talk"
    # Unknown source falls back to the bare domain rather than a raw URL.
    assert _friendly_news_source("https://www.example.com/some/feed.xml") == "example.com"
    assert _friendly_news_source("") == ""


def test_player_news_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/players/9001/news")
    assert response.status_code == 401


def test_player_news_matches_articles_mentioning_the_player_by_name(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    players_frame = pd.DataFrame([{"player_id": "9001", "name": "Nico Collins"}])

    fake_pool = [
        {
            "title": "Nico Collins (hamstring) questionable for Sunday",
            "summary": "The Texans WR was limited in practice.",
            "link": "https://example.com/collins-injury",
            "source": "https://www.espn.com/espn/rss/nfl/news",
            "published_ts": 2000.0,
        },
        # Different player entirely — must not match.
        {
            "title": "Team trades WR to division rival",
            "summary": "A trade sends a wide receiver across the division.",
            "link": "https://example.com/trade-1",
            "source": "https://www.espn.com/espn/rss/nfl/news",
            "published_ts": 3000.0,
        },
    ]

    from modules import news as news_module

    news_module.clear_enriched_news_pool_cache()
    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.rankings.load_players", return_value=players_frame):
            with patch("modules.news.schedule_news_cache_refresh", return_value=False):
                with patch("modules.news.load_cached_news_pool", return_value=fake_pool):
                    response = client.get(
                        "/v1/players/9001/news",
                        headers={"Authorization": "Bearer good-token"},
                    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Nico Collins (hamstring) questionable for Sunday"
    assert body["items"][0]["event_type"] == "injury/status"


def test_player_news_returns_empty_for_unknown_player(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    players_frame = pd.DataFrame([{"player_id": "9001", "name": "Nico Collins"}])

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.rankings.load_players", return_value=players_frame):
            response = client.get(
                "/v1/players/does-not-exist/news",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "items": []}


def test_player_news_rejects_bad_limit(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.get(
            "/v1/players/9001/news?limit=0",
            headers={"Authorization": "Bearer good-token"},
        )
        assert response.status_code == 422

        response = client.get(
            "/v1/players/9001/news?limit=9999",
            headers={"Authorization": "Bearer good-token"},
        )
        assert response.status_code == 422


_RECAP_LEAGUE = {
    "season": "2026",
    "settings": {"leg": 3, "last_scored_leg": 3, "playoff_week_start": 15},
}


def _recap_matchups(league_id: str, week: int):
    if week not in (1, 2, 3):
        return []
    return [
        {"roster_id": 1, "matchup_id": 1, "points": 130.5},
        {"roster_id": 2, "matchup_id": 1, "points": 98.2},
    ]


def _recap_transactions(league_id: str, week: int):
    if week != 3:
        return []
    return [
        {
            "type": "waiver",
            "status": "complete",
            "adds": {"9001": 1},
            "drops": None,
            "roster_ids": [1],
            "status_updated": 1700000000000,
            "transaction_id": "tx1",
            "settings": {"waiver_bid": 12},
        }
    ]


def test_recap_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/recap")
    assert response.status_code == 401


def test_recap_returns_404_for_missing_league(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value={}):
            response = client.get("/v1/leagues/missing/recap", headers={"Authorization": "Bearer good-token"})
    assert response.status_code == 404


def test_recap_reports_no_completed_week(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value=_RECAP_LEAGUE):
            with patch("modules.sleeper.get_matchups", return_value=[]):
                response = client.get("/v1/leagues/abc/recap", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["recap"] is None
    assert body["reason"] == "no_completed_week"
    assert body["max_completed_week"] == 0


def test_recap_returns_real_weekly_recap(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    fake_profiles = {
        "1": {"team_name": "Home Team", "owner_name": "Alice", "username": "alice"},
        "2": {"team_name": "Away Team", "owner_name": "Bob", "username": "bob"},
    }

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value=_RECAP_LEAGUE):
            with patch("modules.sleeper.get_matchups", side_effect=_recap_matchups):
                with patch("modules.sleeper.get_transactions", side_effect=_recap_transactions):
                    with patch("modules.sleeper.get_league_roster_profiles", return_value=fake_profiles):
                        with patch("modules.rankings.load_players", return_value=_fake_players_frame()):
                            with patch(
                                "modules.player_eligibility.filter_current_fantasy_players",
                                side_effect=lambda df, **kwargs: df,
                            ):
                                response = client.get(
                                    "/v1/leagues/abc/recap",
                                    headers={"Authorization": "Bearer good-token"},
                                )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    recap = body["recap"]
    assert recap is not None
    assert recap["week"] == 3
    assert recap["season"] == "2026"
    # Real story generation (modules.league_recaps.build_weekly_recap), not a
    # mocked result — a wiring mistake (e.g. bad profiles/player_lookup shape)
    # would leave this empty.
    assert recap["stories"]
    assert recap["incomplete"] is False
    assert body["max_completed_week"] == 3


def test_recap_accepts_an_explicit_past_week(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    fake_profiles = {
        "1": {"team_name": "Home Team", "owner_name": "Alice", "username": "alice"},
        "2": {"team_name": "Away Team", "owner_name": "Bob", "username": "bob"},
    }

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value=_RECAP_LEAGUE):
            with patch("modules.sleeper.get_matchups", side_effect=_recap_matchups):
                with patch("modules.sleeper.get_transactions", side_effect=_recap_transactions):
                    with patch("modules.sleeper.get_league_roster_profiles", return_value=fake_profiles):
                        with patch("modules.rankings.load_players", return_value=_fake_players_frame()):
                            with patch(
                                "modules.player_eligibility.filter_current_fantasy_players",
                                side_effect=lambda df, **kwargs: df,
                            ):
                                response = client.get(
                                    "/v1/leagues/abc/recap?week=2",
                                    headers={"Authorization": "Bearer good-token"},
                                )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    # Week 2 has matchups but (per _recap_transactions) no transactions —
    # build_weekly_recap should still return a real recap for that week,
    # not silently fall back to the latest completed week (3).
    assert body["recap"] is not None
    assert body["recap"]["week"] == 2
    assert body["max_completed_week"] == 3


def test_recap_rejects_a_week_outside_the_completed_range(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value=_RECAP_LEAGUE):
            with patch("modules.sleeper.get_matchups", side_effect=_recap_matchups):
                response = client.get(
                    "/v1/leagues/abc/recap?week=99",
                    headers={"Authorization": "Bearer good-token"},
                )

    assert response.status_code == 422


def test_roster_relationship_map_classifies_every_slot():
    from services.mobile_api_service import _roster_relationship_map

    roster = {
        "players": ["starter1", "bench1", "taxi1", "ir1"],
        "starters": ["starter1"],
        "taxi": ["taxi1"],
        "reserve": ["ir1"],
    }
    result = _roster_relationship_map(roster)
    assert result == {
        "starter1": "starter",
        "bench1": "bench",
        "taxi1": "taxi",
        "ir1": "ir",
    }


def test_roster_relationship_map_reserve_wins_over_starter():
    from services.mobile_api_service import _roster_relationship_map

    # A player can't actually be both, but if Sleeper's payload ever listed
    # someone as both a starter and on IR, IR should win — a player parked
    # on IR isn't really "starting" regardless of the starters array.
    roster = {"players": ["p1"], "starters": ["p1"], "reserve": ["p1"], "taxi": []}
    assert _roster_relationship_map(roster) == {"p1": "ir"}


def test_roster_relationship_map_handles_missing_keys():
    from services.mobile_api_service import _roster_relationship_map

    assert _roster_relationship_map({"players": ["p1"]}) == {"p1": "bench"}
    assert _roster_relationship_map({}) == {}


def test_alerts_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/alerts")
    assert response.status_code == 401


def test_alerts_rejects_bad_limit(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.get(
            "/v1/leagues/abc/alerts?limit=0",
            headers={"Authorization": "Bearer good-token"},
        )
    assert response.status_code == 422


def test_alerts_reports_no_linked_username(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get("/v1/leagues/abc/alerts", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["reason"] == "no_sleeper_username_linked"


def test_alerts_returns_real_roster_relevant_news(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    fake_pool = [
        {
            "title": "Star Wideout (ankle) limited in practice",
            "summary": "The receiver was limited with an ankle issue heading into Sunday.",
            "link": "https://example.com/star-wideout-injury",
            "source": "https://www.espn.com/espn/rss/nfl/news",
            "published_ts": 1000.0,
        },
        {
            "title": "Unrelated player signs endorsement deal",
            "summary": "A player not on this roster signed a new deal.",
            "link": "https://example.com/unrelated",
            "source": "https://www.espn.com/espn/rss/nfl/news",
            "published_ts": 2000.0,
        },
    ]

    read_keys_response = Mock(status_code=200)
    read_keys_response.json.return_value = []

    with patch("requests.get", side_effect=[auth_user_response, profile_response, read_keys_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": ["9001"]}],
            ):
                with patch("modules.rankings.load_players", return_value=_fake_players_frame()):
                    with patch("modules.news.schedule_news_cache_refresh", return_value=False):
                        with patch("modules.news.load_cached_news_pool", return_value=fake_pool):
                            response = client.get(
                                "/v1/leagues/abc/alerts",
                                headers={"Authorization": "Bearer good-token"},
                            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    items = body["items"]
    # Only the roster-relevant item survives — this exercises the real
    # modules.my_news filtering/curation, not a mocked result.
    assert len(items) == 1
    assert items[0]["matched_player"] == "Star Wideout"
    assert items[0]["matched_player_id"] == "9001"
    assert "ankle" in items[0]["title"].casefold()
    assert items[0]["read"] is False
    assert items[0]["alert_key"]
    # Roster fixture has no starters/taxi/reserve keys at all — a rostered
    # player who isn't in any of those falls through to "bench", not a
    # crash on a missing key.
    assert items[0]["roster_relationship"] == "bench"


def test_alerts_reports_the_real_roster_relationship_for_each_slot(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    fake_pool = [
        {
            "title": "Star Wideout (ankle) limited in practice",
            "summary": "The receiver was limited with an ankle issue.",
            "link": "https://example.com/star-wideout-injury",
            "source": "https://www.espn.com/espn/rss/nfl/news",
            "published_ts": 1000.0,
        },
    ]
    read_keys_response = Mock(status_code=200)
    read_keys_response.json.return_value = []

    with patch("requests.get", side_effect=[auth_user_response, profile_response, read_keys_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[
                    {
                        "roster_id": 1,
                        "owner_id": "sleeper-user-1",
                        "players": ["9001"],
                        "starters": ["9001"],
                        "taxi": [],
                        "reserve": [],
                    }
                ],
            ):
                with patch("modules.rankings.load_players", return_value=_fake_players_frame()):
                    with patch("modules.news.schedule_news_cache_refresh", return_value=False):
                        with patch("modules.news.load_cached_news_pool", return_value=fake_pool):
                            response = client.get(
                                "/v1/leagues/abc/alerts",
                                headers={"Authorization": "Bearer good-token"},
                            )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["roster_relationship"] == "starter"


def test_alerts_marks_items_already_read(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    fake_pool = [
        {
            "title": "Star Wideout (ankle) limited in practice",
            "summary": "The receiver was limited with an ankle issue.",
            "link": "https://example.com/star-wideout-injury",
            "source": "https://www.espn.com/espn/rss/nfl/news",
            "published_ts": 1000.0,
        },
    ]
    from services.mobile_api_service import _alert_key_for_link

    already_read_key = _alert_key_for_link("https://example.com/star-wideout-injury")
    read_keys_response = Mock(status_code=200)
    read_keys_response.json.return_value = [{"alert_key": already_read_key}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response, read_keys_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": ["9001"]}],
            ):
                with patch("modules.rankings.load_players", return_value=_fake_players_frame()):
                    with patch("modules.news.schedule_news_cache_refresh", return_value=False):
                        with patch("modules.news.load_cached_news_pool", return_value=fake_pool):
                            response = client.get(
                                "/v1/leagues/abc/alerts",
                                headers={"Authorization": "Bearer good-token"},
                            )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["read"] is True


def test_mark_alert_read_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.post("/v1/leagues/abc/alerts/read", json={"alert_key": "abc123"})
    assert response.status_code == 401


def test_mark_alert_read_rejects_empty_key(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.post(
            "/v1/leagues/abc/alerts/read",
            json={"alert_key": ""},
            headers={"Authorization": "Bearer good-token"},
        )
    assert response.status_code == 422


def test_mark_alert_read_writes_with_callers_own_token(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    post_response = Mock(status_code=201)

    with patch("requests.get", return_value=auth_user_response):
        with patch("requests.post", return_value=post_response) as mock_post:
            response = client.post(
                "/v1/leagues/abc/alerts/read",
                json={"alert_key": "abc123"},
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "reason": ""}
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer good-token"
    assert call_kwargs["json"] == {"user_id": "user-123", "league_id": "abc", "alert_key": "abc123"}


def test_mark_alert_read_fails_closed_when_table_missing(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    post_response = Mock(status_code=404)

    with patch("requests.get", return_value=auth_user_response):
        with patch("requests.post", return_value=post_response):
            response = client.post(
                "/v1/leagues/abc/alerts/read",
                json={"alert_key": "abc123"},
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"ok": False, "reason": "not_available"}


def _fake_quick_view_frame():
    return pd.DataFrame(
        [
            {
                "player_id": "9001",
                "name": "Star Wideout",
                "position": "WR",
                "years_exp": 3,
                "games_played": 10,
                "stats_season": 2026,
                "targets": 80,
                "receptions": 60,
                "receiving_yards": 900,
                "receiving_tds": 7,
                "fantasy_points_ppr": 210.5,
                "fantasy_points_half_ppr": 180.0,
                "fantasy_points_std": 150.0,
                "ppg": 21.0,
                "snap_share": 0.72,
                "target_share": 0.28,
            },
            {
                "player_id": "9002",
                "name": "No Stats Rookie",
                "position": "WR",
                "years_exp": 0,
            },
        ]
    )


def test_quick_view_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/players/9001/quick-view")
    assert response.status_code == 401


def test_quick_view_reports_not_found_for_unknown_player(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.rankings.load_players", return_value=_fake_quick_view_frame()):
            response = client.get(
                "/v1/players/does-not-exist/quick-view",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["stats"] is None
    assert body["bio"] is None
    assert body["model"] is None
    assert body["reason"] == "not_found"


def test_quick_view_returns_real_season_stats_and_bio(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.rankings.load_players", return_value=_fake_quick_view_frame()):
            response = client.get(
                "/v1/players/9001/quick-view",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    stats = body["stats"]
    # Real modules.player_quick_view engine, not a mocked result — this
    # exercises the same code path the web app's player dossier pop-up uses.
    assert stats["position"] == "WR"
    assert len(stats["seasons"]) == 1
    season = stats["seasons"][0]
    assert season["season"] == 2026
    assert season["games"] == 10
    key_stat_labels = {item["label"] for item in season["key_stats"]}
    assert "Rec Yards" in key_stat_labels
    usage_labels = {item["label"] for item in season["usage"]}
    assert "Snap %" in usage_labels
    assert body["bio"]["years_in_league"] == "3 seasons"
    # The fixture has no market/opportunity/etc. columns at all — a
    # defensive shape (all fields None, no crash), not the "real values"
    # case, which is covered by the dedicated model tests below.
    assert body["model"] is not None
    assert body["model"]["market_score"] is None
    assert body["model"]["age_score_label"] == "Age Lens"


def test_quick_view_reports_no_seasons_when_stats_unavailable(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.rankings.load_players", return_value=_fake_quick_view_frame()):
            response = client.get(
                "/v1/players/9002/quick-view",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["stats"]["seasons"] == []
    assert body["bio"]["years_in_league"] == "Rookie"


def test_quick_view_model_projects_real_score_columns(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    frame = pd.DataFrame(
        [
            {
                "player_id": "9003",
                "name": "Model Player",
                "position": "RB",
                "years_exp": 4,
                "market_score": 71.4,
                "opportunity_score": 82.9,
                "scarcity_score": 65.0,
                "role_score": 90.2,
                "age_score": 55.6,
                "opportunity_confidence": 78,
                "workload_trend": "Rising",
            }
        ]
    )

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.rankings.load_players", return_value=frame):
            response = client.get(
                "/v1/players/9003/quick-view",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    model = response.json()["model"]
    assert model["market_score"] == 71.4
    assert model["opportunity_score"] == 82.9
    assert model["scarcity_score"] == 65.0
    assert model["role_score"] == 90.2
    # A native age_score column present (not NaN) wins the "Age Score" label
    # over the coarser age_penalty fallback.
    assert model["age_score"] == 55.6
    assert model["age_score_label"] == "Age Score"
    assert model["opportunity_confidence"] == 78
    assert model["workload_trend"] == "Rising"


def test_quick_view_model_falls_back_to_age_lens_when_age_score_missing(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    frame = pd.DataFrame(
        [
            {
                "player_id": "9004",
                "name": "Lens Player",
                "position": "RB",
                "years_exp": 2,
                "age_penalty": -12.5,
            }
        ]
    )

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.rankings.load_players", return_value=frame):
            response = client.get(
                "/v1/players/9004/quick-view",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    model = response.json()["model"]
    # No age_score column at all: falls back to age_penalty under the
    # "Age Lens" label instead of the "Age Score" one.
    assert model["age_score"] == -12.5
    assert model["age_score_label"] == "Age Lens"


def _usage_trend_frame(player_id: str, **recency):
    row = {
        "player_id": player_id,
        "name": "Trend Player",
        "position": "RB",
        "years_exp": 3,
        "opportunity_label": "Committee Back",
        "workload_trend": "Rising",
    }
    row.update(recency)
    return pd.DataFrame([row])


def test_quick_view_model_exposes_the_usage_trend_read(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    frame = _usage_trend_frame(
        "9005",
        recency_sample_n=7,
        recency_trend=0.22,
        recency_confidence=1.0,
        recency_usage_rate=17.5,
        recency_baseline_rate=14.3,
    )

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.rankings.load_players", return_value=frame):
            response = client.get(
                "/v1/players/9005/quick-view",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    trend = response.json()["model"]["usage_trend"]
    # Already-computed recency columns, formatted by the one shared helper —
    # the API states the same read the web dossier shows, not a new one.
    assert trend["direction"] == "up"
    assert trend["trend_pct"] == 22
    assert trend["confidence_key"] == "high"
    assert trend["summary"] == "Usage trending up 22% (high confidence)"
    assert trend["sample_n"] == 7


def test_quick_view_model_sends_no_usage_trend_below_the_display_gate(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    # Three usable games is the sample the valuation blend deliberately
    # discounts, so the client is told nothing rather than shown a weak read.
    thin = _usage_trend_frame(
        "9006", recency_sample_n=3, recency_trend=0.31, recency_confidence=0.3333
    )
    # A player with no recency columns at all must not blow up the projection.
    bare = _usage_trend_frame("9007")

    for player_id, frame in (("9006", thin), ("9007", bare)):
        with patch("requests.get", return_value=auth_user_response):
            with patch("modules.rankings.load_players", return_value=frame):
                response = client.get(
                    f"/v1/players/{player_id}/quick-view",
                    headers={"Authorization": "Bearer good-token"},
                )
        assert response.status_code == 200
        assert response.json()["model"]["usage_trend"] is None


def test_rankings_rows_carry_the_usage_trend_beside_opportunity_label(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    fake_league = {
        "scoring_settings": {"rec": 1.0},
        "settings": {"type": 2},
        "roster_positions": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "BN"],
        "total_rosters": 12,
    }

    frame = _fake_players_frame()
    frame["recency_sample_n"] = [6, 3]
    frame["recency_trend"] = [0.19, 0.30]
    frame["recency_confidence"] = [1.0, 0.3333]
    frame["recency_usage_rate"] = [9.1, 6.0]
    frame["recency_baseline_rate"] = [7.6, 4.6]

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value=fake_league):
            with patch("modules.rankings.load_players", return_value=frame):
                with patch(
                    "modules.player_eligibility.filter_current_fantasy_players",
                    side_effect=lambda df, **kwargs: df,
                ):
                    response = client.get(
                        "/v1/leagues/abc/rankings?lens=Dynasty",
                        headers={"Authorization": "Bearer good-token"},
                    )

    assert response.status_code == 200
    by_name = {player["name"]: player for player in response.json()["players"]}
    strong = by_name["Star Wideout"]["usage_trend"]
    assert strong is not None
    assert strong["direction"] == "up"
    assert strong["magnitude_pct"] == 19
    assert strong["confidence_key"] == "high"
    # Same gate as everywhere else: a 3-game read never reaches the client.
    assert by_name["Backup Runner"]["usage_trend"] is None


def test_weekly_stats_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/players/9001/weekly-stats")
    assert response.status_code == 401


def test_weekly_stats_defaults_to_current_season(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    fake_weekly = {
        "9001": {
            "stats_season": 2026,
            "weekly": [
                {"week": 1, "fantasy_points_ppr": 18.4, "snap_share": 0.72},
                {"week": 2, "fantasy_points_ppr": 9.1, "snap_share": 0.55},
            ],
        }
    }

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.default_player_stats_season", return_value=2026):
            with patch("modules.sleeper.get_season_player_stats", return_value=fake_weekly) as mock_stats:
                response = client.get(
                    "/v1/players/9001/weekly-stats",
                    headers={"Authorization": "Bearer good-token"},
                )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["season"] == 2026
    assert body["weeks"] == [
        {"week": 1, "fantasy_points_ppr": 18.4, "snap_share": 0.72},
        {"week": 2, "fantasy_points_ppr": 9.1, "snap_share": 0.55},
    ]
    mock_stats.assert_called_once_with(2026, retain_weekly=True)


def test_weekly_stats_accepts_an_explicit_prior_season(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    fake_weekly = {"9001": {"stats_season": 2025, "weekly": [{"week": 1, "fantasy_points_ppr": 5.0, "snap_share": 0.3}]}}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.default_player_stats_season", return_value=2026):
            with patch("modules.sleeper.get_season_player_stats", return_value=fake_weekly) as mock_stats:
                response = client.get(
                    "/v1/players/9001/weekly-stats?season=2025",
                    headers={"Authorization": "Bearer good-token"},
                )

    assert response.status_code == 200
    assert response.json()["season"] == 2025
    mock_stats.assert_called_once_with(2025, retain_weekly=True)


def test_weekly_stats_rejects_a_season_too_far_in_the_past(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.default_player_stats_season", return_value=2026):
            response = client.get(
                "/v1/players/9001/weekly-stats?season=2000",
                headers={"Authorization": "Bearer good-token"},
            )
    assert response.status_code == 422


def test_weekly_stats_returns_empty_for_a_player_with_no_weekly_rows(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.default_player_stats_season", return_value=2026):
            with patch("modules.sleeper.get_season_player_stats", return_value={}):
                response = client.get(
                    "/v1/players/does-not-exist/weekly-stats",
                    headers={"Authorization": "Bearer good-token"},
                )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["weeks"] == []


def test_gm_targets_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/v1/leagues/abc/gm-targets").status_code == 401
    assert client.post("/v1/leagues/abc/gm-targets", json={"player_id": "1"}).status_code == 401
    assert client.delete("/v1/leagues/abc/gm-targets/1").status_code == 401


def test_get_gm_targets_returns_watchlist(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    targets_response = Mock(status_code=200)
    targets_response.json.return_value = [
        {"player_id": "9001", "source_surface": "player_quick_view", "created_at": "2026-09-01T00:00:00Z"},
    ]

    with patch("requests.get", side_effect=[auth_user_response, targets_response]):
        response = client.get("/v1/leagues/abc/gm-targets", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["targets"] == [
        {"player_id": "9001", "source_surface": "player_quick_view", "created_at": "2026-09-01T00:00:00Z"},
    ]


def test_get_gm_targets_fails_soft_when_table_unreachable(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    error_response = Mock(status_code=404)
    error_response.json.return_value = {"message": "relation does not exist"}

    with patch("requests.get", side_effect=[auth_user_response, error_response]):
        response = client.get("/v1/leagues/abc/gm-targets", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    assert response.json() == {"ok": True, "targets": []}


def test_add_gm_target_rejects_empty_player_id(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.post(
            "/v1/leagues/abc/gm-targets",
            json={"player_id": ""},
            headers={"Authorization": "Bearer good-token"},
        )
    assert response.status_code == 422


def test_add_gm_target_enforces_free_tier_cap(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]
    existing_response = Mock(status_code=200)
    existing_response.json.return_value = [
        {"player_id": "1"}, {"player_id": "2"}, {"player_id": "3"},
    ]

    with patch("requests.get", side_effect=[auth_user_response, profile_response, existing_response]):
        response = client.post(
            "/v1/leagues/abc/gm-targets",
            json={"player_id": "9999"},
            headers={"Authorization": "Bearer good-token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["reason"] == "at_cap"
    assert body["cap"] == 3


def test_add_gm_target_upserts_when_under_cap(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "premium", "sleeper_username": ""}]
    existing_response = Mock(status_code=200)
    existing_response.json.return_value = []
    upsert_response = Mock(status_code=201)

    with patch("requests.get", side_effect=[auth_user_response, profile_response, existing_response]):
        with patch("requests.post", return_value=upsert_response) as mock_post:
            response = client.post(
                "/v1/leagues/abc/gm-targets",
                json={"player_id": "9001", "source_surface": "player_quick_view"},
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "reason": ""}
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"] == {
        "user_id": "user-123",
        "league_id": "abc",
        "player_id": "9001",
        "source_surface": "player_quick_view",
    }


def test_remove_gm_target_deletes_row(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    delete_response = Mock(status_code=200)

    with patch("requests.get", return_value=auth_user_response):
        with patch("requests.delete", return_value=delete_response) as mock_delete:
            response = client.delete(
                "/v1/leagues/abc/gm-targets/9001",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "reason": ""}
    requested_url = mock_delete.call_args.args[0]
    assert "user_id=eq.user-123" in requested_url
    assert "league_id=eq.abc" in requested_url
    assert "player_id=eq.9001" in requested_url


def test_player_awards_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/players/9001/awards")
    assert response.status_code == 401


def test_player_awards_reports_not_found_for_unknown_player(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.rankings.load_players", return_value=_fake_quick_view_frame()):
            response = client.get(
                "/v1/players/does-not-exist/awards",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["awards"] == []
    assert body["reason"] == "not_found"


def test_player_awards_returns_real_badges_for_a_qualifying_season(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    players_frame = pd.DataFrame([{"player_id": "9001", "name": "Star Wideout", "position": "WR"}])
    fake_index = (
        {
            "path": "data/sleeper_player_stats_2025.json",
            "season": 2025,
            "payload": {
                "9001": {
                    "stats_season": 2025,
                    "receiving_yards": 1600,
                    "fantasy_points_ppr": 50.0,
                },
                "9002": {"stats_season": 2025, "fantasy_points_ppr": 10.0},
            },
        },
    )

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.rankings.load_players", return_value=players_frame):
            with patch("modules.player_awards.build_season_cache_index", return_value=fake_index):
                response = client.get(
                    "/v1/players/9001/awards",
                    headers={"Authorization": "Bearer good-token"},
                )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    # Real modules.player_awards engine, not a mocked result — 1600 receiving
    # yards clears the WR gold threshold (>= 1500).
    assert any(award["short_label"] == "1,500+ Rec Yds" for award in body["awards"])
    for award in body["awards"]:
        assert award["tier"] in {"gold", "silver", "bronze", None}


def test_register_push_token_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.post("/v1/push/register", json={"expo_push_token": "ExponentPushToken[abc]"})
    assert response.status_code == 401


def test_register_push_token_rejects_malformed_token(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.post(
            "/v1/push/register",
            json={"expo_push_token": "not-a-real-token"},
            headers={"Authorization": "Bearer good-token"},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": False, "reason": "not_available"}


def test_register_push_token_upserts_with_callers_own_token(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    upsert_response = Mock(status_code=201)

    with patch("requests.get", return_value=auth_user_response):
        with patch("requests.post", return_value=upsert_response) as mock_post:
            response = client.post(
                "/v1/push/register",
                json={
                    "expo_push_token": "ExponentPushToken[abc123]",
                    "platform": "ios",
                    "device_name": "Test iPhone",
                },
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "reason": ""}
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer good-token"
    assert call_kwargs["json"] == {
        "expo_push_token": "ExponentPushToken[abc123]",
        "user_id": "user-123",
        "platform": "ios",
        "device_name": "Test iPhone",
    }
    assert "on_conflict=expo_push_token" in mock_post.call_args.args[0]


def test_unregister_push_token_deletes_callers_own_row(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    delete_response = Mock(status_code=204)

    with patch("requests.get", return_value=auth_user_response):
        with patch("requests.delete", return_value=delete_response) as mock_delete:
            response = client.post(
                "/v1/push/unregister",
                json={"expo_push_token": "ExponentPushToken[abc123]"},
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "reason": ""}
    assert "user_id=eq.user-123" in mock_delete.call_args.args[0]
    assert "expo_push_token=eq.ExponentPushToken[abc123]" in mock_delete.call_args.args[0]


def test_send_test_push_reports_no_registered_tokens(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    empty_tokens_response = Mock(status_code=200)
    empty_tokens_response.json.return_value = []

    with patch("requests.get", side_effect=[auth_user_response, empty_tokens_response]):
        response = client.post(
            "/v1/push/test",
            headers={"Authorization": "Bearer good-token"},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": False, "reason": "no_registered_tokens"}


def test_send_test_push_delivers_via_expo_for_registered_tokens(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    tokens_response = Mock(status_code=200)
    tokens_response.json.return_value = [{"expo_push_token": "ExponentPushToken[abc123]"}]
    expo_response = Mock(status_code=200)
    expo_response.json.return_value = {"data": [{"status": "ok"}]}

    with patch("requests.get", side_effect=[auth_user_response, tokens_response]):
        with patch("requests.post", return_value=expo_response) as mock_post:
            response = client.post(
                "/v1/push/test",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body == {"ok": True, "reason": "", "sent": 1}
    # Real modules.push_tokens.send_expo_push_notifications engine, not a
    # mocked result — verifies it actually posts to Expo's push API.
    assert mock_post.call_args.args[0] == "https://exp.host/--/api/v2/push/send"
    sent_messages = mock_post.call_args.kwargs["json"]
    assert sent_messages == [
        {
            "to": "ExponentPushToken[abc123]",
            "title": "FantasyGM Lab",
            "body": mock_post.call_args.kwargs["json"][0]["body"],
            "data": {"kind": "test"},
        }
    ]


def test_get_push_preferences_defaults_all_categories_enabled(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    settings_response = Mock(status_code=200)
    settings_response.json.return_value = []

    with patch("requests.get", side_effect=[auth_user_response, settings_response]):
        response = client.get("/v1/push/preferences", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["categories"] == {"top_priority": True, "watch": True, "recap": True, "injury": True}


def test_get_push_preferences_reflects_stored_overrides(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    settings_response = Mock(status_code=200)
    settings_response.json.return_value = [
        {"user_id": "user-123", "settings": {"push_categories": {"injury": False}}}
    ]

    with patch("requests.get", side_effect=[auth_user_response, settings_response]):
        response = client.get("/v1/push/preferences", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    assert response.json()["categories"]["injury"] is False
    assert response.json()["categories"]["watch"] is True


def test_update_push_preference_rejects_unknown_category(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.post(
            "/v1/push/preferences",
            json={"category": "not_a_real_category", "enabled": False},
            headers={"Authorization": "Bearer good-token"},
        )

    assert response.status_code == 422


def test_update_push_preference_upserts_merged_settings(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    settings_response = Mock(status_code=200)
    settings_response.json.return_value = [
        {"user_id": "user-123", "settings": {"push_categories": {"watch": False}}}
    ]
    upsert_response = Mock(status_code=200)

    with patch("requests.get", side_effect=[auth_user_response, settings_response]):
        with patch("requests.post", return_value=upsert_response) as mock_post:
            response = client.post(
                "/v1/push/preferences",
                json={"category": "injury", "enabled": False},
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "ok": True,
        "categories": {"top_priority": True, "watch": False, "recap": True, "injury": False},
    }
    # Existing "watch": False override is preserved, not clobbered by the new write.
    upserted_settings = mock_post.call_args.kwargs["json"]["settings"]
    assert upserted_settings["push_categories"] == {
        "top_priority": True,
        "watch": False,
        "recap": True,
        "injury": False,
    }


def test_push_preferences_require_auth(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/v1/push/preferences").status_code == 401
    assert client.post("/v1/push/preferences", json={"category": "watch", "enabled": True}).status_code == 401


def test_device_preferences_require_auth(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/v1/preferences").status_code == 401
    assert client.post("/v1/preferences", json={"ui_density": "compact"}).status_code == 401


def test_get_device_preferences_defaults_to_guided_with_no_league(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    settings_response = Mock(status_code=200)
    settings_response.json.return_value = [{"user_id": "user-123", "settings": {}}]

    with patch("requests.get", side_effect=[auth_user_response, settings_response]):
        response = client.get("/v1/preferences", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    assert response.json() == {"ok": True, "ui_density": "guided", "last_league": None}


def test_get_device_preferences_reflects_stored_values(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    settings_response = Mock(status_code=200)
    settings_response.json.return_value = [
        {
            "user_id": "user-123",
            "settings": {
                "ui_density": "compact",
                "last_league_id": "abc",
                "last_league_name": "Dynasty Warriors",
            },
        }
    ]

    with patch("requests.get", side_effect=[auth_user_response, settings_response]):
        response = client.get("/v1/preferences", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "ui_density": "compact",
        "last_league": {"league_id": "abc", "league_name": "Dynasty Warriors"},
    }


def test_update_device_preferences_rejects_an_invalid_density(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.post(
            "/v1/preferences",
            json={"ui_density": "extra_compact"},
            headers={"Authorization": "Bearer good-token"},
        )
    assert response.status_code == 422


def test_update_device_preferences_merges_without_clobbering_push_categories(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    settings_response = Mock(status_code=200)
    settings_response.json.return_value = [
        {"user_id": "user-123", "settings": {"push_categories": {"watch": False}}}
    ]
    upsert_response = Mock(status_code=200)

    with patch("requests.get", side_effect=[auth_user_response, settings_response]):
        with patch("requests.post", return_value=upsert_response) as mock_post:
            response = client.post(
                "/v1/preferences",
                json={"ui_density": "compact", "last_league_id": "abc", "last_league_name": "Dynasty Warriors"},
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "ui_density": "compact",
        "last_league": {"league_id": "abc", "league_name": "Dynasty Warriors"},
    }
    upserted_settings = mock_post.call_args.kwargs["json"]["settings"]
    assert upserted_settings["push_categories"] == {"watch": False}
    assert upserted_settings["ui_density"] == "compact"
    assert upserted_settings["last_league_id"] == "abc"


def test_update_device_preferences_partial_update_only_touches_sent_fields(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    settings_response = Mock(status_code=200)
    settings_response.json.return_value = [
        {
            "user_id": "user-123",
            "settings": {"ui_density": "compact", "last_league_id": "abc", "last_league_name": "Dynasty Warriors"},
        }
    ]
    upsert_response = Mock(status_code=200)

    with patch("requests.get", side_effect=[auth_user_response, settings_response]):
        with patch("requests.post", return_value=upsert_response):
            response = client.post(
                "/v1/preferences",
                json={"last_league_id": "xyz", "last_league_name": "New League"},
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    # ui_density wasn't sent in this request, so the previously-stored value survives.
    assert response.json() == {
        "ok": True,
        "ui_density": "compact",
        "last_league": {"league_id": "xyz", "league_name": "New League"},
    }


def test_gm_stance_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/v1/leagues/abc/gm-stance").status_code == 401
    assert client.post("/v1/leagues/abc/gm-stance", json={"strategy": "rebuild"}).status_code == 401


def test_get_gm_stance_defaults_to_retool_when_nothing_stored(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    settings_response = Mock(status_code=200)
    settings_response.json.return_value = [{"user_id": "user-123", "settings": {}}]

    with patch("requests.get", side_effect=[auth_user_response, settings_response]):
        response = client.get("/v1/leagues/abc/gm-stance", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    assert response.json() == {"ok": True, "strategy": "retool", "is_set": False}


def test_get_gm_stance_is_scoped_per_league(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    settings_response = Mock(status_code=200)
    settings_response.json.return_value = [
        {
            "user_id": "user-123",
            "settings": {"team_strategy_by_league": {"abc": "rebuild", "xyz": "contender"}},
        }
    ]

    with patch("requests.get", side_effect=[auth_user_response, settings_response]):
        response = client.get("/v1/leagues/abc/gm-stance", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    assert response.json() == {"ok": True, "strategy": "rebuild", "is_set": True}


def test_update_gm_stance_rejects_an_invalid_strategy(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.post(
            "/v1/leagues/abc/gm-stance",
            json={"strategy": "yolo"},
            headers={"Authorization": "Bearer good-token"},
        )
    assert response.status_code == 422


def test_update_gm_stance_merges_without_clobbering_other_leagues(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    settings_response = Mock(status_code=200)
    settings_response.json.return_value = [
        {"user_id": "user-123", "settings": {"team_strategy_by_league": {"xyz": "contender"}}}
    ]
    upsert_response = Mock(status_code=200)

    with patch("requests.get", side_effect=[auth_user_response, settings_response]):
        with patch("requests.post", return_value=upsert_response) as mock_post:
            response = client.post(
                "/v1/leagues/abc/gm-stance",
                json={"strategy": "rebuild"},
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "strategy": "rebuild"}
    upserted_settings = mock_post.call_args.kwargs["json"]["settings"]
    assert upserted_settings["team_strategy_by_league"] == {"xyz": "contender", "abc": "rebuild"}


def test_dashboard_uses_the_stored_gm_stance(monkeypatch):
    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]
    stance_settings_response = Mock(status_code=200)
    stance_settings_response.json.return_value = [
        {"user_id": "user-123", "settings": {"team_strategy_by_league": {"abc": "rebuild"}}}
    ]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]

    with patch(
        "requests.get",
        side_effect=[auth_user_response, profile_response, stance_settings_response],
    ):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[
                    {"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids},
                    {"roster_id": 2, "owner_id": "sleeper-user-2", "players": []},
                ],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.sleeper.get_users", return_value=[
                        {"user_id": "sleeper-user-1", "display_name": "GM One"},
                        {"user_id": "sleeper-user-2", "display_name": "GM Two"},
                    ]):
                        with patch("modules.sleeper.get_traded_picks", return_value=[]):
                            with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                                with patch(
                                    "modules.player_eligibility.filter_current_fantasy_players",
                                    side_effect=lambda df, **kwargs: df,
                                ):
                                    with patch(
                                        "modules.dashboard_engine.compose_next_move_briefing"
                                    ) as mock_compose:
                                        mock_compose.return_value = _fake_daily_gm_briefing(1)
                                        response = _client(monkeypatch).get(
                                            "/v1/leagues/abc/dashboard",
                                            headers={"Authorization": "Bearer good-token"},
                                        )

    assert response.status_code == 200
    assert mock_compose.call_args.kwargs["team_strategy"] == "rebuild"


def test_dashboard_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/dashboard")
    assert response.status_code == 401


def test_dashboard_reports_no_linked_username(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get(
            "/v1/leagues/abc/dashboard",
            headers={"Authorization": "Bearer good-token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["quiet"] is True
    assert body["reason"] == "no_sleeper_username_linked"


def test_dashboard_returns_real_briefing_items(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[
                    {"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids},
                    {"roster_id": 2, "owner_id": "sleeper-user-2", "players": []},
                ],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.sleeper.get_users", return_value=[
                        {"user_id": "sleeper-user-1", "display_name": "GM One"},
                        {"user_id": "sleeper-user-2", "display_name": "GM Two"},
                    ]):
                        with patch("modules.sleeper.get_traded_picks", return_value=[]):
                            with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                                with patch(
                                    "modules.player_eligibility.filter_current_fantasy_players",
                                    side_effect=lambda df, **kwargs: df,
                                ):
                                    response = client.get(
                                        "/v1/leagues/abc/dashboard",
                                        headers={"Authorization": "Bearer good-token"},
                                    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    # Real modules.dashboard_engine composition, not a mocked result — the
    # only unrostered player (target_rb) should surface as the waiver tile.
    # With no trade partner holding any players, there's no trade candidate,
    # so (per app.py's default tile order — see dashboard_engine's module
    # docstring) the waiver tile becomes the primary recommendation
    # ("top_priority"), same as modules.daily_gm_briefing's own
    # `_append(briefing.primary, CATEGORY_TOP_PRIORITY)`.
    assert len(body["items"]) >= 1
    for item in body["items"]:
        assert item["headline"]
        assert item["destination"]
    top_priority_items = [item for item in body["items"] if item["category"] == "top_priority"]
    categories = [item["category"] for item in body["items"]]
    assert top_priority_items, f"expected a top_priority tile, got categories: {categories}"
    assert top_priority_items[0]["route_player_id"] == "target_rb"


def test_dashboard_and_trade_hub_share_one_cached_idea_search(monkeypatch):
    # Dashboard's trade tile and the Trade Hub endpoint ask the identical
    # (league, roster, strategy, lens) question — this pins that they hit
    # ONE cached search (trade_hub_engine.generate_trade_idea_records_cached)
    # instead of each independently recomputing it.
    client = _client(monkeypatch)
    from modules import trade_hub_engine

    trade_hub_engine._generate_trade_idea_records_cached.cache_clear()

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]
    call_count = {"n": 0}
    real_generate = trade_hub_engine.generate_trade_idea_records

    def counting_generate(*args, **kwargs):
        call_count["n"] += 1
        return real_generate(*args, **kwargs)

    # Function-level auth/profile mocks (not a finite requests.get side_effect
    # list) since this test makes two full authenticated requests.
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch(
            "services.mobile_api_service.auth_supabase.fetch_auth_user",
            return_value=({"id": "user-123", "email": "gm@example.com"}, ""),
        ))
        stack.enter_context(patch(
            "services.mobile_api_service._fetch_profile_fields",
            return_value={"entitlement": "free", "sleeper_username": "gm_dynasty"},
        ))
        stack.enter_context(patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"))
        stack.enter_context(patch(
            "modules.sleeper.get_rosters",
            return_value=[
                {"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids},
                {"roster_id": 2, "owner_id": "sleeper-user-2", "players": []},
            ],
        ))
        stack.enter_context(patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE))
        stack.enter_context(patch("modules.sleeper.get_users", return_value=[
            {"user_id": "sleeper-user-1", "display_name": "GM One"},
            {"user_id": "sleeper-user-2", "display_name": "GM Two"},
        ]))
        stack.enter_context(patch("modules.sleeper.get_traded_picks", return_value=[]))
        stack.enter_context(patch("modules.rankings.load_players", return_value=_fake_roster_frame()))
        stack.enter_context(patch(
            "modules.player_eligibility.filter_current_fantasy_players",
            side_effect=lambda df, **kwargs: df,
        ))
        stack.enter_context(patch.object(
            trade_hub_engine, "generate_trade_idea_records", side_effect=counting_generate
        ))
        dashboard_response = client.get(
            "/v1/leagues/abc/dashboard",
            headers={"Authorization": "Bearer good-token"},
        )
        trade_hub_response = client.get(
            "/v1/leagues/abc/trade-hub?strategy=retool&lens=Dynasty",
            headers={"Authorization": "Bearer good-token"},
        )

    assert dashboard_response.status_code == 200
    assert trade_hub_response.status_code == 200
    assert call_count["n"] == 1, "expected the second request to hit the shared cache, not recompute"

    trade_hub_engine._generate_trade_idea_records_cached.cache_clear()


def _fake_daily_gm_briefing(count: int):
    from modules import daily_gm_briefing

    items = tuple(
        daily_gm_briefing.DailyBriefingItem(
            source="test",
            source_id=f"item-{i}",
            recommendation_id=f"rec-{i}",
            category="watch",
            headline=f"Headline {i}",
            reason="",
            supporting_context="",
            destination="waivers",
            league_id="abc",
            roster_id="1",
            valuation_lens="dynasty_score",
            scoring_format="",
            freshness="",
            provenance="test",
        )
        for i in range(count)
    )
    return daily_gm_briefing.DailyGmBriefing(
        items=items,
        quiet=False,
        quiet_reason="",
        entitlement="free",
        league_id="abc",
        roster_id="1",
        valuation_lens="dynasty_score",
        scoring_format="",
    )


def _dashboard_request_with_mocked_briefing(monkeypatch, entitlement: str, item_count: int):
    client = _client(monkeypatch)
    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": entitlement, "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[
                    {"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids},
                    {"roster_id": 2, "owner_id": "sleeper-user-2", "players": []},
                ],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.sleeper.get_users", return_value=[
                        {"user_id": "sleeper-user-1", "display_name": "GM One"},
                        {"user_id": "sleeper-user-2", "display_name": "GM Two"},
                    ]):
                        with patch("modules.sleeper.get_traded_picks", return_value=[]):
                            with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                                with patch(
                                    "modules.player_eligibility.filter_current_fantasy_players",
                                    side_effect=lambda df, **kwargs: df,
                                ):
                                    with patch(
                                        "modules.dashboard_engine.compose_next_move_briefing",
                                        return_value=_fake_daily_gm_briefing(item_count),
                                    ):
                                        return client.get(
                                            "/v1/leagues/abc/dashboard",
                                            headers={"Authorization": "Bearer good-token"},
                                        )


def test_dashboard_caps_items_at_four_for_free_users(monkeypatch):
    response = _dashboard_request_with_mocked_briefing(monkeypatch, "free", item_count=6)

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 4
    assert body["entitlement"] == {"is_premium": False, "visible_count": 4, "hidden_count": 2}


def test_dashboard_shows_all_items_for_premium_users(monkeypatch):
    response = _dashboard_request_with_mocked_briefing(monkeypatch, "premium", item_count=6)

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 6
    assert body["entitlement"] == {"is_premium": True, "visible_count": 6, "hidden_count": 0}


def test_dashboard_includes_team_snapshot(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[
                    {
                        "roster_id": 1,
                        "owner_id": "sleeper-user-1",
                        "players": my_roster_ids,
                        "settings": {"wins": 7, "losses": 6, "ties": 0},
                    },
                    {"roster_id": 2, "owner_id": "sleeper-user-2", "players": []},
                ],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.sleeper.get_users", return_value=[
                        {"user_id": "sleeper-user-1", "display_name": "GM One"},
                        {"user_id": "sleeper-user-2", "display_name": "GM Two"},
                    ]):
                        with patch("modules.sleeper.get_traded_picks", return_value=[]):
                            with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                                with patch(
                                    "modules.player_eligibility.filter_current_fantasy_players",
                                    side_effect=lambda df, **kwargs: df,
                                ):
                                    response = client.get(
                                        "/v1/leagues/abc/dashboard",
                                        headers={"Authorization": "Bearer good-token"},
                                    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    snapshot = body["team_snapshot"]
    assert snapshot is not None
    assert snapshot["wins"] == 7
    assert snapshot["losses"] == 6
    assert snapshot["ties"] == 0
    # _fake_roster_frame's roster rows are all age 26 (except the bench RB at
    # 30), so the average is pulled up slightly above 26 but nowhere near 30.
    assert 26.0 <= snapshot["average_age"] <= 27.0
    assert isinstance(snapshot["health_flag"], str)
    assert snapshot["health_flag"]
    # Roster 1's 10 starter-weighted players comfortably outscore roster 2's
    # empty roster, so it takes the top power/franchise rank — same real
    # modules.league_rankings computation get_league_team_rankings uses.
    assert snapshot["power_rank"] == 1
    assert snapshot["franchise_rank"] == 1
    # The "why" fields ride along with the flag even on a clean roster — this
    # frame carries no injury_status values, so they're simply empty.
    assert snapshot["key_injuries_summary"] == ""
    assert snapshot["top_injury_impact_summary"] == ""
    assert snapshot["top_injury_impact_players"] == []


def test_dashboard_team_snapshot_explains_the_health_flag(monkeypatch):
    """health_flag's supporting context (which injuries, which players) is
    already computed by modules.rankings.roster_injury_context and rendered on
    web — the mobile snapshot forwards it instead of dropping it."""

    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]

    injured_frame = _fake_roster_frame()
    injured_frame["news_updated"] = time.time()
    injured_frame.loc[injured_frame["player_id"] == "my2", "injury_status"] = "Out"
    injured_frame.loc[injured_frame["player_id"] == "my2", "status"] = "Injured Reserve"

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[
                    {
                        "roster_id": 1,
                        "owner_id": "sleeper-user-1",
                        "players": my_roster_ids,
                        "settings": {"wins": 7, "losses": 6, "ties": 0},
                    },
                    {"roster_id": 2, "owner_id": "sleeper-user-2", "players": []},
                ],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.sleeper.get_users", return_value=[
                        {"user_id": "sleeper-user-1", "display_name": "GM One"},
                        {"user_id": "sleeper-user-2", "display_name": "GM Two"},
                    ]):
                        with patch("modules.sleeper.get_traded_picks", return_value=[]):
                            with patch("modules.rankings.load_players", return_value=injured_frame):
                                with patch(
                                    "modules.player_eligibility.filter_current_fantasy_players",
                                    side_effect=lambda df, **kwargs: df,
                                ):
                                    response = client.get(
                                        "/v1/leagues/abc/dashboard",
                                        headers={"Authorization": "Bearer good-token"},
                                    )

    assert response.status_code == 200
    snapshot = response.json()["team_snapshot"]
    assert snapshot is not None
    assert snapshot["health_flag"] != "Stable"

    impact_players = snapshot["top_injury_impact_players"]
    assert impact_players, "an Out starter should surface as an injury impact driver"
    driver = impact_players[0]
    assert driver["name"] == "My Player 2"
    assert driver["position"] == "RB"
    assert driver["injury_status"] == "Out"
    assert driver["injury_level"] == "major"
    assert driver["impact_contribution"] > 0
    assert driver["player_value_score"] > 0
    assert driver["freshness_label"] == "current"

    # Same two strings web renders (the "Key injuries: ..." caption and the
    # engine's own impact summary), not a mobile-only rewording.
    assert "My Player 2" in snapshot["key_injuries_summary"]
    assert "My Player 2" in snapshot["top_injury_impact_summary"]


def test_dashboard_team_snapshot_is_none_without_a_resolved_roster(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get(
            "/v1/leagues/abc/dashboard",
            headers={"Authorization": "Bearer good-token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["team_snapshot"] is None
    assert body["reason"] == "no_sleeper_username_linked"


def test_trade_hub_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/trade-hub")
    assert response.status_code == 401


def test_trade_hub_reports_no_linked_username(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get(
            "/v1/leagues/abc/trade-hub",
            headers={"Authorization": "Bearer good-token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["ideas"] == []
    assert body["reason"] == "no_sleeper_username_linked"


def test_trade_hub_resolves_roster_and_projects_generated_ideas(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]
    fake_record = {
        "partner_team_name": "Rival GM",
        "rationale": "Clear upgrade at RB.",
        "trade_gain": 25,
        "trade_confidence_label": "High",
        "market_realism_label": "Realistic",
        "reasoning_tags": ["Need-Based"],
        "send_assets": [],
        "receive_assets": [],
    }

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids}],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                        with patch(
                            "modules.player_eligibility.filter_current_fantasy_players",
                            side_effect=lambda df, **kwargs: df,
                        ):
                            with patch(
                                "modules.trade_hub_engine.generate_trade_idea_records",
                                return_value=[fake_record],
                            ) as mock_generate:
                                response = client.get(
                                    "/v1/leagues/abc/trade-hub?strategy=contender",
                                    headers={"Authorization": "Bearer good-token"},
                                )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    assert len(body["ideas"]) == 1
    assert body["ideas"][0]["partner_team_name"] == "Rival GM"
    assert body["ideas"][0]["trade_gain"] == 25
    assert body["ideas"][0]["confidence_label"] == "High"
    assert mock_generate.call_args.kwargs["my_roster_id"] == 1
    assert mock_generate.call_args.kwargs["team_strategy"] == "contender"
    assert mock_generate.call_args.kwargs["league_id"] == "abc"


def test_trade_hub_resolves_partner_avatar_by_team_name(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]
    fake_record = {
        "partner_team_name": "Rival GM",
        "rationale": "Clear upgrade at RB.",
        "trade_gain": 25,
        "trade_confidence_label": "High",
        "market_realism_label": "Realistic",
        "reasoning_tags": ["Need-Based"],
        "send_assets": [],
        "receive_assets": [],
    }
    fake_profiles = {
        "1": {"team_name": "My Team", "avatar_url": "https://example.com/me.png"},
        "2": {"team_name": "Rival GM", "avatar_url": "https://example.com/rival.png"},
    }

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids}],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.sleeper.get_league_roster_profiles", return_value=fake_profiles):
                        with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                            with patch(
                                "modules.player_eligibility.filter_current_fantasy_players",
                                side_effect=lambda df, **kwargs: df,
                            ):
                                with patch(
                                    "modules.trade_hub_engine.generate_trade_idea_records",
                                    return_value=[fake_record],
                                ):
                                    response = client.get(
                                        "/v1/leagues/abc/trade-hub?strategy=contender",
                                        headers={"Authorization": "Bearer good-token"},
                                    )

    assert response.status_code == 200
    body = response.json()
    assert body["ideas"][0]["partner_team_avatar_url"] == "https://example.com/rival.png"


def _fake_idea_record(name: str, *, gain: int) -> dict:
    return {
        "partner_team_name": name,
        "rationale": "Clear upgrade.",
        "trade_gain": gain,
        "trade_confidence_label": "High",
        "market_realism_label": "Realistic",
        "reasoning_tags": [],
        "send_assets": [],
        "receive_assets": [],
    }


def test_trade_hub_gates_free_entitlement_to_two_ideas_and_reveals_via_ads(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]
    fake_cards = [_fake_idea_record(f"Rival {i}", gain=10 - i) for i in range(4)]

    # Two full requests, each: require_user's auth check + one profile fetch
    # shared between entitlement and _resolve_my_roster (no double-fetch).
    responses = [auth_user_response, profile_response] * 2
    with patch("requests.get", side_effect=responses):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids}],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                        with patch(
                            "modules.player_eligibility.filter_current_fantasy_players",
                            side_effect=lambda df, **kwargs: df,
                        ):
                            with patch(
                                "modules.trade_hub_engine.generate_trade_idea_records",
                                return_value=fake_cards,
                            ):
                                free_response = client.get(
                                    "/v1/leagues/abc/trade-hub?strategy=contender",
                                    headers={"Authorization": "Bearer good-token"},
                                )
                                unlocked_response = client.get(
                                    "/v1/leagues/abc/trade-hub?strategy=contender&ad_unlocks=1",
                                    headers={"Authorization": "Bearer good-token"},
                                )

    assert free_response.status_code == 200
    free_body = free_response.json()
    assert len(free_body["ideas"]) == 2
    assert free_body["entitlement"] == {
        "is_premium": False,
        "approved_count": 4,
        "visible_count": 2,
        "hidden_count": 2,
        "free_limit": 2,
        "ad_bonus_per_unlock": 2,
        "max_ad_unlocks": 3,
        "ad_unlocks_applied": 0,
    }

    assert unlocked_response.status_code == 200
    unlocked_body = unlocked_response.json()
    assert len(unlocked_body["ideas"]) == 4
    assert unlocked_body["entitlement"]["visible_count"] == 4
    assert unlocked_body["entitlement"]["ad_unlocks_applied"] == 1
    assert unlocked_body["entitlement"]["hidden_count"] == 0


def test_trade_hub_premium_entitlement_sees_full_board_ignoring_ad_unlocks(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "premium", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]
    fake_cards = [_fake_idea_record(f"Rival {i}", gain=10 - i) for i in range(3)]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids}],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                        with patch(
                            "modules.player_eligibility.filter_current_fantasy_players",
                            side_effect=lambda df, **kwargs: df,
                        ):
                            with patch(
                                "modules.trade_hub_engine.generate_trade_idea_records",
                                return_value=fake_cards,
                            ):
                                response = client.get(
                                    "/v1/leagues/abc/trade-hub?strategy=contender",
                                    headers={"Authorization": "Bearer good-token"},
                                )

    body = response.json()
    assert len(body["ideas"]) == 3
    assert body["entitlement"]["is_premium"] is True
    assert body["entitlement"]["hidden_count"] == 0


def test_waivers_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/waivers")
    assert response.status_code == 401


def test_waivers_reports_no_linked_username(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get(
            "/v1/leagues/abc/waivers",
            headers={"Authorization": "Bearer good-token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["players"] == []
    assert body["priority_adds"] == []
    assert body["reason"] == "no_sleeper_username_linked"


def test_waivers_excludes_rostered_players_and_ranks_free_agents(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]

    # waiver_actionable_player_pool runs the real (unmocked)
    # player_eligibility() check per row — unlike the dashboard/trade-hub
    # tests, which never call it. That function requires at least one
    # "current signal" (recent news, depth chart, current-season stats,
    # market value, or rookie flag) beyond just status="Active", or it
    # returns eligible=False with reason "missing_current_player_
    # corroboration". The shared fixture has none of those, so give
    # target_rb a current stats_season to satisfy it.
    roster_frame = _fake_roster_frame()
    roster_frame.loc[roster_frame["player_id"] == "target_rb", "stats_season"] = 2025

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[
                    {"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids},
                    {"roster_id": 2, "owner_id": "sleeper-user-2", "players": []},
                ],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.rankings.load_players", return_value=roster_frame):
                        with patch(
                            "modules.player_eligibility.filter_current_fantasy_players",
                            side_effect=lambda df, **kwargs: df,
                        ):
                            # player_state_authority imports this name directly
                            # (`from modules.player_eligibility import
                            # filter_current_fantasy_players`), so it has its own
                            # bound reference the patch above doesn't reach —
                            # waiver_actionable_player_pool calls that one
                            # internally, and it needs patching separately.
                            with patch(
                                "modules.player_state_authority.filter_current_fantasy_players",
                                side_effect=lambda df, **kwargs: df,
                            ):
                                response = client.get(
                                    "/v1/leagues/abc/waivers",
                                    headers={"Authorization": "Bearer good-token"},
                                )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    # Every my*/my_bench_rb id is rostered (roster 1 or 2); target_rb is the
    # one player in the fixture nobody owns, so it's the entire free-agent
    # pool — same fixture the dashboard/trade-hub tests reuse.
    player_ids = [p["player_id"] for p in body["players"]]
    assert player_ids == ["target_rb"]
    assert body["available_count"] == 1
    target = body["players"][0]
    # apply_valuation_lens recomputes the Dynasty score from the player's
    # attributes rather than echoing the fixture's raw dynasty_score field
    # (5428 for this row, not the fixture's 6000) — assert self-consistency
    # with the single free agent's own score instead of a hardcoded formula
    # output this test has no business predicting.
    assert body["avg_wire_score"] == round(target["score"])
    assert target["score"] > 0
    assert target["stale_free_agent"] is False
    # Wire-relative rank among the (single-player) free-agent pool, not the
    # league-global canonical rank.
    assert target["position_rank"] == 1
    assert target["overall_rank"] == 1


def _waivers_secondary_board_request(monkeypatch, entitlement: str):
    """target_rb plus 7 more free agents (8 total) — Priority Adds caps at
    6, so at least one of the low-scored extras (young_wr, age 22) always
    overflows into the secondary board regardless of exactly how the
    priority ranking breaks ties."""

    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": entitlement, "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]

    roster_frame = _fake_roster_frame()
    roster_frame.loc[roster_frame["player_id"] == "target_rb", "stats_season"] = 2025
    extra_free_agents = [
        {
            "player_id": "young_wr",
            "name": "Young Prospect",
            "position": "WR",
            "team": "SF",
            "age": 22,
            "years_exp": 1,
            "status": "Active",
            "injury_status": None,
            "score": 100,
            "dynasty_score": 100,
            "value_score": 100,
            "rebuild_score": 100,
            "stats_season": 2025,
        },
    ] + [
        {
            "player_id": f"fa_{i}",
            "name": f"Free Agent {i}",
            "position": "WR",
            "team": "SF",
            "age": 28,
            "years_exp": 6,
            "status": "Active",
            "injury_status": None,
            "score": 200 + i,
            "dynasty_score": 200 + i,
            "value_score": 200 + i,
            "rebuild_score": 200 + i,
            "stats_season": 2025,
        }
        for i in range(6)
    ]
    roster_frame = pd.concat([roster_frame, pd.DataFrame(extra_free_agents)], ignore_index=True)

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[
                    {"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids},
                    {"roster_id": 2, "owner_id": "sleeper-user-2", "players": []},
                ],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.rankings.load_players", return_value=roster_frame):
                        with patch(
                            "modules.player_eligibility.filter_current_fantasy_players",
                            side_effect=lambda df, **kwargs: df,
                        ):
                            with patch(
                                "modules.player_state_authority.filter_current_fantasy_players",
                                side_effect=lambda df, **kwargs: df,
                            ):
                                return client.get(
                                    "/v1/leagues/abc/waivers",
                                    headers={"Authorization": "Bearer good-token"},
                                )


def test_waivers_secondary_board_is_empty_for_free_users(monkeypatch):
    response = _waivers_secondary_board_request(monkeypatch, "free")

    assert response.status_code == 200
    body = response.json()
    assert body["stash_candidates"] == []
    assert body["watchlist_candidates"] == []
    assert body["faab_targets"] == []
    assert body["entitlement"] == {"is_premium": False}


def test_waivers_secondary_board_is_populated_for_premium_users(monkeypatch):
    response = _waivers_secondary_board_request(monkeypatch, "premium")

    assert response.status_code == 200
    body = response.json()
    assert body["entitlement"] == {"is_premium": True}
    # young_wr (age 22) isn't the Priority Add (target_rb outscores it), so
    # it's the one candidate available to land in the secondary board — the
    # age<=24 rule puts it in Stash Candidates specifically.
    stash_ids = [p["player_id"] for p in body["stash_candidates"]]
    assert "young_wr" in stash_ids
    all_secondary_ids = {
        p["player_id"]
        for group in ("stash_candidates", "watchlist_candidates", "faab_targets")
        for p in body[group]
    }
    assert "target_rb" not in all_secondary_ids


def test_team_rankings_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/team-rankings")
    assert response.status_code == 401


def test_team_rankings_returns_power_and_franchise_ranks(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]
    fake_rosters = [
        {
            "roster_id": 1,
            "owner_id": "sleeper-user-1",
            "players": my_roster_ids,
            "settings": {"wins": 7, "losses": 6, "ties": 0},
        },
        {
            "roster_id": 2,
            "owner_id": "sleeper-user-2",
            "players": ["target_rb"],
            "settings": {"wins": 3, "losses": 10, "ties": 0},
        },
    ]
    fake_users = [
        {"user_id": "sleeper-user-1", "display_name": "GM One"},
        {"user_id": "sleeper-user-2", "display_name": "GM Two"},
    ]

    # require_user is the only auth check here (no _resolve_my_roster / no
    # profile fetch — team-rankings is public league-wide data, same as
    # /team-profiles and /rosters), so exactly one requests.get call fires.
    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
            with patch("modules.sleeper.get_rosters", return_value=fake_rosters):
                with patch("modules.sleeper.get_users", return_value=fake_users):
                    with patch("modules.sleeper.get_traded_picks", return_value=[]):
                        with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                            with patch(
                                "modules.player_eligibility.filter_current_fantasy_players",
                                side_effect=lambda df, **kwargs: df,
                            ):
                                response = client.get(
                                    "/v1/leagues/abc/team-rankings",
                                    headers={"Authorization": "Bearer good-token"},
                                )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    teams = body["teams"]
    assert len(teams) == 2
    by_roster = {t["roster_id"]: t for t in teams}
    # Roster 1's 10 starter-weighted players comfortably outscore roster 2's
    # single player, so roster 1 gets the top power/franchise rank.
    assert by_roster["1"]["power_rank"] == 1
    assert by_roster["2"]["power_rank"] == 2
    assert by_roster["1"]["franchise_rank"] == 1
    # Standings come straight off each roster's own settings, independent of
    # the rank computation.
    assert by_roster["1"]["wins"] == 7
    assert by_roster["1"]["losses"] == 6
    assert by_roster["2"]["wins"] == 3
    assert by_roster["2"]["losses"] == 10
    assert isinstance(by_roster["1"]["average_age"], (int, float))
    # No traded picks in this fixture — asserting draft_capital_rank doesn't
    # crash and comes back as a real int is the honest claim here; the exact
    # tie-breaking between rosters depends on default future-pick generation
    # this test has no business predicting.
    assert isinstance(by_roster["1"]["draft_capital_rank"], int)
    assert isinstance(by_roster["2"]["draft_capital_rank"], int)
    # Archetype/strategy classification (modules.team_eval.refine_team_directions)
    # runs on real strength inputs here (starter/bench/age/draft-capital ranks
    # all come from the fixture, not neutral fallbacks) — asserting the fields
    # are populated, non-empty labels is the honest claim; the exact archetype
    # a 2-team, lopsided-roster fixture lands on isn't this test's business.
    for team in teams:
        assert isinstance(team["strategy"], str) and team["strategy"]
        assert isinstance(team["strategy_label"], str) and team["strategy_label"]
        assert isinstance(team["archetype"], str) and team["archetype"]
        assert isinstance(team["archetype_label"], str) and team["archetype_label"]
        assert isinstance(team["archetype_explanation"], str) and team["archetype_explanation"]
        assert isinstance(team["archetype_strengths"], list)
        assert isinstance(team["archetype_risks"], list)
        assert isinstance(team["archetype_recommendations"], list)


def test_draft_center_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/draft-center")
    assert response.status_code == 401


def _draft_center_rosters_and_users():
    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]
    rosters = [
        {
            "roster_id": 1,
            "owner_id": "sleeper-user-1",
            "players": my_roster_ids,
            "settings": {"wins": 7, "losses": 6, "ties": 0},
        },
        {
            "roster_id": 2,
            "owner_id": "sleeper-user-2",
            "players": ["target_rb"],
            "settings": {"wins": 3, "losses": 10, "ties": 0},
        },
    ]
    users = [
        {"user_id": "sleeper-user-1", "display_name": "GM One"},
        {"user_id": "sleeper-user-2", "display_name": "GM Two"},
    ]
    return rosters, users


def test_draft_center_returns_league_wide_cards_and_resolved_posture(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    fake_rosters, fake_users = _draft_center_rosters_and_users()

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                with patch("modules.sleeper.get_rosters", return_value=fake_rosters):
                    with patch("modules.sleeper.get_users", return_value=fake_users):
                        with patch("modules.sleeper.get_traded_picks", return_value=[]):
                            with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                                with patch(
                                    "modules.player_eligibility.filter_current_fantasy_players",
                                    side_effect=lambda df, **kwargs: df,
                                ):
                                    response = client.get(
                                        "/v1/leagues/abc/draft-center",
                                        headers={"Authorization": "Bearer good-token"},
                                    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""

    # Decision/partner cards are real modules.draft_center_ui output, not
    # mocked — each is a {label, title, tone, items: [str]} card.
    assert body["decision_cards"]
    assert body["partner_cards"]
    for card in body["decision_cards"] + body["partner_cards"]:
        assert card["label"]
        assert card["title"]
        assert card["tone"]
        assert isinstance(card["items"], list) and card["items"]

    # Roster 1's Sleeper username resolves to its own roster, so posture
    # should be populated (real modules.draft_center_ui.draft_posture_profile
    # output against the roster's own real draft-capital row).
    posture = body["posture"]
    assert body["posture_reason"] == ""
    assert posture is not None
    assert posture["label"]
    assert posture["note"]
    assert posture["tone"]
    assert isinstance(posture["draft_capital_rank"], int)
    assert isinstance(posture["future_draft_capital_rank"], int)
    assert isinstance(posture["power_rank"], int)
    assert isinstance(posture["franchise_rank"], int)


def test_draft_center_posture_is_null_without_a_resolved_roster(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]

    fake_rosters, fake_users = _draft_center_rosters_and_users()

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
            with patch("modules.sleeper.get_rosters", return_value=fake_rosters):
                with patch("modules.sleeper.get_users", return_value=fake_users):
                    with patch("modules.sleeper.get_traded_picks", return_value=[]):
                        with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                            with patch(
                                "modules.player_eligibility.filter_current_fantasy_players",
                                side_effect=lambda df, **kwargs: df,
                            ):
                                response = client.get(
                                    "/v1/leagues/abc/draft-center",
                                    headers={"Authorization": "Bearer good-token"},
                                )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    # No linked Sleeper username: posture can't be resolved, but the
    # league-wide cards don't gate on that — they're still real output.
    assert body["posture"] is None
    assert body["posture_reason"] == "no_sleeper_username_linked"
    assert body["decision_cards"]
    assert body["partner_cards"]


def test_my_team_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/v1/leagues/abc/my-team")
    assert response.status_code == 401


def test_my_team_reports_no_linked_username(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get("/v1/leagues/abc/my-team", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["starters"] == []
    assert body["bench"] == []
    assert body["reason"] == "no_sleeper_username_linked"


def test_my_team_returns_the_real_suggested_lineup_split(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]

    my_roster_ids = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb"]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper.get_rosters",
                return_value=[
                    {"roster_id": 1, "owner_id": "sleeper-user-1", "players": my_roster_ids},
                    {"roster_id": 2, "owner_id": "sleeper-user-2", "players": []},
                ],
            ):
                with patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE):
                    with patch("modules.rankings.load_players", return_value=_fake_roster_frame()):
                        with patch(
                            "modules.player_eligibility.filter_current_fantasy_players",
                            side_effect=lambda df, **kwargs: df,
                        ):
                            response = client.get(
                                "/v1/leagues/abc/my-team",
                                headers={"Authorization": "Bearer good-token"},
                            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""

    # Real modules.team_eval.suggest_optimal_lineup output, not a mocked
    # result. The fixture roster has 1 QB, 4 RB, 4 WR, 1 TE (10 players);
    # _TRADE_ANALYZER_LEAGUE's roster_positions is
    # ["QB","RB","RB","WR","WR","WR","TE","FLEX","BN","BN"], i.e. 8
    # assignable starter slots (QB1+RB2+WR3+TE1+FLEX1) — so exactly 8
    # starters and 2 bench, regardless of which specific tied-score players
    # land in which slot (that tie-break isn't this test's business).
    starters = body["starters"]
    bench = body["bench"]
    assert len(starters) == 8
    assert len(bench) == 2
    assert len(starters) + len(bench) == 10

    for player in starters:
        assert player["suggested_starter"] is True
        assert player["slot"] != "BENCH"
    for player in bench:
        assert player["suggested_starter"] is False
        assert player["slot"] == "BENCH"

    # Starters are ordered QB first (matches _LINEUP_SLOT_ORDER), and the
    # one clearly-weakest roster player (score 300 vs. everyone else's
    # 2000) is deterministically bench regardless of tie-breaking among
    # the 2000-score players.
    assert starters[0]["slot"] == "QB"
    bench_ids = {player["player_id"] for player in bench}
    assert "my_bench_rb" in bench_ids


def _fake_matchup_players_frame():
    """Two full rosters: mine (season value 2000/player) and my opponent's
    (1000/player), so the season-value comparison has a deterministic winner.
    """

    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "RB", "WR"]
    rows = []
    for prefix, score, tier, opportunity in (
        ("mine", 2000, "Elite", "Workhorse"),
        ("opp", 1000, "Solid", "Rotational"),
    ):
        for i, position in enumerate(positions, start=1):
            rows.append(
                {
                    "player_id": f"{prefix}{i}",
                    "name": f"{prefix.title()} Player {i}",
                    "position": position,
                    "team": "KC",
                    "age": 26,
                    "years_exp": 4,
                    "status": "Active",
                    "injury_status": None,
                    "player_tier": tier,
                    "opportunity_label": opportunity,
                    "score": score,
                    "dynasty_score": score,
                    "value_score": score,
                    "rebuild_score": score,
                }
            )
    return pd.DataFrame(rows)


_MATCHUP_LEAGUE = {
    "scoring_settings": {"rec": 1.0},
    # `leg` is Sleeper's current-week field — the endpoint reads it rather
    # than guessing a week from the calendar.
    "settings": {"type": 2, "leg": 5},
    "roster_positions": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "BN", "BN"],
    "total_rosters": 12,
}

_MATCHUP_ROSTERS = [
    {
        "roster_id": 1,
        "owner_id": "sleeper-user-1",
        "players": [f"mine{i}" for i in range(1, 10)],
        "settings": {"wins": 3, "losses": 1, "ties": 0},
    },
    {
        "roster_id": 2,
        "owner_id": "sleeper-user-2",
        "players": [f"opp{i}" for i in range(1, 10)],
        "settings": {"wins": 2, "losses": 2, "ties": 0},
    },
]


def _matchup_auth_mocks():
    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]
    return [auth_user_response, profile_response]


@contextlib.contextmanager
def _matchup_world(matchups, league=None, rosters=None):
    """Every Sleeper/player-data seam the matchup endpoint touches, mocked."""

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch("requests.get", side_effect=_matchup_auth_mocks()))
        stack.enter_context(patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"))
        stack.enter_context(
            patch("modules.sleeper.get_rosters", return_value=rosters if rosters is not None else _MATCHUP_ROSTERS)
        )
        stack.enter_context(patch("modules.sleeper.get_league", return_value=league or _MATCHUP_LEAGUE))
        stack.enter_context(patch("modules.sleeper.get_matchups", return_value=matchups))
        stack.enter_context(
            patch(
                "modules.sleeper.get_league_roster_profiles",
                return_value={
                    "1": {"team_name": "My Squad", "owner_name": "Me", "avatar_url": None},
                    "2": {"team_name": "Their Squad", "owner_name": "Them", "avatar_url": None},
                },
            )
        )
        stack.enter_context(patch("modules.rankings.load_players", return_value=_fake_matchup_players_frame()))
        stack.enter_context(
            patch("modules.player_eligibility.filter_current_fantasy_players", side_effect=lambda df, **kwargs: df)
        )
        yield


def test_matchup_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/v1/leagues/abc/matchup").status_code == 401


def test_matchup_rejects_unknown_lens(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.get(
            "/v1/leagues/abc/matchup?lens=Vibes", headers={"Authorization": "Bearer good-token"}
        )

    assert response.status_code == 422


def test_matchup_reports_no_linked_username(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        response = client.get("/v1/leagues/abc/matchup", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["my_team"] is None
    assert body["opponent"] is None
    assert body["comparison"] is None
    assert body["reason"] == "no_sleeper_username_linked"
    # The honest-framing label ships even on not-ready responses, so no
    # client can render a matchup shell without it.
    assert body["basis"] == "season_value"
    assert "not a weekly points projection" in body["basis_label"]


def test_matchup_reports_bye_week_when_roster_is_unpaired(monkeypatch):
    client = _client(monkeypatch)

    with _matchup_world([{"roster_id": 1, "matchup_id": None}, {"roster_id": 2, "matchup_id": 4}]):
        response = client.get("/v1/leagues/abc/matchup", headers={"Authorization": "Bearer good-token"})

    body = response.json()
    assert response.status_code == 200
    assert body["reason"] == "bye_week"
    assert body["week"] == 5
    assert body["my_team"] is None


def test_matchup_reports_missing_week_when_league_has_no_leg(monkeypatch):
    client = _client(monkeypatch)
    league = {**_MATCHUP_LEAGUE, "settings": {"type": 2}}

    with _matchup_world([], league=league):
        response = client.get("/v1/leagues/abc/matchup", headers={"Authorization": "Bearer good-token"})

    body = response.json()
    assert body["reason"] == "no_current_week"
    assert body["week"] is None


def test_matchup_reports_no_matchup_data_when_sleeper_returns_nothing(monkeypatch):
    client = _client(monkeypatch)

    with _matchup_world([]):
        response = client.get("/v1/leagues/abc/matchup", headers={"Authorization": "Bearer good-token"})

    body = response.json()
    assert body["reason"] == "no_matchup_data"
    assert body["week"] == 5


def test_matchup_returns_both_sides_and_a_season_value_comparison(monkeypatch):
    client = _client(monkeypatch)

    with _matchup_world([{"roster_id": 1, "matchup_id": 3}, {"roster_id": 2, "matchup_id": 3}]):
        response = client.get("/v1/leagues/abc/matchup", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reason"] == ""
    assert body["week"] == 5

    mine = body["my_team"]
    theirs = body["opponent"]
    assert mine["roster_id"] == "1"
    assert mine["team_name"] == "My Squad"
    assert mine["wins"] == 3
    assert theirs["roster_id"] == "2"
    assert theirs["team_name"] == "Their Squad"

    # _MATCHUP_LEAGUE's roster_positions give 8 assignable starter slots
    # (QB1 + RB2 + WR3 + TE1 + FLEX1); both fixture rosters are 9 players,
    # so both sides fill all 8. Same suggest_optimal_lineup pass on each
    # side — that's what makes the totals comparable at all.
    assert len(mine["starters"]) == 8
    assert len(theirs["starters"]) == 8
    assert mine["starters"][0]["slot"] == "QB"
    assert all(player["suggested_starter"] is True for player in mine["starters"])
    assert mine["starters_basis"] == "suggested_optimal_lineup"

    # Season-value totals, NOT projected points — each side's total is the
    # sum of its own starters' lens-adjusted season scores (the Dynasty lens
    # reweights the raw fixture scores by age/position, so this asserts the
    # relationship rather than a frozen magic number).
    assert mine["season_value_total"] == round(sum(p["score"] for p in mine["starters"]), 1)
    assert theirs["season_value_total"] == round(sum(p["score"] for p in theirs["starters"]), 1)
    # My fixture roster is 2000/player against their 1000/player.
    assert mine["season_value_total"] > theirs["season_value_total"]

    comparison = body["comparison"]
    assert comparison["edge"] == "you"
    assert comparison["margin"] == round(mine["season_value_total"] - theirs["season_value_total"], 1)
    assert comparison["my_season_value"] == mine["season_value_total"]
    assert comparison["opponent_season_value"] == theirs["season_value_total"]
    assert comparison["basis"] == "season_value"
    assert "not a weekly points projection" in comparison["basis_label"]
    # Nothing in this response may present itself as a points projection.
    assert "projected_points" not in str(body)

    # The per-starter "why" is built from real season-form fields only —
    # tier (recomputed by the valuation lens, so only the shape is asserted),
    # workload/opportunity label, and season-value rank on that roster.
    why = mine["starters"][0]["why"]
    assert "tier" in why
    assert "Workhorse" in why
    assert "top QB on this roster by season value" in why
    # ...and never about this week's opponent or expected points.
    for player in mine["starters"] + theirs["starters"]:
        assert "project" not in player["why"].lower()
        assert "points" not in player["why"].lower()


def test_matchup_uses_the_leagues_current_week_for_the_live_sleeper_call(monkeypatch):
    """The whole point of reading settings.leg: the in-progress week is
    requested from Sleeper, not a completed one."""

    client = _client(monkeypatch)
    calls: list[tuple] = []

    def fake_get_matchups(league_id, round_num):
        calls.append((league_id, round_num))
        return [{"roster_id": 1, "matchup_id": 3}, {"roster_id": 2, "matchup_id": 3}]

    with _matchup_world([]):
        with patch("modules.sleeper.get_matchups", side_effect=fake_get_matchups):
            client.get("/v1/leagues/abc/matchup", headers={"Authorization": "Bearer good-token"})

    assert calls == [("abc", 5)]


def test_trade_outcomes_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    assert client.post("/v1/leagues/abc/trade-outcomes", json={}).status_code == 401
    assert client.get("/v1/trade-outcomes/pending").status_code == 401
    assert client.post("/v1/trade-outcomes/some-id/answer", json={"outcome": "yes"}).status_code == 401


def test_record_trade_share_writes_a_snapshot_with_callers_own_token(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    post_response = Mock(status_code=201)

    with patch("requests.get", return_value=auth_user_response):
        with patch("requests.post", return_value=post_response) as mock_post:
            response = client.post(
                "/v1/leagues/abc/trade-outcomes",
                json={
                    "partner_team_name": "Team Rocket",
                    "send": [{"name": "Player A", "position": "RB"}],
                    "receive": [{"name": "Player B", "position": "WR"}],
                    "value_edge_label": "+120",
                },
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "reason": ""}
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer good-token"
    body = call_kwargs["json"]
    assert body["user_id"] == "user-123"
    assert body["league_id"] == "abc"
    assert body["partner_team_name"] == "Team Rocket"
    assert body["trade_summary"]["send"] == [{"name": "Player A", "position": "RB"}]
    assert body["trade_summary"]["receive"] == [{"name": "Player B", "position": "WR"}]
    assert body["trade_summary"]["value_edge_label"] == "+120"


def test_record_trade_share_fails_closed_when_table_missing(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    post_response = Mock(status_code=404)

    with patch("requests.get", return_value=auth_user_response):
        with patch("requests.post", return_value=post_response):
            response = client.post(
                "/v1/leagues/abc/trade-outcomes",
                json={"partner_team_name": "Team Rocket"},
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"ok": False, "reason": "not_available"}


def test_pending_trade_outcomes_returns_real_rows(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    pending_response = Mock(status_code=200)
    pending_response.json.return_value = [
        {
            "id": "outcome-1",
            "league_id": "abc",
            "partner_team_name": "Team Rocket",
            "trade_summary": {"send": [], "receive": [], "value_edge_label": "+120"},
            "shared_at": "2026-09-01T00:00:00Z",
        }
    ]

    with patch("requests.get", side_effect=[auth_user_response, pending_response]) as mock_get:
        response = client.get("/v1/trade-outcomes/pending", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["outcomes"] == [
        {
            "id": "outcome-1",
            "league_id": "abc",
            "partner_team_name": "Team Rocket",
            "trade_summary": {"send": [], "receive": [], "value_edge_label": "+120"},
            "shared_at": "2026-09-01T00:00:00Z",
        }
    ]
    # The pending query must filter to this user's own rows, still-pending
    # outcomes, an aged-enough shared_at, and an expired-or-absent snooze —
    # not just "everything in the table".
    pending_url = mock_get.call_args_list[1].args[0]
    assert "user_id=eq.user-123" in pending_url
    assert "outcome=eq.pending" in pending_url
    assert "shared_at=lte." in pending_url
    assert "snoozed_until" in pending_url


def test_pending_trade_outcomes_fails_soft_when_table_unreachable(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    error_response = Mock(status_code=404)

    with patch("requests.get", side_effect=[auth_user_response, error_response]):
        response = client.get("/v1/trade-outcomes/pending", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    assert response.json() == {"ok": True, "outcomes": []}


def test_answer_trade_outcome_rejects_an_invalid_outcome(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.post(
            "/v1/trade-outcomes/outcome-1/answer",
            json={"outcome": "maybe"},
            headers={"Authorization": "Bearer good-token"},
        )
    assert response.status_code == 422


def test_answer_trade_outcome_records_yes_with_callers_own_token(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    patch_response = Mock(status_code=204)

    with patch("requests.get", return_value=auth_user_response):
        with patch("requests.patch", return_value=patch_response) as mock_patch:
            response = client.post(
                "/v1/trade-outcomes/outcome-1/answer",
                json={"outcome": "yes"},
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "reason": ""}
    call_kwargs = mock_patch.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer good-token"
    assert call_kwargs["json"]["outcome"] == "yes"
    assert "outcome_recorded_at" in call_kwargs["json"]
    patch_url = mock_patch.call_args.args[0]
    assert "id=eq.outcome-1" in patch_url
    assert "user_id=eq.user-123" in patch_url


def test_answer_trade_outcome_still_pending_only_snoozes(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    patch_response = Mock(status_code=204)

    with patch("requests.get", return_value=auth_user_response):
        with patch("requests.patch", return_value=patch_response) as mock_patch:
            response = client.post(
                "/v1/trade-outcomes/outcome-1/answer",
                json={"outcome": "still_pending"},
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "reason": ""}
    call_kwargs = mock_patch.call_args.kwargs
    assert "snoozed_until" in call_kwargs["json"]
    assert "outcome" not in call_kwargs["json"]
    assert "outcome_recorded_at" not in call_kwargs["json"]


def test_save_league_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    assert client.post("/v1/leagues/save", json={"league_id": "123"}).status_code == 401
    assert client.get("/v1/sleeper/leagues?username=gm").status_code == 401


def test_me_reports_the_saved_league_cap_for_the_plan(monkeypatch):
    client = _client(monkeypatch)
    from modules import saved_leagues

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    free_profile = Mock(status_code=200)
    free_profile.json.return_value = [{"entitlement": "free"}]
    premium_profile = Mock(status_code=200)
    premium_profile.json.return_value = [{"entitlement": "premium"}]

    with patch("requests.get", side_effect=[auth_user_response, free_profile]):
        free = client.get("/v1/me", headers={"Authorization": "Bearer good-token"})
    with patch("requests.get", side_effect=[auth_user_response, premium_profile]):
        paid = client.get("/v1/me", headers={"Authorization": "Bearer good-token"})

    # The client renders the league wall from this number, so it has to be
    # the server's cap — never a constant duplicated in the app.
    assert free.json()["user"]["league_cap"] == saved_leagues.MAX_LEAGUES_FREE
    assert paid.json()["user"]["league_cap"] == saved_leagues.MAX_LEAGUES_PREMIUM


def test_save_league_rejects_empty_league_id(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        response = client.post(
            "/v1/leagues/save",
            json={"league_id": "   "},
            headers={"Authorization": "Bearer good-token"},
        )
    assert response.status_code == 422


def test_save_league_rejects_a_league_sleeper_does_not_have(monkeypatch):
    """A typo'd id must not become a permanent dead row on Home."""

    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper.get_league", return_value={}):
            with patch("requests.post") as mock_post:
                response = client.post(
                    "/v1/leagues/save",
                    json={"league_id": "999999999999999999"},
                    headers={"Authorization": "Bearer good-token"},
                )

    assert response.status_code == 200
    assert response.json()["reason"] == "league_not_found"
    mock_post.assert_not_called()


def test_save_league_enforces_the_free_tier_cap(monkeypatch):
    client = _client(monkeypatch)
    from modules import saved_leagues

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]
    existing_response = Mock(status_code=200)
    existing_response.json.return_value = [{"league_id": "already-saved"}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response, existing_response]):
        with patch("modules.sleeper.get_league", return_value={"league_id": "new-league", "name": "Second"}):
            with patch("requests.post") as mock_post:
                response = client.post(
                    "/v1/leagues/save",
                    json={"league_id": "new-league"},
                    headers={"Authorization": "Bearer good-token"},
                )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["reason"] == "at_cap"
    assert body["cap"] == saved_leagues.MAX_LEAGUES_FREE
    # Refused means refused: nothing is written on the way out.
    mock_post.assert_not_called()


def test_save_league_lets_premium_past_the_free_cap(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "premium", "sleeper_username": "gm_dynasty"}]
    existing_response = Mock(status_code=200)
    existing_response.json.return_value = [{"league_id": "already-saved"}]
    write_response = Mock(status_code=201)
    write_response.json.return_value = []

    with patch("requests.get", side_effect=[auth_user_response, profile_response, existing_response]):
        with patch("modules.sleeper.get_league", return_value={"league_id": "new-league", "name": "Second"}):
            with patch("modules.sleeper.get_user_roster_id", return_value=4):
                with patch("requests.post", return_value=write_response) as mock_post:
                    response = client.post(
                        "/v1/leagues/save",
                        json={"league_id": "new-league"},
                        headers={"Authorization": "Bearer good-token"},
                    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    written = mock_post.call_args.kwargs["json"]
    assert written["user_id"] == "user-123"
    assert written["league_id"] == "new-league"
    assert written["league_name"] == "Second"
    assert written["roster_id"] == "4"
    # Not the account's first league, so it must not steal the default.
    assert written["is_default"] is False


def test_save_league_makes_a_first_league_the_default(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]
    existing_response = Mock(status_code=200)
    existing_response.json.return_value = []
    clear_default_response = Mock(status_code=204)
    write_response = Mock(status_code=201)
    write_response.json.return_value = []

    with patch("requests.get", side_effect=[auth_user_response, profile_response, existing_response]):
        with patch("modules.sleeper.get_league", return_value={"league_id": "first", "name": "Dynasty"}):
            with patch("requests.patch", return_value=clear_default_response):
                with patch("requests.post", return_value=write_response) as mock_post:
                    response = client.post(
                        "/v1/leagues/save",
                        json={"league_id": "first", "sleeper_username": "gm_dynasty"},
                        headers={"Authorization": "Bearer good-token"},
                    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["league"] == {"league_id": "first", "league_name": "Dynasty", "is_default": True}
    assert mock_post.call_args.kwargs["json"]["sleeper_username"] == "gm_dynasty"


def test_save_league_allows_resaving_a_league_already_on_the_account(monkeypatch):
    """Re-saving refreshes name/roster/default — an update, not a new league,
    so a Free account at cap must not be blocked from it."""

    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]
    existing_response = Mock(status_code=200)
    existing_response.json.return_value = [{"league_id": "already-saved"}]
    write_response = Mock(status_code=201)
    write_response.json.return_value = []

    with patch("requests.get", side_effect=[auth_user_response, profile_response, existing_response]):
        with patch("modules.sleeper.get_league", return_value={"league_id": "already-saved", "name": "Dynasty"}):
            with patch("requests.post", return_value=write_response):
                response = client.post(
                    "/v1/leagues/save",
                    json={"league_id": "already-saved"},
                    headers={"Authorization": "Bearer good-token"},
                )

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_save_league_fails_closed_when_the_saved_league_count_is_unreadable(monkeypatch):
    client = _client(monkeypatch)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": ""}]
    error_response = Mock(status_code=500)
    error_response.json.return_value = {"message": "boom"}

    with patch("requests.get", side_effect=[auth_user_response, profile_response, error_response]):
        with patch("modules.sleeper.get_league", return_value={"league_id": "new", "name": "Dynasty"}):
            with patch("requests.post") as mock_post:
                response = client.post(
                    "/v1/leagues/save",
                    json={"league_id": "new"},
                    headers={"Authorization": "Bearer good-token"},
                )

    assert response.json() == {"ok": False, "reason": "not_available", "cap": 1}
    mock_post.assert_not_called()


def test_lookup_sleeper_leagues_returns_the_picker_options(monkeypatch):
    client = _client(monkeypatch)
    from modules import sleeper_leagues

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    lookup = sleeper_leagues.LeagueLookupResult(
        [{"league_id": "abc", "name": "Dynasty", "season": "2026", "total_rosters": 12}],
        "ok",
    )

    with patch("requests.get", return_value=auth_user_response):
        with patch("modules.sleeper_leagues.lookup_user_leagues", return_value=lookup) as mock_lookup:
            response = client.get(
                "/v1/sleeper/leagues?username=gm_dynasty",
                headers={"Authorization": "Bearer good-token"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["username"] == "gm_dynasty"
    assert body["leagues"] == [
        {"league_id": "abc", "name": "Dynasty", "season": "2026", "total_rosters": 12},
    ]
    mock_lookup.assert_called_once_with("gm_dynasty")


def test_lookup_sleeper_leagues_falls_back_to_the_linked_username(monkeypatch):
    client = _client(monkeypatch)
    from modules import sleeper_leagues

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": "linked_gm"}]

    with patch("requests.get", side_effect=[auth_user_response, profile_response]):
        with patch(
            "modules.sleeper_leagues.lookup_user_leagues",
            return_value=sleeper_leagues.LeagueLookupResult([], "no_leagues"),
        ) as mock_lookup:
            response = client.get("/v1/sleeper/leagues", headers={"Authorization": "Bearer good-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "no_leagues"
    assert body["message"]
    mock_lookup.assert_called_once_with("linked_gm")

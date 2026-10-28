"""Paywall circumvention regressions (audit 2026-10, docs/paywall-audit-2026-10.md).

Every test drives the real FastAPI app through TestClient as a FREE account
(fake auth/profile) and pins one leak that used to let it exceed the Free
allowance. Redis is conftest's autouse fakeredis, fresh per test.
"""

from __future__ import annotations

import contextlib
from unittest.mock import patch

import pytest

from modules import free_tier_ledger
from tests.test_mobile_api_service import (
    _TRADE_ANALYZER_LEAGUE,
    _all_trades_rosters,
    _client,
    _fake_idea_record,
    _fake_roster_frame,
)

AUTH = {"Authorization": "Bearer good-token"}


def _records_for(strategy: str, lens: str, count: int = 6, roster_id: int = 1) -> list[dict]:
    return [
        _fake_idea_record(f"{strategy}-{lens}-r{roster_id}-partner-{i}", gain=60 - i) for i in range(count)
    ]


@pytest.fixture
def free_env(monkeypatch):
    """A Free account, one saved league ('abc'), a roster in it, and an idea
    engine whose board differs per (strategy, lens)."""

    client = _client(monkeypatch)
    state = {"entitlement": "free", "saved": ["abc"]}
    monkeypatch.setattr(
        "services.mobile_api_service._fetch_saved_leagues_cached",
        lambda *a, **k: ([{"league_id": lid, "sleeper_username": "gm_dynasty"} for lid in state["saved"]], ""),
    )
    monkeypatch.setattr("services.mobile_api_service._fetch_gm_target_player_ids", lambda *a, **k: ((), ()))
    monkeypatch.setattr("services.mobile_api_service._fetch_team_stance", lambda *a, **k: "")
    monkeypatch.setattr(
        "services.mobile_api_service._fetch_profile_fields",
        lambda *a, **k: {"entitlement": state["entitlement"], "sleeper_username": "gm_dynasty", "status": "ok"},
    )

    def fake_cached(*, league_id, roster_id, strategy, lens, **kwargs):
        return _records_for(strategy, lens, roster_id=roster_id)

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch(
            "services.mobile_api_service.auth_supabase.fetch_auth_user",
            return_value=({"id": "user-123", "email": "gm@example.com"}, ""),
        ))
        stack.enter_context(patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"))
        stack.enter_context(patch("modules.sleeper.get_rosters", return_value=_all_trades_rosters(4)))
        stack.enter_context(patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE))
        stack.enter_context(patch("modules.sleeper.get_league_roster_profiles", return_value={}))
        stack.enter_context(patch(
            "modules.league_rankings.build_league_rankings_frame_cached", return_value=__import__("pandas").DataFrame()
        ))
        stack.enter_context(patch("modules.rankings.load_players", return_value=_fake_roster_frame()))
        stack.enter_context(patch(
            "modules.player_eligibility.filter_current_fantasy_players", side_effect=lambda df, **kw: df
        ))
        stack.enter_context(patch("modules.trade_hub_engine.generate_trade_idea_records_cached", side_effect=fake_cached))
        yield client, state


def _hub(client, league="abc", **params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    response = client.get(f"/v1/leagues/{league}/trade-hub?{query}", headers=AUTH)
    assert response.status_code == 200
    return response.json()


def _ids(body):
    return {card["recommendation_id"] for card in body["ideas"]}


def test_forged_ad_unlocks_cannot_grant_the_full_bonus(free_env):
    client, _ = free_env
    # Before: ad_unlocks=3 straight from the query string -> 2 + 6 = 8 ideas.
    body = _hub(client, strategy="retool", ad_unlocks=3)
    assert len(body["ideas"]) <= 4
    # Hammering the same forged claim inside the cooldown does not add more.
    for _ in range(5):
        body = _hub(client, strategy="retool", ad_unlocks=3)
    assert len(body["ideas"]) <= 4
    assert body["entitlement"]["ad_unlocks_applied"] == 1


def test_switching_strategy_and_lens_does_not_mint_new_free_ideas(free_env):
    client, _ = free_env
    seen: set[str] = set()
    for strategy in ("retool", "contender", "rebuild"):
        for lens in ("Dynasty", "Rebuild", "Non-Dynasty"):
            seen |= _ids(_hub(client, strategy=strategy, lens=lens))
    assert len(seen) <= 2  # one shared pool, not 2 per board


def test_all_trades_pages_and_shown_count_reset_do_not_reset_the_cap(free_env):
    client, _ = free_env
    seen: set[str] = set()
    for cursor in (0, 3, 0, 3):
        response = client.get(
            f"/v1/leagues/abc/all-trades?page_size=3&cursor={cursor}&shown_count=0&ad_unlocks=0", headers=AUTH
        )
        assert response.status_code == 200
        seen |= {card["recommendation_id"] for card in response.json()["ideas"]}
    assert len(seen) <= 2


def test_trade_hub_and_all_trades_draw_from_one_pool(free_env):
    client, _ = free_env
    hub_ids = _ids(_hub(client, strategy="retool"))
    response = client.get("/v1/leagues/abc/all-trades?page_size=6&cursor=0", headers=AUTH)
    all_ids = {card["recommendation_id"] for card in response.json()["ideas"]}
    assert len(hub_ids | all_ids) <= 2


def test_dashboard_headline_trade_idea_counts_against_the_same_pool(free_env):
    client, _ = free_env
    # Use up the pool on one board, then ask the Dashboard (different lens ->
    # different headline idea): the trade tile must be withheld.
    _hub(client, strategy="retool", lens="Dynasty")
    response = client.get("/v1/leagues/abc/dashboard?lens=Rebuild", headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert not [item for item in body["items"] if "trade_package" in (item.get("presentation") or {})]
    assert free_tier_ledger.pool_size("user-123") <= 2


def test_dashboard_headline_alone_is_visible_then_trade_hub_stays_within_cap(free_env):
    client, _ = free_env
    dash = client.get("/v1/leagues/abc/dashboard?lens=Dynasty", headers=AUTH).json()
    tiles = [i for i in dash["items"] if "trade_package" in (i.get("presentation") or {})]
    assert len(tiles) <= 1
    hub = _hub(client, strategy="retool", lens="Dynasty")
    assert free_tier_ledger.pool_size("user-123") <= 2
    assert len(hub["ideas"]) <= 2


def test_share_card_refuses_a_hidden_idea(free_env):
    client, _ = free_env
    from modules import trade_hub_presentation

    records = _records_for("retool", "Dynasty")
    shown = _ids(_hub(client, strategy="retool", lens="Dynasty"))
    hidden_id = next(
        trade_hub_presentation.idea_recommendation_id(r)
        for r in records
        if trade_hub_presentation.idea_recommendation_id(r) not in shown
    )
    from types import SimpleNamespace

    shown_id = next(iter(shown))
    with patch(
        "services.mobile_api_service.share_recommendation_cards.build_trade_share_card",
        return_value=SimpleNamespace(is_shareable=True, decline_reason=""),
    ), patch("services.mobile_api_service.share_card_renderer.render_share_card_png", return_value=b"png"):
        ok = client.get(
            f"/v1/leagues/abc/trade-hub/{shown_id}/share-card.png?strategy=retool&lens=Dynasty", headers=AUTH
        )
        locked = client.get(
            f"/v1/leagues/abc/trade-hub/{hidden_id}/share-card.png?strategy=retool&lens=Dynasty", headers=AUTH
        )
    assert ok.status_code == 200
    assert locked.status_code == 404


def test_free_account_cannot_use_a_second_unsaved_league(free_env):
    client, _ = free_env
    body = _hub(client, league="other-league", strategy="retool")
    assert body["ideas"] == []
    assert body["reason"] == "free_league_cap"
    dash = client.get("/v1/leagues/other-league/dashboard", headers=AUTH).json()
    assert dash["items"] == []
    glance = client.get(
        "/v1/leagues/other-league/all-trades?cursor=0", headers=AUTH
    ).json()
    assert glance["ideas"] == []


def test_free_account_with_no_saved_league_gets_exactly_one_league(free_env):
    client, state = free_env
    state["saved"] = []
    assert _hub(client, league="first", strategy="retool")["reason"] == ""
    assert _hub(client, league="second", strategy="retool")["reason"] == "free_league_cap"
    # Still allowed to go back to the first one.
    assert _hub(client, league="first", strategy="retool")["reason"] == ""


def test_pro_account_is_not_limited_by_the_league_cap_or_pool(free_env):
    client, state = free_env
    state["entitlement"] = "premium"
    body = _hub(client, league="other-league", strategy="retool", ad_unlocks=0)
    assert len(body["ideas"]) == 6
    assert body["reason"] == ""


def test_parallel_requests_never_exceed_the_pool_cap():
    import threading

    results: list[set[str]] = []
    lock = threading.Lock()

    def worker(i: int) -> None:
        allowed = free_tier_ledger.claim_trade_ideas("u", [f"idea-{i}-{j}" for j in range(4)], 2)
        with lock:
            results.append(allowed)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert free_tier_ledger.pool_size("u") <= 2


def test_ad_unlock_grants_respect_cooldown_and_daily_max():
    assert free_tier_ledger.grant_ad_unlock_if_claimed("u", 3, 3) == 1
    assert free_tier_ledger.grant_ad_unlock_if_claimed("u", 3, 3) == 1  # cooldown
    assert free_tier_ledger.ad_unlocks_granted("u") == 1


def test_live_draft_trade_evaluator_is_pro_only(free_env):
    client, _ = free_env
    with patch("services.mobile_api_service._load_active_live_draft", return_value=({}, {})):
        options = client.get("/v1/leagues/abc/live-draft/d1/trade-evaluator", headers=AUTH).json()
        verdict = client.post(
            "/v1/leagues/abc/live-draft/d1/trade-evaluator",
            headers=AUTH,
            json={"send_pick_keys": ["pick:1"], "receive_player_ids": ["p1"]},
        ).json()
    assert options["is_premium"] is False and options["pick_options"] == []
    assert verdict["is_premium"] is False and verdict["verdict"] is None


def test_weekly_trade_analyzer_limit_is_enforced_server_side():
    from modules import trade_eval_usage

    limit = trade_eval_usage.FREE_WEEKLY_TRADE_EVAL_LIMIT
    assert all(free_tier_ledger.consume_weekly_trade_eval("u", limit) for _ in range(limit))
    assert free_tier_ledger.consume_weekly_trade_eval("u", limit) is False
    assert free_tier_ledger.consume_weekly_trade_eval("someone-else", limit) is True


def test_analyzer_route_returns_weekly_limit_reached_for_free(free_env):
    client, _ = free_env
    from modules import trade_eval_usage

    for _ in range(trade_eval_usage.FREE_WEEKLY_TRADE_EVAL_LIMIT):
        assert free_tier_ledger.consume_weekly_trade_eval("user-123", trade_eval_usage.FREE_WEEKLY_TRADE_EVAL_LIMIT)
    response = client.post(
        "/v1/leagues/abc/trade-analyzer", headers=AUTH, json={"send_player_ids": ["my1"], "receive_player_ids": ["x"]}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] is None and body["reason"] == "weekly_limit_reached"
    assert body["limit"]["limit"] == trade_eval_usage.FREE_WEEKLY_TRADE_EVAL_LIMIT
    assert body["limit"]["window"] == "week"
    assert body["limit"]["resets_at"] == free_tier_ledger.next_weekly_reset().isoformat()


def test_next_weekly_reset_is_the_ledger_window_boundary():
    from datetime import datetime, timezone

    wed = datetime(2026, 10, 28, 15, 30, tzinfo=timezone.utc)
    assert free_tier_ledger.next_weekly_reset(wed) == datetime(2026, 11, 2, tzinfo=timezone.utc)
    mon = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
    assert free_tier_ledger.next_weekly_reset(mon) == datetime(2026, 11, 9, tzinfo=timezone.utc)
    # Same week key just before the boundary, next key at it.
    assert free_tier_ledger._week(datetime(2026, 11, 1, 23, 59, tzinfo=timezone.utc)) == "20261026"
    assert free_tier_ledger._week(datetime(2026, 11, 2, tzinfo=timezone.utc)) == "20261102"


def _exhaust_analyzer_quota():
    from modules import trade_eval_usage

    limit = trade_eval_usage.FREE_WEEKLY_TRADE_EVAL_LIMIT
    for _ in range(limit):
        assert free_tier_ledger.consume_weekly_trade_eval("user-123", limit)


def test_free_analyzer_quota_gate_is_enforced_server_side(free_env):
    client, _ = free_env
    _exhaust_analyzer_quota()
    body = {"send_player_ids": ["my1"], "receive_player_ids": ["x"]}
    # No header (or any bogus bypass header) changes anything: the exhausted
    # Free account is gated, so the web share card can never be a quota bypass.
    for headers in ({}, {"X-Share-Card-Token": "anything"}):
        r = client.post("/v1/leagues/abc/trade-analyzer", headers={**AUTH, **headers}, json=body)
        assert r.json()["verdict"] is None and r.json()["reason"] == "weekly_limit_reached"


# --------------------------------------------------------------------------
# Playoff Odds, Draft Center, College Scouting are Pro (owner 2026-10-23).
# Free gets a locked payload and the expensive/withheld work never runs; Pro,
# Front Office and trialing accounts (stored as Pro) get the real data.
# --------------------------------------------------------------------------

_PRO_FEATURE_ENTITLEMENTS = [
    ("free", False),
    ("premium", True),
    ("front_office", True),
]


def _set_profile(monkeypatch, entitlement: str, **extra):
    monkeypatch.setattr(
        "services.mobile_api_service._fetch_profile_fields",
        lambda *a, **k: {"entitlement": entitlement, "sleeper_username": "gm_dynasty", "status": "ok", **extra},
    )


@pytest.fixture
def pro_feature_client(monkeypatch):
    client = _client(monkeypatch)
    with patch(
        "services.mobile_api_service.auth_supabase.fetch_auth_user",
        return_value=({"id": "user-123", "email": "gm@example.com"}, ""),
    ):
        yield client


@pytest.mark.parametrize("entitlement,allowed", _PRO_FEATURE_ENTITLEMENTS)
def test_playoff_odds_is_pro_only(pro_feature_client, monkeypatch, entitlement, allowed):
    _set_profile(monkeypatch, entitlement)
    real = {"ok": True, "reason": "", "teams": [{"roster_id": "1", "playoff_probability": 61.0}]}
    with patch("modules.playoff_simulator.build_league_playoff_odds_cached", return_value=real) as sim:
        body = pro_feature_client.get("/v1/leagues/abc/playoff-odds", headers=AUTH).json()
    if allowed:
        assert body["teams"] == real["teams"] and body["is_premium"] is True and body["upsell"] is None
    else:
        assert body["reason"] == "premium_required" and body["teams"] == []
        assert body["is_premium"] is False and body["upsell"]["title"]
        sim.assert_not_called()


def test_playoff_odds_trialing_account_counts_as_pro(pro_feature_client, monkeypatch):
    _set_profile(monkeypatch, "premium", trial_ends_at="2999-01-01T00:00:00+00:00")
    real = {"ok": True, "reason": "", "teams": [{"roster_id": "1", "playoff_probability": 40.0}]}
    with patch("modules.playoff_simulator.build_league_playoff_odds_cached", return_value=real):
        body = pro_feature_client.get("/v1/leagues/abc/playoff-odds", headers=AUTH).json()
    assert body["teams"] and body["is_premium"] is True


@pytest.mark.parametrize("entitlement,allowed", _PRO_FEATURE_ENTITLEMENTS)
def test_draft_center_is_pro_only(pro_feature_client, monkeypatch, entitlement, allowed):
    _set_profile(monkeypatch, entitlement)
    with (
        patch("modules.sleeper.get_league", return_value=_TRADE_ANALYZER_LEAGUE),
        patch("modules.rankings.load_players") as load,
        patch("modules.rankings.build_players_table") as build,
        patch("modules.player_eligibility.filter_current_fantasy_players", side_effect=lambda df, **kw: df),
    ):
        empty = __import__("pandas").DataFrame()
        load.return_value = empty
        build.return_value = empty
        body = pro_feature_client.get("/v1/leagues/abc/draft-center", headers=AUTH).json()
    if allowed:
        # Reaches the real pipeline (empty fixture frame -> no_player_data).
        assert body["reason"] == "no_player_data"
    else:
        assert body["reason"] == "premium_required"
        assert body["decision_cards"] == [] and body["partner_cards"] == [] and body["posture"] is None
        assert body["is_premium"] is False and body["upsell"]["title"]
        load.assert_not_called()


@pytest.mark.parametrize("entitlement,allowed", _PRO_FEATURE_ENTITLEMENTS)
def test_college_scouting_is_pro_only(pro_feature_client, monkeypatch, entitlement, allowed):
    _set_profile(monkeypatch, entitlement)
    prospect = {"id": "p1", "name": "Real Prospect", "position": "QB", "school": "State", "draft_year": 2027}
    with (
        patch("modules.college_scouting.get_cached_all_prospects", return_value=([prospect], "")) as cat,
        patch("modules.college_scouting.get_cached_all_scouting_reports", return_value=([], "")),
        patch("modules.account_store.fetch_rows", return_value=([], "")),
        patch("modules.account_store.upsert_row", return_value=(True, "")) as upsert,
    ):
        listing = pro_feature_client.get("/v1/scouting/prospects", headers=AUTH).json()
        report = pro_feature_client.post(
            "/v1/scouting/prospects/p1/report", json={"grade": 4}, headers=AUTH
        ).json()
        follow = pro_feature_client.post("/v1/scouting/watchlist/p1", headers=AUTH).json()
    if allowed:
        assert [p["name"] for p in listing["prospects"]] == ["Real Prospect"]
        assert listing["is_premium"] is True
        assert report["ok"] is True and follow["ok"] is True
    else:
        assert listing["reason"] == "premium_required" and listing["prospects"] == []
        assert listing["is_premium"] is False and listing["upsell"]["title"]
        assert report["ok"] is False and report["reason"] == "premium_required"
        assert follow["ok"] is False and follow["reason"] == "premium_required"
        cat.assert_not_called()
        upsert.assert_not_called()

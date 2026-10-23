"""General polish + performance pass — freshness, copy, and presentation contracts."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

from modules import game_plan_package
from modules import game_plan_process_cache
from modules import sleeper


ROOT = Path(__file__).resolve().parents[1]


def test_waiver_pool_digest_changes_package_signature():
    base = dict(
        account_user_id="u1",
        league_id="L1",
        roster_id="7",
        prepared_frame_signature="frame",
        roster_state_version="rv1",
    )
    a = game_plan_package.build_package_signature(**base, waiver_pool_digest="pool-a")
    b = game_plan_package.build_package_signature(**base, waiver_pool_digest="pool-b")
    c = game_plan_package.build_package_signature(**base, waiver_pool_digest="pool-a")
    assert a != b
    assert a == c
    components = game_plan_package.package_fingerprint_components(
        **base, waiver_pool_digest="pool-a"
    )
    assert components["waiver_pool_digest"]
    assert game_plan_package.PACKAGE_FINGERPRINT_VERSION == 3


def test_rostered_universe_digest_is_order_stable_and_fa_sensitive():
    same_a = game_plan_package.rostered_universe_digest(
        {"1": ["p2", "p1"], "2": ["p3"]}
    )
    same_b = game_plan_package.rostered_universe_digest(
        {"2": ["p3"], "1": ["p1", "p2"]}
    )
    dropped = game_plan_package.rostered_universe_digest(
        {"1": ["p1", "p2"], "2": []}
    )
    assert same_a == same_b
    assert same_a != dropped
    assert game_plan_package.rostered_universe_digest({}) == ""


def test_league_process_signature_includes_waiver_pool_digest():
    a = game_plan_process_cache.build_league_process_signature(
        prepared_frame_signature="f",
        league_id="L1",
        score_field="value_score",
        waiver_pool_digest="pool-a",
    )
    b = game_plan_process_cache.build_league_process_signature(
        prepared_frame_signature="f",
        league_id="L1",
        score_field="value_score",
        waiver_pool_digest="pool-b",
    )
    assert a != b


def test_process_league_context_respects_soft_ttl():
    game_plan_process_cache.clear_process_game_plan_caches()
    calls = {"n": 0}

    def builder():
        calls["n"] += 1
        return {"n": calls["n"]}

    first, miss = game_plan_process_cache.get_or_build_league_context(
        signature="ttl-league", builder=builder
    )
    assert miss is False
    assert first["n"] == 1
    second, hit = game_plan_process_cache.get_or_build_league_context(
        signature="ttl-league", builder=builder
    )
    assert hit is True
    assert calls["n"] == 1
    game_plan_process_cache._PROCESS_LEAGUE_BUILT_AT["ttl-league"] = time.time() - (
        6 * 60 * 60
    )
    third, rebuilt = game_plan_process_cache.get_or_build_league_context(
        signature="ttl-league", builder=builder
    )
    assert rebuilt is False
    assert third["n"] == 2
    assert calls["n"] == 2


def test_process_trade_headline_respects_soft_ttl():
    game_plan_process_cache.clear_process_game_plan_caches()
    calls = {"n": 0}

    def builder():
        calls["n"] += 1
        return [{"id": calls["n"]}]

    first, miss = game_plan_process_cache.get_or_build_trade_headline(
        signature="ttl-trade", builder=builder
    )
    assert miss is False
    second, hit = game_plan_process_cache.get_or_build_trade_headline(
        signature="ttl-trade", builder=builder
    )
    assert hit is True
    assert calls["n"] == 1
    game_plan_process_cache._PROCESS_TRADE_BUILT_AT["ttl-trade"] = time.time() - (
        6 * 60 * 60
    )
    third, rebuilt = game_plan_process_cache.get_or_build_trade_headline(
        signature="ttl-trade", builder=builder
    )
    assert rebuilt is False
    assert third[0]["id"] == 2


def test_manual_refresh_clears_live_sleeper_and_process_memos():
    game_plan_process_cache.clear_process_game_plan_caches()
    game_plan_process_cache.get_or_build_league_context(
        signature="refresh-league", builder=lambda: {"ok": True}
    )
    state: dict = {}
    sig = "refresh-pkg"
    game_plan_package.store_package(state, signature=sig, package={"briefing": {}})
    with patch("modules.sleeper.clear_live_league_endpoint_caches") as clear_live:
        game_plan_package.invalidate_recommendation_packages(state, signature=sig)
    clear_live.assert_called_once()
    assert sig not in game_plan_package._PROCESS_PACKAGE_STORE
    assert "refresh-league" not in game_plan_process_cache._PROCESS_LEAGUE_CONTEXT


def test_package_ttl_stale_clears_live_inputs():
    state: dict = {}
    sig = "stale-pkg"
    game_plan_package.store_package(state, signature=sig, package={"briefing": {}})
    state[game_plan_package.PACKAGE_KEY]["built_at"] = time.time() - (6 * 60 * 60)
    game_plan_package._PROCESS_PACKAGE_STORE[sig]["built_at"] = time.time() - (
        6 * 60 * 60
    )
    with patch("modules.sleeper.clear_live_league_endpoint_caches") as clear_live:
        cached, hit = game_plan_package.lookup_package(state, signature=sig)
    assert hit is False
    assert cached is None
    clear_live.assert_called()
    assert state[game_plan_package.LAST_MISS_REASON_KEY] == "soft_ttl_expired"


def test_clear_live_league_caches_preserve_username_and_players():
    source = (ROOT / "modules" / "sleeper.py").read_text(encoding="utf-8")
    assert "def clear_live_league_endpoint_caches" in source
    assert "_get_rosters_cached.cache_clear()" in source
    assert "get_user_id.cache_clear()" not in source
    assert "get_players.cache_clear()" not in source
    sleeper.clear_live_league_endpoint_caches()


def test_package_signature_still_account_scoped():
    a = game_plan_package.build_package_signature(
        account_user_id="user-a", league_id="L1", roster_id="7"
    )
    b = game_plan_package.build_package_signature(
        account_user_id="user-b", league_id="L1", roster_id="7"
    )
    assert a != b

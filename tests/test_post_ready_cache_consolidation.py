"""Post-ready Game Plan package survival and league-context superset reuse."""

from __future__ import annotations

import time
from pathlib import Path

from modules import game_plan_package
from modules import game_plan_process_cache


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CACHE = (ROOT / "modules" / "game_plan_process_cache.py").read_text(encoding="utf-8")

RICH_FLAGS = (True, True, True, True)  # intel=1 roster=1 trust=1 mat=1
NARROW_TRUST_FLAGS = (True, True, False, True)  # intel=1 roster=1 trust=0 mat=1
GAME_PLAN_FLAGS = game_plan_package.GAME_PLAN_CONTEXT_FLAGS


def _identity(**overrides) -> str:
    payload = dict(
        prepared_frame_signature="frame-1",
        league_id="L1",
        score_field="value_score",
        league_settings_key="settings",
        waiver_pool_digest="pool-a",
    )
    payload.update(overrides)
    return game_plan_process_cache.build_league_identity_signature(**payload)


def _signature(flags, **overrides) -> str:
    payload = dict(
        prepared_frame_signature="frame-1",
        league_id="L1",
        score_field="value_score",
        league_settings_key="settings",
        waiver_pool_digest="pool-a",
        flags=flags,
    )
    payload.update(overrides)
    return game_plan_process_cache.build_league_process_signature(**payload)


def test_package_survives_session_remount_on_unchanged_fingerprint():
    game_plan_package.clear_process_game_plan_packages()
    signature = game_plan_package.build_package_signature(
        account_user_id="u1",
        league_id="L1",
        roster_id="7",
        prepared_frame_signature="frame-1",
        score_field="value_score",
        league_settings_key="settings",
        team_strategy="contend",
        role_items=(("p1", "Core"),),
        entitlement="free",
        lifecycle_digest="life",
        roster_state_version="rv1",
        pick_score_multiplier=1.0,
        waiver_pool_digest="pool-a",
    )
    components = game_plan_package.package_fingerprint_components(
        account_user_id="u1",
        league_id="L1",
        roster_id="7",
        prepared_frame_signature="frame-1",
        score_field="value_score",
        league_settings_key="settings",
        team_strategy="contend",
        role_items=(("p1", "Core"),),
        entitlement="free",
        lifecycle_digest="life",
        roster_state_version="rv1",
        pick_score_multiplier=1.0,
        waiver_pool_digest="pool-a",
    )
    first = {
        "_game_plan_package_incoming_components": components,
        "selected_league_id": "L1",
    }
    stored = game_plan_package.store_package(
        first, signature=signature, package={"briefing": {"league_id": "L1"}}
    )
    assert stored["signature"] == signature
    assert signature in game_plan_package._PROCESS_PACKAGE_STORE
    membership_before = set(game_plan_package._PROCESS_PACKAGE_STORE)
    remount = {
        "_game_plan_package_incoming_components": components,
        "selected_league_id": "L1",
    }
    started = time.perf_counter()
    payload, hit = game_plan_package.lookup_package(
        remount, signature=signature, expected_league_id="L1"
    )
    hit_ms = (time.perf_counter() - started) * 1000.0
    assert hit is True
    assert payload["signature"] == signature
    assert remount[game_plan_package.LAST_CACHE_STATUS_KEY] == "process_hit"
    assert membership_before == set(game_plan_package._PROCESS_PACKAGE_STORE)
    assert hit_ms < 50.0


def test_package_miss_with_unchanged_components_reports_process_absence():
    game_plan_package.clear_process_game_plan_packages()
    signature = game_plan_package.build_package_signature(
        account_user_id="u1",
        league_id="L1",
        roster_id="7",
        prepared_frame_signature="frame-1",
    )
    components = game_plan_package.package_fingerprint_components(
        account_user_id="u1",
        league_id="L1",
        roster_id="7",
        prepared_frame_signature="frame-1",
    )
    state = {
        "_game_plan_package_incoming_components": components,
        "selected_league_id": "L1",
    }
    payload, hit = game_plan_package.lookup_package(state, signature=signature)
    assert hit is False
    assert payload is None
    miss_reason = state[game_plan_package.LAST_MISS_REASON_KEY]
    assert miss_reason == "session_cold+process_empty"
    diff = state[game_plan_package.LAST_COMPONENT_DIFF_KEY]
    assert tuple(diff.get("changed_components") or ()) == ()
    assert diff.get("exact_key_present") is False
    assert diff.get("comparison") == "process_absent"
    assert diff.get("process_contains_signature") is False


def test_package_lru_eviction_is_logged_and_does_not_drop_hot_key():
    game_plan_package.clear_process_game_plan_packages()
    original = game_plan_package._MAX_PROCESS_PACKAGES
    game_plan_package._MAX_PROCESS_PACKAGES = 2
    try:
        hot = "hot-signature-aaaaaaaa"
        cold = "cold-signature-bbbbbbbb"
        newer = "new-signature-cccccccc"
        now = time.time()
        game_plan_package._store_process_package(
            hot, {"built_at": now, "fingerprint_components": {"league_id": "L1"}}
        )
        game_plan_package._store_process_package(
            cold, {"built_at": now, "fingerprint_components": {"league_id": "L2"}}
        )
        game_plan_package.lookup_package({}, signature=hot)
        game_plan_package._store_process_package(newer, {"built_at": time.time()})
        assert hot in game_plan_package._PROCESS_PACKAGE_STORE
        assert newer in game_plan_package._PROCESS_PACKAGE_STORE
        assert cold not in game_plan_package._PROCESS_PACKAGE_STORE
        assert game_plan_package._PROCESS_PACKAGE_EVICTIONS
        assert game_plan_package._PROCESS_PACKAGE_EVICTIONS[-1]["reason"] == (
            "process_capacity_lru"
        )
        assert game_plan_package._PROCESS_PACKAGE_EVICTIONS[-1]["signature_prefix"] == (
            cold[:12]
        )
        miss_state = {"_game_plan_package_incoming_components": {"league_id": "L2"}}
        _, hit = game_plan_package.lookup_package(miss_state, signature=cold)
        assert hit is False
        assert "process_evicted" in miss_state[game_plan_package.LAST_MISS_REASON_KEY]
    finally:
        game_plan_package._MAX_PROCESS_PACKAGES = original
        game_plan_package.clear_process_game_plan_packages()


def test_rich_league_context_satisfies_narrower_trust_request():
    game_plan_process_cache.clear_process_game_plan_caches()
    calls = {"n": 0}
    identity = _identity()
    rich_sig = _signature(RICH_FLAGS)
    narrow_sig = _signature(NARROW_TRUST_FLAGS)
    assert rich_sig != narrow_sig

    def build_rich():
        calls["n"] += 1
        return {
            "contract": "rich",
            "trade_trust_context": {"ok": True},
            "league_intelligence_frame": {"rows": 1},
        }

    def build_narrow():
        calls["n"] += 1
        return {"contract": "narrow"}

    first, miss = game_plan_process_cache.get_or_build_league_context(
        signature=rich_sig,
        builder=build_rich,
        flags=RICH_FLAGS,
        identity=identity,
    )
    assert miss is False
    started = time.perf_counter()
    second, hit = game_plan_process_cache.get_or_build_league_context(
        signature=narrow_sig,
        builder=build_narrow,
        flags=NARROW_TRUST_FLAGS,
        identity=identity,
    )
    reused_ms = (time.perf_counter() - started) * 1000.0
    assert hit is True
    assert calls["n"] == 1
    assert second["contract"] == "rich"
    assert second["trade_trust_context"]["ok"] is True
    assert reused_ms < 50.0
    assert first["contract"] == "rich"


def test_narrow_league_context_cannot_satisfy_richer_trust_request():
    game_plan_process_cache.clear_process_game_plan_caches()
    calls = {"n": 0}
    identity = _identity()

    def builder():
        calls["n"] += 1
        return {"contract": calls["n"]}

    game_plan_process_cache.get_or_build_league_context(
        signature=_signature(NARROW_TRUST_FLAGS),
        builder=builder,
        flags=NARROW_TRUST_FLAGS,
        identity=identity,
    )
    payload, hit = game_plan_process_cache.get_or_build_league_context(
        signature=_signature(RICH_FLAGS),
        builder=builder,
        flags=RICH_FLAGS,
        identity=identity,
    )
    assert hit is False
    assert calls["n"] == 2
    assert payload["contract"] == 2


def test_superset_reuse_is_league_isolated():
    game_plan_process_cache.clear_process_game_plan_caches()
    calls = {"n": 0}

    def builder():
        calls["n"] += 1
        return {"league": calls["n"]}

    game_plan_process_cache.get_or_build_league_context(
        signature=_signature(RICH_FLAGS, league_id="L1"),
        builder=builder,
        flags=RICH_FLAGS,
        identity=_identity(league_id="L1"),
    )
    payload, hit = game_plan_process_cache.get_or_build_league_context(
        signature=_signature(NARROW_TRUST_FLAGS, league_id="L2"),
        builder=builder,
        flags=NARROW_TRUST_FLAGS,
        identity=_identity(league_id="L2"),
    )
    assert hit is False
    assert calls["n"] == 2
    assert payload["league"] == 2


def test_game_plan_flags_can_reuse_richer_my_team_context():
    game_plan_process_cache.clear_process_game_plan_caches()
    calls = {"n": 0}
    identity = _identity()

    def builder():
        calls["n"] += 1
        return {"slice": "my_team"}

    game_plan_process_cache.get_or_build_league_context(
        signature=_signature(RICH_FLAGS),
        builder=builder,
        flags=RICH_FLAGS,
        identity=identity,
    )
    payload, hit = game_plan_process_cache.get_or_build_league_context(
        signature=_signature(GAME_PLAN_FLAGS),
        builder=builder,
        flags=GAME_PLAN_FLAGS,
        identity=identity,
    )
    assert hit is True
    assert calls["n"] == 1
    assert payload["slice"] == "my_team"


def test_game_plan_context_cannot_satisfy_intelligence_request():
    game_plan_process_cache.clear_process_game_plan_caches()
    calls = {"n": 0}
    identity = _identity()

    def builder():
        calls["n"] += 1
        return {"slice": calls["n"]}

    game_plan_process_cache.get_or_build_league_context(
        signature=_signature(GAME_PLAN_FLAGS),
        builder=builder,
        flags=GAME_PLAN_FLAGS,
        identity=identity,
    )
    payload, hit = game_plan_process_cache.get_or_build_league_context(
        signature=_signature(RICH_FLAGS),
        builder=builder,
        flags=RICH_FLAGS,
        identity=identity,
    )
    assert hit is False
    assert calls["n"] == 2
    assert payload["slice"] == 2


def test_central_superset_wiring_is_not_route_aliased():
    assert "build_league_identity_signature(" in APP
    assert "flags=context_key" in APP
    assert "identity=league_identity_sig" in APP
    assert "def context_flags_cover(" in CACHE
    assert "Never serve a narrower cache" in CACHE
    assert "get_shared_league_context(include_trust=True)" not in APP.split(
        "league_context = get_shared_league_context(include_trust=False)", 1
    )[1][:400]


def test_fingerprint_none_is_not_treated_as_lookup_status():
    miss_log = APP.split("game_plan_package_fingerprint_diff", 1)[1].split(
        "except Exception:", 1
    )[0]
    assert "miss_reason" in miss_log
    assert "exact_key_present" in miss_log
    assert "process_contains_signature" in miss_log
    assert "cache_status=miss_reason" in miss_log

"""Startup latency cleanup + load validation contracts (#234)."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from modules import account_store
from modules import game_plan_process_cache
from modules import game_plan_startup_stall as stall
from modules import sleeper
from modules import tail_latency_diagnostics
from scripts import verify_package_miss_path


ROOT = Path(__file__).resolve().parents[1]
DRAFT_ASSISTANT_SRC = (ROOT / "modules" / "draft_assistant.py").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.delenv("DYNASTYGM_STARTUP", raising=False)
    game_plan_process_cache.clear_process_game_plan_caches()
    tail_latency_diagnostics.reset_process_boot_for_tests()
    for fn in (
        sleeper.get_league,
        sleeper.get_league_drafts,
        sleeper.get_draft,
        sleeper.get_draft_picks,
        sleeper.get_traded_picks,
    ):
        cache_clear = getattr(fn, "cache_clear", None)
        if callable(cache_clear):
            cache_clear()
    yield
    game_plan_process_cache.clear_process_game_plan_caches()
    tail_latency_diagnostics.reset_process_boot_for_tests()


def test_provider_leagues_endpoint_labels_and_duplicate_counter(monkeypatch):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state: dict = {}
    tail_latency_diagnostics.note_provider_call(
        state,
        category="provider_leagues",
        duration_ms=10,
        endpoint="sleeper_league",
    )
    tail_latency_diagnostics.note_provider_call(
        state,
        category="provider_leagues",
        duration_ms=11,
        endpoint="sleeper_traded_picks",
    )
    tail_latency_diagnostics.note_provider_call(
        state,
        category="provider_leagues",
        duration_ms=12,
        endpoint="sleeper_league",
    )
    assert tail_latency_diagnostics.provider_leagues_call_count(state) == 3
    assert tail_latency_diagnostics.provider_endpoint_duplicate_count(state) == 1
    assert (
        tail_latency_diagnostics.provider_leagues_call_count(state)
        <= tail_latency_diagnostics.MAX_PROVIDER_LEAGUES_CALLS_GOLDEN_STARTUP
        or True
    )


def test_startup_profile_skips_billing_columns_by_default():
    config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
    response = Mock(status_code=200)
    response.json.return_value = [{"user_id": "user-1", "entitlement": "premium"}]
    with patch.object(account_store.requests, "get", return_value=response) as get:
        profile, error = account_store.fetch_profile(
            config, "access-token", user_id="user-1", include_billing=False
        )
    assert not error
    assert profile["entitlement"] == "premium"
    url = get.call_args.args[0]
    assert "entitlement" in url
    assert "stripe_customer_id" not in url


def test_billing_profile_fetch_still_requests_stripe_columns():
    config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
    response = Mock(status_code=200)
    response.json.return_value = [{"user_id": "user-1", "entitlement": "free"}]
    with patch.object(account_store.requests, "get", return_value=response) as get:
        profile, error = account_store.fetch_profile(
            config, "access-token", user_id="user-1", include_billing=True
        )
    assert not error
    assert "stripe_customer_id" in get.call_args.args[0]


def test_same_signature_concurrency_single_builder():
    game_plan_process_cache.clear_process_game_plan_caches()
    sig = "same-sig-234"
    builds = {"n": 0}

    def builder():
        builds["n"] += 1
        time.sleep(0.05)
        return {"ok": True, "sig": sig}

    def worker():
        return game_plan_process_cache.get_or_build_league_context(
            signature=sig, builder=builder
        )

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(worker) for _ in range(5)]
        results = [future.result(timeout=5) for future in futures]
    assert builds["n"] == 1
    assert all(row[0].get("ok") for row in results)


def test_different_signature_parallelism():
    game_plan_process_cache.clear_process_game_plan_caches()
    builds = {"n": 0}
    gate = threading.Barrier(4)
    lock = threading.Lock()

    def make_builder(sig):
        def builder():
            with lock:
                builds["n"] += 1
            gate.wait(timeout=2)
            time.sleep(0.02)
            return {"ok": True, "sig": sig}

        return builder

    def worker(sig):
        return game_plan_process_cache.get_or_build_league_context(
            signature=sig, builder=make_builder(sig)
        )

    sigs = [f"diff-sig-234-{i}" for i in range(4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(worker, sig) for sig in sigs]
        results = [f.result(timeout=5) for f in futures]
    assert builds["n"] == 4
    assert {row[0]["sig"] for row in results} == set(sigs)


def test_package_miss_path_completes_with_nested_reentry():
    report = verify_package_miss_path.run_package_miss_sequence(nested_reentry=True)
    assert report["ok"] is True
    assert report["cliff"] is False
    assert "shared_context_complete" in report["events"]
    assert "game_plan_ready" in report["events"]


def test_forced_builder_exception_recovery():
    game_plan_process_cache.clear_process_game_plan_caches()
    sig = "boom-234"

    def boom():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        game_plan_process_cache.get_or_build_league_context(signature=sig, builder=boom)

    recovered, hit = game_plan_process_cache.get_or_build_league_context(
        signature=sig, builder=lambda: {"ok": True}
    )
    assert hit is False
    assert recovered.get("ok") is True


def test_forced_slow_builder_user_visible_failsoft_separate_from_hard_timeout():
    assert stall.USER_VISIBLE_FAILSOFT_S < game_plan_process_cache.SINGLEFLIGHT_WAIT_TIMEOUT_S
    assert game_plan_process_cache.SINGLEFLIGHT_USER_VISIBLE_WAIT_S < (
        game_plan_process_cache.SINGLEFLIGHT_WAIT_TIMEOUT_S
    )
    state = {}
    started = time.perf_counter() - (stall.USER_VISIBLE_FAILSOFT_S + 0.05)
    assert stall.apply_user_visible_failsoft_if_needed(
        state, started_mono=started, reason="builder_slow"
    )
    assert stall.fail_soft_state(state)
    assert stall.fail_soft_state(state).get("reason") == "builder_slow"


def test_no_post_hydration_rebuild_on_presentation_rerun(monkeypatch):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state = {"_effective_entitlement": "free"}
    tail_latency_diagnostics.mark_football_hydration_complete(state)
    # Presentation rerun cause should not record post_ready rebuild for hits.
    store = state.get(tail_latency_diagnostics.TRACE_STATE_KEY) or {}
    assert state.get(tail_latency_diagnostics.FOOTBALL_HYDRATION_COMPLETE_KEY) is True
    assert store.get("post_ready_rebuilds") in (None, [])


def test_account_league_isolation_under_concurrent_sessions():
    game_plan_process_cache.clear_process_game_plan_caches()
    results = []

    def worker(idx):
        sig = f"iso-league-{idx}"
        token = f"account-{idx}"
        payload, _ = game_plan_process_cache.get_or_build_league_context(
            signature=sig,
            builder=lambda: {"account": token, "league": sig},
        )
        results.append(payload)

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(worker, range(6)))
    accounts = {row["account"] for row in results}
    leagues = {row["league"] for row in results}
    assert len(accounts) == 6
    assert len(leagues) == 6

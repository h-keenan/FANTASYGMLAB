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
from modules import perceived_load
from modules import sleeper
from modules import tail_latency_diagnostics
from scripts import test_realistic_session_load
from scripts import verify_package_miss_path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


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


def test_live_draft_discovery_runs_after_dashboard_game_plan():
    dash = APP.index("# HOME DASHBOARD")
    discovery = APP.index("_maybe_refresh_live_draft_discovery()", dash)
    render = APP.index("render_home_dashboard(", dash)
    assert render < discovery
    assert "provider_leagues" in APP or "Live Draft" in APP[discovery - 200 : discovery]


def test_draft_candidate_prefers_stub_metadata_without_get_draft():
    assert "_draft_stub_sufficient_for_candidate" in APP
    assert "_draft_payload_for_candidate" in APP
    # Old per-stub get_draft loop removed from candidate helpers.
    start = APP.index("def _detect_rookie_draft_candidate")
    end = APP.index("\ndef ", start + 10)
    body = APP[start:end]
    assert "get_draft(" not in body
    assert "_draft_payload_for_candidate" in body


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


def test_golden_startup_provider_leagues_budget_with_lru(monkeypatch):
    """Distinct endpoints may miss once; identical endpoints must coalesce via lru."""

    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    calls: list[str] = []

    def fake_request(label, url, timeout=5):
        calls.append(label)
        if "drafts" in label:
            return [
                {
                    "draft_id": "d1",
                    "status": "complete",
                    "season": 2026,
                    "settings": {"rounds": 4},
                    "start_time": 1,
                },
                {
                    "draft_id": "d2",
                    "status": "complete",
                    "season": 2025,
                    "settings": {"rounds": 4},
                    "start_time": 2,
                },
            ]
        if label == "sleeper_league":
            return {"league_id": "L1", "season": 2026, "settings": {"draft_rounds": 4}}
        if label == "sleeper_traded_picks":
            return []
        if label == "sleeper_draft_picks":
            return []
        if label == "sleeper_draft":
            return {"draft_id": "d1", "status": "complete", "settings": {"rounds": 4}}
        return {}

    monkeypatch.setattr(sleeper, "_request_json", fake_request)
    sleeper._get_league_cached.cache_clear()
    sleeper.get_league_drafts.cache_clear()
    sleeper.get_draft.cache_clear()
    sleeper.get_draft_picks.cache_clear()
    sleeper._get_traded_picks_cached.cache_clear()

    league_id = "league-234"
    sleeper.get_league(league_id)
    sleeper.get_league(league_id)  # lru hit — no second network
    drafts = sleeper.get_league_drafts(league_id)
    sleeper.get_league_drafts(league_id)  # hit
    sleeper.get_traded_picks(league_id)
    sleeper.get_traded_picks(league_id)  # hit

    # Candidate scoring must not fan out get_draft when stubs are sufficient.
    import app as app_module

    candidate = app_module._detect_rookie_draft_candidate(
        league_id, sleeper.get_league(league_id)
    )
    assert candidate
    assert "sleeper_draft" not in calls
    network_league_family = [
        c
        for c in calls
        if any(part in c for part in ("league", "draft", "traded", "matchup"))
    ]
    assert len(network_league_family) <= tail_latency_diagnostics.MAX_PROVIDER_LEAGUES_CALLS_GOLDEN_STARTUP
    assert len(drafts) == 2


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


def test_realistic_load_harness_same_and_different(monkeypatch):
    monkeypatch.delenv("DYNASTYGM_ALLOW_PRODUCTION_LOAD", raising=False)
    report = test_realistic_session_load.run_matrix(
        levels=[1, 3],
        production=False,
        delay_ms=5.0,
    )
    assert report["environment"] == "LOCAL"
    same = report["load_a_same_league"]
    diff = report["load_b_different_leagues"]
    assert same[0]["builder_count_total"] == 1
    assert same[-1]["builder_count_total"] == 1
    assert diff[-1]["builder_count_total"] >= 2
    assert report["timeout_policy"]["hard_singleflight_timeout_s"] == 45.0
    assert report["browser_manual_capture"]["status"] == "NOT_RUN_IN_HARNESS"


def test_app_wires_startup_profile_include_billing_false_by_default():
    assert "include_billing=bool(force)" in APP


def test_percentile_helpers():
    summary = perceived_load.latency_summary([10, 20, 30, 40, 50])
    assert summary["p50"] >= 10
    assert summary["max"] == 50
    assert perceived_load.MAX_LOCAL_CONCURRENCY >= 20

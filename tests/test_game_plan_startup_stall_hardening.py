"""Game Plan startup stall hardening contracts (#233)."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from modules import auth_restore_lifecycle
from modules import game_plan_process_cache
from modules import game_plan_startup_stall as stall
from modules import startup_coordinator
from modules import tail_latency_diagnostics
from scripts import diagnose_tail_latency


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.delenv("DYNASTYGM_STARTUP", raising=False)
    game_plan_process_cache.clear_process_game_plan_caches()
    tail_latency_diagnostics.reset_process_boot_for_tests()
    yield
    game_plan_process_cache.clear_process_game_plan_caches()
    tail_latency_diagnostics.reset_process_boot_for_tests()


def test_dashboard_loader_avoids_nested_shared_league_context():
    """Cold package MISS must not re-enter get_or_build via get_shared_league_context."""

    start = APP.index("def _load_game_plan_league_context()")
    end = APP.index("render_home_dashboard(", start)
    body = APP[start:end]
    assert "get_shared_league_context(" not in body
    assert "cached_league_context(" in body
    assert "non-reentrant" in body or "deadlock" in body.casefold()


def test_nested_same_signature_does_not_deadlock():
    game_plan_process_cache.clear_process_game_plan_caches()
    sig = "nested-reentrant-sig-233"
    builds = {"n": 0}

    def outer_builder():
        builds["n"] += 1

        def inner_builder():
            builds["n"] += 1
            return {"inner": True}

        # Same-thread nested acquire must complete (reentrancy), not hang.
        inner, _ = game_plan_process_cache.get_or_build_league_context(
            signature=sig, builder=inner_builder
        )
        return {"outer": True, "inner": inner}

    result, hit = game_plan_process_cache.get_or_build_league_context(
        signature=sig, builder=outer_builder
    )
    assert hit is False
    assert result.get("outer") is True
    assert builds["n"] >= 1


def test_builder_exception_releases_owner_for_later_requests():
    game_plan_process_cache.clear_process_game_plan_caches()
    sig = "exc-release-233"
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        game_plan_process_cache.get_or_build_league_context(signature=sig, builder=boom)

    def ok():
        calls["n"] += 1
        return {"ok": True}

    result, hit = game_plan_process_cache.get_or_build_league_context(
        signature=sig, builder=ok
    )
    assert hit is False
    assert result["ok"] is True
    assert calls["n"] == 2


def test_same_signature_concurrency_single_build():
    game_plan_process_cache.clear_process_game_plan_caches()
    sig = "concurrent-miss-233"
    builds = {"n": 0}
    gate = threading.Event()

    def builder():
        builds["n"] += 1
        gate.wait(timeout=1.0)
        time.sleep(0.05)
        return {"n": builds["n"]}

    def worker():
        return game_plan_process_cache.get_or_build_league_context(
            signature=sig, builder=builder
        )

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(worker) for _ in range(10)]
        gate.set()
        results = [f.result(timeout=5) for f in as_completed(futures)]
    assert builds["n"] == 1
    assert all(row[0].get("n") == 1 for row in results)


def test_unrelated_signatures_run_independently():
    game_plan_process_cache.clear_process_game_plan_caches()
    builds = {"a": 0, "b": 0}

    def build_a():
        builds["a"] += 1
        time.sleep(0.05)
        return {"sig": "a"}

    def build_b():
        builds["b"] += 1
        time.sleep(0.05)
        return {"sig": "b"}

    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(
            game_plan_process_cache.get_or_build_league_context,
            signature="sig-a",
            builder=build_a,
        )
        fb = pool.submit(
            game_plan_process_cache.get_or_build_league_context,
            signature="sig-b",
            builder=build_b,
        )
        a = fa.result(timeout=5)
        b = fb.result(timeout=5)
    assert builds == {"a": 1, "b": 1}
    assert a[0]["sig"] == "a"
    assert b[0]["sig"] == "b"


def test_forced_builder_exception_wakes_waiters_into_error_then_recover():
    game_plan_process_cache.clear_process_game_plan_caches()
    sig = "forced-exc-waiters-233"
    release_boom = threading.Event()
    entered = threading.Event()

    def boom():
        entered.set()
        release_boom.wait(timeout=2)
        raise ValueError("forced")

    def worker():
        try:
            return (
                "ok",
                game_plan_process_cache.get_or_build_league_context(
                    signature=sig, builder=boom
                ),
            )
        except ValueError as exc:
            return ("err", type(exc).__name__)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(worker) for _ in range(4)]
        assert entered.wait(timeout=2)
        release_boom.set()
        outcomes = [f.result(timeout=5) for f in futures]
    # Owner raises; subsequent waiters rebuild and also raise — none may hang.
    assert all(item[0] == "err" for item in outcomes)

    # Recovery after exception: later request succeeds.
    result, _ = game_plan_process_cache.get_or_build_league_context(
        signature=sig, builder=lambda: {"recovered": True}
    )
    assert result["recovered"] is True


def test_initial_hydration_is_not_post_ready_rebuild(monkeypatch):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state = {}
    auth_restore_lifecycle.ensure_startup_session(state)
    state[startup_coordinator.STARTUP_COMPLETE_KEY] = True
    assert state.get(tail_latency_diagnostics.FOOTBALL_HYDRATION_COMPLETE_KEY) is not True
    tail_latency_diagnostics.note_build(
        state,
        family="league_context",
        signature="abc12345deadbeef",
        cache_status="miss",
        duration_ms=10.0,
    )
    store = state[tail_latency_diagnostics.TRACE_STATE_KEY]
    assert store.get("post_ready_rebuilds") in (None, [])
    assert store.get("initial_post_dismiss_hydrations")


def test_true_repeated_rebuild_after_football_ready(monkeypatch):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state = {}
    auth_restore_lifecycle.ensure_startup_session(state)
    state[startup_coordinator.STARTUP_COMPLETE_KEY] = True
    tail_latency_diagnostics.mark_football_hydration_complete(state)
    tail_latency_diagnostics.note_build(
        state,
        family="league_context",
        signature="abc12345deadbeef",
        cache_status="miss",
        duration_ms=12.0,
    )
    store = state[tail_latency_diagnostics.TRACE_STATE_KEY]
    assert store.get("post_ready_rebuilds")


def test_summary_aggregation_includes_milestone_gaps(monkeypatch):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state = {}
    auth_restore_lifecycle.ensure_startup_session(state)
    origin = time.perf_counter() - 2.0
    startup_coordinator.log_startup_milestone(
        state, "profile_fetch_start", started_at=origin
    )
    time.sleep(0.02)
    startup_coordinator.log_startup_milestone(
        state, "profile_fetch_complete", started_at=origin
    )
    store = state[tail_latency_diagnostics.TRACE_STATE_KEY]
    durations = store.get("stage_durations_ms") or {}
    assert float(durations.get("profile_fetch") or 0) > 0
    store.setdefault("user_milestones_ms", {})["dashboard_complete"] = 5000.0
    summary = tail_latency_diagnostics.maybe_emit_summary(state, force=True)
    assert summary is not None
    assert summary.get("profile_fetch_ms", 0) > 0
    assert summary.get("stage_duration_semantics") == "exclusive"


def test_stage_error_events_omit_pii(monkeypatch, capsys):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state = {"auth_user": {"email": "secret@example.com", "id": "user-1"}}
    auth_restore_lifecycle.ensure_startup_session(state)
    try:
        with stall.stage_span(state, "game_plan_shared_context", signature_prefix="deadbeef"):
            raise RuntimeError("failed for league My Secret League and player Mahomes")
    except RuntimeError:
        pass
    out = capsys.readouterr().out
    assert "secret@example.com" not in out
    assert "Mahomes" not in out
    assert "My Secret League" not in out
    assert "startup_stage_error" in out
    assert "RuntimeError" in out


def test_diagnostics_off_emits_nothing(monkeypatch, capsys):
    monkeypatch.delenv("DYNASTYGM_STARTUP", raising=False)
    state = {}
    with stall.stage_span(state, "game_plan_compose"):
        pass
    assert capsys.readouterr().out == ""


def test_fail_soft_retry_bounded():
    state = {}
    stall.set_fail_soft(state, reason="shared_context_failed", exception_type="TimeoutError")
    assert stall.fail_soft_state(state)
    assert stall.can_retry(state)
    stall.note_retry(state)
    assert not stall.can_retry(state)
    title, body = stall.fail_soft_copy()
    assert "Game Plan" in title
    assert "Trade Hub" in body


def test_diagnose_stall_classification_package_miss():
    rows = [
        {"kind": "startup_milestone", "milestone": "game_plan_package_cache_lookup", "cache_status": "miss"},
        {"kind": "startup_stage_start", "stage": "game_plan_trade"},
    ]
    result = diagnose_tail_latency.classify_session_stall(rows)
    assert result["classification"] == "UNKNOWN_AFTER_PACKAGE_MISS"
    assert result["last_stage"] == "game_plan_trade"


def test_app_wires_fail_soft_and_stall_helpers():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "game_plan_startup_stall" in app
    assert "Retry Game Plan" in app
    title, body = stall.fail_soft_copy()
    assert "Game Plan is taking longer than expected" in title
    assert "Trade Hub" in body
    assert "SINGLEFLIGHT_WAIT_TIMEOUT_S" in (
        ROOT / "modules" / "game_plan_process_cache.py"
    ).read_text(encoding="utf-8")

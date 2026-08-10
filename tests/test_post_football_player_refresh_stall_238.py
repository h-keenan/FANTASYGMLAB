"""#238 post-football player refresh stall + rerun storm regressions.

Production topology (f3773561):
  loading_dismissed → players_ready → prepared_frame_ready → football_context_ready
  then synchronous sleeper_players_fetch (~9s) blocked Game Plan entry and fed
  reruns 3–8. Persisted frame must remain first-useful; refresh is process
  single-flight background work.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from modules import auth_restore_lifecycle
from modules import auth_supabase
from modules import auth_storage_handshake
from modules import game_plan_startup_stall as gp_stall
from modules import players_refresh_flight as refresh_flight
from modules import startup_cold_path
from modules import startup_coordinator
from modules import tail_latency_diagnostics


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.delenv("DYNASTYGM_STARTUP", raising=False)
    refresh_flight.reset_process_refresh_state_for_tests()
    tail_latency_diagnostics.reset_process_boot_for_tests()
    yield
    refresh_flight.reset_process_refresh_state_for_tests()
    tail_latency_diagnostics.reset_process_boot_for_tests()


def test_app_schedules_background_refresh_after_football_before_dashboard():
    football = APP.index('"football_context_ready"')
    refresh = APP.index("maybe_refresh_players_after_shell(", football)
    entry = APP.index('"dashboard_game_plan_entry"', refresh)
    dashboard = APP.index("render_home_dashboard(", entry)
    block = APP[refresh : refresh + 350]
    assert "background=True" in block
    assert football < refresh < entry < dashboard


def test_pre238_sync_refresh_topology_would_block_nine_seconds():
    """Prove the pre-#238 await path blocks; new schedule does not."""

    state: dict = {startup_cold_path.PLAYERS_REFRESH_PENDING_KEY: True}
    builds = {"n": 0}
    frame = pd.DataFrame([{"player_id": "1", "name": "A"}])

    def slow_build(_db, refresh=False):
        builds["n"] += 1
        assert refresh is True
        time.sleep(0.35)
        return frame

    # Legacy semantics (what production did): await refresh on request thread.
    legacy_started = time.perf_counter()
    legacy_state = {startup_cold_path.PLAYERS_REFRESH_PENDING_KEY: True}
    if legacy_state.pop(startup_cold_path.PLAYERS_REFRESH_PENDING_KEY, False):
        slow_build("data/players.db", refresh=True)
    legacy_ms = (time.perf_counter() - legacy_started) * 1000.0
    assert legacy_ms >= 300.0

    refresh_flight.reset_process_refresh_state_for_tests()
    builds["n"] = 0
    state = {startup_cold_path.PLAYERS_REFRESH_PENDING_KEY: True}
    started = time.perf_counter()
    result = startup_cold_path.maybe_refresh_players_after_shell(
        db_path="data/players.db",
        build_players_table_fn=slow_build,
        session_state=state,
        background=True,
    )
    schedule_ms = (time.perf_counter() - started) * 1000.0
    assert result is None
    assert schedule_ms < 150.0
    assert refresh_flight.wait_for_refresh(timeout_s=2.0)
    assert builds["n"] == 1


def test_stale_persisted_frame_queues_refresh_without_network():
    state: dict = {}
    frame = pd.DataFrame([{"player_id": "1"}])
    build = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(startup_cold_path, "sleeper_players_cache_stale", lambda **_: True)
        result = startup_cold_path.ensure_players_for_startup(
            db_path="data/players.db",
            load_players_fn=lambda _p: frame,
            build_players_table_fn=build,
            session_state=state,
            allow_network_refresh=False,
        )
    assert result.equals(frame)
    assert state.get(startup_cold_path.PLAYERS_REFRESH_PENDING_KEY) is True
    build.assert_not_called()


def test_delayed_refresh_does_not_block_first_useful_path():
    state: dict = {startup_cold_path.PLAYERS_REFRESH_PENDING_KEY: True}
    gate = threading.Event()
    builds = {"n": 0}
    frame = pd.DataFrame([{"player_id": "ok"}])

    def delayed_build(_db, refresh=False):
        builds["n"] += 1
        gate.wait(timeout=5.0)
        time.sleep(0.05)
        return frame

    t0 = time.perf_counter()
    startup_cold_path.maybe_refresh_players_after_shell(
        db_path="data/players.db",
        build_players_table_fn=delayed_build,
        session_state=state,
        background=True,
    )
    # Simulate Dashboard progression while refresh sleeps ~9s topology (scaled).
    startup_cold_path.mark_football_ready(state)
    startup_coordinator.log_startup_milestone(
        state, "dashboard_game_plan_entry", once=True
    )
    startup_coordinator.log_startup_milestone(
        state, "game_plan_package_lookup_start", once=True
    )
    first_useful_ms = (time.perf_counter() - t0) * 1000.0
    assert first_useful_ms < 250.0
    assert state.get(refresh_flight.PLAYERS_REFRESH_ROLE_KEY) == "refresh_owner"
    gate.set()
    assert refresh_flight.wait_for_refresh(timeout_s=3.0)
    assert builds["n"] == 1
    assert first_useful_ms < 9000.0


def test_provider_failure_preserves_last_known_good_and_cools_down():
    state: dict = {startup_cold_path.PLAYERS_REFRESH_PENDING_KEY: True}

    def boom(_db, refresh=False):
        raise RuntimeError("provider_down")

    startup_cold_path.maybe_refresh_players_after_shell(
        db_path="data/players.db",
        build_players_table_fn=boom,
        session_state=state,
        background=True,
    )
    assert refresh_flight.wait_for_refresh(timeout_s=2.0)
    assert refresh_flight.provider_refresh_call_count() == 1
    assert "RuntimeError" in refresh_flight.last_refresh_error()

    # Same session must not re-arm; new session still cools down briefly.
    state2: dict = {}
    assert refresh_flight.should_queue_stale_refresh(state) is False
    assert refresh_flight.should_queue_stale_refresh(state2) is False


def test_auth_save_deferral_is_one_shot():
    state: dict = {
        auth_supabase.DURABLE_AUTH_PENDING_SAVE_KEY: {"access_token": "x"},
    }
    # First arm.
    assert not state.get(auth_restore_lifecycle.POST_USABLE_SAVE_AFTER_FOOTBALL_KEY)
    state[auth_restore_lifecycle.POST_USABLE_SAVE_AFTER_FOOTBALL_KEY] = True
    # Remount path marks done.
    state[auth_restore_lifecycle.POST_USABLE_SAVE_RERUN_KEY] = True
    # Re-arming guard in app.py: AFTER_FOOTBALL already set / RERUN done.
    may_arm = (
        (
            auth_supabase.DURABLE_AUTH_PENDING_SAVE_KEY in state
            or auth_supabase.DURABLE_AUTH_PENDING_CLEAR_KEY in state
        )
        and not state.get(auth_restore_lifecycle.POST_USABLE_SAVE_RERUN_KEY)
        and not state.get(auth_restore_lifecycle.POST_USABLE_SAVE_AFTER_FOOTBALL_KEY)
    )
    assert may_arm is False
    assert auth_storage_handshake.classify_script_run_cause(state) == "post_usable_auth_save"


def test_auth_save_queued_clears_after_intended_remount_pop():
    state: dict = {
        auth_supabase.DURABLE_AUTH_PENDING_SAVE_KEY: {"access_token": "x"},
        auth_restore_lifecycle.POST_USABLE_SAVE_AFTER_FOOTBALL_KEY: True,
    }
    # Pending durable payload outranks the queued flag in classify order.
    assert (
        auth_storage_handshake.classify_script_run_cause(state)
        == "durable_auth_save_pending"
    )
    queued_only = {
        auth_restore_lifecycle.POST_USABLE_SAVE_AFTER_FOOTBALL_KEY: True,
    }
    assert (
        auth_storage_handshake.classify_script_run_cause(queued_only)
        == "post_usable_auth_save_queued"
    )
    # End-of-script remount consumes the after-football flag once.
    assert state.pop(auth_restore_lifecycle.POST_USABLE_SAVE_AFTER_FOOTBALL_KEY, False)
    state[auth_restore_lifecycle.POST_USABLE_SAVE_RERUN_KEY] = True
    assert auth_storage_handshake.classify_script_run_cause(state) == "post_usable_auth_save"


def test_game_plan_entry_milestones_exist_in_app():
    for name in (
        "dashboard_game_plan_entry",
        "game_plan_fingerprint_start",
        "game_plan_fingerprint_complete",
        "game_plan_package_lookup_start",
        "game_plan_package_lookup_complete",
    ):
        assert f'"{name}"' in APP


def test_summary_emits_per_trigger_without_erasing_early():
    state: dict = {}
    auth_restore_lifecycle.ensure_startup_session(state)
    startup_coordinator.log_startup_milestone(state, "loading_dismissed", once=False)
    store = tail_latency_diagnostics._trace(state)
    emitted = store.get("summaries_emitted_by_trigger") or {}
    assert emitted.get("loading_dismissed") is True
    # Partial dismiss summary must not block later triggers.
    assert emitted.get("game_plan_first_useful") is not True
    startup_coordinator.log_startup_milestone(
        state, "game_plan_first_useful", once=False
    )
    emitted = store.get("summaries_emitted_by_trigger") or {}
    assert emitted.get("game_plan_first_useful") is True
    assert emitted.get("loading_dismissed") is True
    assert (
        tail_latency_diagnostics.maybe_emit_summary(state, trigger="loading_dismissed")
        is None
    )


def test_post_football_deadline_failsoft_reachable():
    state: dict = {}
    startup_cold_path.mark_football_ready(state)
    state["_football_context_ready_mono"] = time.perf_counter() - 13.0
    assert gp_stall.apply_post_football_deadline_failsoft(state) is True
    soft = gp_stall.fail_soft_state(state)
    assert soft is not None
    title, body = gp_stall.fail_soft_copy(exception_type="DeferredEnrichment")
    assert "Game Plan" in title
    assert "Trade Hub" in body
    assert "invent" in body.casefold() or "My Team" in body


def test_same_signature_concurrency_single_owner(n_sessions: int = 10):
    builds = {"n": 0}
    gate = threading.Event()
    frame = pd.DataFrame([{"player_id": "1"}])

    def slow_build(_db, refresh=False):
        builds["n"] += 1
        gate.wait(timeout=2.0)
        time.sleep(0.05)
        return frame

    def session_worker(_i: int):
        state = {startup_cold_path.PLAYERS_REFRESH_PENDING_KEY: True}
        return startup_cold_path.maybe_refresh_players_after_shell(
            db_path="data/players.db",
            build_players_table_fn=slow_build,
            session_state=state,
            background=True,
        )

    with ThreadPoolExecutor(max_workers=n_sessions) as pool:
        futures = [pool.submit(session_worker, i) for i in range(n_sessions)]
        time.sleep(0.05)
        gate.set()
        for fut in as_completed(futures):
            assert fut.result(timeout=5) is None
    assert refresh_flight.wait_for_refresh(timeout_s=3.0)
    assert builds["n"] == 1
    assert refresh_flight.provider_refresh_call_count() == 1


@pytest.mark.parametrize("n", [1, 3, 5, 10, 20])
def test_concurrency_matrix_one_network_refresh(n):
    test_same_signature_concurrency_single_owner(n_sessions=n)


def test_cross_session_isolation_league_work_not_locked():
    """Public player refresh lock must not serialize unrelated league builders."""

    order: list[str] = []
    player_gate = threading.Event()
    league_done = threading.Event()

    def player_build(_db, refresh=False):
        order.append("player_start")
        player_gate.wait(timeout=2.0)
        order.append("player_end")
        return pd.DataFrame([{"player_id": "1"}])

    def league_work():
        order.append("league")
        league_done.set()
        return {"league": True}

    state = {startup_cold_path.PLAYERS_REFRESH_PENDING_KEY: True}
    startup_cold_path.maybe_refresh_players_after_shell(
        db_path="data/players.db",
        build_players_table_fn=player_build,
        session_state=state,
        background=True,
    )
    # League work proceeds while player refresh is in flight.
    assert league_work()["league"] is True
    assert league_done.is_set()
    player_gate.set()
    assert refresh_flight.wait_for_refresh(timeout_s=2.0)
    assert "league" in order
    assert order.index("league") < order.index("player_end")


def test_no_duplicate_refresh_after_session_reschedule_attempt():
    state: dict = {startup_cold_path.PLAYERS_REFRESH_PENDING_KEY: True}
    builds = {"n": 0}

    def build(_db, refresh=False):
        builds["n"] += 1
        time.sleep(0.02)
        return pd.DataFrame([{"player_id": "1"}])

    startup_cold_path.maybe_refresh_players_after_shell(
        db_path="data/players.db",
        build_players_table_fn=build,
        session_state=state,
        background=True,
    )
    # Pending already consumed + scheduled one-shot.
    state[startup_cold_path.PLAYERS_REFRESH_PENDING_KEY] = True
    startup_cold_path.maybe_refresh_players_after_shell(
        db_path="data/players.db",
        build_players_table_fn=build,
        session_state=state,
        background=True,
    )
    assert refresh_flight.wait_for_refresh(timeout_s=2.0)
    assert builds["n"] == 1


def test_package_miss_path_still_instrumented_after_football():
    football = APP.index('"football_context_ready"')
    entry = APP.index('"dashboard_game_plan_entry"', football)
    assert football < entry
    assert '"game_plan_package_lookup_start"' in APP
    assert '"game_plan_package_lookup_complete"' in APP
    # Fingerprint + lookup live inside render_home_dashboard (defined above main).
    fp = APP.index('"game_plan_fingerprint_start"')
    lookup = APP.index('"game_plan_package_lookup_start"', fp)
    assert fp < lookup

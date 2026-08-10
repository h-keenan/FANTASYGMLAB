"""Tail latency / startup_trace_summary contracts (#230)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from modules import auth_restore_lifecycle
from modules import game_plan_process_cache
from modules import startup_cold_path
from modules import startup_coordinator
from modules import tail_latency_diagnostics
from scripts import diagnose_tail_latency
from scripts.report_startup_waterfall import _parse_lines


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _reset_diag(monkeypatch):
    monkeypatch.delenv("DYNASTYGM_STARTUP", raising=False)
    game_plan_process_cache.clear_process_game_plan_caches()
    tail_latency_diagnostics.reset_process_boot_for_tests()
    try:
        from modules import prepared_player_frame
        from modules import daily_gm_briefing

        prepared_player_frame.clear_process_valued_ranked_frames()
        daily_gm_briefing.clear_compose_memo()
    except Exception:
        pass
    yield
    game_plan_process_cache.clear_process_game_plan_caches()
    tail_latency_diagnostics.reset_process_boot_for_tests()
    try:
        from modules import prepared_player_frame
        from modules import daily_gm_briefing

        prepared_player_frame.clear_process_valued_ranked_frames()
        daily_gm_briefing.clear_compose_memo()
    except Exception:
        pass


def test_diagnostics_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DYNASTYGM_STARTUP", raising=False)
    assert tail_latency_diagnostics.diagnostics_enabled() is False
    state = {}
    auth_restore_lifecycle.ensure_startup_session(state)
    # begin_script_run should not require diagnostics for counter, but print is gated.
    first = auth_restore_lifecycle.begin_script_run(state)
    assert first["startup_run_number"] == 1


def test_process_temperature_classification_stable():
    game_plan_process_cache.clear_process_game_plan_caches()
    try:
        from modules import prepared_player_frame
        from modules import daily_gm_briefing

        prepared_player_frame.clear_process_valued_ranked_frames()
        daily_gm_briefing.clear_compose_memo()
    except Exception:
        pass
    cold = {"_startup_run_number": 1}
    auth_restore_lifecycle.ensure_startup_session(cold)
    assert (
        tail_latency_diagnostics.classify_process_temperature(cold, run_cause="startup_shell")
        == "PROCESS_COLD"
    )

    warm_session = {
        "_startup_coordinator_complete": True,
        "_game_plan_package_signature": "abc",
        "_startup_run_number": 4,
    }
    auth_restore_lifecycle.ensure_startup_session(warm_session)
    assert (
        tail_latency_diagnostics.classify_process_temperature(
            warm_session, run_cause="post_ready_interactive"
        )
        == "PRESENTATION_RERUN"
    )


def test_same_signature_duplicate_detection(monkeypatch, capsys):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state = {}
    auth_restore_lifecycle.ensure_startup_session(state)
    assert (
        tail_latency_diagnostics.note_build(
            state, family="league_context", signature="deadbeef11", cache_status="miss"
        )
        is None
    )
    dup = tail_latency_diagnostics.note_build(
        state, family="league_context", signature="deadbeef11", cache_status="miss"
    )
    assert dup is not None
    assert dup["kind"] == "duplicate_work"
    assert dup["occurrence"] == 2
    out = capsys.readouterr().out
    assert "duplicate_work" in out


def test_post_ready_rebuild_invariant(monkeypatch, capsys):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state = {startup_coordinator.STARTUP_COMPLETE_KEY: True}
    auth_restore_lifecycle.ensure_startup_session(state)
    # First miss after dismiss is expected hydration, not a rebuild regression.
    tail_latency_diagnostics.note_build(
        state, family="trade_inventory", signature="cafebabe22", cache_status="miss"
    )
    out = capsys.readouterr().out
    assert "initial_post_dismiss_hydration" in out
    assert "post_ready_rebuild" not in out
    # After football hydration completes, same-family miss is a rebuild signal.
    tail_latency_diagnostics.mark_football_hydration_complete(state)
    tail_latency_diagnostics.note_build(
        state, family="trade_inventory", signature="cafebabe22", cache_status="miss"
    )
    out = capsys.readouterr().out
    assert "post_ready_rebuild" in out


def test_summary_event_schema_and_no_pii(monkeypatch, capsys):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state = {}
    auth_restore_lifecycle.ensure_startup_session(state)
    auth_restore_lifecycle.begin_script_run(state)
    startup_coordinator.log_startup_milestone(state, "loading_dismissed", once=False)
    startup_coordinator.log_startup_milestone(state, "game_plan_first_useful", once=False)
    startup_coordinator.log_startup_milestone(state, "dashboard_football_ready", once=False)
    out = capsys.readouterr().out
    assert "startup_trace_summary" in out
    for line in out.splitlines():
        if "startup_trace_summary" not in line:
            continue
        payload = json.loads(line.split("DYNASTYGM_STARTUP ", 1)[1])
        blob = json.dumps(payload).casefold()
        assert "email" not in blob
        assert "token" not in blob
        assert "@" not in blob
        for key in (
            "startup_session_id",
            "run_count",
            "process_temperature",
            "loading_dismissed_ms",
            "first_useful_ms",
            "slowest_stage",
        ):
            assert key in payload


def test_stage_timer_and_provider_wrapper(monkeypatch):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state = {}
    with tail_latency_diagnostics.stage_timer(state, "briefing_assembly"):
        pass
    store = state[tail_latency_diagnostics.TRACE_STATE_KEY]
    assert store["stage_durations_ms"]["briefing_assembly"] >= 0

    def _work():
        return 42

    assert tail_latency_diagnostics.provider_timed(state, "provider_rosters", _work) == 42
    assert store["provider_calls"] == 1


def test_monotonic_duration_on_milestones(monkeypatch, capsys):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state = {}
    auth_restore_lifecycle.ensure_startup_session(state)
    startup_coordinator.log_startup_milestone(state, "shell_chrome_ready", once=False)
    startup_coordinator.log_startup_milestone(state, "loading_dismissed", once=False)
    rows = []
    for line in capsys.readouterr().out.splitlines():
        if "startup_milestone" not in line:
            continue
        rows.append(json.loads(line.split("DYNASTYGM_STARTUP ", 1)[1]))
    assert any("duration_ms" in row for row in rows)
    assert any(row.get("process_temperature") for row in rows)


def test_process_cache_hit_accounting_with_session_state():
    state = {}
    auth_restore_lifecycle.ensure_startup_session(state)
    sig = "abc12345" * 4
    first, miss = game_plan_process_cache.get_or_build_league_context(
        signature=sig,
        builder=lambda: {"ok": True},
        session_state=state,
    )
    second, hit = game_plan_process_cache.get_or_build_league_context(
        signature=sig,
        builder=lambda: {"ok": False},
        session_state=state,
    )
    assert miss is False
    assert hit is True
    assert first["ok"] is True
    assert second["ok"] is True
    survival = tail_latency_diagnostics.process_cache_survival_snapshot()
    assert survival["league_process_entries"] >= 1


def test_percentile_helper_and_synthetic_report():
    assert tail_latency_diagnostics.percentile([1, 2, 3, 4, 5], 50) == 3
    report = diagnose_tail_latency.render_report(diagnose_tail_latency.synthetic_samples())
    assert "interactive stable" in report
    assert "PROCESS_COLD" in report
    assert "Owners:" in report
    assert "UNEXPLAINED/gap" in report


def test_waterfall_parser_accepts_new_kinds():
    text = "\n".join(
        [
            'DYNASTYGM_STARTUP {"kind":"startup_trace_summary","interactive_stable_ms":100}',
            'DYNASTYGM_STARTUP {"kind":"duplicate_work","family":"compose"}',
            'DYNASTYGM_STARTUP {"kind":"startup_stage_duration","stage":"compose","duration_ms":12}',
            'DYNASTYGM_STARTUP {"kind":"provider_timing","category":"provider_rosters","duration_ms":9}',
            'DYNASTYGM_STARTUP {"kind":"post_ready_rebuild","family":"league_context"}',
        ]
    )
    assert len(diagnose_tail_latency.parse_log_text(text)) == 5
    rows = _parse_lines(text)
    kinds = {row.get("kind") for row in rows}
    assert "startup_trace_summary" in kinds
    assert "duplicate_work" in kinds
    assert "provider_timing" in kinds
    classic = (
        'DYNASTYGM_STARTUP {"kind":"startup_run","startup_session_id":"a","startup_run_number":1,'
        '"restore_phase":"UNINITIALIZED"}'
    )
    assert _parse_lines(classic)


def test_briefing_substage_accounting_present_in_app_source():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'f"briefing_{_name}"' in app_source
    assert '"briefing_assembly"' in app_source
    for name in ("injury", "waiver", "tiles", "organization", "snapshot"):
        assert f'"{name}"' in app_source


def test_provider_category_mapping():
    from modules import sleeper

    assert sleeper._provider_category("sleeper_user_lookup") == "provider_user_lookup"
    assert sleeper._provider_category("sleeper_league_rosters") == "provider_rosters"
    assert sleeper._provider_category("sleeper_transactions") == "provider_transactions"
    assert sleeper._provider_category("sleeper_players_fetch") == "provider_players"


def test_overhead_probe_is_cheap():
    ms = tail_latency_diagnostics.estimate_diagnostics_overhead_ms(iterations=50)
    assert ms < 5.0


def test_module_and_script_exist():
    assert (ROOT / "modules" / "tail_latency_diagnostics.py").exists()
    assert (ROOT / "scripts" / "diagnose_tail_latency.py").exists()
    assert startup_cold_path.STARTUP_ENV_KEY == "DYNASTYGM_STARTUP"

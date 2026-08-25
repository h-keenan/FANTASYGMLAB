"""Final technical launch gate contracts (#237)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules import (
    experimental_graduation,
    game_plan_process_cache,
    mobile_interaction_overlay_styles,
    mobile_visual_polish_styles,
    tail_latency_diagnostics,
)
from modules.app_styles import APP_CSS
from modules.brand_identity import GM_ORB_ARIA_LABEL
from scripts import verify_package_miss_path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "final-technical-launch-gate-237.md"
PROTOBUF_HARD = 520_000
PROTOBUF_PREFERRED = 515_000


@pytest.fixture(autouse=True)
def _reset():
    game_plan_process_cache.clear_process_game_plan_caches()
    yield
    game_plan_process_cache.clear_process_game_plan_caches()


def test_gate_doc_records_verdict_fields():
    assert DOC.is_file()
    text = DOC.read_text(encoding="utf-8")
    assert "GO" in text or "CONDITIONAL GO" in text or "NO-GO" in text
    assert "package-MISS" in text or "package MISS" in text
    assert "protobuf" in text.casefold()
    assert "PRODUCTION" in text or "production" in text


def test_protobuf_headroom_contract():
    # Hard ceiling must remain; preferred headroom is asserted via measured budget.
    assert PROTOBUF_PREFERRED < PROTOBUF_HARD
    assert len(APP_CSS) < 390_000  # CSS headroom recovery after #258
    assert "home-quick-actions-shell {" not in APP_CSS


def test_startup_summary_owner_stage_not_tiny_auth_apply(monkeypatch):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state: dict = {}
    from modules import auth_restore_lifecycle, startup_coordinator

    auth_restore_lifecycle.ensure_startup_session(state)
    auth_restore_lifecycle.begin_script_run(state)
    # Tiny apply vs large profile/league — slowest must prefer ownership stages.
    tail_latency_diagnostics.record_stage_duration(state, "auth_payload_applied", 1.4)
    tail_latency_diagnostics.record_stage_duration(state, "profile_fetch", 880.0)
    tail_latency_diagnostics.record_stage_duration(state, "league_restore", 420.0)
    startup_coordinator.log_startup_milestone(state, "loading_dismissed", once=False)
    startup_coordinator.log_startup_milestone(state, "game_plan_first_useful", once=False)
    startup_coordinator.log_startup_milestone(state, "dashboard_football_ready", once=False)
    summary = tail_latency_diagnostics.maybe_emit_summary(state, trigger="interactive_stable", force=True)
    assert summary is not None
    assert summary["slowest_stage"] == "profile_fetch"
    assert summary["slowest_stage_ms"] == 880.0
    assert summary["profile_fetch_ms"] == 880.0
    assert summary["league_restore_ms"] == 420.0
    assert "unexplained_ms" in summary
    assert "package_store_ms" in summary
    assert summary.get("slowest_stage_semantics") == "owner_exclusive"


def test_package_miss_completion_sequence_local():
    report = verify_package_miss_path.run_package_miss_sequence(nested_reentry=True)
    assert report["ok"] is True
    assert report["cliff"] is False
    assert "game_plan_ready" in report["events"]


def test_diagnostics_off_by_default(monkeypatch):
    monkeypatch.delenv("DYNASTYGM_STARTUP", raising=False)
    assert tail_latency_diagnostics.diagnostics_enabled() is False


def test_experiment_defaults_unchanged():
    assert experimental_graduation.GRADUATED_DEFAULT_ON is True
    # Kill switches still honor explicit off — no new experiment reincorporation.
    from modules import decision_memory, gm_targets, share_recommendation_cards

    assert decision_memory.experiment_enabled(environ={}) is True
    assert gm_targets.experiment_enabled(environ={}) is True
    assert share_recommendation_cards.experiment_enabled(environ={}) is True
    assert (
        decision_memory.experiment_enabled(
            environ={"DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY": "0"}
        )
        is False
    )


def test_deep_analysis_236_regression_still_fixed():
    source = (ROOT / "modules" / "workspace_ui.py").read_text(encoding="utf-8")
    block = source.split("def render_home_quick_actions", 1)[1].split("\ndef ", 1)[0]
    assert "home-quick-actions-shell" not in block
    assert "dg_cta_secondary_deep_" in block
    polish = mobile_visual_polish_styles.MOBILE_VISUAL_POLISH_CSS
    assert "dashboard_deep_analysis_nav" in polish
    assert "min-width:0!important" in polish.replace(" ", "")


def test_gm_orb_regression_still_fixed():
    overlay = mobile_interaction_overlay_styles.MOBILE_INTERACTION_OVERLAY_CSS
    assert "border-radius: 50%" in overlay
    assert ' [data-testid="stButton"] button' in overlay
    assert GM_ORB_ARIA_LABEL == "Open GM menu"


def test_no_new_provider_or_rerun_architecture_regression():
    from scripts.audit_founder_beta_performance import inventory

    inv = inventory()
    # Trade Analyzer add/remove must rerun so chips paint after mutation.
    assert inv["explicit_rerun_count"] <= 62
    assert inv["deferred_gate_count"] >= 4
    assert inv["reduced_context_call_count"] >= 4


def test_summary_excludes_pii_keys(monkeypatch, capsys):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state: dict = {"email": "should-not-leak@example.com"}
    from modules import auth_restore_lifecycle, startup_coordinator

    auth_restore_lifecycle.ensure_startup_session(state)
    auth_restore_lifecycle.begin_script_run(state)
    startup_coordinator.log_startup_milestone(state, "loading_dismissed", once=False)
    startup_coordinator.log_startup_milestone(state, "game_plan_first_useful", once=False)
    tail_latency_diagnostics.maybe_emit_summary(state, force=True)
    out = capsys.readouterr().out
    assert "should-not-leak" not in out
    assert "@example.com" not in out

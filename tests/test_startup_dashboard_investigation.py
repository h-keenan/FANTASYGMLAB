from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from modules import dashboard_workflow, startup_coordinator


APP_PATH = Path("app.py")
DASHBOARD_WORKFLOW_PATH = Path("modules/dashboard_workflow.py")


def test_dashboard_workflow_uses_unique_home_command_tile_key_prefixes():
    source = DASHBOARD_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert 'key_prefix="dashboard_immediate_action"' in source
    assert 'key_prefix="dashboard_primary_move"' in source
    assert 'key_prefix="dashboard_additional_moves"' in source
    assert 'key_prefix="dashboard_intelligence"' in source


def test_home_command_interaction_grid_key_is_prefix_scoped():
    from modules import player_cards

    component = Mock(return_value=Mock(clicked=None))
    with patch.object(player_cards, "PLAYER_SCAN_TAP_COMPONENT", component):
        player_cards.render_player_interaction_grid(
            html="<div class='home-command-grid'></div>",
            key_prefix="dashboard_primary_move",
        )
        player_cards.render_player_interaction_grid(
            html="<div class='home-command-grid'></div>",
            key_prefix="dashboard_intelligence",
        )

    keys = [call.kwargs["key"] for call in component.call_args_list]
    assert keys == [
        "dashboard_primary_move_tap_grid",
        "dashboard_intelligence_tap_grid",
    ]
    assert len(set(keys)) == 2


def test_dashboard_workflow_tile_calls_receive_distinct_prefixes():
    render_tiles = Mock()
    briefing = dashboard_workflow.organize_dashboard_items(
        [
            {"label": "Roster Pressure", "value": "2 Over", "note": "Over limit"},
            {"label": "Injury Alert", "value": "1", "note": "Starter out"},
            {"label": "Biggest Team Need", "value": "WR", "note": "Need help"},
            {"label": "Top Trade Opportunity", "value": "Partner", "note": "Trade path"},
            {"label": "Top Waiver Opportunity", "value": "Player", "note": "Add now"},
        ],
        immediate_labels=frozenset({"Roster Pressure", "Injury Alert"}),
    )

    dashboard_workflow.render_dashboard_workflow(
        briefing,
        snapshot_items=[{"label": "Starter Unit", "value": "#3", "note": "Depth"}],
        render_tiles=render_tiles,
        render_snapshot=Mock(),
        render_quick_actions=Mock(),
        render_league_pulse=Mock(),
    )

    prefixes = [call.kwargs["key_prefix"] for call in render_tiles.call_args_list]
    assert prefixes == [
        "dashboard_immediate_action",
        "dashboard_primary_move",
        "dashboard_intelligence",
    ]
    assert len(set(prefixes)) == len(prefixes)


def test_app_dashboard_is_rendered_once_per_main_dispatch():
    source = APP_PATH.read_text(encoding="utf-8")
    main_source = source.split("def main():", 1)[1]

    assert main_source.count('if current_page == "dashboard":') == 1
    assert main_source.count("render_home_dashboard(") == 1


def test_startup_milestones_are_logged_in_authenticated_pipeline_order():
    source = APP_PATH.read_text(encoding="utf-8")
    main_source = source.split("def main():", 1)[1]
    dashboard_source = source.split("def render_home_dashboard(", 1)[1].split(
        "STARTUP_DRAFT_STRATEGIES",
        1,
    )[0]

    pipeline_markers = (
        '"session_restored"',
        '"profile_loaded"',
        '"entitlements_loaded"',
        '"league_restored"',
    )
    pipeline_offsets = [main_source.index(marker) for marker in pipeline_markers]
    assert pipeline_offsets == sorted(pipeline_offsets)

    assert '"dashboard_rendered"' in dashboard_source
    assert main_source.index("StartupPhase.PAGE_READY") < main_source.index(
        '"loading_dismissed"'
    )


def test_startup_milestone_logging_emits_structured_line(capsys):
    state: dict = {}
    startup_coordinator.log_startup_milestone(state, "session_restored", started_at=0.0)

    captured = capsys.readouterr().out
    assert "DYNASTYGM_STARTUP" in captured
    assert "session_restored" in captured
    assert "Session restored" in captured
    assert "elapsed_ms" in captured


def test_render_failure_flag_dismisses_startup_shell(monkeypatch):
    state = {}
    placeholder = Mock()
    monkeypatch.setattr(startup_coordinator.st, "empty", lambda: placeholder)
    monkeypatch.setattr(startup_coordinator.runtime_trace, "count", lambda *_: None)
    monkeypatch.setattr(startup_coordinator, "log_startup_milestone", lambda *_a, **_k: 0.0)

    coordinator = startup_coordinator.StartupCoordinator.begin(state)
    coordinator.advance(startup_coordinator.StartupPhase.PAGE_READY)
    state["_startup_route_render_failed"] = True

    if state.pop("_startup_route_render_failed", False):
        coordinator.abort()

    assert coordinator.active is False
    placeholder.empty.assert_called()


def test_fail_startup_with_error_aborts_shell_and_surfaces_recovery(monkeypatch):
    state: dict = {}
    placeholder = Mock()
    monkeypatch.setattr(startup_coordinator.st, "empty", lambda: placeholder)
    monkeypatch.setattr(startup_coordinator.st, "error", Mock())
    monkeypatch.setattr(startup_coordinator.st, "button", Mock(return_value=False))
    monkeypatch.setattr(startup_coordinator.runtime_trace, "count", lambda *_: None)
    monkeypatch.setattr(startup_coordinator, "log_startup_milestone", lambda *_a, **_k: 0.0)

    coordinator = startup_coordinator.StartupCoordinator.begin(state)
    startup_coordinator.fail_startup_with_error(
        coordinator,
        state,
        message="Recover me",
        started_at=0.0,
    )

    assert coordinator.active is False
    placeholder.empty.assert_called()
    startup_coordinator.st.error.assert_called_once()
    startup_coordinator.st.button.assert_called_once()
    assert (
        startup_coordinator.st.button.call_args.kwargs["key"]
        == "_startup_recovery_refresh"
    )


def test_startup_coordinator_reset_clears_timing_anchor():
    state = {
        startup_coordinator.STARTUP_COMPLETE_KEY: True,
        startup_coordinator.STARTUP_TIMING_STARTED_KEY: 12.34,
    }

    startup_coordinator.reset_startup_coordinator(state)

    assert startup_coordinator.STARTUP_TIMING_STARTED_KEY not in state

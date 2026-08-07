"""Executive workflow continuity contracts — presentation only."""

from __future__ import annotations

from pathlib import Path

from modules import navigation_state, workflow_continuity


ROOT = Path(__file__).resolve().parents[1]


def test_push_and_clear_return_context():
    state = {}
    workflow_continuity.push_return_context(
        state,
        "dashboard",
        origin_label="Dashboard",
        note="Top Trade Opportunity",
        league_id="league-a",
        recommendation_id="rec-1",
        handoff_source="dashboard_quick_action",
    )
    loaded = workflow_continuity.current_return_context(state, league_id="league-a")
    assert loaded is not None
    assert loaded.origin_page == "dashboard"
    assert loaded.recommendation_id == "rec-1"

    workflow_continuity.clear_return_context(state)
    assert workflow_continuity.current_return_context(state) is None


def test_return_context_invalidates_on_league_mismatch():
    state = {}
    workflow_continuity.push_return_context(
        state,
        "dashboard",
        league_id="league-a",
    )
    assert (
        workflow_continuity.current_return_context(state, league_id="league-b") is None
    )
    assert workflow_continuity.WORKFLOW_RETURN_KEY not in state


def test_scroll_restore_mode_is_distinct_from_reset():
    state = {}
    reset_token = navigation_state.request_scroll_reset(state, "trade_hub")
    restore_token = navigation_state.request_scroll_restore(state, "dashboard")
    assert reset_token != restore_token
    pending = navigation_state.consume_scroll_reset(state, "dashboard")
    assert pending is not None
    assert pending["mode"] == "restore"
    assert pending["reason"] == "workflow_back"


def test_continuity_banner_includes_trail_and_provenance():
    context = workflow_continuity.WorkflowReturnContext(
        origin_page="dashboard",
        origin_label="Dashboard",
        note="Top Trade Opportunity",
        league_id="league-a",
        recommendation_id="abc123",
    )
    html = workflow_continuity.continuity_banner_html(context, current_page="trade_hub")
    assert "Dashboard → Trade Hub" in html
    assert "Top Trade Opportunity" in html
    assert "data-recommendation-id='abc123'" in html


def test_app_wires_workflow_continuity():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "workflow_continuity" in source
    assert "render_workflow_continuity_bar" in source
    assert "_capture_workflow_handoff" in source
    assert "_workflow_return_to_origin" in source
    assert "request_scroll_restore" in source
    assert "WORKFLOW_RETURN_KEY" in source
    clearer = source.split("def _clear_league_switch_workflow_state(", 1)[1].split(
        "\ndef ", 1
    )[0]
    assert "clear_return_context" in clearer


def test_audit_document_exists():
    doc = (ROOT / "docs" / "executive-workflow-continuity-audit.md").read_text(
        encoding="utf-8"
    )
    for section in (
        "Workflow journeys",
        "Before navigation map",
        "After navigation map",
        "Dead ends removed",
        "Duplicate transitions removed",
        "Remaining workflow friction",
        "Future opportunities",
        "Cross-page state",
    ):
        assert section in doc

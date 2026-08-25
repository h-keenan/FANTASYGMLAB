"""Decision Memory route commit + Player Quick View action routing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from modules import decision_change_history as history
from modules import decision_change_history_ui as ui
from modules import decision_memory
from modules.navigation_state import (
    PENDING_ROUTE_SOURCE_KEY,
    commit_destination_navigation,
    queue_destination_navigation,
    resolve_resume_destination,
)
from modules import player_quick_view


ROOT = Path(__file__).resolve().parents[1]
APP_SRC = (ROOT / "app.py").read_text(encoding="utf-8")
UI_SRC = (ROOT / "modules" / "decision_change_history_ui.py").read_text(encoding="utf-8")


def _event(**overrides) -> history.DecisionChangeEvent:
    payload = dict(
        event_id="e1",
        recommendation_id="r1",
        league_id="L1",
        roster_id="1",
        timestamp=1.0,
        lifecycle_transition="none->current",
        reason="recommendation",
        category="Trades",
        target_label="Josh Jacobs",
        player_id="6794",
        destination="trade_hub",
        previous_state={"action": "Hold", "title": "Hold Jacobs"},
        current_state={"action": "Shop", "title": "Shop Jacobs"},
        summary_headline="Trade priority moved up",
        summary_detail="Jacobs is now the top shop candidate.",
        why_label="Recommendation priority changed",
        current_confidence_band="high",
        scoring_format="PPR",
    )
    payload.update(overrides)
    return history.DecisionChangeEvent(**payload)


def _load_app(session: dict):
    import app

    app.st.session_state = session
    return app


def test_home_command_route_commits_instead_of_queue_only():
    opener = APP_SRC[
        APP_SRC.index("def _open_home_command_route(") : APP_SRC.index(
            "def _open_daily_gm_briefing_item("
        )
    ]
    assert "_commit_platform_destination(" in opener
    assert "_queue_platform_route(" not in opener


def test_decision_memory_trade_hub_and_waivers_commit_current_page():
    app = _load_app({"selected_league_id": "L1", "platform_nav_page": "dashboard"})
    with patch.object(app, "_commit_platform_destination") as commit:
        app._open_decision_change_event(_event(destination="trade_hub"))
        app._open_decision_change_event(
            _event(event_id="e2", destination="waivers", category="Waivers")
        )
    assert [call.args[0] for call in commit.call_args_list] == ["trade_hub", "waivers"]
    assert commit.call_args_list[0].kwargs["source"] == "what_changed"


def test_commit_survives_session_page_when_pending_is_consumed():
    state = {"platform_nav_page": "dashboard"}
    commit_destination_navigation(
        state,
        "trade_hub",
        current_destination="dashboard",
        source="what_changed",
    )
    pending = state.pop("_pending_platform_route", "")
    source = state.pop(PENDING_ROUTE_SOURCE_KEY, "")
    resumed = resolve_resume_destination(
        pending_page=pending,
        pending_source=source,
        query_page="",
        session_page=state.get("platform_nav_page"),
        allowed=("dashboard", "trade_hub", "waivers"),
    )
    assert state["platform_nav_page"] == "trade_hub"
    assert resumed == "trade_hub"


def test_queue_only_drops_when_pending_is_lost_before_resume():
    state = {"platform_nav_page": "dashboard"}
    queue_destination_navigation(
        state,
        "waivers",
        current_destination="dashboard",
        source="what_changed",
    )
    state.pop("_pending_platform_route", None)
    state.pop(PENDING_ROUTE_SOURCE_KEY, None)
    resumed = resolve_resume_destination(
        pending_page="",
        pending_source="",
        query_page="",
        session_page=state.get("platform_nav_page"),
        allowed=("dashboard", "trade_hub", "waivers"),
    )
    assert resumed == ""
    assert state["platform_nav_page"] == "dashboard"


def test_empty_destination_does_not_route():
    app = _load_app({"selected_league_id": "L1", "platform_nav_page": "dashboard"})
    with patch.object(app, "_commit_platform_destination") as commit:
        app._open_decision_change_event(_event(destination=""))
    commit.assert_not_called()


def test_resolved_history_stays_readable_without_route_action():
    event = _event(
        lifecycle_transition="current->resolved",
        destination="waivers",
        summary_headline="Waiver opportunity resolved",
    )
    assert history.destination_is_current(event)
    assert not decision_memory.route_action_is_relevant(event)
    html = ui.decision_memory_timeline_item_html(event)
    assert "Josh Jacobs" in html
    assert "Waiver opportunity resolved" in html
    assert "Hold → Shop" in html or "Hold" in html
    assert "@st.dialog" not in UI_SRC
    assert "dg-decision-memory-sheet" in UI_SRC
    assert "Open in Trade Hub →" == decision_memory.cta_label_for_event(
        _event(destination="trade_hub")
    )
    assert "Open in Waivers →" == decision_memory.cta_label_for_event(
        _event(destination="waivers")
    )


def test_history_open_closes_sheet_before_routing():
    open_fn = UI_SRC[
        UI_SRC.index("def _open_current(event") : UI_SRC.index(
            'title = "Decision Memory"'
        )
    ]
    assert "_close_flag(close_key)" in open_fn
    assert "open_event(event)" in open_fn
    assert open_fn.index("_close_flag(close_key)") < open_fn.index("open_event(event)")
    assert "on_click=_open_current" in UI_SRC
    assert "_render_history_sheet" in UI_SRC


def test_pqv_trade_hub_uses_commit_and_app_scope_rerun():
    assert 'on_click=_pqv_open_trade_hub' in APP_SRC
    opener = APP_SRC[
        APP_SRC.index("def _open_trade_hub_for_player_focus(") : APP_SRC.index(
            "def render_player_detail_picker("
        )
    ]
    assert '_commit_platform_destination("trade_hub", source="player_quick_view")' in opener
    assert "st.rerun(scope=" in opener
    assert "_queue_platform_route" not in opener


def test_pqv_active_recommendation_does_not_duplicate_why():
    html = player_quick_view.recommendation_context_html(
        "Elite workload plus production.",
        "",
        action="Shop",
        confidence="High confidence",
        factors=(("Why", "Elite workload plus production."), ("Risk", "Questionable")),
    )
    assert html.count("Elite workload plus production.") == 1
    assert "Shop" in html
    assert "High confidence" in html
    assert "FantasyGM Read" not in html

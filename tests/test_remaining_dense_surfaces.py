"""Remaining dense-surface migration contracts (News, Decision, Draft, Explorer)."""

from __future__ import annotations

from pathlib import Path

from modules import (
    decision_change_history as history,
    decision_change_history_ui,
    dense_list_primitives,
    league_intelligence_ui,
    live_draft_ui,
    player_asset_explorer_ui as explorer,
)
from modules.app_styles import APP_CSS
from modules.dense_list_styles import DENSE_LIST_CSS
from modules.league_intelligence_styles import LEAGUE_INTELLIGENCE_CSS
from tests.test_league_intelligence import NOW, build, news


ROOT = Path(__file__).resolve().parents[1]


def test_app_css_stays_under_budget_after_migration():
    assert len(APP_CSS) < 390_000
    assert DENSE_LIST_CSS in APP_CSS
    assert APP_CSS.index(DENSE_LIST_CSS) < APP_CSS.index(LEAGUE_INTELLIGENCE_CSS)


def test_dense_row_helper_assembles_canonical_slots():
    html = dense_list_primitives.dense_row_html(
        lead_html=dense_list_primitives.dense_lead_html("#1"),
        identity_html=dense_list_primitives.dense_identity_html(
            primary="Alpha",
            secondary="WR · KC",
        ),
        metric_html=dense_list_primitives.dense_metric_html("12.4", "Value"),
        trail_html=dense_list_primitives.dense_trail_html(
            status_html=dense_list_primitives.dense_status_html("STARTER"),
            meta_html=dense_list_primitives.dense_meta_html("Today"),
            exception_html=dense_list_primitives.dense_exception_html("OUT", label="Injury"),
        ),
        extra_classes=["fixture-row"],
    )
    assert "dg-dense-row" in html
    assert "fixture-row" in html
    assert html.index("dg-dense-lead") < html.index("dg-dense-identity")
    assert html.index("dg-dense-identity") < html.index("dg-dense-metric")
    assert html.index("dg-dense-metric") < html.index("dg-dense-status")
    assert html.index("dg-dense-status") < html.index("dg-dense-meta")
    assert html.index("dg-dense-meta") < html.index("dg-dense-exception")


def test_no_late_ranking_stylesheet_reintroduced():
    assert live_draft_ui.ranking_card_styles_html() == ""
    source = (ROOT / "modules" / "live_draft_ui.py").read_text(encoding="utf-8")
    assert ".live-rank-row{align-items:center" not in source


def test_news_decision_draft_explorer_use_dense_row():
    news_html = league_intelligence_ui.intelligence_item_html(
        build([news("My Player", NOW - 60, reason="injury/status")]).items[0]
    )
    assert "dg-dense-row" in news_html
    assert "dg-intelligence-item__summary" not in news_html

    event = history.DecisionChangeEvent(
        event_id="e1",
        recommendation_id="r1",
        league_id="L",
        roster_id="1",
        timestamp=NOW,
        lifecycle_transition="current->changed",
        reason="recommendation",
        category="trade",
        target_label="Player A",
        player_id="p1",
        destination="trade_hub",
        previous_state=None,
        current_state=None,
        summary_headline="Priority increased",
        summary_detail="Moved from #4 to #1",
        why_label="Strategy focus changed",
        current_confidence_band="high",
    )
    decision_html = decision_change_history_ui.decision_event_row_html(event)
    assert "dg-dense-row" in decision_html
    assert "data-decision-event-id='e1'" in decision_html
    assert "Changed" in decision_html or "changed" in decision_html.casefold()

    pick_html = live_draft_ui._pick_row_html(
        {
            "pick_no": 12,
            "player_name": "Test WR",
            "position": "WR",
            "team": "KC",
            "round_pick": "2.01",
            "fantasy_team": "War Room",
            "is_mine": True,
        },
        latest_pick_no=12,
    )
    assert "dg-dense-row" in pick_html
    assert "War Room" in pick_html

    explorer_html = explorer.pick_card_html(
        {
            "label": "2027 1st",
            "season": 2027,
            "round": 1,
            "score": 900,
            "owner_team_name": "War Room",
            "projected_pick_range": "Early",
        },
        score_label="Value",
    )
    assert "dg-dense-row" in explorer_html
    assert "explorer-pick-card" in explorer_html


def test_player_tap_selector_includes_dense_rows():
    source = (ROOT / "modules" / "interaction_contract.py").read_text(encoding="utf-8")
    assert ".dg-dense-row[data-player-id]" in source

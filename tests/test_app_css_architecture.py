"""APP_CSS architecture: global vs route-owned CSS contracts."""

from __future__ import annotations

from pathlib import Path

from modules.app_styles import APP_CSS
from modules.live_draft_styles import LIVE_DRAFT_CSS
from modules.methodology_page_styles import METHODOLOGY_PAGE_CSS
from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS
from modules.trade_detail_styles import TRADE_DETAIL_CSS
from modules.waivers_presentation_styles import WAIVERS_PRESENTATION_CSS
from modules.my_team_decision_styles import MY_TEAM_DECISION_CSS
from modules.dashboard_workflow_styles import DASHBOARD_WORKFLOW_CSS
from modules.league_recaps_styles import LEAGUE_RECAPS_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_route_owned_css_is_not_in_app_css():
    for css in (
        PLAYER_QUICK_VIEW_CSS,
        WAIVERS_PRESENTATION_CSS,
        TRADE_DETAIL_CSS,
        METHODOLOGY_PAGE_CSS,
        LIVE_DRAFT_CSS,
        MY_TEAM_DECISION_CSS,
        LEAGUE_RECAPS_CSS,
    ):
        assert css not in APP_CSS


def test_route_owned_css_is_injected_by_owners():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "inject_global_styles(PLAYER_QUICK_VIEW_CSS)" in app
    assert "inject_global_styles(WAIVERS_PRESENTATION_CSS)" in (
        ROOT / "modules" / "waivers_ui.py"
    ).read_text(encoding="utf-8")
    trade_hub = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    assert "inject_global_styles(TRADE_DETAIL_CSS)" in trade_hub
    methodology = (ROOT / "modules" / "methodology_page.py").read_text(encoding="utf-8")
    assert "inject_global_styles(METHODOLOGY_PAGE_CSS)" in methodology
    live_draft = (ROOT / "modules" / "live_draft_ui.py").read_text(encoding="utf-8")
    assert "inject_global_styles(LIVE_DRAFT_CSS)" in live_draft
    my_team = (ROOT / "modules" / "my_team_ui.py").read_text(encoding="utf-8")
    assert "inject_global_styles(MY_TEAM_DECISION_CSS)" in my_team
    recaps = (ROOT / "modules" / "league_recaps_ui.py").read_text(encoding="utf-8")
    assert "inject_global_styles(LEAGUE_RECAPS_CSS)" in recaps
    assert "st-key-dashboard_team_snapshot" in DASHBOARD_WORKFLOW_CSS


def test_dead_pqv_generations_are_gone_from_global_css():
    for selector in (
        ".player-quick-view-submeta",
        ".player-quick-view-primary-row",
        ".player-quick-view-score-pill",
        ".player-quick-view-injury-pill",
        ".player-quick-view-tag-group",
        ".player-quick-view-summary",
        ".player-quick-view-metrics",
        ".player-quick-view-headshot",
        ".player-quick-view-recommendation-copy",
        ".player-quick-view-recommendation-title",
    ):
        assert selector not in APP_CSS
    assert ".player-quick-view-shell" in APP_CSS
    assert ".player-quick-view-recommendation-card" in APP_CSS
    assert ".player-quick-view-panel-body" in APP_CSS


def test_app_css_stays_under_existing_guardrail():
    assert len(APP_CSS) < 390_000

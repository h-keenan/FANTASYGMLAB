"""My Team decision-first IA + Dashboard disclosure cleanup."""

from __future__ import annotations

from pathlib import Path

from modules import deferred_rendering, football_assets, my_team_ui, player_tier_identity
from modules.app_styles import APP_CSS
from modules.dashboard_workflow_styles import DASHBOARD_WORKFLOW_CSS
from modules.my_team_decision_styles import MY_TEAM_DECISION_CSS


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
WORKSPACE = (ROOT / "modules" / "my_team_ui.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")


def test_strategy_has_single_visible_owner():
    html = my_team_ui.strategy_identity_html(
        strategy_label="Contender",
        archetype_label="One Move Away",
        auto_strategy_label="Contender",
    )
    assert html.count("Contender") == 1
    assert "One Move Away" in html
    assert "Team strategy" in html
    assert WORKSPACE.count('"label": "Roster posture"') == 0
    assert WORKSPACE.count('"label": "Team archetype"') == 0
    my_team = APP[APP.index('if current_page == "my_team":') : APP.index("# STARTUP DRAFT CENTER")]
    assert my_team.count("active_team_strategy_label, \"premium\"") == 0


def test_roster_decisions_are_first_class_before_core():
    assert WORKSPACE.index('_canonical_header("Roster Decisions")') < WORKSPACE.index(
        '_canonical_header("Roster Actions")'
    )
    assert WORKSPACE.index('_canonical_header("Roster Decisions")') < WORKSPACE.index(
        '_canonical_header("Roster Core")'
    )
    assert "Protected players and secondary decisions" not in WORKSPACE
    for label in ("Untouchables", "Trade Candidates", "Hold Candidates", "Drop Candidates"):
        assert f'title="{label}"' in WORKSPACE


def test_no_duplicate_strategy_widget_keys():
    my_team = APP[APP.index('if current_page == "my_team":') : APP.index("# STARTUP DRAFT CENTER")]
    assert my_team.count("key=strategy_key") == 1
    assert my_team.count("key=untouchables_key") == 1
    assert "_render_my_team_strategy_management" in my_team
    assert "render_strategy_management=_render_my_team_strategy_management" in my_team
    tables = my_team[my_team.index("Detailed roster tables") :]
    assert "key=strategy_key" not in tables
    assert "key=untouchables_key" not in tables


def test_strategy_state_keys_are_unchanged():
    assert "team_strategy_select_{selected_league_id}_{my_roster_id}" in APP
    assert "untouchables_ms_{selected_league_id}" in APP
    assert "role_{selected_league_id}_{pid}" in APP
    assert 'f"my_team_strategy_panel_{' in WORKSPACE or "_strategy_panel_key" in WORKSPACE


def test_queue_q_injury_badge_is_labeled():
    html = football_assets.injury_badge_html("Q")
    assert ">Ques<" in html
    assert "aria-label='Player status:" in html
    assert "title='Player status:" in html
    assert ">Q<" not in html


def test_dashboard_sections_are_first_class_not_accordions():
    assert 'with st.expander("League Insights"' not in DASHBOARD
    assert 'with st.expander("Team Snapshot"' not in DASHBOARD
    assert 'render_section_header("League Insights"' in DASHBOARD
    assert 'render_section_header("Team Snapshot"' in DASHBOARD
    assert 'st.container(key="dashboard_team_snapshot")' in DASHBOARD
    assert "st-key-dashboard_team_snapshot" in DASHBOARD_WORKFLOW_CSS
    assert "grid-template-columns: 1fr 1fr" in DASHBOARD_WORKFLOW_CSS
    assert 'with st.expander("League Pulse and supporting trends"' in DASHBOARD


def test_league_insights_are_not_a_deferred_gate():
    insights = DASHBOARD[
        DASHBOARD.index("dashboard_league_insights") : DASHBOARD.index("dashboard_team_snapshot")
    ]
    assert "render_deferred_section_gate" not in insights
    assert "already-computed" in insights


def test_detailed_tables_remain_deferred():
    tables = APP[APP.index("Detailed roster tables") :]
    assert "Load detailed roster tables" in tables
    assert "my_team_deep_analysis_" in tables
    gate = tables.index("Load detailed roster tables")
    assert tables.index("Detailed Roster Table") > gate
    assert deferred_rendering.deferred_state_key("my_team_deep_analysis_x_y").startswith(
        "deferred_section_ready__"
    )


def test_player_tier_ladder_unchanged():
    assert [tier.tier_id for tier in player_tier_identity.PLAYER_TIER_LADDER] == [
        "generational",
        "elite",
        "impact_starter",
        "starter",
        "contributor",
        "committee_role",
        "depth_developmental",
    ]


def test_css_ownership_does_not_grow_app_css():
    assert MY_TEAM_DECISION_CSS not in APP_CSS
    assert len(APP_CSS) < 390_000
    assert "inject_global_styles(MY_TEAM_DECISION_CSS)" in WORKSPACE
    assert "my-team-strategy-identity" in MY_TEAM_DECISION_CSS


def test_decision_cards_do_not_restate_category_prestige():
    decisions = WORKSPACE[
        WORKSPACE.index('_canonical_header("Roster Decisions")') : WORKSPACE.index(
            '_canonical_header("Roster Actions")'
        )
    ]
    assert decisions.count("show_prestige=False") >= 4
    assert "reason_limit=80" in decisions
    assert "reason_limit=160" in decisions

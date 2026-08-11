"""Contracts for executive workflow compression presentation polish."""

from pathlib import Path

from modules.executive_workflow_compression_styles import EXECUTIVE_WORKFLOW_COMPRESSION_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_compression_css_is_token_backed_and_wired_into_app_css():
    assert "home-command-card-cta" in EXECUTIVE_WORKFLOW_COMPRESSION_CSS
    assert "st-key-dashboard_workflow" in EXECUTIVE_WORKFLOW_COMPRESSION_CSS
    assert "player-dossier-recommendation-context" in EXECUTIVE_WORKFLOW_COMPRESSION_CSS
    assert "#" not in EXECUTIVE_WORKFLOW_COMPRESSION_CSS
    assert "rgba(" not in EXECUTIVE_WORKFLOW_COMPRESSION_CSS
    app_styles = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    assert "EXECUTIVE_WORKFLOW_COMPRESSION_CSS" in app_styles


def test_dashboard_workflow_omits_redundant_section_chrome():
    source = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
    assert 'if not game_plan_present:' in source
    assert "Needs Attention" not in source
    assert "Only issues that require a decision now." not in source
    assert "Why this matters now" not in source
    assert source.index("render_todays_game_plan()") < source.index("render_what_changed()")
    assert source.index('with st.expander("League Insights"') < source.index(
        'with st.expander("Team Snapshot"'
    )


def test_my_team_next_move_leads_roster_actions():
    source = (ROOT / "modules" / "my_team_ui.py").read_text(encoding="utf-8")
    actions = source[
        source.index('_canonical_header("Roster Actions")') : source.index(
            '_canonical_header("Roster Core")'
        )
    ]
    assert actions.index('"label": "Next Move"') < actions.index('"label": "Roster Status"')
    assert actions.index('"label": "Roster Status"') < actions.index('"label": "Injury Alerts"')
    assert 'route_key": "trade_hub"' in actions
    assert 'route_key": "waivers"' in actions
    assert "What to do next" not in actions


def test_recommendation_route_cta_is_chevron_not_competing_copy():
    source = (ROOT / "modules" / "workspace_ui.py").read_text(encoding="utf-8")
    assert "home-command-card-cta" in source
    assert "→" in source
    assert source.count("Open in Trade Hub") == 0

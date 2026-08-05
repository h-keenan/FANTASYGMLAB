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
    assert 'render_section_header("Immediate Action", weight="primary")' in source
    assert 'render_section_header("Your Next Move", weight="secondary")' in source
    assert "Needs Attention" not in source
    assert "Only issues that require a decision now." not in source
    assert "Why this matters now" not in source


def test_my_team_next_move_leads_roster_priorities():
    source = (ROOT / "modules" / "my_team_ui.py").read_text(encoding="utf-8")
    priorities = source[
        source.index('_canonical_header("Roster Priorities")') : source.index(
            '_canonical_header("Roster Decisions")'
        )
    ]
    assert priorities.index('"label": "Next Move"') < priorities.index('"label": "Roster Status"')
    assert priorities.index('"label": "Roster Status"') < priorities.index('"label": "Injury Alerts"')
    assert "What to do next" not in priorities


def test_recommendation_route_cta_is_chevron_not_competing_copy():
    source = (ROOT / "modules" / "workspace_ui.py").read_text(encoding="utf-8")
    assert "home-command-card-cta" in source
    assert "→" in source
    assert source.count("Open in Trade Hub") == 0

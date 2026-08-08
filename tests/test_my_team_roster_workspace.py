"""My Team roster workspace hierarchy — presentation only."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_workspace_audit_doc_exists():
    doc = ROOT / "docs" / "my-team-roster-workspace-audit.md"
    text = doc.read_text(encoding="utf-8")
    assert "Final hierarchy" in text
    assert "Roster Snapshot" in text
    assert "format_compact_rank" in text
    assert "suggest_optimal_lineup" in text


def test_my_team_hierarchy_and_advice_demotion():
    workspace = (ROOT / "modules" / "my_team_ui.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    my_team = app[
        app.index('if current_page == "my_team":') : app.index(
            "# STARTUP DRAFT CENTER"
        )
    ]
    assert workspace.index('_canonical_header("Roster Priorities")') < workspace.index(
        '_canonical_header("Roster Decisions")'
    )
    assert workspace.index('_canonical_header("Roster Decisions")') < workspace.index(
        '_canonical_header("Starting Lineup")'
    )
    assert workspace.index('_canonical_header("Starting Lineup")') < workspace.index(
        '_canonical_header("Roster Snapshot")'
    )
    assert '_canonical_header("Team Summary")' not in workspace
    assert '_canonical_header("Team Outlook")' not in workspace
    assert workspace.count('"label": "Health Outlook"') == 1
    assert 'with st.expander("Front-office context", expanded=False):' in my_team
    assert 'render_section_header(\n                    "Front-Office Advice"' not in my_team
    deep = my_team[my_team.index('with st.expander("Deep Analysis"') :]
    premium_body = deep.split("else:", 1)[1]
    assert "Edit Roles" in premium_body
    assert "render_analysis_cards" not in premium_body
    assert "render_archetype_summary" not in premium_body
def test_starter_and_bench_rows_use_canonical_compact_ranks():
    source = (ROOT / "modules" / "my_team_ui.py").read_text(encoding="utf-8")
    assert source.count("canonical_player_ranking.format_compact_rank(") >= 3

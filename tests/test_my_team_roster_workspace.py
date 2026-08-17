"""My Team roster workspace hierarchy — presentation only (#194 / #199)."""

from __future__ import annotations

from pathlib import Path

from modules import my_team_ui
from modules.roster_needs import PositionNeedAssessment, TeamNeedsAssessment

ROOT = Path(__file__).resolve().parents[1]


def test_workspace_finalization_doc_exists():
    doc = ROOT / "docs" / "my-team-roster-workspace-finalization.md"
    text = doc.read_text(encoding="utf-8")
    assert "Final hierarchy" in text
    assert "Roster Posture" in text
    assert "Position Groups" in text
    assert "Draft Capital" in text
    assert "suggest_optimal_lineup" in text or "projected" in text.lower()


def test_my_team_hierarchy_construction_first():
    workspace = (ROOT / "modules" / "my_team_ui.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    my_team = app[
        app.index('if current_page == "my_team":') : app.index(
            "# STARTUP DRAFT CENTER"
        )
    ]
    assert workspace.index('_canonical_header("Roster Signals")') < workspace.index(
        '_canonical_header("Strength & Pressure")'
    )
    assert workspace.index('_canonical_header("Strength & Pressure")') < workspace.index(
        '_canonical_header("Roster Decisions")'
    )
    assert workspace.index('_canonical_header("Roster Decisions")') < workspace.index(
        '_canonical_header("Roster Actions")'
    )
    assert workspace.index('_canonical_header("Roster Actions")') < workspace.index(
        '_canonical_header("Roster Core")'
    )
    assert workspace.index('_canonical_header("Roster Core")') < workspace.index(
        '_canonical_header("Position Groups")'
    )
    assert 'st.container(key="my_team_roster_core")' in workspace
    assert workspace.index('_canonical_header("Position Groups")') < workspace.index(
        '_canonical_header("Draft Capital")'
    )
    assert '_canonical_header("Roster Snapshot")' not in workspace
    assert '_canonical_header("Starting Lineup")' not in workspace
    assert '_canonical_header("Team Summary")' not in workspace
    assert "How these roster grades work" in workspace
    assert "How to read this roster" not in workspace
    assert 'route_key": "waivers"' in workspace
    assert "client_disclosure_html" in workspace
    assert 'with st.expander("Front-office context"' not in my_team
    assert "advice_items=advice_items" in my_team
    assert "draft_pick_assets=" in my_team
    assert "team_needs_assessment=" in my_team
    deep = my_team[my_team.index('render_section_header(\n                    "Detailed roster tables"') :]
    premium_body = deep
    assert "Edit Roles" in my_team
    assert "render_analysis_cards" not in premium_body
    assert "render_archetype_summary" not in premium_body


def test_starter_and_bench_rows_use_canonical_compact_ranks():
    source = (ROOT / "modules" / "my_team_ui.py").read_text(encoding="utf-8")
    assert source.count("canonical_player_ranking.format_compact_rank(") >= 3


def test_room_outlook_label_maps_existing_classifications_only():
    assert (
        my_team_ui.room_outlook_label(
            position="WR",
            classification="covered",
            strengths=["WR"],
        )
        == "Strength"
    )
    assert (
        my_team_ui.room_outlook_label(
            position="RB",
            classification="short_term_need",
            strengths=[],
        )
        == "Thin"
    )
    assert (
        my_team_ui.room_outlook_label(
            position="TE",
            classification="future_risk",
            strengths=[],
        )
        == "Future risk"
    )
    assert (
        my_team_ui.room_outlook_label(
            position="QB",
            classification="covered",
            strengths=[],
            upgrade_opportunity=True,
        )
        == "Upgrade room"
    )


def test_compact_owned_draft_capital_groups_by_season():
    rows = my_team_ui.compact_owned_draft_capital(
        [
            {"owner_roster_id": "7", "season": 2027, "round": 1},
            {"owner_roster_id": "7", "season": 2027, "round": 3},
            {"owner_roster_id": "7", "season": 2028, "round": 2},
            {"owner_roster_id": "9", "season": 2027, "round": 1},
        ],
        7,
    )
    assert rows == [
        {"season": 2027, "rounds": [1, 3], "label": "1st · 3rd"},
        {"season": 2028, "rounds": [2], "label": "2nd"},
    ]


def test_position_groups_respect_superflex_and_te_premium_context():
    assessment = TeamNeedsAssessment(
        positions=(
            PositionNeedAssessment(
                position="QB",
                severity=0.0,
                classification="covered",
                starter_quality=None,
                backup_quality=None,
                depth_quality=None,
                future_stability=None,
                injury_pressure=0.0,
                replacement_gap=None,
                required_starters=2,
                reasons=("Starter covered with backup/future depth",),
                reason_codes=("room_covered",),
                data_quality="complete",
                true_need=False,
                relative_weakness=False,
                upgrade_opportunity=False,
                temporary_injury_pressure=False,
                future_risk=False,
            ),
            PositionNeedAssessment(
                position="TE",
                severity=1.0,
                classification="short_term_need",
                starter_quality=None,
                backup_quality=None,
                depth_quality=None,
                future_stability=None,
                injury_pressure=0.0,
                replacement_gap=None,
                required_starters=1,
                reasons=("TE-premium depth",),
                reason_codes=("insufficient_active_coverage",),
                data_quality="complete",
                true_need=True,
                relative_weakness=False,
                upgrade_opportunity=False,
                temporary_injury_pressure=False,
                future_risk=False,
            ),
        ),
        true_needs=("TE",),
        relative_weaknesses=(),
        upgrade_opportunities=(),
        temporary_injury_pressures=(),
        future_risks=(),
    )
    items = my_team_ui._position_groups_items(
        assessment,
        strengths=[],
        league_settings={"superflex_count": 1, "te_premium": True},
    )
    titles = {item["title"]: item["label"] for item in items}
    assert "QB · Superflex" in titles
    assert titles["QB · Superflex"] == "Covered"
    assert "TE · TE Premium" in titles
    assert titles["TE · TE Premium"] == "Thin"

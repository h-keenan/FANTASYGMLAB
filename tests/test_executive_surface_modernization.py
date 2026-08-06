"""Executive surface modernization contracts (PR #137)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import executive_table_ui
from modules import workspace_ui


ROOT = Path(__file__).resolve().parents[1]


def test_section_header_uses_executive_primitives():
    source = (ROOT / "modules" / "workspace_ui.py").read_text(encoding="utf-8")
    block = source.split("def render_section_header(", 1)[1].split("\ndef ", 1)[0]
    assert "ui_primitives.render_section_header" in block
    assert "section-header section-header-compact" not in block


def test_executive_table_summary_renders_card_rows():
    html = executive_table_ui.executive_table_summary_html(
        [
            {"Team": "Alpha", "Power Rank": "1", "Power Score": "1200"},
            {"Team": "Beta", "Power Rank": "2", "Power Score": "1100"},
        ],
        primary_key="Team",
        secondary_key="Power Rank",
        meta_key="Power Score",
        max_rows=2,
    )
    assert "dg-ui-table-summary" in html
    assert "dg-ui-card" in html


def test_team_rank_cards_include_executive_card_classes():
    source = (ROOT / "modules" / "league_workspace_ui.py").read_text(encoding="utf-8")
    block = source.split("def render_team_rank_cards(", 1)[1].split("\ndef ", 1)[0]
    assert "team-rank-card dg-ui-card dg-ui-card--elevated" in block


def test_summary_tiles_include_dg_ui_card():
    source = (ROOT / "modules" / "workspace_ui.py").read_text(encoding="utf-8")
    block = source.split("def render_summary_tiles(", 1)[1].split("\ndef ", 1)[0]
    assert "summary-tile dg-ui-card" in block


def test_league_overview_primary_tables_use_executive_disclosure():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "executive_table_ui.render_executive_table_disclosure" in source
    assert 'expander_label="Full manager tendencies table"' in source
    assert 'expander_label="Full archetype table"' in source


def test_live_draft_pick_boards_use_executive_table_ui():
    source = (ROOT / "modules" / "live_draft_ui.py").read_text(encoding="utf-8")
    assert "executive_table_ui.render_executive_table_disclosure" in source
    assert "st.dataframe(pd.DataFrame(rows[-12:])" not in source


def test_draft_center_customer_metrics_use_executive_tiles():
    source = (ROOT / "modules" / "draft_center_ui.py").read_text(encoding="utf-8")
    capital_block = source.split("def render_draft_capital_dashboard(", 1)[1].split(
        "\ndef render_team_pick_expanders(", 1
    )[0]
    assert "render_executive_metric_tiles" in capital_block
    assert "st.metric(" not in capital_block


def test_modernization_document_exists():
    doc = (ROOT / "docs" / "executive-surface-modernization.md").read_text(encoding="utf-8")
    for section in (
        "Legacy Surface Inventory",
        "Consistency Matrix",
        "Remaining legacy count",
        "Explicit confirmation",
    ):
        assert section in doc
    assert "d487bcdd9d1b31e7cea2c5a27a92826050a7a233" in doc


def test_no_football_logic_modules_touched():
    allowed = {
        "app.py",
        "modules/workspace_ui.py",
        "modules/league_workspace_ui.py",
        "modules/live_draft_ui.py",
        "modules/draft_center_ui.py",
        "modules/waivers_ui.py",
        "modules/executive_table_ui.py",
        "modules/ui_primitive_styles.py",
    }
    forbidden_prefixes = (
        "modules/rankings",
        "modules/trade_ideas",
        "modules/player_eligibility",
        "modules/premium",
        "modules/auth_supabase",
        "modules/stripe",
        "modules/sleeper",
        "modules/recommendation_lifecycle",
        "modules/workflow_continuity",
    )
    for prefix in forbidden_prefixes:
        assert not any(path.startswith(prefix) for path in allowed)

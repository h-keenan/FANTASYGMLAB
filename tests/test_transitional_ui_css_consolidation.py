"""Transitional UI / CSS consolidation contracts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_consolidation_document_exists():
    doc = ROOT / "docs" / "transitional-ui-css-consolidation.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    for marker in (
        "Transitional classes before / after",
        "CSS ownership map",
        "Override chains eliminated",
        "Table / disclosure decision",
        "Remaining intentional style debt",
    ):
        assert marker in text


def test_removed_transitional_classes_absent_from_customer_markup_helpers():
    sources = {
        "league": (ROOT / "modules" / "league_workspace_ui.py").read_text(encoding="utf-8"),
        "draft": (ROOT / "modules" / "draft_center_ui.py").read_text(encoding="utf-8"),
        "workspace": (ROOT / "modules" / "workspace_ui.py").read_text(encoding="utf-8"),
    }
    for label, source in sources.items():
        assert "power-row" not in source, label
        assert "power-logo-wrap" not in source, label
        assert "team-rank-card" not in source, label
        assert "trade-idea-card-compact" not in source, label
        assert "intelligence-grid" not in source, label

    league = sources["league"]
    assert "dg-ranked-row" in league
    assert "dg-intel-card" in league
    assert "workspace_ui.render_summary_tiles" in league.split("def render_team_rank_cards(", 1)[1]


def test_canonical_cards_dual_class_dg_ui_card():
    workspace = (ROOT / "modules" / "workspace_ui.py").read_text(encoding="utf-8")
    my_team = (ROOT / "modules" / "my_team_ui.py").read_text(encoding="utf-8")
    assert "summary-tile dg-ui-card" in workspace
    assert "analysis-card dg-ui-card" in workspace
    assert "advice-card dg-ui-card" in my_team
    assert "prospect-card dg-ui-card" in my_team


def test_app_css_drops_removed_transitional_selectors():
    from modules.app_styles import APP_CSS

    for selector in (
        ".power-row",
        ".power-logo-wrap",
        ".team-rank-card",
        ".trade-idea-card-compact",
        ".summary-tile-kicker",
        ".intelligence-grid",
        ".concept-band",
        ".concept-chip",
        ".concept-label",
        ".concept-title",
        ".concept-body",
    ):
        assert selector not in APP_CSS
    # Avoid false positives from `.dg-intel-card`
    assert ".intel-card" not in APP_CSS.replace(".dg-intel-card", "")
    assert ".dg-ranked-row" in APP_CSS
    assert ".dg-intel-card" in APP_CSS
    assert ".summary-tile" in APP_CSS

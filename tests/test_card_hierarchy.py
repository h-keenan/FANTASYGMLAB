"""Shared card hierarchy: titles high-emphasis, muted metadata only."""

from modules.app_styles import APP_CSS
from modules.card_hierarchy_styles import CARD_HIERARCHY_CSS
from modules.semantic_glyphs import KIND_CONCEPT, normalize_concept
from modules.workspace_ui import summary_tiles_html


def test_card_hierarchy_css_wins_after_unify():
    from modules.executive_design_unify_styles import EXECUTIVE_DESIGN_UNIFY_CSS

    assert CARD_HIERARCHY_CSS in APP_CSS
    assert APP_CSS.index(EXECUTIVE_DESIGN_UNIFY_CSS) < APP_CSS.index(CARD_HIERARCHY_CSS)


def test_primary_titles_are_high_emphasis_in_late_layer():
    assert ".summary-tile-label" in CARD_HIERARCHY_CSS
    assert ".analysis-card-title" in CARD_HIERARCHY_CSS
    assert "color:var(--color-text-primary)" in CARD_HIERARCHY_CSS.replace(" ", "")
    assert ".summary-tile-unavailable" in CARD_HIERARCHY_CSS


def test_power_and_franchise_use_distinct_glyphs():
    assert normalize_concept("power") == "rankings"
    assert normalize_concept("franchise") == "draft"
    assert KIND_CONCEPT["power"] != KIND_CONCEPT["franchise"]


def test_summary_tiles_keep_unavailable_muted():
    html = summary_tiles_html(
        [{"label": "Power", "value": "Unavailable", "note": "n/a", "tone": "power"}]
    )
    assert "summary-tile-unavailable" in html
    assert "summary-tile-power" in html

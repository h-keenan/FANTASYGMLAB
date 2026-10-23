from pathlib import Path

from modules.design_tokens import DESIGN_TOKEN_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_ten_level_typography_hierarchy_is_tokenized():
    required = (
        "--type-page-eyebrow-size",
        "--type-page-title",
        "--type-body-explanation",
        "--type-section-eyebrow-size",
        "--type-section-title",
        "--type-card-title",
        "--type-primary-metric",
        "--type-supporting-metadata",
        "--type-badge-size",
    )
    for token in required:
        assert token in DESIGN_TOKEN_CSS


def test_hierarchy_document_contains_before_after_table_and_all_surfaces():
    document = (ROOT / "docs" / "founder-beta-ui-hierarchy.md").read_text(
        encoding="utf-8"
    )
    assert "| Level | Role | Token | Before | Founder Beta |" in document
    for surface in (
        "Dashboard",
        "League Rankings",
        "Trade Hub",
        "My Team",
        "Waivers",
        "Player Explorer",
        "Premium",
    ):
        assert surface in document

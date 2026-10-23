"""Contracts for executive design-system unification (presentation only)."""

from pathlib import Path

from modules.design_tokens import DESIGN_TOKEN_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_type_scale_widens_hierarchy_contrast():
    assert "--type-page-title-size: clamp(1.85rem" in DESIGN_TOKEN_CSS
    assert "--type-section-title-size: clamp(1.35rem" in DESIGN_TOKEN_CSS
    assert "--type-card-title-size: 1rem" in DESIGN_TOKEN_CSS
    assert "--type-supporting-metadata-size: 0.6875rem" in DESIGN_TOKEN_CSS
    assert "--space-4xl: 64px" in DESIGN_TOKEN_CSS

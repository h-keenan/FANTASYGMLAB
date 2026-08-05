"""Contracts for executive design-system unification (presentation only)."""

from pathlib import Path

from modules.app_styles import APP_CSS
from modules.design_tokens import DESIGN_TOKEN_CSS
from modules.executive_design_unify_styles import EXECUTIVE_DESIGN_UNIFY_CSS
from modules.executive_workflow_compression_styles import (
    EXECUTIVE_WORKFLOW_COMPRESSION_CSS,
)
from modules import ui_primitives


ROOT = Path(__file__).resolve().parents[1]


def test_unify_css_is_token_backed_and_in_app_css_last():
    assert "body:has(.dg-executive-shell) .app-hero" in EXECUTIVE_DESIGN_UNIFY_CSS
    assert "dg-ui-section-header--primary" in EXECUTIVE_DESIGN_UNIFY_CSS
    assert "dg-founder-badge__mark" in EXECUTIVE_DESIGN_UNIFY_CSS
    assert "#" not in EXECUTIVE_DESIGN_UNIFY_CSS
    assert "rgba(" not in EXECUTIVE_DESIGN_UNIFY_CSS
    assert EXECUTIVE_DESIGN_UNIFY_CSS in APP_CSS
    assert APP_CSS.index(EXECUTIVE_WORKFLOW_COMPRESSION_CSS) < APP_CSS.index(
        EXECUTIVE_DESIGN_UNIFY_CSS
    )


def test_section_header_weight_classes_support_hierarchy():
    primary = ui_primitives.section_header_html("Immediate Action", weight="primary")
    support = ui_primitives.section_header_html("Deep Analysis", weight="support")
    assert "dg-ui-section-header--primary" in primary
    assert "dg-ui-section-header--support" in support


def test_dashboard_workflow_assigns_section_weights():
    source = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
    assert 'render_section_header("Immediate Action", weight="primary")' in source
    assert 'render_section_header("Your Next Move", weight="secondary")' in source
    assert 'render_section_header("Deep Analysis", weight="support")' in source


def test_type_scale_widens_hierarchy_contrast():
    assert "--type-page-title-size: clamp(1.85rem" in DESIGN_TOKEN_CSS
    assert "--type-section-title-size: clamp(1.35rem" in DESIGN_TOKEN_CSS
    assert "--type-card-title-size: 1rem" in DESIGN_TOKEN_CSS
    assert "--type-supporting-metadata-size: 0.6875rem" in DESIGN_TOKEN_CSS
    assert "--space-4xl: 64px" in DESIGN_TOKEN_CSS

"""Contracts for product-wide UI design-system consolidation."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from modules.app_styles import APP_CSS
from modules.component_family_styles import COMPONENT_FAMILY_CSS
from modules.design_tokens import DESIGN_TOKEN_CSS
from modules.executive_command_header_styles import EXECUTIVE_COMMAND_HEADER_CSS
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS


ROOT = Path(__file__).resolve().parents[1]


def _properties(css: str) -> dict[str, str]:
    return {
        name: value.strip()
        for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", css)
    }


def test_semantic_aliases_and_radius_scale_exist():
    tokens = _properties(DESIGN_TOKEN_CSS)
    for name in (
        "--surface-1",
        "--surface-2",
        "--surface-raised",
        "--surface-interactive",
        "--surface-selected",
        "--text-primary",
        "--text-muted",
        "--text-positive",
        "--text-negative",
        "--border-subtle",
        "--border-standard",
        "--border-strong",
        "--border-accent",
        "--radius-square",
        "--radius-control",
        "--radius-panel",
        "--radius-pill",
        "--radius-segment",
    ):
        assert name in tokens
    assert tokens["--radius-control"] == "0"
    assert tokens["--radius-panel"] == "0"
    assert tokens["--radius-pill"] == "2px"
    assert tokens["--radius-segment"] == "999px"
    assert tokens["--surface-1"] == "var(--color-surface-primary)"


def test_component_family_owns_equivalent_roles_early_in_app_css():
    assert COMPONENT_FAMILY_CSS in APP_CSS
    assert APP_CSS.index(DESIGN_TOKEN_CSS) < APP_CSS.index(COMPONENT_FAMILY_CSS)
    compact = COMPONENT_FAMILY_CSS.replace(" ", "")
    for needle in (
        "dg_cta_primary_",
        "dg_cta_secondary_",
        "dg_cta_tertiary_",
        "dg_cta_destructive_",
        'div[data-testid="stExpander"]',
        "dashboard_deep_analysis_nav",
        ".legal-footer-link",
        ".trade-summary-card",
        "--radius-segment",
    ):
        assert needle.replace(" ", "") in compact or needle in COMPONENT_FAMILY_CSS


def test_legacy_dg_radius_aliases_to_canonical_tokens():
    assert "--dg-radius-card: var(--radius-panel)" in APP_CSS
    assert "--dg-radius-control: var(--radius-control)" in APP_CSS
    assert "--dg-radius-chip: var(--radius-pill)" in APP_CSS
    assert "--dg-shell-black: var(--color-bg)" in APP_CSS


def test_literal_card_radii_are_not_reintroduced_at_scale():
    radii = re.findall(r"border-radius\s*:\s*([^;!}]+)", APP_CSS)
    literals = Counter()
    for decl in radii:
        for part in re.split(r"\s+", decl.strip()):
            if re.fullmatch(r"\d+px", part) and part not in {"2px"}:
                literals[part] += 1
    # Allow rare intentional leftovers; forbid the old 12–18px card language.
    for banned in ("12px", "14px", "16px", "18px", "999px"):
        assert literals.get(banned, 0) == 0, literals


def test_header_command_cells_share_centered_geometry_contract():
    css = EXECUTIVE_COMMAND_HEADER_CSS
    assert "justify-content: center !important" in css
    assert "minmax(0, auto) 0.75rem" in css
    assert "translateY" not in css


def test_gm_orb_244_247_guards_remain_scoped():
    overlay = MOBILE_INTERACTION_OVERLAY_CSS
    assert "--dg-gm-orb-size" in overlay
    # Direct-child scoped :has must remain (unscoped ancestor :has is the #244 bug).
    assert ":has(>" in overlay.replace(" ", "") or ":has(>" in overlay
    assert "width: var(--dg-gm-orb-size)" in overlay or "width:var(--dg-gm-orb-size)" in overlay.replace(" ", "")


def test_harness_exposes_design_system_surface():
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    assert '"design-system"' in harness
    assert "def _design_system" in harness
    assert "validate_design_system_ui.py" in (
        ROOT / "scripts" / "validate_design_system_ui.py"
    ).name
    assert (ROOT / "scripts" / "validate_design_system_ui.py").exists()


def test_app_css_budget_still_holds():
    assert len(APP_CSS) < 418_220

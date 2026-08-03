from pathlib import Path

from modules.app_styles import APP_CSS
from modules.design_tokens import DESIGN_TOKEN_CSS
from modules.founder_beta_quick_fix_styles import FOUNDER_BETA_QUICK_FIX_CSS


def test_quick_fix_is_the_last_shared_style_layer():
    assert APP_CSS.index(FOUNDER_BETA_QUICK_FIX_CSS) > APP_CSS.index("Founder beta responsive shell")
    assert APP_CSS.index(FOUNDER_BETA_QUICK_FIX_CSS) > APP_CSS.index("One-dialog Trade Hub detail")


def test_founder_navigation_is_hard_edged_opaque_and_scroll_bounded():
    for contract in (
        "background: var(--color-shell) !important",
        "border-radius: var(--radius-none) !important",
        "overflow-y: auto !important",
        "overscroll-behavior: contain !important",
        "max-height: min(72dvh, 640px) !important",
        "min-height: var(--touch-target-min) !important",
        'button[kind="primary"]',
        'content: "CURRENT" !important',
    ):
        assert contract in FOUNDER_BETA_QUICK_FIX_CSS
    assert "linear-gradient" not in FOUNDER_BETA_QUICK_FIX_CSS
    assert "border-radius: 14px" not in FOUNDER_BETA_QUICK_FIX_CSS


def test_canonical_modal_and_rendered_surfaces_use_semantic_radius_tokens():
    assert 'div[data-testid="stDialog"] div[role="dialog"]' in FOUNDER_BETA_QUICK_FIX_CSS
    assert "border-radius: var(--radius-none) !important" in FOUNDER_BETA_QUICK_FIX_CSS
    assert "max-height: min(90dvh, 920px) !important" in FOUNDER_BETA_QUICK_FIX_CSS
    assert "--radius-panel: 0" in DESIGN_TOKEN_CSS
    assert "--radius-pill: 2px" in DESIGN_TOKEN_CSS


def test_quick_fix_does_not_enter_application_or_business_logic():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "founder_beta_quick_fix_styles" not in source
    assert "FOUNDER_BETA_QUICK_FIX_CSS" not in source

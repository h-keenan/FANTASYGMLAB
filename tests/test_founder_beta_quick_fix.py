from pathlib import Path

from modules.app_styles import APP_CSS
from modules.design_tokens import DESIGN_TOKEN_CSS
from modules.founder_beta_quick_fix_styles import FOUNDER_BETA_QUICK_FIX_CSS
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS
from modules.trade_detail_styles import TRADE_DETAIL_CSS


def test_quick_fix_loads_after_shell_and_before_overlay():
    assert APP_CSS.index(FOUNDER_BETA_QUICK_FIX_CSS) > APP_CSS.index("Founder beta responsive shell")
    assert TRADE_DETAIL_CSS not in APP_CSS
    assert "One-dialog Trade Hub detail" in TRADE_DETAIL_CSS
    assert APP_CSS.index(FOUNDER_BETA_QUICK_FIX_CSS) < APP_CSS.index(
        MOBILE_INTERACTION_OVERLAY_CSS
    )


def test_founder_dialog_contracts_remain_in_quick_fix():
    assert 'div[role="dialog"]' in FOUNDER_BETA_QUICK_FIX_CSS
    assert "border-radius: var(--radius-none) !important" in FOUNDER_BETA_QUICK_FIX_CSS
    assert "max-height: min(90dvh, 920px) !important" in FOUNDER_BETA_QUICK_FIX_CSS
    assert "--radius-panel: 0" in DESIGN_TOKEN_CSS
    assert "--radius-pill: 2px" in DESIGN_TOKEN_CSS
    assert "linear-gradient" not in FOUNDER_BETA_QUICK_FIX_CSS
    assert "border-radius: 14px" not in FOUNDER_BETA_QUICK_FIX_CSS


def test_gm_sheet_navigation_contracts_moved_to_overlay():
    for contract in (
        "background: var(--color-shell) !important",
        "border-radius: var(--radius-none) !important",
        "overflow-y: auto !important",
        "overscroll-behavior: contain !important",
        "max-height: min(72dvh, 640px) !important",
        "min-height: calc(var(--touch-target-min) + 1px) !important",
        'button[kind="primary"]',
        'content: "CURRENT" !important',
    ):
        assert contract in MOBILE_INTERACTION_OVERLAY_CSS
    assert "mobile-gm-sheet-marker" not in FOUNDER_BETA_QUICK_FIX_CSS


def test_quick_fix_does_not_enter_application_or_business_logic():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "founder_beta_quick_fix_styles" not in source
    assert "FOUNDER_BETA_QUICK_FIX_CSS" not in source

"""Permanent regression: GM-orb :has() must not collapse the Streamlit root (#244/#246)."""

from __future__ import annotations

from pathlib import Path

from modules.app_styles import APP_CSS
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS


ROOT = Path(__file__).resolve().parents[1]
UNSCOPED = 'stVerticalBlock"]:has(.mobile-gm-floating-trigger-marker)'
SCOPED = (
    'stVerticalBlock"]:has(> div[data-testid="stElementContainer"] '
    ".mobile-gm-floating-trigger-marker)"
)


def test_overlay_css_uses_direct_child_has_scope_only():
    assert SCOPED in MOBILE_INTERACTION_OVERLAY_CSS
    assert UNSCOPED not in MOBILE_INTERACTION_OVERLAY_CSS
    # body:has(.mobile-gm-sheet-marker) scrim is allowed; stVerticalBlock must stay scoped.
    assert (
        'stVerticalBlock"]:has(.mobile-gm-sheet-marker)'
        not in MOBILE_INTERACTION_OVERLAY_CSS
    )
    assert (
        ':has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker)'
        in MOBILE_INTERACTION_OVERLAY_CSS
    )
    assert "body:has(.mobile-gm-sheet-marker)::before" in MOBILE_INTERACTION_OVERLAY_CSS


def test_full_app_css_keeps_scoped_orb_rule_and_no_unscoped_collapse():
    """Regression against concatenated production APP_CSS, not an isolated fragment."""

    assert "MOBILE_INTERACTION_OVERLAY_CSS" in (
        ROOT / "modules" / "app_styles.py"
    ).read_text(encoding="utf-8")
    assert SCOPED in APP_CSS
    assert UNSCOPED not in APP_CSS
    # Orb geometry may fix the marker-owning block, never the generic root class alone.
    assert "position: fixed !important" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "width: var(--dg-gm-orb-size) !important" in MOBILE_INTERACTION_OVERLAY_CSS


def test_overlay_still_hides_orb_button_label_children():
    assert "button > *" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "opacity: 0 !important" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "border-radius: 50% !important" in MOBILE_INTERACTION_OVERLAY_CSS


def test_app_css_concatenates_overlay_last():
    source = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    assert source.rindex("MOBILE_INTERACTION_OVERLAY_CSS") > source.index(
        "EXECUTIVE_DESIGN_UNIFY_CSS"
    )


def test_temporary_p0_diagnostic_modules_removed():
    for rel in (
        "modules/p0_render_canary.py",
        "modules/p0_dashboard_bisect.py",
        "modules/p0_native_render_bypass.py",
    ):
        assert not (ROOT / rel).exists()
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    for token in (
        "FGL_P0_",
        "FGL_P0_TEST_BUTTON",
        "p0_render_canary",
        "p0_dashboard_bisect",
        "p0_native_render",
        "DASHBOARD_CANARY_",
    ):
        assert token not in app

"""Regression contracts for GM-orb CSS collapse (#244)."""

from __future__ import annotations

from pathlib import Path

from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS
from modules.p0_native_render_bypass import NATIVE_RENDER_ENV, native_render_enabled


ROOT = Path(__file__).resolve().parents[1]
UNSCOPED = 'stVerticalBlock"]:has(.mobile-gm-floating-trigger-marker)'
SCOPED = (
    'stVerticalBlock"]:has(> div[data-testid="stElementContainer"] '
    ".mobile-gm-floating-trigger-marker)"
)


def test_overlay_css_uses_direct_child_has_scope_only():
    assert SCOPED in MOBILE_INTERACTION_OVERLAY_CSS
    assert UNSCOPED not in MOBILE_INTERACTION_OVERLAY_CSS
    assert ":has(.mobile-gm-sheet-marker)" not in MOBILE_INTERACTION_OVERLAY_CSS
    assert (
        ':has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker)'
        in MOBILE_INTERACTION_OVERLAY_CSS
    )


def test_overlay_still_hides_orb_button_label_children():
    assert "button > *" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "opacity: 0 !important" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "border-radius: 50% !important" in MOBILE_INTERACTION_OVERLAY_CSS


def test_app_css_concatenates_overlay_last():
    source = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    assert source.rindex("MOBILE_INTERACTION_OVERLAY_CSS") > source.index(
        "EXECUTIVE_DESIGN_UNIFY_CSS"
    )


def test_native_render_bypass_gated_by_env(monkeypatch):
    monkeypatch.delenv(NATIVE_RENDER_ENV, raising=False)
    assert native_render_enabled() is False
    monkeypatch.setenv(NATIVE_RENDER_ENV, "1")
    assert native_render_enabled() is True


def test_app_main_calls_native_bypass_before_page_config():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    bypass_at = app.index("maybe_run_native_only_bypass")
    config_at = app.index('st.set_page_config(\n        page_title="FantasyGM Lab"')
    assert bypass_at < config_at


def test_dashboard_harness_includes_gm_orb_marker():
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    dash_at = harness.index("def _dashboard()")
    league_at = harness.index("def _league()")
    dash = harness[dash_at:league_at]
    assert "mobile_gm_sheet_trigger_dashboard" in dash
    assert "gm_orb_floating_trigger_html" in dash

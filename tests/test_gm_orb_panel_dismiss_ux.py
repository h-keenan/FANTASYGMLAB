"""GM Orb destination panel dismiss UX regressions."""

from __future__ import annotations

from pathlib import Path

from modules.app_styles import APP_CSS
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
DISMISS = (ROOT / "modules" / "gm_sheet_dismiss.py").read_text(encoding="utf-8")
HARNESS = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")

SCOPED = (
    'stVerticalBlock"]:has(> div[data-testid="stElementContainer"] '
    ".mobile-gm-floating-trigger-marker)"
)
UNSCOPED = 'stVerticalBlock"]:has(.mobile-gm-floating-trigger-marker)'


def _sheet_section() -> str:
    return APP.split("def _open_mobile_destination_sheet", 1)[1].split(
        "def safe_pick_value", 1
    )[0]


def test_authoritative_open_flag_is_session_state_only():
    section = _sheet_section()
    assert 'st.session_state["_mobile_destination_sheet_open"] = True' in section
    assert 'st.session_state["_mobile_destination_sheet_open"] = False' in section
    assert "def _toggle_mobile_destination_sheet" in section
    assert "on_click=_toggle_mobile_destination_sheet" in section
    assert section.count("_mobile_destination_sheet_open") >= 4


def test_close_control_is_not_close_destinations_label():
    section = _sheet_section()
    assert "Close destinations" not in section
    assert "Close destinations" not in HARNESS
    assert '"Close"' in section
    assert "Close navigation" in section
    assert 'key="mobile_sheet_close"' in section
    assert "st-key-mobile_sheet_close" in MOBILE_INTERACTION_OVERLAY_CSS
    assert 'content: "×"' in MOBILE_INTERACTION_OVERLAY_CSS


def test_dismiss_uses_js_bridge_not_fullscreen_click_overlay():
    assert 'setTriggerValue("dismiss"' in DISMISS
    assert "pointerdown" in DISMISS
    assert "Escape" in DISMISS
    assert "consume_gm_sheet_dismiss" in APP
    assert "pointer-events: auto" not in DISMISS
    # No click-catching cover element (docstring may mention fullscreen as forbidden).
    assert "position:fixed;inset:0" not in DISMISS.replace(" ", "").casefold()
    assert 'id="gm-sheet-dismiss-backdrop"' not in DISMISS
    assert "createElement('div')" not in DISMISS


def test_orb_and_sheet_244_247_geometry_preserved():
    assert SCOPED in MOBILE_INTERACTION_OVERLAY_CSS
    assert SCOPED in APP_CSS
    assert UNSCOPED not in MOBILE_INTERACTION_OVERLAY_CSS
    assert UNSCOPED not in APP_CSS
    compact = MOBILE_INTERACTION_OVERLAY_CSS.replace(" ", "")
    assert "gap:0!important" in compact
    assert "width:var(--dg-gm-orb-size)!important" in compact
    assert "height:var(--dg-gm-orb-size)!important" in compact
    assert "bottom:max(var(--space-md),env(safe-area-inset-bottom,0px))!important" in compact
    assert "left:max(var(--space-md),env(safe-area-inset-left,0px))!important" in compact


def test_destination_selection_still_closes_via_callback():
    section = _sheet_section()
    assert "on_click=_navigate_from_mobile_destination" in section
    nav = section.split("def _navigate_from_mobile_destination", 1)[1].split(
        "def render_mobile_destination_sheet", 1
    )[0]
    assert '["_mobile_destination_sheet_open"] = False' in nav
    assert "st.rerun()" not in section


def test_harness_navigation_mirrors_toggle_and_close():
    assert "not bool(st.session_state.get(\"_fixture_gm_open\"))" in HARNESS
    assert "consume_gm_sheet_dismiss" in HARNESS
    assert "Close destinations" not in HARNESS

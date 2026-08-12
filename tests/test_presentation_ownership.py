"""Presentation ownership contracts — forbid retired helpers and dual orb owners."""

from pathlib import Path

from modules.app_styles import APP_CSS
from modules.desktop_executive_layout_styles import DESKTOP_EXECUTIVE_LAYOUT_CSS
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS
from modules.visual_hierarchy_styles import VISUAL_HIERARCHY_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_app_css_loads_overlay_after_desktop_executive():
    assert DESKTOP_EXECUTIVE_LAYOUT_CSS in APP_CSS
    assert MOBILE_INTERACTION_OVERLAY_CSS in APP_CSS
    assert APP_CSS.index(DESKTOP_EXECUTIVE_LAYOUT_CSS) < APP_CSS.index(
        MOBILE_INTERACTION_OVERLAY_CSS
    )


def test_gm_orb_geometry_has_one_late_canonical_owner():
    assert "st-key-mobile_gm_sheet_trigger_" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "st-key-mobile_gm_sheet_trigger_" not in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert (
        'mobile-gm-floating-trigger-marker) [data-testid="stButton"] button'
        not in DESKTOP_EXECUTIVE_LAYOUT_CSS
    )


def test_desktop_width_owner_not_duplicated_in_visual_hierarchy():
    assert ".block-container" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "padding-inline: var(--space-2xl) !important" not in VISUAL_HIERARCHY_CSS


def test_dead_render_helpers_are_gone():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    workspace = (ROOT / "modules" / "workspace_ui.py").read_text(encoding="utf-8")
    premium = (ROOT / "modules" / "premium.py").read_text(encoding="utf-8")
    waivers = (ROOT / "modules" / "waivers_ui.py").read_text(encoding="utf-8")
    visibility = (ROOT / "modules" / "dashboard_visibility.py").read_text(
        encoding="utf-8"
    )

    for needle in (
        "def render_team_identity_card",
        "def render_home_command_hero",
        "def render_home_status_strip",
        "def _normalize_trade_html",
        "def _render_trade_html",
        "_render_player_scan_tap_grid",
    ):
        assert needle not in app_source
        if needle.startswith("def render_"):
            assert needle not in workspace

    assert "def render_premium_badge" not in premium
    assert "def render_waivers_page_header" not in waivers
    assert "SAFE_VISIBILITY_CSS" not in visibility


def test_trade_html_owned_by_trade_hub_module():
    from modules import trade_hub_ui

    assert callable(trade_hub_ui.normalize_trade_html)
    assert callable(trade_hub_ui.render_trade_html)

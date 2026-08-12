"""Single-owner contracts for executive header geometry (forensics pass)."""

from __future__ import annotations

import re
from pathlib import Path

from modules.application_shell_styles import APPLICATION_SHELL_CSS
from modules.executive_command_header_styles import EXECUTIVE_COMMAND_HEADER_CSS
from modules.executive_design_unify_styles import EXECUTIVE_DESIGN_UNIFY_CSS
from modules.founder_beta_quick_fix_styles import FOUNDER_BETA_QUICK_FIX_CSS
from modules.interface_reimagining_styles import INTERFACE_REIMAGINING_CSS
from modules.mobile_visual_polish_styles import MOBILE_VISUAL_POLISH_CSS
from modules.ux_polish_styles import FOUNDER_BETA_UX_CSS
from modules.visual_hierarchy_styles import VISUAL_HIERARCHY_CSS
from modules.visual_identity_styles import COMMAND_CENTER_CSS


ROOT = Path(__file__).resolve().parents[1]

# Modules that must NOT own command-cell geometry.
_NON_OWNERS = {
    "visual_hierarchy": VISUAL_HIERARCHY_CSS,
    "command_center": COMMAND_CENTER_CSS,
    "interface_reimagining": INTERFACE_REIMAGINING_CSS,
    "founder_beta_quick_fix": FOUNDER_BETA_QUICK_FIX_CSS,
    "mobile_visual_polish": MOBILE_VISUAL_POLISH_CSS,
    "founder_beta_ux": FOUNDER_BETA_UX_CSS,
    "executive_design_unify": EXECUTIVE_DESIGN_UNIFY_CSS,
    "application_shell": APPLICATION_SHELL_CSS,
}


def _command_scoped(css: str) -> str:
    """Return CSS slices that target the executive command rail."""
    chunks: list[str] = []
    for match in re.finditer(
        r"div\[class\*=\"st-key-executive_command_actions\"][^{]*\{[^}]*\}",
        css,
        flags=re.DOTALL,
    ):
        chunks.append(match.group(0))
    return "\n".join(chunks)


def test_sole_owner_command_height_padding_align_lineheight():
    owner = EXECUTIVE_COMMAND_HEADER_CSS
    trigger = owner.split("/* Notification Center")[0]
    assert "min-height: var(--touch-target-min) !important" in trigger
    assert "padding-block: 0 !important" in trigger
    assert "align-items: center !important" in trigger
    assert "line-height: 1 !important" in trigger
    assert "transform: none !important" in trigger
    assert "translateY(" not in trigger
    assert "margin-top:" not in trigger
    assert "margin-bottom:" not in trigger

    for name, css in _NON_OWNERS.items():
        scoped = _command_scoped(css)
        # Non-owners must not set the four geometry families on command rail.
        for prop in (
            "min-height:",
            "padding-block:",
            "align-items:",
            "line-height:",
        ):
            assert prop not in scoped, f"{name} re-owns command {prop}"
    # Global popover geometry selectors removed from competing modules.
    assert '[data-testid="stPopover"] > button' not in COMMAND_CENTER_CSS
    assert '[data-testid="stPopover"] > button' not in INTERFACE_REIMAGINING_CSS
    quick_fix_controls = FOUNDER_BETA_QUICK_FIX_CSS.split("/* stPopover triggers")[0]
    assert '[data-testid="stPopover"] > button' not in quick_fix_controls
    # UX polish must not set popover min-height (command rail owns that).
    assert not re.search(
        r'\[data-testid="stPopover"\]\s*>\s*button[^{]{0,120}'
        r"min-height:\s*var\(--dg-ux-control-height\)",
        FOUNDER_BETA_UX_CSS,
        flags=re.DOTALL,
    )


def test_sole_owner_shell_geometry():
    assert "st-key-executive_workspace_shell" in APPLICATION_SHELL_CSS
    assert "grid-template-columns: minmax(0, 1fr) minmax(min(100%, 28rem), 1fr)" in (
        APPLICATION_SHELL_CSS
    )
    assert "st-key-executive_workspace_shell" not in VISUAL_HIERARCHY_CSS
    desktop = EXECUTIVE_COMMAND_HEADER_CSS.split("@media (min-width: 761px)")[1].split(
        "@media (max-width: 760px)"
    )[0]
    assert "st-key-executive_workspace_shell" not in desktop
    polish = MOBILE_VISUAL_POLISH_CSS
    assert ".dg-executive-shell{" not in polish.replace(" ", "")
    assert "padding-block:var(--space-2xs)!important" not in polish.replace(" ", "")


def test_harness_injection_order_matches_production_pattern():
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    # Production script-start order.
    assert app.index("inject_global_styles(APP_CSS)") < app.index(
        "inject_global_styles(MOBILE_VISUAL_POLISH_CSS)"
    )
    assert app.index("inject_global_styles(MOBILE_VISUAL_POLISH_CSS)") < app.index(
        "inject_global_styles(FOUNDER_BETA_UX_CSS)"
    )
    # Command header is late-injected from the header renderer (after APP_CSS at runtime).
    assert "inject_global_styles(EXECUTIVE_COMMAND_HEADER_CSS)" in app
    # Harness mirrors script-start then command header last among shell owners.
    h_app = harness.index("inject_global_styles(APP_CSS)")
    h_polish = harness.index("inject_global_styles(MOBILE_VISUAL_POLISH_CSS)")
    h_ux = harness.index("inject_global_styles(FOUNDER_BETA_UX_CSS)")
    h_dash = harness.index("inject_global_styles(DASHBOARD_WORKFLOW_CSS)")
    h_cmd = harness.index("inject_global_styles(EXECUTIVE_COMMAND_HEADER_CSS)")
    assert h_app < h_polish < h_ux < h_dash < h_cmd
    # Do not re-inject overlay after the command owner (it lives inside APP_CSS).
    assert "inject_global_styles(MOBILE_INTERACTION_OVERLAY_CSS)" not in harness


def test_popover_label_matches_production_league_not_switch_league():
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    assert 'st.popover(\n                        "League"' in harness or 'st.popover(\n                        "League",' in harness or (
        '"League"' in harness and "top_league_actions_fixture" in harness
    )
    assert 'st.popover("Switch League"' not in harness
    assert 'help="Account, Premium, and Feedback"' not in harness
    assert 'help="Switch league"' not in harness
    assert 'help="Select a league"' not in harness
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    league_popover = app[
        app.index("executive_command_cell_league_") : app.index("league-actions-sheet-marker")
    ]
    assert 'width="content"' not in league_popover
    assert "width='content'" not in league_popover
    assert "help=" not in league_popover
    profile_popover = app[
        app.index("def render_executive_profile_control") : app.index(
            "def render_platform_topbar"
        )
    ]
    assert 'st.popover("You")' in profile_popover
    assert "help=" not in profile_popover
    # Owner still defends against residual tooltip wrappers without forcing
    # min-width:100% (that made duplicate triggers fill adjacent columns).
    assert "stTooltipHoverTarget" in EXECUTIVE_COMMAND_HEADER_CSS
    assert "min-width: 100% !important" not in EXECUTIVE_COMMAND_HEADER_CSS
    assert (
        'button[data-testid="stPopoverButton"] ~ button[data-testid="stPopoverButton"]'
        in EXECUTIVE_COMMAND_HEADER_CSS
    )
    assert "flex-direction: column !important" in EXECUTIVE_COMMAND_HEADER_CSS

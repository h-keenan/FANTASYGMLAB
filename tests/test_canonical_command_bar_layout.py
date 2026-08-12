"""Geometry contracts for the canonical executive command-bar layout."""

from __future__ import annotations

from pathlib import Path

from modules.application_shell_styles import APPLICATION_SHELL_CSS
from modules.brand_identity_styles import BRAND_IDENTITY_CSS
from modules.executive_command_header_styles import EXECUTIVE_COMMAND_HEADER_CSS
from modules.executive_design_unify_styles import EXECUTIVE_DESIGN_UNIFY_CSS
from modules.visual_hierarchy_styles import VISUAL_HIERARCHY_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_one_canonical_command_cell_primitive_is_shared():
    css = EXECUTIVE_COMMAND_HEADER_CSS
    assert "st-key-executive_command_cell_" in css
    assert "dg-command-cell" in css
    assert "height: 100% !important" in css
    assert "min-height: var(--touch-target-min) !important" in css
    assert "line-height: 1 !important" in css
    assert "padding-block: 0 !important" in css
    assert "transform: none !important" in css
    # Shared trigger rule — not League-only forks
    assert "st-key-top_league_actions" not in css
    assert '[data-testid="stPopover"] button' in css


def test_command_rail_uses_flexible_width_not_fixed_narrow_strip():
    css = EXECUTIVE_COMMAND_HEADER_CSS
    assert "width: 22.5rem;" not in css
    assert "min-width: 16.5rem" not in css
    assert "flex: 1 1 0 !important;" in css
    # Chevron protection is label-ellipsis + non-shrinking icon, not per-control hacks.
    desktop = css.split("@media (min-width: 761px)")[1].split("@media (max-width: 760px)")[0]
    assert "translateY(" not in desktop
    assert "width: 100%;" in desktop
    assert "max-width: none;" in desktop
    # Shell column template is owned by APPLICATION_SHELL_CSS only.
    assert "minmax(min(100%, 28rem), 1fr)" in APPLICATION_SHELL_CSS
    assert "minmax(min(100%, 28rem), 1fr)" not in css
    assert "grid-template-columns: minmax(0, auto) 0.75rem !important;" in css
    assert "grid-column: 2 !important;" in css
    assert "max-width: 0.75rem !important;" in css
    assert "justify-content: center !important;" in css
    assert "flex-direction: row !important;" not in css.split("/* Notification Center")[0]


def test_command_cells_forbid_layout_debt_hacks():
    css = EXECUTIVE_COMMAND_HEADER_CSS
    trigger_block = css.split("/* Notification Center")[0]
    for forbidden in ("translateY(", "margin-top:", "margin-bottom:", "position: relative"):
        assert forbidden not in trigger_block
    # Explicitly reset floating feedback; do not introduce offsets.
    assert "transform: none !important" in trigger_block


def test_competing_shell_contracts_removed():
    # Visual hierarchy must not own shell geometry anymore.
    assert "st-key-executive_workspace_shell" not in VISUAL_HIERARCHY_CSS
    assert ".dg-executive-shell {" not in VISUAL_HIERARCHY_CSS
    assert "st-key-top_league_actions" not in VISUAL_HIERARCHY_CSS
    assert "st-key-top_league_actions" not in APPLICATION_SHELL_CSS
    assert "0.7rem 0.9rem" not in BRAND_IDENTITY_CSS
    assert ".dg-executive-shell {\n        gap: 0.85rem" not in BRAND_IDENTITY_CSS
    app_styles = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    assert (
        'div[class*="st-key-top_league_actions"] [data-testid="stPopover"] > button'
        not in app_styles
    )
    assert "min-height:var(--touch-target-min)!important;padding-block:0!important}" not in (
        EXECUTIVE_DESIGN_UNIFY_CSS
    )
    assert "min-height:0!important" in EXECUTIVE_DESIGN_UNIFY_CSS
    # Command header must not re-own shell grid columns.
    desktop = EXECUTIVE_COMMAND_HEADER_CSS.split("@media (min-width: 761px)")[1].split(
        "@media (max-width: 760px)"
    )[0]
    assert "st-key-executive_workspace_shell" not in desktop


def test_production_wires_equal_command_cell_wrappers():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    league = app[
        app.index("def render_top_league_identity_header(") : app.index(
            "def _league_display_name("
        )
    ]
    profile = app[
        app.index("def render_executive_profile_control(") : app.index(
            "def render_platform_topbar("
        )
    ]
    notifications = (ROOT / "modules" / "notification_center.py").read_text(
        encoding="utf-8"
    )
    assert "executive_command_cell_league_" in league
    assert "executive_command_cell_profile_" in profile
    assert "executive_command_cell_alerts_" in notifications


def test_shell_identity_keeps_flat_vertical_padding():
    assert "padding-block: 0" in APPLICATION_SHELL_CSS
    assert ".dg-executive-shell" in APPLICATION_SHELL_CSS
    # Sole geometry owner — hierarchy/polish must not reintroduce shell padding.
    assert "padding-block:" not in VISUAL_HIERARCHY_CSS or ".dg-executive-shell" not in VISUAL_HIERARCHY_CSS
    polish = (ROOT / "modules" / "mobile_visual_polish_styles.py").read_text(encoding="utf-8")
    assert "padding-block:var(--space-2xs)!important" not in polish.replace(" ", "")


def test_contract_doc_exists():
    text = (
        ROOT / "docs" / "canonical-command-bar-layout-contract.md"
    ).read_text(encoding="utf-8")
    for heading in (
        "Previous competing contracts",
        "Root cause",
        "Final primitive",
        "CSS removed",
        "Responsive rules",
        "Remaining limitations",
    ):
        assert heading in text
    assert "0c5ba3387e87004deaa6a859d9f7a97e69ef47e4" in text

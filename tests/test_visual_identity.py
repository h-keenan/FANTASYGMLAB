from pathlib import Path

from modules.app_styles import APP_CSS
from modules.design_tokens import DESIGN_TOKEN_CSS
from modules.player_cards import (
    PLAYER_PRESTIGE_LEVELS,
    player_prestige_level,
    player_status_pill_html,
)
from modules.ui_primitives import status_badge_html
from modules.visual_identity_styles import COMMAND_CENTER_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_command_center_css_is_final_shared_layer():
    assert APP_CSS.index(COMMAND_CENTER_CSS) > APP_CSS.index("trade-idea-card")
    assert APP_CSS.index(COMMAND_CENTER_CSS) > APP_CSS.index("dg-executive-shell")


def test_geometry_tokens_are_rectilinear():
    for token in (
        "--radius-sm: 0",
        "--radius-md: 0",
        "--radius-lg: 0",
        "--radius-panel: 0",
    ):
        assert token in DESIGN_TOKEN_CSS
    assert "--radius-pill: 2px" in DESIGN_TOKEN_CSS


def test_monochrome_foundation_and_semantic_prestige_tokens_exist():
    for token in (
        "--color-bg: #050607",
        "--color-surface-primary: #0f1114",
        "--color-surface-secondary: #15171b",
        "--color-prestige-elite",
        "--color-prestige-starter",
        "--color-prestige-contributor",
        "--color-prestige-development",
        "--color-prestige-depth",
        "--color-prestige-replacement",
        "--color-position-qb",
        "--color-position-wr",
    ):
        assert token in DESIGN_TOKEN_CSS


def test_prestige_mapping_is_complete_and_stable():
    assert PLAYER_PRESTIGE_LEVELS == (
        "elite", "starter", "contributor", "development", "depth", "replacement"
    )
    expected = {
        "Elite": "elite",
        "Core Starter": "starter",
        "Contributor": "contributor",
        "Developmental": "development",
        "Young Stash": "development",
        "Depth": "depth",
        "Drop Candidate": "replacement",
    }
    assert {label: player_prestige_level(label) for label in expected} == expected


def test_player_pill_exposes_text_and_machine_readable_prestige():
    html = player_status_pill_html("Elite")
    assert "player-prestige-elite" in html
    assert "data-prestige='elite'" in html
    assert ">Elite<" in html


def test_canonical_badge_and_status_pill_share_visible_text_contract():
    badge = status_badge_html("Starter", variant="information")
    pill = player_status_pill_html("Starter")
    assert "dg-ui-badge--information" in badge
    assert "Information status: Starter" in badge
    assert "player-prestige-starter" in pill
    assert ">Starter<" in pill


def test_shared_player_card_contract_covers_current_renderers():
    for selector in (
        ".scan-card,",
        ".compact-player-row,",
    ):
        assert selector in COMMAND_CENTER_CSS
    assert ".player-asset-card" not in COMMAND_CENTER_CSS
    assert "border-left: var(--border-width-semantic)" in COMMAND_CENTER_CSS


def test_controls_preserve_focus_and_mobile_touch_targets():
    assert ":focus-visible" in APP_CSS
    assert "box-shadow: var(--focus-ring)" in APP_CSS
    assert "min-height: var(--touch-target-min) !important" in COMMAND_CENTER_CSS


def test_tables_and_dialogs_use_command_center_contract():
    assert 'div[data-testid="stDialog"] div[role="dialog"]' in COMMAND_CENTER_CSS
    assert "border-radius: var(--radius-none) !important" in COMMAND_CENTER_CSS
    assert "font-variant-numeric: tabular-nums" in COMMAND_CENTER_CSS
    assert "table tbody tr:nth-child(even)" in COMMAND_CENTER_CSS


def test_reduced_motion_contract_is_global():
    assert "@media (prefers-reduced-motion: reduce)" in COMMAND_CENTER_CSS
    assert "animation-duration: 0.01ms !important" in COMMAND_CENTER_CSS


def test_app_py_and_business_modules_are_unchanged_by_visual_layer():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "visual_identity_styles" not in source
    assert "COMMAND_CENTER_CSS" not in source

"""Top-5 presentation ownership contracts after #269 follow-up."""

from pathlib import Path

from modules.app_styles import APP_CSS
from modules.desktop_executive_layout_styles import DESKTOP_EXECUTIVE_LAYOUT_CSS
from modules.executive_design_unify_styles import EXECUTIVE_DESIGN_UNIFY_CSS
from modules.founder_beta_consistency_styles import FOUNDER_BETA_CONSISTENCY_CSS
from modules.founder_beta_quick_fix_styles import FOUNDER_BETA_QUICK_FIX_CSS
from modules.interface_reimagining_styles import INTERFACE_REIMAGINING_CSS
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS
from modules.visual_identity_styles import COMMAND_CENTER_CSS
from modules import league_workspace_ui
import app


ROOT = Path(__file__).resolve().parents[1]


def test_gm_sheet_chrome_owned_only_by_overlay():
    assert 'content: "CURRENT" !important' in MOBILE_INTERACTION_OVERLAY_CSS
    assert "--dg-founder-nav-width" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "mobile-gm-destination-panel" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "mobile-gm-sheet-marker" not in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "mobile-gm-sheet-marker" not in FOUNDER_BETA_QUICK_FIX_CSS
    assert "st-key-mobile_gm_sheet_trigger_" not in FOUNDER_BETA_QUICK_FIX_CSS
    assert APP_CSS.index(DESKTOP_EXECUTIVE_LAYOUT_CSS) < APP_CSS.index(
        MOBILE_INTERACTION_OVERLAY_CSS
    )


def test_global_button_geometry_has_one_command_center_owner():
    assert ".stButton > button" in COMMAND_CENTER_CSS
    assert ".stButton > button" not in INTERFACE_REIMAGINING_CSS
    assert '[data-testid="stButton"] > button' not in FOUNDER_BETA_QUICK_FIX_CSS
    # Component family may own keyed CTAs only — not unscoped globals.
    family = (ROOT / "modules" / "component_family_styles.py").read_text(
        encoding="utf-8"
    )
    assert 'st-key-dg_cta_' in family
    assert ".stButton > button" not in family


def test_midfile_does_not_redeclare_card_accent_strips():
    mid = Path("modules/app_styles.py").read_text(encoding="utf-8")
    unify = EXECUTIVE_DESIGN_UNIFY_CSS.replace(" ", "")
    assert "trade-idea-card::after," in unify
    assert "team-identity-card::after," in unify
    assert "content:none!important" in unify
    assert "home-command-card::after" not in mid
    assert "summary-tile::after" not in mid


def test_block_container_padding_owned_only_by_desktop_executive():
    assert ".block-container" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    assert "padding-block-end: var(--space-3xl)" in DESKTOP_EXECUTIVE_LAYOUT_CSS
    for css, name in (
        (INTERFACE_REIMAGINING_CSS, "interface"),
        (FOUNDER_BETA_CONSISTENCY_CSS, "consistency"),
    ):
        # Comments may mention the owner; live rules must not.
        live = "\n".join(
            line for line in css.splitlines() if not line.strip().startswith("/*")
        )
        assert ".block-container" not in live, name


def test_format_score_and_rank_have_single_owner():
    assert app._format_score is league_workspace_ui._format_score
    assert app._format_rank is league_workspace_ui._format_rank
    app_source = Path("app.py").read_text(encoding="utf-8")
    assert "def _format_score(" not in app_source
    assert "def _format_rank(" not in app_source


def test_format_score_and_rank_edge_cases():
    assert league_workspace_ui._format_score(None) == "0"
    assert league_workspace_ui._format_score(float("nan")) == "0"
    assert league_workspace_ui._format_score(0) == "0"
    assert league_workspace_ui._format_score(12) == "12"
    assert league_workspace_ui._format_score(12.6) == "13"
    assert league_workspace_ui._format_score(1234.4) == "1,234"
    assert league_workspace_ui._format_rank(None) == "N/A"
    assert league_workspace_ui._format_rank(float("nan")) == "N/A"
    assert league_workspace_ui._format_rank(0) == "N/A"
    assert league_workspace_ui._format_rank(-1) == "N/A"
    assert league_workspace_ui._format_rank(1) == "#1"
    assert league_workspace_ui._format_rank(12.4) == "#12"

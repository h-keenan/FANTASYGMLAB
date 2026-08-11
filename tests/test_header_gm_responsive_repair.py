"""Header + GM control responsive repair contracts (#229)."""

from __future__ import annotations

from pathlib import Path

from modules import application_shell, brand_identity
from modules.app_styles import APP_CSS
from modules.application_shell_styles import APPLICATION_SHELL_CSS
from modules.executive_command_header_styles import (
    COMMAND_COLUMN_WEIGHTS,
    EXECUTIVE_COMMAND_HEADER_CSS,
)
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_gm_text_pill_geometry_removed_from_app_css():
    # The pre-#229 mobile pill forced visible uppercase label text into the orb.
    assert "linear-gradient(180deg, rgba(14, 165, 233, 0.95), rgba(37, 99, 235, 0.92))" not in APP_CSS
    assert "letter-spacing: 0.08em;\n        min-height: 48px;\n        min-width: 60px;" not in APP_CSS
    assert "padding: 0.28rem 0.82rem 0.28rem 0.76rem;\n        text-transform: uppercase;" not in APP_CSS


def test_gm_orb_overlay_is_circular_icon_with_accessible_label():
    assert "border-radius: 50% !important" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "font-size: 0 !important" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "color: transparent !important" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "background-size: contain !important" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "--dg-gm-orb-size" in MOBILE_INTERACTION_OVERLAY_CSS
    assert brand_identity.GM_ORB_ARIA_LABEL == "Open GM menu"
    html = brand_identity.gm_orb_floating_trigger_html()
    assert "background-size:contain" in html
    assert "mobile-gm-floating-trigger-marker" in html


def test_gm_orb_hides_button_children_not_warped_text():
    assert "button > *" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "opacity: 0 !important" in MOBILE_INTERACTION_OVERLAY_CSS
    assert ".mobile-gm-orb-hint" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "writing-mode" not in MOBILE_INTERACTION_OVERLAY_CSS


def test_mobile_shell_hides_war_room_and_truncates_league():
    assert ".dg-executive-shell__room" in APPLICATION_SHELL_CSS
    mobile = APPLICATION_SHELL_CSS.split("@media (max-width: 760px)", 1)[1]
    assert ".dg-executive-shell__room" in mobile
    assert "display: none" in mobile.split(".dg-executive-shell__room", 1)[1][:120]
    assert "text-overflow: ellipsis" in APPLICATION_SHELL_CSS
    assert "safe-area-inset-top" in APPLICATION_SHELL_CSS
    assert "clamp(" in mobile


def test_long_league_name_still_renders_in_shell_html():
    html = application_shell.executive_workspace_shell_html(
        application_shell.ExecutiveWorkspaceShell(
            page_title="Dashboard",
            page_note="",
            league_name="Revivallry Super Long Dynasty League Name 2026",
            team_name="Team",
            platform="Sleeper",
            account_label="Guest",
            entitlement_label="Free",
            has_league=True,
        )
    )
    assert "Revivallry Super Long Dynasty League Name 2026" in html
    assert "dg-executive-shell__league" in html
    assert "War Room" in html  # desktop still has it; mobile CSS hides


def test_compact_league_switch_trigger_preserves_help_and_sheet():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    header = app.split("def render_top_league_identity_header", 1)[1].split(
        "def ", 1
    )[0]
    assert '"League" if selected_league_id else "Select"' in header
    assert 'help="Switch league"' in header
    assert "Switch League" in app  # sheet section title remains
    assert "_switch_to_saved_league" in app


def test_command_rail_weights_fit_compact_labels():
    assert COMMAND_COLUMN_WEIGHTS == (1.15, 1.15, 0.95)
    assert "grid-template-columns: minmax(0, auto) 0.75rem" in EXECUTIVE_COMMAND_HEADER_CSS
    assert "justify-content: center !important" in EXECUTIVE_COMMAND_HEADER_CSS


def test_forbidden_legacy_gm_selectors_stay_gone():
    assert "writing-mode: vertical-rl" not in APP_CSS
    assert "mobile-gm-orb-hint {" not in APP_CSS or "display: none" in MOBILE_INTERACTION_OVERLAY_CSS


def test_overlay_appended_after_legacy_app_css_chunks():
    # Ensure authoritative overlay is concatenated last among style modules.
    source = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    assert source.index("MOBILE_INTERACTION_OVERLAY_CSS") > source.index("BRAND_IDENTITY_CSS")
    assert "MOBILE_INTERACTION_OVERLAY_CSS" in source.split("APP_CSS =", 1)[1]

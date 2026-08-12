"""Production mobile header + early account-control contracts."""

from __future__ import annotations

from pathlib import Path

from modules.executive_command_header_styles import EXECUTIVE_COMMAND_HEADER_CSS
from modules import startup_critical_path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_command_rail_popovers_omit_help_to_prevent_duplicate_triggers():
    league_fn = APP.split("def render_top_league_identity_header", 1)[1].split("\ndef ", 1)[0]
    assert "st.popover(" in league_fn
    assert "help=" not in league_fn
    profile_fn = APP.split("def render_executive_profile_control", 1)[1].split(
        "\ndef render_platform_topbar", 1
    )[0]
    assert 'st.popover("You")' in profile_fn
    assert "help=" not in profile_fn


def test_command_owner_collapses_duplicate_popover_buttons():
    css = EXECUTIVE_COMMAND_HEADER_CSS
    assert 'button[data-testid="stPopoverButton"] ~ button[data-testid="stPopoverButton"]' in css
    assert "flex-direction: column !important" in css
    # Former shrink-wrap fix that forced duplicates into adjacent columns.
    assert "min-width: 100% !important" not in css


def test_early_guest_account_controls_precede_sidebar():
    early = APP.index("early_launch_account_decision")
    sidebar = APP.index("# SIDEBAR")
    auth_entry = APP.index("account_controls_ready")
    assert early < sidebar
    assert auth_entry < sidebar
    assert "_early_launch_account_rendered" in APP
    assert "skip_account_entry" in APP or "_early_launch_account_rendered" in APP


def test_auth_storage_deadline_is_bounded_for_account_cta_latency():
    assert startup_critical_path.AUTH_STORAGE_CLIENT_DEADLINE_MS == 1_500
    assert startup_critical_path.AUTH_STORAGE_CLIENT_DEADLINE_MS < 3_000

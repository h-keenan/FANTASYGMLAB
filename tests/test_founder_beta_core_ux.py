"""Core Founder Beta journey consistency — terminology, gates, and launch CTAs.

Retriggers Delivery Validation after an empty Actions runner allocation.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from modules import product_copy
from modules import ui_architecture
from modules import workspace_notices


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
EXPLORER = (ROOT / "modules" / "player_asset_explorer_ui.py").read_text(encoding="utf-8")
PREMIUM = (ROOT / "modules" / "premium_page.py").read_text(encoding="utf-8")
LANDING_CSS = (ROOT / "modules" / "marketing_landing_styles.py").read_text(encoding="utf-8")
HARNESS = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")


def test_product_copy_matches_platform_destination_labels():
    for key, label in (
        ("players", "Players"),
        ("trade_hub", "Trade Hub"),
        ("rankings", "League Overview"),
        ("dashboard", "Dashboard"),
        ("my_team", "My Team"),
        ("waivers", "Waivers"),
    ):
        assert product_copy.destination_label(key) == label
        assert next(page.label for page in ui_architecture.PLATFORM_DESTINATIONS if page.key == key) == label


def test_core_customer_surfaces_drop_deprecated_terms():
    for source in (APP, EXPLORER, PREMIUM, HARNESS):
        for term in product_copy.DEPRECATED_CUSTOMER_TERMS:
            assert term not in source


def test_players_page_title_matches_nav_label():
    players = APP.split('if current_page == "players":', 1)[1].split(
        "explorer_context =", 1
    )[0]
    assert "product_copy.PLAYERS" in players
    assert "Players & Picks" not in players
    assert "PLAYERS_EXPLORER_TITLE" in EXPLORER
    assert "weight=\"secondary\"" in EXPLORER or "weight='secondary'" in EXPLORER


def test_load_leagues_cta_is_canonical_on_launch_and_sidebar():
    launch = APP.split("def render_home_launch_screen", 1)[1].split(
        "def render_onboarding_handoff", 1
    )[0]
    sidebar = APP.split("# SIDEBAR", 1)[1].split("leagues = st.session_state.get", 1)[0]
    assert "product_copy.LOAD_LEAGUES_CTA" in launch
    assert "product_copy.LOAD_LEAGUES_CTA" in sidebar
    assert "Load leagues for user" not in APP
    assert "Load my leagues" in HARNESS


def test_league_open_buttons_do_not_embed_long_names():
    launch = APP.split("def render_home_launch_screen", 1)[1].split(
        "def render_onboarding_handoff", 1
    )[0]
    assert "product_copy.OPEN_LEAGUE_CTA" in launch
    assert "product_copy.CONTINUE_LAST_LEAGUE_CTA" in launch
    assert "Open {" not in launch
    assert "Continue last league:" not in launch


def test_gated_pages_use_compact_launch_instead_of_restacking_marketing():
    handoff = APP.split("def render_onboarding_handoff", 1)[1].split(
        "def render_workspace_handoff", 1
    )[0]
    assert "compact=True" in handoff
    assert "render_workspace_note" in handoff
    assert "st.info(" not in handoff
    launch = APP.split("def render_home_launch_screen", 1)[1].split(
        "def render_onboarding_handoff", 1
    )[0]
    assert "if not compact:" in launch
    assert "render_marketing_landing_deferred()" in launch


def test_core_gates_use_canonical_empty_states():
    assert APP.count("render_roster_mismatch_notice") >= 3
    assert APP.count("render_startup_blocked_notice") >= 3
    assert APP.count("render_lookup_notice") >= 2
    assert "render_action_row" in APP.split("def render_trade_workflow_handoff", 1)[1].split(
        "render_archetype_summary", 1
    )[0]
    assert 'type="primary"' in APP.split("def render_trade_workflow_handoff", 1)[1].split(
        "render_archetype_summary", 1
    )[0]


def test_trade_hub_loading_copy_is_scoped_not_board_jargon():
    assert "product_copy.LOADING_TRADE_IDEAS" in APP
    assert product_copy.LOADING_TRADE_IDEAS == "Loading trade ideas…"
    assert "Building the trade board" not in APP


def test_premium_and_landing_use_full_trade_hub():
    assert "PREMIUM_FULL_TRADE_HUB" in PREMIUM
    assert product_copy.PREMIUM_FULL_TRADE_HUB == "Full Trade Hub"
    html = (ROOT / "static" / "landing" / "index.html").read_text(encoding="utf-8")
    assert "Full Trade Hub" in html
    assert "Full trade board" not in html


def test_landing_headline_wraps_by_words_on_narrow_phones():
    assert "overflow-wrap:break-word" in LANDING_CSS
    assert "word-break:normal" in LANDING_CSS
    assert "hyphens:none" in LANDING_CSS
    assert "@media (max-width:430px)" in LANDING_CSS
    assert "fgl-landing__hero" not in (ROOT / "modules" / "app_styles.py").read_text(
        encoding="utf-8"
    )


def test_lookup_and_roster_notices_use_empty_state_kinds():
    rendered: list[tuple] = []

    def _capture(*args, **kwargs):
        rendered.append((args, kwargs))

    with patch.object(workspace_notices.ui_primitives, "render_empty_state_panel", _capture):
        assert workspace_notices.render_lookup_notice("user_not_found") is True
        workspace_notices.render_roster_mismatch_notice()
        workspace_notices.render_startup_blocked_notice("Trade discovery unlocks later.")
        assert workspace_notices.render_lookup_notice("ok") is False

    kinds = [kwargs["kind"] for _args, kwargs in rendered]
    assert kinds == ["no-data", "error", "unavailable"]
    assert product_copy.ROSTER_MISMATCH_BODY in rendered[1][0]

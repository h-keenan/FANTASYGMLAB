"""Canonical semantic glyph registry and GM Orb / Dashboard mapping."""

from __future__ import annotations

from pathlib import Path

from modules import ui_architecture, workspace_ui
from modules.app_styles import APP_CSS
from modules.daily_gm_briefing_ui import DAILY_GM_BRIEFING_CSS
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS
from modules.semantic_glyphs import (
    CONCEPTS,
    DESTINATION_CONCEPT,
    SEMANTIC_GLYPH_CSS,
    concept_for,
    concept_for_destination,
    concept_for_header,
    glyph_html,
    glyph_mask_data_uri,
    route_row_glyph_html,
    gm_orb_row_css,
    svg_markup,
)
from modules.ui_primitives import section_header_html


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_concept_set_is_small_and_reusable():
    assert 8 <= len(CONCEPTS) <= 12
    for name in (
        "home",
        "roster",
        "trade",
        "waiver",
        "rankings",
        "draft",
        "league",
        "insights",
        "alerts",
        "history",
        "more",
    ):
        assert name in CONCEPTS


def test_every_visible_destination_has_a_glyph_concept():
    for page in ui_architecture.PLATFORM_DESTINATIONS:
        if page.category == "ARCHIVED":
            continue
        assert concept_for_destination(page.key) in CONCEPTS
        html = route_row_glyph_html(page.key)
        assert f"data-dg-glyph='{concept_for_destination(page.key)}'" in html
        assert "<svg" in html
        assert f"st-key-mobile_sheet_nav_{page.key}" in gm_orb_row_css()


def test_league_overview_does_not_share_the_rankings_bars_concept():
    assert "rankings" in CONCEPTS
    assert concept_for_destination("rankings") == "league"
    assert "data-dg-glyph='league'" in route_row_glyph_html("rankings")
    assert concept_for_destination("players") == "rankings"
    assert "data-dg-glyph='rankings'" in route_row_glyph_html("players")


def test_glyph_html_is_decorative_inline_svg_without_emoji_or_network():
    html = glyph_html("trade_hub", size="row")
    assert "aria-hidden='true'" in html
    assert "<svg" in html
    assert "data-dg-glyph='trade'" in html
    assert "http://" not in html
    assert "https://" not in html
    assert "emoji" not in html.casefold()
    joined = svg_markup("home") + svg_markup("alerts") + SEMANTIC_GLYPH_CSS
    assert "😀" not in joined
    assert "@fortawesome" not in joined
    assert "fontawesome" not in joined.casefold()
    assert "iconify" not in joined.casefold()


def test_no_external_icon_dependency_in_requirements():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8").casefold()
    for blocked in ("fontawesome", "font-awesome", "iconify", "feather-icons", "material-icons"):
        assert blocked not in req


def test_workspace_semantic_icon_uses_concepts_not_ascii_ornaments():
    assert workspace_ui.semantic_icon("trade_hub") == "trade"
    assert workspace_ui.semantic_icon("waivers") == "waiver"
    assert workspace_ui.semantic_icon("draft_summary") == "draft"
    html = workspace_ui.semantic_icon_html("trade")
    assert "<svg" in html
    assert "aria-hidden='true'" in html
    assert "$" not in html


def test_dashboard_headers_receive_section_glyphs():
    plan = section_header_html("Today's Game Plan", weight="primary")
    insights = section_header_html("League Insights", weight="secondary")
    snapshot = section_header_html("Team Snapshot", weight="secondary")
    assert "dg-ui-section-title--glyph" in plan
    assert "data-dg-glyph='home'" in plan
    assert "data-dg-glyph='insights'" in insights
    assert "data-dg-glyph='roster'" in snapshot
    other = section_header_html("Filters", weight="secondary")
    assert "dg-ui-section-title--glyph" not in other
    assert concept_for_header("Weekly Recaps") == ""
    assert concept_for("history") == "history"
    assert concept_for("storylines") == "history"


def test_gm_orb_css_covers_route_rows_and_active_state():
    css = gm_orb_row_css()
    assert "st-key-mobile_sheet_row_" in css
    assert "st-key-mobile_sheet_nav_" in css
    assert "button::before" in css
    assert "data:image/svg+xml" in css
    assert "-webkit-mask:" in css
    assert ":has(.dg-gm-route-glyph)" not in css
    assert "position:absolute" not in css
    assert "st-key-mobile_sheet_row_" in MOBILE_INTERACTION_OVERLAY_CSS
    assert ".dg-glyph" in APP_CSS
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "mobile_sheet_row_" in app
    assert "route_row_glyph_html(page.key)" not in app
    assert "https://" not in css
    assert glyph_mask_data_uri("home").startswith('url("data:image/svg+xml,')


def test_game_plan_kind_row_uses_shared_glyphs():
    source = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    assert "glyph_html(kind_concept" in source
    assert "Trade" in source and "Waiver" in source
    assert ".dg-daily-briefing-kind" in DAILY_GM_BRIEFING_CSS


def test_alerts_unread_hook_exists_without_new_logic():
    assert ".dg-glyph--alerts" in SEMANTIC_GLYPH_CSS
    assert ".dg-glyph--alerts.is-unread" in SEMANTIC_GLYPH_CSS
    notify = (ROOT / "modules" / "notification_center.py").read_text(encoding="utf-8")
    assert "def alerts_command_label" in notify
    assert "Alerts (99+)" in notify
    assert "alerts" not in DESTINATION_CONCEPT
    assert "glyph_html" not in notify


def test_visible_destination_labels_are_unique():
    labels = [
        page.label
        for page in ui_architecture.PLATFORM_DESTINATIONS
        if page.category != "ARCHIVED"
    ]
    assert labels
    assert len(labels) == len(set(labels))


def test_orb_sheet_keeps_text_labels_and_no_rerun():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    sheet = app.split("def render_mobile_destination_sheet", 1)[1].split(
        "def render_mobile_navigation_shell", 1
    )[0]
    assert "st.rerun()" not in sheet
    assert "command_label" in sheet
    assert "st.button(" in sheet
    assert "route_row_glyph_html" not in sheet


def test_orb_row_css_puts_glyph_on_the_real_button():
    css = gm_orb_row_css()
    assert "button::before" in css
    assert '[data-testid="stElementContainer"]:has(.dg-gm-route-glyph)' not in css
    assert "max-height:0!important" not in css
    assert "dg-gm-route-glyph" not in css


def test_dashboard_owns_header_glyph_size_not_app_css_dump():
    from modules.dashboard_workflow_styles import DASHBOARD_WORKFLOW_CSS

    assert "1.4rem" in DASHBOARD_WORKFLOW_CSS
    assert ".dg-ui-section-title--glyph .dg-glyph" in DASHBOARD_WORKFLOW_CSS
    assert DASHBOARD_WORKFLOW_CSS not in APP_CSS
    assert ".dg-daily-briefing-kind .dg-glyph" in DAILY_GM_BRIEFING_CSS
    assert "fontawesome" not in SEMANTIC_GLYPH_CSS.casefold()


def test_future_memory_concepts_reuse_history_without_new_routes():
    assert concept_for("recap") == "history"
    assert concept_for("storylines") == "history"
    keys = {page.key for page in ui_architecture.PLATFORM_DESTINATIONS}
    assert "weekly_recaps" not in keys
    assert "storylines" not in keys


def test_harness_navigation_fixture_uses_button_owned_glyphs():
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    assert "route_row_glyph_html" not in harness
    assert "mobile_sheet_row_" in harness
    assert "mobile_sheet_nav_{page_key}_fixture" in harness
    assert "mobile_sheet_row_{page_key}" in harness
    assert "_production_equivalent_headshot_src" in harness
    assert "data-testid='stDialog'" in harness

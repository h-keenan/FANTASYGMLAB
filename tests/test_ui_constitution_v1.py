"""UI Magna Carta + interaction reliability v1 regressions."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from modules.app_styles import APP_CSS
from modules.alerts_activity import (
    EMPTY_COPY,
    FILTER_DECISIONS,
    FILTER_IMPORTANT,
    FILTER_LEAGUE,
    FILTER_MY_PLAYERS,
    FILTER_NEWS,
    compose_activity_timeline,
    empty_copy,
    filter_timeline,
    humanize_headline,
)
from modules.compact_fantasy_assets import compact_asset_html
from modules.interaction_contract import TAP_DELEGATION_JS, on_clicked_change
from modules.news_intelligence import FT_OTHER, FootballEvent, _alert_identity_title
from modules.player_cards import player_status_pill_html
from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS
from modules.player_quick_view_bridge import PLAYER_QUICK_VIEW_EVENT
from modules.signal_freshness import format_human_age_label, humanize_age_label
from modules.trade_analyzer_styles import TRADE_ANALYZER_CSS
from scripts.measure_interaction_rerun_architecture import count_explicit_reruns


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
TRADE = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
PQV = APP[
    APP.index("def render_player_quick_view_content(") : APP.index(
        "def render_player_detail_content("
    )
]


def test_magna_carta_exists_with_shall_rules():
    text = (ROOT / "docs" / "UI_MAGNA_CARTA.md").read_text(encoding="utf-8")
    assert "SHALL" in text
    assert "SHALL NOT" in text
    assert "PAGE TITLE" in text
    assert "ONE GESTURE" in text


def test_no_legacy_pqv_more_hide_button():
    assert "More details" not in PQV
    assert "Hide details" not in PQV
    assert "pqv_more_details_open_" not in PQV
    assert "pqv_detail_nav_" in PQV


def test_no_gradient_on_pqv_disclosure_nav():
    css = PLAYER_QUICK_VIEW_CSS
    assert "st-key-pqv_detail_nav_rail" in css
    assert "background-image:none" in css
    nav = css.split("st-key-pqv_detail_nav_rail", 1)[1][:500]
    assert "linear-gradient" not in nav


def test_one_pqv_interaction_owner():
    assert "def render_player_quick_view_modal(" in APP
    assert "player_quick_view_player_id" in APP
    dialog = TRADE[
        TRADE.index("def _trade_detail_dialog()") : TRADE.index(
            "def render_trade_idea_player_actions("
        )
    ]
    assert "render_player_dossier(" not in dialog
    assert "st.rerun()" not in dialog
    assert "open_player_quick_view" in dialog


def test_trade_hub_player_and_chrome_first_tap_contract():
    assert "kind: \"player\"" in TAP_DELEGATION_JS or "kind: \"player\"" in TAP_DELEGATION_JS.replace(
        "'", '"'
    )
    assert "stopPropagation" in TAP_DELEGATION_JS
    assert "data-html-sig" in TAP_DELEGATION_JS
    assert "dg-player-asset-tap" in TAP_DELEGATION_JS
    html = compact_asset_html(
        {"asset_type": "player", "player_id": "p1", "name": "Star Runner", "position": "RB"}
    )
    assert "dg-player-asset-tap" in html
    assert "data-player-id" in html
    assert "p1" in html
    assert "min-height:var(--touch-target-min)" in (
        ROOT / "modules" / "compact_fantasy_assets.py"
    ).read_text(encoding="utf-8")
    assert "rootId" in TRADE
    assert on_clicked_change() is None
    assert PLAYER_QUICK_VIEW_EVENT in TAP_DELEGATION_JS
    assert "bridgePlayerOpens" in TAP_DELEGATION_JS


def test_no_nested_pqv_or_dialog_rerun():
    assert "render_player_dossier is not None else open_player_quick_view" not in TRADE
    assert TRADE.count("st.rerun()") == 0


def test_viewport_records_overlay_and_disclosures():
    js = (ROOT / "modules" / "viewport_preservation.py").read_text(encoding="utf-8")
    assert "isOverlayChrome(target)) return" not in js.split("pointerdown", 1)[1][:800]
    assert "stDialog" in js


def test_one_page_title_owner_on_alerts():
    ui = (ROOT / "modules" / "alerts_activity_ui.py").read_text(encoding="utf-8")
    assert 'render_section_header(\n            "Alerts"' in ui or 'render_section_header(' in ui
    assert "Not a second History" not in ui


def test_pqv_default_path_hides_full_tables_and_model():
    assert "current_season_summary_html(" in PQV
    assert PQV.index("current_season_summary_html(") < PQV.index("pqv_detail_nav_")
    stats_gate = PQV.index('detail_choice == "STATS"')
    assert PQV.index("render_current_season(") > stats_gate
    assert PQV.index('detail_choice == "STATS"') < PQV.rindex("render_current_season(")
    assert PQV.index('detail_choice == "MODEL"') < PQV.rindex("advanced_detail_rows_html")
    career_gate = PQV.index('detail_choice == "CAREER"')
    assert PQV.index("career_timeline_html(") > career_gate
    assert "skip_current_season=True" in PQV
    assert "career_dossier_html(" in PQV
    assert PQV.index("career_dossier_html(") < PQV.index("pqv_actions_")


def test_no_old_blue_gradient_cta_in_pqv():
    assert "linear-gradient" not in PQV
    assert ".stButton button" in APP_CSS
    button_block = APP_CSS.split(".stButton button {", 1)[1][:280]
    assert "linear-gradient" not in button_block


def test_dialog_cyan_rail_not_on_tertiary():
    assert "stBaseButton-tertiary" in APP_CSS
    assert "border-left: 3px solid var(--dg-theme-accent-cyan)" in APP_CSS
    tertiary = APP_CSS.split("stBaseButton-tertiary", 1)[1][:220]
    assert "border-left: 1px solid" in tertiary or "border-left:0" in PLAYER_QUICK_VIEW_CSS


def test_command_header_styles_only_the_popover_trigger_not_its_body():
    css = (ROOT / "modules" / "executive_command_header_styles.py").read_text(
        encoding="utf-8"
    )
    assert '[data-testid="stPopover"] button,' not in css
    assert '> div[aria-haspopup="true"] > button[data-testid="stPopoverButton"]' in css


def test_analyzer_canonical_radius():
    assert "16px" not in TRADE_ANALYZER_CSS
    assert "var(--radius-panel, 0)" in TRADE_ANALYZER_CSS


def test_alerts_sources_empty_states_and_copy():
    assert empty_copy(FILTER_IMPORTANT) == "You’re caught up."
    assert empty_copy(FILTER_MY_PLAYERS) == "No recent player-specific alerts."
    assert empty_copy(FILTER_NEWS) == "No recent mapped news."
    assert empty_copy(FILTER_LEAGUE) == "No notable league activity recently."
    assert empty_copy(FILTER_DECISIONS) == "No new recommendation changes."
    assert humanize_headline({"headline": "Player: Other", "player_id": ""}) != "Player: Other"
    assert "Player: Other" not in humanize_headline(
        {"headline": "Player: Other", "category": "NEWS", "player_id": ""}
    )
    event = FootballEvent(event_type=FT_OTHER, player_name="Other", player_id="")
    assert "Player: Other" not in _alert_identity_title(event)
    rows = compose_activity_timeline(session={}, league_id="L1")
    visible = filter_timeline(rows, FILTER_IMPORTANT)
    assert isinstance(visible, tuple)
    styles = (ROOT / "modules" / "alerts_activity_styles.py").read_text(encoding="utf-8")
    assert "flex-wrap:nowrap" in styles
    assert "overflow-x:auto" in styles


def test_freshness_humanization_contract():
    assert format_human_age_label(28 * 60) == "28m"
    assert format_human_age_label(3 * 3600) == "3h"
    assert format_human_age_label(2 * 86400) == "2d"
    week = format_human_age_label(10 * 86400, now=1_700_000_000.0)
    assert re.search(r"[A-Z][a-z]{2} \d+", week)
    assert "m" not in week[-2:] or "Last confirmed" in week
    stale = humanize_age_label("stale · 60486m")
    assert "60486" not in stale
    assert re.search(r"\d{4,}m", stale) is None
    assert "Last confirmed" in stale


def test_status_badge_not_pill_on_canonical_helper():
    html = player_status_pill_html("Elite")
    assert "player-status-pill" not in html
    assert "dg-status-badge" in html


def test_no_per_player_portrait_hacks_in_pqv():
    assert "object-position:" not in PQV
    assert "--pqv-portrait-size" in PLAYER_QUICK_VIEW_CSS


def test_explicit_rerun_budget_and_app_css():
    assert count_explicit_reruns() <= 58
    assert len(APP_CSS) < 390_000


def test_pqv_first_screen_height_contract_at_390():
    css = PLAYER_QUICK_VIEW_CSS.replace(" ", "")
    assert "--pqv-portrait-size:clamp(4.75rem,22vw,5.75rem)" in css
    assert "render_developer_diagnostics" not in PQV
    assert PQV.index("current_season_summary_html(") < PQV.index('detail_choice == "STATS"')


def test_alerts_filters_map_to_existing_sources():
    source = (ROOT / "modules" / "alerts_activity.py").read_text(encoding="utf-8")
    assert "compose_activity_inbox" in source
    assert "load_cached_news_pool" in source
    assert "TIMELINE_EVENT_KEY" in source
    assert "decision_memory" in source
    assert "FILTER_IMPORTANT" in source
    assert "FILTER_MY_PLAYERS" in source
    carta = (ROOT / "docs" / "UI_MAGNA_CARTA.md").read_text(encoding="utf-8")
    assert "Notification inbox" in carta
    assert "Decision Memory" in carta


def test_first_tap_player_vs_trade_delegation_playwright():
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    markup = """
    <div id="trade-summary-tap-root"></div>
    """
    inner = """
    <article class="trade-summary-card" data-trade-summary-key="trade-1">
      <div class="dg-player-asset-tap" data-player-id="p1" id="player-target">Star Runner</div>
      <div data-trade-chrome="1" id="chrome-target">FOR</div>
    </article>
    """
    js = TAP_DELEGATION_JS.replace(
        "export default function(component)",
        "window.__tapInit = function(component)",
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.set_content(markup)
        page.add_script_tag(content=js)
        page.evaluate(
            """(html) => {
              window.__clicks = [];
              window.__tapInit({
                data: { html, key: "trade-1", rootId: "trade-summary-tap-root" },
                parentElement: document.body,
                setTriggerValue: (name, payload) => window.__clicks.push([name, payload])
              });
            }""",
            inner,
        )
        page.click("#player-target")
        player_clicks = page.evaluate("window.__clicks")
        page.evaluate("window.__clicks = []")
        page.click("#chrome-target")
        chrome_clicks = page.evaluate("window.__clicks")
        browser.close()
    assert player_clicks[0][1]["kind"] == "player"
    assert player_clicks[0][1]["player_id"] == "p1"
    assert len(player_clicks) == 1
    assert chrome_clicks[0][1]["kind"] == "trade"
    assert chrome_clicks[0][1]["key"] == "trade-1"
    assert len(chrome_clicks) == 1

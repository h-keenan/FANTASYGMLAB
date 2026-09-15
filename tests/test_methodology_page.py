from pathlib import Path
from unittest.mock import patch

from modules import methodology_page
from modules.app_styles import APP_CSS
from modules.live_draft import LIVE_DRAFT_DISCOVERY_SKIP_ROUTES
from modules.methodology_page_styles import METHODOLOGY_PAGE_CSS
from modules.ui_architecture import (
    current_platform_destinations,
    mobile_primary_destinations,
    mobile_secondary_destinations,
)


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
METHODOLOGY = (ROOT / "modules" / "methodology_page.py").read_text(encoding="utf-8")
RANKINGS = (ROOT / "modules" / "rankings.py").read_text(encoding="utf-8")
VALUATION = (ROOT / "modules" / "league_value_settings.py").read_text(encoding="utf-8")


def test_methodology_is_support_not_primary_nav():
    destinations = {page.key: page for page in current_platform_destinations(False)}
    primary = {page.key for page in mobile_primary_destinations(False)}
    secondary = {page.key for page in mobile_secondary_destinations(False)}

    assert methodology_page.PAGE_KEY in destinations
    assert destinations[methodology_page.PAGE_KEY].category == "SUPPORT"
    assert destinations[methodology_page.PAGE_KEY].label == methodology_page.NAV_LABEL
    assert methodology_page.PAGE_KEY not in primary
    assert methodology_page.PAGE_KEY in secondary


def test_methodology_footer_and_route_wiring():
    from modules import legal_pages

    assert (methodology_page.FOOTER_LABEL, methodology_page.PAGE_KEY) in legal_pages.LEGAL_FOOTER_LINKS
    assert methodology_page.PAGE_KEY not in legal_pages.LEGAL_PAGE_KEYS
    assert f'"{methodology_page.PAGE_KEY}": methodology_page.PAGE_PURPOSE' in APP
    assert "methodology_page.render_methodology_page()" in APP
    assert "elif current_page == methodology_page.PAGE_KEY:" in APP
    assert 'prepared_frame_signature = "methodology_static_page"' in APP
    assert "current_page not in {methodology_page.PAGE_KEY, \"player_detail\"}" in APP
    assert methodology_page.PAGE_KEY in LIVE_DRAFT_DISCOVERY_SKIP_ROUTES


def test_methodology_page_is_static_and_avoids_providers():
    runtime = METHODOLOGY.split("FORBIDDEN_USER_SUBSTRINGS", 1)[0]
    forbidden_imports = (
        "modules.sleeper",
        "modules.fantasycalc",
        "modules.rankings",
        "modules.trade_ideas",
        "pandas",
        "requests",
    )
    for token in forbidden_imports:
        assert token not in METHODOLOGY
    assert "ensure_players" not in runtime
    assert "apply_valuation" not in runtime
    assert "get_league(" not in runtime
    assert "time_block" not in runtime
    assert "st.cache" not in runtime


def test_methodology_copy_matches_implemented_behavior():
    html = methodology_page.methodology_page_html()
    lowered = html.lower()

    assert methodology_page.PAGE_TITLE in html
    assert methodology_page.PAGE_KICKER in html
    for phrase in methodology_page.REQUIRED_USER_PHRASES:
        assert phrase.lower() in lowered
    for token in methodology_page.FORBIDDEN_USER_SUBSTRINGS:
        assert token not in html
        assert token not in METHODOLOGY.split("FORBIDDEN_USER_SUBSTRINGS", 1)[0]
    assert "class='methodology-factor-grid'" in html
    assert "What FantasyGM Lab does not claim" in html
    assert "AI-powered" not in html


def test_methodology_render_uses_html_fragment_only():
    with patch.object(methodology_page, "render_html_fragment") as fragment:
        methodology_page.render_methodology_page()
    fragment.assert_called_once()
    html = fragment.call_args.args[0]
    assert "methodology-page" in html
    assert "ensure_players" not in html


def test_methodology_css_is_mobile_first_and_route_owned():
    assert METHODOLOGY_PAGE_CSS not in APP_CSS
    assert "inject_global_styles(METHODOLOGY_PAGE_CSS)" in METHODOLOGY
    compact = METHODOLOGY_PAGE_CSS.replace(" ", "")
    assert "grid-template-columns:1fr;" in compact or "grid-template-columns: 1fr;" in METHODOLOGY_PAGE_CSS
    assert "@media (min-width: 700px)" in METHODOLOGY_PAGE_CSS
    assert "@media (max-width: 430px)" in METHODOLOGY_PAGE_CSS
    assert "min-height: var(--touch-target-min)" in METHODOLOGY_PAGE_CSS
    assert "animation:" not in METHODOLOGY_PAGE_CSS
    assert "transition:" not in METHODOLOGY_PAGE_CSS


def test_methodology_guest_query_skips_marketing_hero_before_resume():
    early = APP.split("_early_league_id = _safe_text", 1)[1][:900]
    assert "_query_param_page() or st.session_state.get(\"platform_nav_page\")" in early
    assert "LIVE_DRAFT_DISCOVERY_SKIP_ROUTES" in early
    render_at = APP.index("methodology_page.render_methodology_page()")
    nearby = APP[render_at - 80 : render_at + 80]
    assert "render_onboarding_handoff(" not in nearby
    assert "render_marketing_landing(" not in nearby


def test_methodology_route_does_not_change_valuation_logic():
    assert "COMPOSITE_WEIGHT_MARKET = 0.44" in RANKINGS
    assert "def apply_valuation_lens(" in VALUATION
    hydrate = APP.split("# --- Football hydration", 1)[1].split(
        "# Enrich strategy/ranks after prepared frame", 1
    )[0]
    assert "elif current_page == methodology_page.PAGE_KEY:" in hydrate
    assert hydrate.index("elif current_page == methodology_page.PAGE_KEY:") < hydrate.index(
        "get_or_build_valued_ranked_frame"
    )
    refresh_gate = APP.split("maybe_refresh_players_after_shell(", 1)[0][-900:]
    assert "LIVE_DRAFT_DISCOVERY_SKIP_ROUTES" in refresh_gate
    assert "methodology_page.PAGE_KEY" in APP.split("maybe_refresh_players_after_shell(", 1)[0] or (
        "LIVE_DRAFT_DISCOVERY_SKIP_ROUTES" in refresh_gate
    )

from pathlib import Path
from unittest.mock import patch

from modules import methodology_page
from modules.live_draft import LIVE_DRAFT_DISCOVERY_SKIP_ROUTES
from modules.ui_architecture import (
    current_platform_destinations,
    mobile_primary_destinations,
    mobile_secondary_destinations,
)


ROOT = Path(__file__).resolve().parents[1]
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
    assert "What FantasyDesk does not claim" in html
    assert "AI-powered" not in html

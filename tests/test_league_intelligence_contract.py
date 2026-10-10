from pathlib import Path

from modules.app_styles import APP_CSS
from modules.dense_list_styles import DENSE_LIST_CSS
from modules.league_intelligence_styles import LEAGUE_INTELLIGENCE_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_styles_load_once_use_tokens_and_avoid_raw_colors():
    assert APP_CSS.count(LEAGUE_INTELLIGENCE_CSS) == 1
    assert DENSE_LIST_CSS in APP_CSS
    assert "var(--touch-target-min)" in LEAGUE_INTELLIGENCE_CSS
    assert "dg-intelligence-item {" not in LEAGUE_INTELLIGENCE_CSS
    assert "#" not in LEAGUE_INTELLIGENCE_CSS


def test_feed_module_is_isolated_from_football_engines():
    source = (ROOT / "modules" / "league_intelligence.py").read_text(encoding="utf-8")
    for forbidden in (
        "trade_ideas",
        "waivers_ui",
        "team_needs",
        "valuation",
        "rankings",
        "archetype",
        "trust",
    ):
        assert forbidden not in source.lower()


def test_news_route_is_general_feed_not_league_intelligence():
    # News graduated from the old roster-scoped league_intelligence feed to
    # a general, non-roster-scoped feed — the web counterpart to mobile's
    # NewsScreen (mobile/src/screens/NewsScreen.tsx). build_league_intelligence_feed
    # / render_league_intelligence_feed are no longer wired into app.py at
    # all; player-detail's own "Recent News" section still reuses the
    # shared render_news_card card renderer.
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    route = source.split('if current_page == "news":', 1)[1].split("# TRADE IDEAS", 1)[0]
    assert "build_league_intelligence_feed" not in source
    assert "render_league_intelligence_feed" not in source
    assert "general_news_feed(" in route
    assert "render_general_news_feed(" in route
    assert "def render_news_card" in source

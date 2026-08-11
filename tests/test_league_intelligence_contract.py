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


def test_production_route_uses_feed_without_replacing_player_detail_news():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    route = source.split("# MY PLAYERS' NEWS", 1)[1].split("# TRADE IDEAS", 1)[0]
    assert "build_league_intelligence_feed" in route
    assert "render_league_intelligence_feed" in route
    assert "league_player_names" in route
    assert "news_roster_player_map" in route
    assert "get_shared_league_context()" not in route
    assert "render_news_card(item, news_idx)" not in route
    assert "def render_news_card" in source

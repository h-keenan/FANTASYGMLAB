import inspect
import unittest
from pathlib import Path

import app


class TestPerformanceCache(unittest.TestCase):
    def test_expensive_trade_cache_is_keyed_by_league_and_settings_context(self):
        cached_callable = getattr(app.cached_trade_ideas, "__wrapped__", app.cached_trade_ideas)
        params = inspect.signature(cached_callable).parameters

        for required in (
            "league_id",
            "my_roster_id",
            "score_field",
            "team_strategy",
            "team_archetype",
            "league_settings_items",
            "draft_status_items",
        ):
            self.assertIn(required, params)

    def test_expensive_league_context_cache_is_keyed_by_league_and_lineup_context(self):
        cached_callable = getattr(app.cached_league_context, "__wrapped__", app.cached_league_context)
        params = inspect.signature(cached_callable).parameters

        self.assertIn("league_id", params)
        self.assertIn("score_field", params)
        self.assertIn("lineup_settings", params)

    def test_free_waivers_do_not_compute_premium_only_slices_before_gate(self):
        app_source = Path("app.py").read_text(encoding="utf-8")
        start = app_source.index('if not startup_waiver_blocked and selected_league_id and not free_agents_ranked.empty:')
        end = app_source.index("waivers_ui.render_waiver_workspace_sections(")
        waiver_branch = app_source[start:end]

        self.assertIn("is_premium = current_user_is_premium()", waiver_branch)
        self.assertIn("if is_premium:", waiver_branch)
        self.assertIn("else:", waiver_branch)
        self.assertLess(
            waiver_branch.index("if is_premium:"),
            waiver_branch.index("stash_candidates = featured_free_agents["),
        )
        self.assertIn("stash_candidates = featured_free_agents.iloc[0:0].copy()", waiver_branch)
        self.assertIn("watchlist_candidates = featured_free_agents.iloc[0:0].copy()", waiver_branch)
        self.assertIn("faab_targets = free_agents_ranked.iloc[0:0].copy()", waiver_branch)

    def test_player_detail_news_section_never_blocks_render_on_live_rss(self):
        # Player Detail is reachable from League Overview, My Team, Trade Hub,
        # Trade Analyzer, Waivers, and Draft Center. The News/Alerts surfaces
        # already use a non-blocking contract for a stale on-disk cache:
        # render whatever is cached and let a background thread
        # (schedule_news_cache_refresh) catch it up, instead of calling
        # fetch_news() inline, which performs synchronous live RSS fetches
        # whenever the on-disk cache is older than NEWS_CACHE_TTL_SECONDS.
        # Player Detail's news section must follow the same contract so
        # opening any player's profile can never block on live network I/O.
        app_source = Path("app.py").read_text(encoding="utf-8")
        start = app_source.index("def render_player_detail_content(")
        end = app_source.index("def render_player_detail_page(")
        section = app_source[start:end]
        news_start = section.index('if include_news:')
        news_section = section[news_start:]

        self.assertIn("load_cached_news_pool()", news_section)
        self.assertIn("schedule_news_cache_refresh()", news_section)
        self.assertNotIn("fetch_news()", news_section)


if __name__ == "__main__":
    unittest.main()

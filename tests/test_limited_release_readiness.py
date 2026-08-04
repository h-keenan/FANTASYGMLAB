import unittest
from pathlib import Path

from modules import account_store, account_ui, auth_supabase, legal_pages, platform_import_ui


class TestLimitedReleaseReadiness(unittest.TestCase):
    def test_visible_player_explanation_copy_avoids_known_run_on_fragment(self):
        rankings_source = Path("modules/rankings.py").read_text(encoding="utf-8")

        self.assertNotIn("misses time\"", rankings_source)
        self.assertIn("misses time.\"", rankings_source)

    def test_premium_is_support_destination_but_not_primary_mobile_route(self):
        architecture_source = Path("modules/ui_architecture.py").read_text(encoding="utf-8")

        self.assertIn('PageDefinition("premium", "Premium", "SUPPORT"', architecture_source)
        self.assertIn('"premium": "Free and Premium plan preview for FantasyGM Lab."', Path("app.py").read_text(encoding="utf-8"))
        self.assertNotIn('"premium",\n    "my_team"', architecture_source)
        self.assertIn('"dashboard"', architecture_source)
        self.assertIn('"waivers"', architecture_source)

    def test_espn_import_remains_experimental_and_sleeper_recommended(self):
        source = Path("modules/platform_import_ui.py").read_text(encoding="utf-8")

        self.assertEqual(platform_import_ui.DEFAULT_LEAGUE_IMPORT_PLATFORM, "Sleeper")
        self.assertIn("Sleeper is the recommended full-support path", source)
        self.assertIn("ESPN import is experimental", source)
        self.assertIn("Limited ESPN review mode", source)
        self.assertIn("Cookies are session-only", source)

    def test_unaffiliated_and_estimate_disclaimers_exist(self):
        legal_source = Path("modules/legal_pages.py").read_text(encoding="utf-8")

        self.assertIn("not affiliated with", legal_source)
        self.assertIn("Sleeper, ESPN", legal_source)
        self.assertIn("Projections, rankings, player values", legal_source)
        self.assertIn("Verify important league, player, injury, and news information", legal_source)
        self.assertIn("FantasyGM Lab is an independent fantasy football tool", legal_pages.NO_AFFILIATION_TEXT)
        self.assertIn("not affiliated with, endorsed by, sponsored by", legal_pages.NO_AFFILIATION_TEXT)

    def test_billing_foundation_is_test_mode_only_and_not_primary_navigation(self):
        combined = "\n".join(
            Path(path).read_text(encoding="utf-8").casefold()
            for path in (
                "app.py",
                "modules/premium_page.py",
                "modules/stripe_billing.py",
                "modules/ui_architecture.py",
                "requirements.txt",
            )
        )

        self.assertIn("stripe test mode", combined)
        self.assertIn("live billing is not enabled", combined)
        self.assertIn("premium checkout will appear here once billing is enabled", combined)
        for blocked in ("payment link", "subscribe now", "sk_live_", "pk_live_"):
            self.assertNotIn(blocked, combined)
        self.assertIn('pagedefinition("premium", "premium", "support"', combined)

    def test_saved_league_and_auth_helpers_still_import(self):
        self.assertTrue(callable(account_store.default_saved_league))
        self.assertTrue(callable(account_store.build_saved_league_payload))
        self.assertTrue(callable(account_ui.render_mobile_auth_entry))
        self.assertTrue(callable(account_ui.render_durable_auth_bridge))
        self.assertTrue(callable(auth_supabase.restore_auth_payload))
        self.assertTrue(callable(auth_supabase.clear_auth_session))

    def test_quick_view_avatar_containment_and_menu_labels_remain_clean(self):
        css = Path("modules/app_styles.py").read_text(encoding="utf-8")
        app_source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn(".player-quick-view-avatar", css)
        self.assertIn("--avatar-size: 92px", css)
        self.assertIn(".player-quick-view-avatar img", css)
        self.assertIn("max-height: 58px", css)
        self.assertIn("object-fit: cover", css)
        for stale_label in ("HQ Dashboard", "TM My Team", "TR Trade Hub", ">Action Center<"):
            self.assertNotIn(stale_label, app_source)


if __name__ == "__main__":
    unittest.main()

import unittest

from modules.app_header import league_identity_header_html


class TestAppHeader(unittest.TestCase):
    def test_loaded_league_header_includes_identity(self):
        html = league_identity_header_html(
            league_name="Founder League",
            team_name="Chicago Build",
            platform="Sleeper",
            avatar_url="https://example.com/avatar.png",
            has_league=True,
            account_label="Signed in",
            entitlement_label="Premium",
        )

        self.assertIn("app-top-league-header", html)
        self.assertIn("Founder League", html)
        self.assertIn("Chicago Build", html)
        self.assertIn("Sleeper", html)
        self.assertIn("Signed in", html)
        self.assertIn("Premium", html)
        self.assertIn("Switch League / Refresh / Import / Premium", html)
        self.assertIn("https://example.com/avatar.png", html)

    def test_no_league_header_guides_import_without_breaking(self):
        html = league_identity_header_html(has_league=False, account_label="Guest", entitlement_label="Free")

        self.assertIn("FantasyGM Lab", html)
        self.assertIn("Import a Sleeper league", html)
        self.assertIn("ESPN early access", html)
        self.assertIn("Import League / Account / Premium", html)
        self.assertIn("app-top-league-avatar-fallback", html)
        self.assertIn("Founder Beta", html)


if __name__ == "__main__":
    unittest.main()

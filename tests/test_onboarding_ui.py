import unittest

from modules import onboarding_ui


class TestOnboardingUI(unittest.TestCase):
    def test_eligible_leagues_deduplicates_and_ignores_missing_ids(self):
        leagues = onboarding_ui.eligible_leagues(
            [
                {"league_id": "1", "name": "One"},
                {"league_id": "", "name": "Missing"},
                {"league_id": "1", "name": "Duplicate"},
                {"league_id": "2", "name": "Two"},
            ]
        )

        self.assertEqual([league["league_id"] for league in leagues], ["1", "2"])

    def test_last_league_option_requires_matching_username_and_valid_league(self):
        leagues = [
            {"league_id": "1", "name": "One"},
            {"league_id": "2", "name": "Two"},
        ]

        self.assertEqual(
            onboarding_ui.last_league_option(
                username="user-a",
                leagues=leagues,
                account={"username": "user-a", "league_id": "2"},
            ),
            "2",
        )
        self.assertEqual(
            onboarding_ui.last_league_option(
                username="user-b",
                leagues=leagues,
                account={"username": "user-a", "league_id": "2"},
            ),
            "",
        )

    def test_league_card_includes_distinguishing_context(self):
        html = onboarding_ui.league_card_html(
            {
                "league_name": "Test League",
                "team_name": "Test Team",
                "format_label": "Dynasty",
                "draft_state_label": "Drafted",
                "league_size": 12,
                "season": "2026",
                "platform_label": "Sleeper",
            },
            team_logo_html=lambda *args, **kwargs: "<div class='logo'></div>",
            last_used=True,
        )

        for expected in [
            "Test League",
            "Test Team",
            "Dynasty",
            "Drafted",
            "12 teams",
            "S2026",
            "Sleeper",
            "Last used",
        ]:
            self.assertIn(expected, html)


if __name__ == "__main__":
    unittest.main()

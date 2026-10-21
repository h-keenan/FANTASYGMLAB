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

    def test_last_league_option_resolves_rolled_over_account_league_to_current_season(self):
        # Real shape confirmed live against Sleeper's API (2026-10-21): a
        # continuing dynasty league gets a brand-new league_id each season
        # but the previous season's league_id keeps resolving too, so a
        # user's merged lookup_user_leagues() result legitimately contains
        # BOTH seasons of "the same" league as separate entries. If the
        # account's saved league_id is the now-stale 2025 one, naively
        # treating "still present in the list" as "still correct" sends a
        # returning user straight into last year's league (the reported bug).
        leagues = [
            {"league_id": "1354612949834035200", "name": "Dynasty Warriors", "season": "2026", "previous_league_id": "1181182612893843456"},
            {"league_id": "1181182612893843456", "name": "Dynasty Warriors", "season": "2025", "previous_league_id": "0"},
        ]

        self.assertEqual(
            onboarding_ui.last_league_option(
                username="progamer",
                leagues=leagues,
                account={"username": "progamer", "league_id": "1181182612893843456"},
            ),
            "1354612949834035200",
        )

    def test_last_league_option_resolves_rolled_over_current_league_to_current_season(self):
        leagues = [
            {"league_id": "1354612949834035200", "name": "Dynasty Warriors", "season": "2026", "previous_league_id": "1181182612893843456"},
            {"league_id": "1181182612893843456", "name": "Dynasty Warriors", "season": "2025", "previous_league_id": "0"},
        ]

        self.assertEqual(
            onboarding_ui.last_league_option(
                username="progamer",
                leagues=leagues,
                account=None,
                current_league_id="1181182612893843456",
                current_username="progamer",
            ),
            "1354612949834035200",
        )

    def test_last_league_option_leaves_non_rolled_over_leagues_unaffected(self):
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

    def test_last_league_option_drops_saved_league_with_no_current_rollover(self):
        # The saved league no longer exists at all (e.g. deleted on
        # Sleeper's side) and nothing points forward to it -- falls back to
        # no pre-selection rather than resolving to a bogus id.
        leagues = [
            {"league_id": "1", "name": "One"},
        ]

        self.assertEqual(
            onboarding_ui.last_league_option(
                username="user-a",
                leagues=leagues,
                account={"username": "user-a", "league_id": "99"},
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

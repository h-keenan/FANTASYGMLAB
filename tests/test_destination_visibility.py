import unittest
from pathlib import Path

from modules import app_config
from modules import brand_identity
from modules.ui_architecture import (
    PLATFORM_DESTINATIONS,
    current_platform_destinations,
    mobile_primary_destinations,
    mobile_secondary_destinations,
)


class TestDestinationVisibility(unittest.TestCase):
    def test_core_and_support_destinations_are_visible_by_default(self):
        destinations = current_platform_destinations(startup_mode=False)
        by_key = {destination.key: destination for destination in destinations}

        for key in (
            "dashboard",
            "my_team",
            "trade_hub",
            "trade_analyzer",
            "rankings",
            "draft_summary",
            "waivers",
            "alerts",
            "league_recaps",
            "news",
        ):
            self.assertIn(key, by_key)
            self.assertEqual(by_key[key].category, "CORE")

        for key in ("premium", "methodology", "about_disclaimer", "terms", "privacy", "no_affiliation"):
            self.assertIn(key, by_key)
            self.assertEqual(by_key[key].category, "SUPPORT")

    def test_experimental_destinations_are_hidden_by_default(self):
        visible_keys = {destination.key for destination in current_platform_destinations(startup_mode=False)}

        # Players graduated to CORE (#232) and is visible by default.
        self.assertIn("players", visible_keys)
        for key in (
            "teams",
            "weekly_report",
            "archetypes",
            "manager_tendencies",
            "live_draft",
            "player_detail",
            "gm_targets",
        ):
            self.assertNotIn(key, visible_keys)
        # News (general, non-roster NFL feed) graduated from ARCHIVED to CORE
        # to restore a third, standalone general-news surface alongside
        # Dashboard's tiles and the roster-scoped Alerts timeline.
        self.assertIn("news", visible_keys)

    def test_experimental_flag_exposes_conditional_only(self):
        visible = current_platform_destinations(startup_mode=False, show_experimental=True)
        visible_by_key = {destination.key: destination for destination in visible}

        # Archived duplicates stay hidden even when SHOW_EXPERIMENTAL is on.
        for key in (
            "weekly_report",
            "manager_tendencies",
            "teams",
            "player_detail",
            "archetypes",
        ):
            self.assertNotIn(key, visible_by_key)
        # News is CORE (always visible), not an archived duplicate.
        self.assertIn("news", visible_by_key)
        self.assertEqual(visible_by_key["trade_analyzer"].category, "CORE")
        # Graduated conditionals are visible for Ops via SHOW_EXPERIMENTAL.
        self.assertEqual(visible_by_key["live_draft"].category, "CONDITIONAL")
        self.assertEqual(visible_by_key["gm_targets"].category, "CONDITIONAL")
        self.assertEqual(visible_by_key["players"].category, "CORE")


    def test_mobile_secondary_normal_users_are_support_only_after_core_routes(self):
        secondary = mobile_secondary_destinations(startup_mode=False)
        secondary_by_key = {destination.key: destination for destination in secondary}

        self.assertIn("premium", secondary_by_key)
        self.assertIn("methodology", secondary_by_key)
        self.assertIn("about_disclaimer", secondary_by_key)
        self.assertNotIn("weekly_report", secondary_by_key)
        # Trade Analyzer is CORE but not a mobile primary tab — lives in secondary.
        self.assertIn("trade_analyzer", secondary_by_key)

    def test_all_destination_labels_are_clean_and_not_route_codes(self):
        all_labels = " ".join(destination.label for destination in PLATFORM_DESTINATIONS)

        for stale in ("HQ Dashboard", "TM My Team", "TR Trade Hub", "WV", "DR", "Action Center"):
            self.assertNotIn(stale, all_labels)


    def test_hidden_direct_routes_fall_back_without_feature_deletion(self):
        visible_keys = {destination.key for destination in current_platform_destinations(startup_mode=False)}
        all_keys = {destination.key for destination in PLATFORM_DESTINATIONS}

        self.assertIn("weekly_report", all_keys)
        self.assertNotIn("weekly_report", visible_keys)


    def _experimental_flag(self, raw):
        environ = {}
        if raw is not None:
            environ["DYNASTYGM_SHOW_EXPERIMENTAL"] = raw
        return app_config.config_bool(
            "DYNASTYGM_SHOW_EXPERIMENTAL",
            environ=environ,
            secrets={},
            local_secrets_path="tests/does-not-exist.toml",
        )

    def test_production_style_experimental_flag_values(self):
        for raw in ("true", "TRUE", "1", "yes"):
            with self.subTest(raw=raw):
                self.assertTrue(self._experimental_flag(raw))
        self.assertFalse(self._experimental_flag("false"))
        self.assertFalse(self._experimental_flag(None))

    def test_startup_mode_does_not_hide_live_draft_when_enabled(self):
        keys = {
            page.key
            for page in current_platform_destinations(
                startup_mode=True,
                show_experimental=self._experimental_flag("true"),
            )
        }
        self.assertIn("startup_draft_center", keys)
        self.assertIn("live_draft", keys)

    def test_live_draft_is_conditional_launch_surface(self):
        pages = current_platform_destinations(
            startup_mode=False,
            show_experimental=self._experimental_flag("TRUE"),
        )
        live_draft = next(page for page in pages if page.key == "live_draft")
        self.assertEqual(live_draft.category, "CONDITIONAL")
        # Active-draft enable path does not require SHOW_EXPERIMENTAL.
        active_only = {
            page.key
            for page in current_platform_destinations(
                startup_mode=False,
                enabled_experimental=("live_draft",),
            )
        }
        self.assertIn("live_draft", active_only)
        self.assertIn("trade_analyzer", active_only)


    def test_visibility_flag_is_not_cached_across_environment_changes(self):
        self.assertFalse(self._experimental_flag("false"))
        self.assertTrue(self._experimental_flag("yes"))
        self.assertFalse(self._experimental_flag(None))


if __name__ == "__main__":
    unittest.main()

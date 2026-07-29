import unittest
from pathlib import Path

from modules import app_config
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

        for key in ("dashboard", "my_team", "trade_hub", "rankings", "draft_summary", "waivers"):
            self.assertIn(key, by_key)
            self.assertEqual(by_key[key].category, "CORE")

        for key in ("premium", "about_disclaimer", "terms", "privacy", "no_affiliation"):
            self.assertIn(key, by_key)
            self.assertEqual(by_key[key].category, "SUPPORT")

    def test_experimental_destinations_are_hidden_by_default(self):
        visible_keys = {destination.key for destination in current_platform_destinations(startup_mode=False)}

        for key in (
            "players",
            "teams",
            "weekly_report",
            "news",
            "archetypes",
            "manager_tendencies",
            "trade_analyzer",
        ):
            self.assertNotIn(key, visible_keys)

    def test_experimental_flag_exposes_experimental_group(self):
        visible = current_platform_destinations(startup_mode=False, show_experimental=True)
        visible_by_key = {destination.key: destination for destination in visible}

        self.assertEqual(visible_by_key["weekly_report"].category, "EXPERIMENTAL")
        self.assertEqual(visible_by_key["trade_analyzer"].category, "EXPERIMENTAL")
        self.assertEqual(visible_by_key["archetypes"].category, "EXPERIMENTAL")

    def test_premium_is_support_not_primary_gm_route(self):
        primary_keys = {destination.key for destination in mobile_primary_destinations(startup_mode=False)}
        visible_by_key = {destination.key: destination for destination in current_platform_destinations(startup_mode=False)}
        app_source = Path("app.py").read_text(encoding="utf-8")

        self.assertNotIn("premium", primary_keys)
        self.assertEqual(visible_by_key["premium"].category, "SUPPORT")
        self.assertIn('"premium": "Free and Premium plan preview. Stripe is test-mode only."', app_source)
        self.assertNotIn("primary_labels = {", app_source)

    def test_mobile_secondary_normal_users_are_support_only_after_core_routes(self):
        secondary = mobile_secondary_destinations(startup_mode=False)
        secondary_by_key = {destination.key: destination for destination in secondary}

        self.assertIn("premium", secondary_by_key)
        self.assertIn("about_disclaimer", secondary_by_key)
        self.assertNotIn("weekly_report", secondary_by_key)
        self.assertNotIn("trade_analyzer", secondary_by_key)

    def test_all_destination_labels_are_clean_and_not_route_codes(self):
        all_labels = " ".join(destination.label for destination in PLATFORM_DESTINATIONS)

        for stale in ("HQ Dashboard", "TM My Team", "TR Trade Hub", "WV", "DR", "Action Center"):
            self.assertNotIn(stale, all_labels)

    def test_app_wires_destination_visibility_flags(self):
        app_source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn("DYNASTYGM_SHOW_EXPERIMENTAL", app_source)
        self.assertIn("DYNASTYGM_SHOW_DEV_DESTINATIONS", app_source)
        self.assertIn("current_platform_destinations(startup_mode, **destination_visibility)", app_source)
        self.assertIn("Core beta routes first", app_source)
        self.assertIn(" - Experimental", app_source)

    def test_gm_orb_opens_all_destinations_without_legacy_popup(self):
        app_source = Path("app.py").read_text(encoding="utf-8")
        nav_source = app_source.split("def render_mobile_navigation_shell", 1)[1].split("def safe_pick_value", 1)[0]

        self.assertIn("mobile_gm_sheet_trigger_", nav_source)
        self.assertIn("mobile-gm-floating-trigger-marker", nav_source)
        self.assertIn("mobile_gm_sheet_open_", nav_source)
        self.assertIn("Open All Destinations", nav_source)
        self.assertNotIn("st.popover(\"GM\"", nav_source)
        self.assertNotIn("mobile_gm_nav_", nav_source)
        self.assertNotIn("Open GM command menu", nav_source)
        self.assertNotIn("GM Command", nav_source)

    def test_navigation_uses_buttons_without_platform_radio_key_conflict(self):
        app_source = Path("app.py").read_text(encoding="utf-8")
        shell_source = app_source.split("destination_visibility = _destination_visibility_flags()", 1)[1].split("page_note_map = {", 1)[0]

        self.assertIn('key=f"desktop_nav_{destination.key}"', shell_source)
        self.assertIn('key=f"mobile_sheet_nav_{page.key}"', app_source)
        self.assertIn("_queue_platform_route(", shell_source)
        self.assertIn('source="sidebar_destination"', shell_source)
        self.assertNotIn('st.session_state["platform_nav_page"] = destination.key', shell_source)
        self.assertIn('st.session_state["platform_nav_group"] = destination.group', shell_source)
        self.assertNotIn('key="platform_nav_group"', shell_source)
        self.assertNotIn('key="platform_nav_page"', shell_source)
        self.assertNotIn("current_page = st.radio", shell_source)

    def test_header_and_fixed_controls_have_distinct_selectors(self):
        css = Path("modules/app_styles.py").read_text(encoding="utf-8")

        self.assertIn(".app-top-league-header", css)
        self.assertIn(".app-top-league-avatar img", css)
        self.assertIn("object-fit: cover", css)
        self.assertIn("object-position: center center", css)
        self.assertIn("mobile_gm_sheet_trigger_", css)
        self.assertIn("mobile-gm-floating-trigger-marker", css)
        self.assertNotIn("mobile_gm_command_menu_", css)
        self.assertIn("_global_feedback_control", css)
        self.assertIn("left: max(env(safe-area-inset-left", css)
        self.assertIn("right: calc(0.85rem + env(safe-area-inset-right))", css)

    def test_quick_view_avatar_containment_rules_remain(self):
        css = Path("modules/app_styles.py").read_text(encoding="utf-8")

        self.assertIn("div[data-testid=\"stDialog\"] .player-quick-view-avatar", css)
        self.assertIn("--avatar-size: 64px", css)
        self.assertIn("max-height: var(--avatar-size)", css)
        self.assertIn("--avatar-size: 58px", css)

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

    def test_live_draft_remains_experimental_in_non_startup_leagues(self):
        pages = current_platform_destinations(
            startup_mode=False,
            show_experimental=self._experimental_flag("TRUE"),
        )
        live_draft = next(page for page in pages if page.key == "live_draft")
        self.assertEqual(live_draft.category, "EXPERIMENTAL")

    def test_mobile_all_destinations_contains_live_draft(self):
        keys = {
            page.key
            for page in mobile_secondary_destinations(
                startup_mode=True,
                show_experimental=self._experimental_flag("1"),
            )
        }
        self.assertIn("live_draft", keys)
        app_source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn("all_pages = current_platform_destinations(startup_mode, **visibility)", app_source)

    def test_visibility_flag_is_not_cached_across_environment_changes(self):
        self.assertFalse(self._experimental_flag("false"))
        self.assertTrue(self._experimental_flag("yes"))
        self.assertFalse(self._experimental_flag(None))


if __name__ == "__main__":
    unittest.main()

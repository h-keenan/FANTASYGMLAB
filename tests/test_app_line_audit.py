import unittest
from pathlib import Path


class TestAppLineAudit(unittest.TestCase):
    def test_removed_dead_app_helpers_do_not_return(self):
        source = Path("app.py").read_text(encoding="utf-8")

        for stale_helper in (
            "def polish_chart(",
            "def render_player_image_or_placeholder(",
            "def mobile_nav_icon(",
            "def suggest_lineup(",
            "def _rank_fill_width(",
            "def _format_share_pct(",
            "def _has_player_stat_value(",
            "def _first_player_stat_value(",
            "def _format_player_stat_value(",
        ):
            self.assertNotIn(stale_helper, source)

    def test_app_has_single_destination_registry_source(self):
        app_source = Path("app.py").read_text(encoding="utf-8")
        architecture_source = Path("modules/ui_architecture.py").read_text(encoding="utf-8")

        self.assertIn("PLATFORM_DESTINATIONS", architecture_source)
        self.assertNotIn("MOBILE_NAV_ICONS", app_source)
        self.assertNotIn("PLATFORM_DESTINATIONS = (", app_source)

    def test_no_stale_mobile_route_code_labels_in_app(self):
        source = Path("app.py").read_text(encoding="utf-8")

        for stale_label in ("HQ Dashboard", "TM My Team", "TR Trade Hub", "WV Waivers", "DR Draft"):
            self.assertNotIn(stale_label, source)


if __name__ == "__main__":
    unittest.main()

import unittest

import pandas as pd

import app
from modules import player_profile_ui, player_quick_view


class TestPlayerProfileUI(unittest.TestCase):
    def test_avatar_html_wrapper_preserves_markup(self):
        expected = (
            "<div class='player-avatar dg-player-headshot dg-player-headshot--standard'>"
            "<span class='dg-player-headshot-fallback' aria-hidden='true'>TP</span>"
            "<img class='dg-player-headshot-image' src='https://example.com/player.png' alt='' decoding='async' "
            "onload=\"this.classList.add('is-loaded');if(!this.naturalWidth)this.remove();\" onerror=\"this.remove()\">"
            "</div>"
        )
        self.assertEqual(
            player_profile_ui.avatar_html(
                "https://example.com/player.png",
                "TP",
            ),
            expected,
        )
        self.assertEqual(
            app.avatar_html("https://example.com/player.png", "TP"),
            expected,
        )

    def test_player_display_name_wrapper_removes_raw_injury_prefix(self):
        row = {
            "name": "INJ Test Player",
            "status": "IR",
            "injury_status": "season-ending",
        }
        self.assertEqual(app.player_display_name(row), "Test Player")

    def test_stat_groups_preserve_zeroes_and_share_formatting(self):
        row = pd.Series(
            {
                "games_played": 2,
                "targets": 0,
                "receiving_yards": 120,
                "snap_share": 0.75,
                "fantasy_points_ppr": 27.0,
                "ppg": 13.5,
            }
        )

        module_groups = player_profile_ui.player_profile_stat_groups(row)
        wrapper_groups = app._player_profile_stat_groups(row)

        self.assertEqual(wrapper_groups, module_groups)
        self.assertEqual(player_profile_ui.format_share_pct(0.75), "75%")
        production = dict(
            (item["label"], item["value"])
            for label, items in module_groups
            if label == "NFL Stats"
            for item in items
        )
        self.assertEqual(production["Targets"], "0")
        self.assertEqual(production["Rec Yards"], "120")

    def test_college_stats_render_only_when_college_production_exists(self):
        row = pd.Series(
            {
                "college": "Texas",
                "college_receiving_yards": 950,
                "college_receiving_tds": 8,
            }
        )

        groups = player_profile_ui.player_profile_stat_groups(row)
        college = dict(
            (item["label"], item["value"])
            for label, items in groups
            if label == "College Stats"
            for item in items
        )

        self.assertEqual(college["College"], "Texas")
        self.assertEqual(college["Rec Yards"], "950")
        self.assertEqual(college["Rec TDs"], "8")

    def test_college_name_alone_does_not_fake_college_stats(self):
        groups = player_profile_ui.player_profile_stat_groups(pd.Series({"college": "Texas"}))
        labels = [label for label, _items in groups]

        self.assertNotIn("College Stats", labels)

    def test_college_production_field_debug_lists_present_and_missing_fields(self):
        row = pd.Series(
            {
                "college": "Texas",
                "college_receiving_yards": 950,
                "fantasy_points_ppr": 120.5,
            }
        )

        debug = player_profile_ui.player_stat_field_debug(row)

        self.assertIn("fantasy_points_ppr", debug["nfl_present"])
        self.assertIn("college", debug["college_identity_present"])
        self.assertIn("college_receiving_yards", debug["college_production_present"])
        self.assertIn("college_rushing_yards", debug["college_production_missing"])

    def test_missing_college_field_diagnostics_remain_available_to_developers(self):
        row = pd.Series({"college": "Texas", "years_exp": 0})
        message = player_profile_ui.missing_college_production_fields(row)

        self.assertIn("college_receiving_yards", message)

    def test_quick_view_source_uses_clear_stat_and_action_copy(self):
        source = (
            open("app.py", encoding="utf-8").read()
            + open("modules/player_quick_view.py", encoding="utf-8").read()
        )

        self.assertIn("player-quick-view-stats-empty", source)
        self.assertIn("No professional statistics are available for the loaded season.", source)
        self.assertIn("college_unavailable_message()", source)
        self.assertIn('"Open in Trade Hub"', source)
        self.assertIn('"Untouchable"', source)
        self.assertNotIn('"Open Trade Hub for Player"', source)
        self.assertNotIn('"Add Untouchable"', source)

    def test_quick_view_stats_use_dense_non_tappable_rows(self):
        source = (
            open("app.py", encoding="utf-8").read()
            + open("modules/player_quick_view.py", encoding="utf-8").read()
        )

        self.assertIn("player-quick-view-stat-grid", source)
        self.assertIn("player-quick-view-stat-row", source)
        self.assertIn("pqv-bio", source)
        self.assertIn("player-dossier-snapshot", source)
        self.assertIn("player-dossier-recommendation-context", source)
        self.assertIn("pqv_more_details_open_", source)
        self.assertIn("build_stats_view", source)
        self.assertIn("Professional Production", source)
        self.assertIn("Fantasy Production", source)
        self.assertIn("College Production", source)
        self.assertIn("Career Context", source)
        self.assertNotIn("render_summary_tiles(quick_view_tiles", source)

    def test_quick_view_stat_helpers_preserve_existing_values_by_section(self):
        row = pd.Series(
            {
                "position": "RB",
                "games_played": 10,
                "rushing_yards": 750,
                "receiving_yards": 210,
                "rushing_tds": 6,
                "targets": 42,
                "fantasy_points_ppr": 155.5,
                "fantasy_points_half_ppr": 142.0,
                "fantasy_points": 128.5,
                "ppg": 15.5,
                "snap_share": 0.71,
                "rush_share": 0.54,
            }
        )

        season = player_quick_view.build_stats_view(row).seasons[0]
        key_stats = {item.label: item.value for item in season.key_stats}
        fantasy_stats = {item.label: item.value for item in season.fantasy}
        usage_stats = {item.label: item.value for item in season.usage}

        self.assertEqual(key_stats["Rush Yards"], "750")
        self.assertEqual(key_stats["Targets"], "42")
        self.assertEqual(fantasy_stats["PPR"], "155.5")
        self.assertEqual(fantasy_stats["Half PPR"], "142.0")
        self.assertEqual(fantasy_stats["Standard"], "128.5")
        self.assertEqual(usage_stats["Snap %"], "71%")
        self.assertEqual(usage_stats["Carry Share"], "54%")


if __name__ == "__main__":
    unittest.main()

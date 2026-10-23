import unittest

import pandas as pd

from modules import player_profile_ui, player_quick_view


class TestPlayerProfileUI(unittest.TestCase):


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

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd
from modules import player_cards


class TestPlayerCards(unittest.TestCase):


    def test_overall_rating_gauge_renders_nothing_without_rating_column(self):
        self.assertEqual(player_cards.overall_rating_gauge_html({}), "")
        self.assertEqual(
            player_cards.overall_rating_gauge_html({"_overall_rating_col": None}),
            "",
        )

    def test_overall_rating_gauge_only_crowns_top_five_position_rank(self):
        uncrowned = player_cards.overall_rating_gauge_html(
            {"_overall_rating_col": 70, "canonical_position_rank": 12}
        )
        self.assertIn("dg-ovr-gauge", uncrowned)
        self.assertIn("70", uncrowned)
        self.assertNotIn("dg-ovr-gauge--crowned", uncrowned)

        crowned = player_cards.overall_rating_gauge_html(
            {"_overall_rating_col": 95, "canonical_position_rank": 1}
        )
        self.assertIn("dg-ovr-gauge--crowned", crowned)
        self.assertIn("95", crowned)

    def test_overall_rating_gauge_size_variants(self):
        sm = player_cards.overall_rating_gauge_html(
            {"_overall_rating_col": 60}, size="sm"
        )
        md = player_cards.overall_rating_gauge_html(
            {"_overall_rating_col": 60}, size="md"
        )
        self.assertIn("dg-ovr-gauge--sm", sm)
        self.assertNotIn("dg-ovr-gauge--md", sm)
        self.assertIn("dg-ovr-gauge--md", md)
        self.assertNotIn("dg-ovr-gauge--sm", md)


if __name__ == "__main__":
    unittest.main()

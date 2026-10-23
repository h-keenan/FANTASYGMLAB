import unittest
from pathlib import Path

from modules import account_store, auth_supabase, legal_pages


class TestLimitedReleaseReadiness(unittest.TestCase):
    def test_visible_player_explanation_copy_avoids_known_run_on_fragment(self):
        rankings_source = Path("modules/rankings.py").read_text(encoding="utf-8")

        self.assertNotIn("misses time\"", rankings_source)
        self.assertIn("misses time.\"", rankings_source)


if __name__ == "__main__":
    unittest.main()

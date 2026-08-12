import unittest
from pathlib import Path

import pandas as pd

from modules import platform_import_ui


class FakeESPNImportAdapter:
    def __init__(self, *, matched=9, total=10, teams=2):
        self.matched = matched
        self.total = total
        self.teams = teams

    def get_league(self, league_id, season=None, swid=None, espn_s2=None):
        if league_id == "private":
            raise RuntimeError(f"unauthorized for {swid} {espn_s2}")
        return {"league_id": league_id, "name": "ESPN Fake", "season": season}

    def get_rosters(self, league_id, season=None, swid=None, espn_s2=None):
        return [
            {"roster_id": index + 1, "players": [f"p{index}"], "platform_player_ids": [f"e{index}"]}
            for index in range(self.teams)
        ]

    def mapping_diagnostics(self):
        unmatched = max(0, self.total - self.matched)
        return {
            "total_espn_players_seen": self.total,
            "canonical_matched_count": self.matched,
            "unmatched_count": unmatched,
            "ambiguous_count": 0,
            "unmatched_examples": [{"name": "Unmatched", "position": "WR", "team": "DAL"}] if unmatched else [],
            "ambiguous_examples": [],
        }


class TestESPNImportUI(unittest.TestCase):
    def test_sleeper_remains_default_import_platform(self):
        self.assertEqual(platform_import_ui.DEFAULT_LEAGUE_IMPORT_PLATFORM, "Sleeper")

    def test_import_panel_copy_labels_sleeper_recommended_and_espn_limited(self):
        source = Path("modules/platform_import_ui.py").read_text(encoding="utf-8")

        self.assertIn("Import your Sleeper league", source)
        self.assertEqual(platform_import_ui.DEFAULT_LEAGUE_IMPORT_PLATFORM, "Sleeper")
        self.assertIn("ESPN is experimental", source)
        self.assertIn("ESPN experimental", source)

    def test_launch_screen_renders_account_before_import(self):
        source = Path("app.py").read_text(encoding="utf-8")
        account_idx = source.index("account_ui.render_mobile_auth_entry")
        import_idx = source.index("platform_import_ui.render_platform_import_panel")

        self.assertLess(account_idx, import_idx)

    def test_good_mapping_rate_allows_limited_proceed(self):
        result = platform_import_ui.build_espn_import_result(
            league_id="123",
            season=2026,
            df_players=pd.DataFrame(),
            adapter_factory=lambda **kwargs: FakeESPNImportAdapter(matched=9, total=10),
        )

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["can_proceed"])
        self.assertEqual(result["diagnostics"]["teams_found"], 2)

    def test_medium_mapping_rate_warns_but_allows_degraded_proceed(self):
        result = platform_import_ui.build_espn_import_result(
            league_id="123",
            season=2026,
            df_players=pd.DataFrame(),
            adapter_factory=lambda **kwargs: FakeESPNImportAdapter(matched=7, total=10),
        )

        self.assertEqual(result["status"], "degraded")
        self.assertTrue(result["can_proceed"])

    def test_low_mapping_rate_blocks_proceed(self):
        result = platform_import_ui.build_espn_import_result(
            league_id="123",
            season=2026,
            df_players=pd.DataFrame(),
            adapter_factory=lambda **kwargs: FakeESPNImportAdapter(matched=5, total=10),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["can_proceed"])

    def test_private_cookie_error_is_redacted(self):
        result = platform_import_ui.build_espn_import_result(
            league_id="private",
            season=2026,
            df_players=pd.DataFrame(),
            swid="{secret-swid}",
            espn_s2="secret-token",
            adapter_factory=lambda **kwargs: FakeESPNImportAdapter(),
        )

        self.assertFalse(result["ok"])
        self.assertIn("Private leagues require valid SWID and ESPN_S2 cookies", result["error"])
        self.assertNotIn("secret-token", result["error"])
        self.assertNotIn("secret-swid", result["error"])

    def test_store_espn_import_result_does_not_store_cookies(self):
        session_state = {}
        result = {
            "platform": "espn",
            "can_proceed": True,
            "swid": "{secret}",
            "espn_s2": "secret-token",
            "diagnostics": {"total_espn_players_seen": 1},
        }

        platform_import_ui.store_espn_import_result(session_state, result)

        stored = session_state["espn_import_result"]
        self.assertEqual(session_state["active_platform"], "espn")
        self.assertTrue(session_state["espn_limited_mode"])
        self.assertNotIn("swid", stored)
        self.assertNotIn("espn_s2", stored)

    def test_unsupported_espn_features_are_flagged_as_degraded(self):
        degraded = platform_import_ui.ESPN_LIMITED_FEATURES["degraded"]

        self.assertTrue(any("Draft Assistant" in item for item in degraded))
        self.assertTrue(any("Trade Hub" in item for item in degraded))

    def test_classify_mapping_handles_no_players(self):
        quality = platform_import_ui.classify_mapping_quality(
            {"total_espn_players_seen": 0, "canonical_matched_count": 0}
        )

        self.assertEqual(quality["status"], "fail")
        self.assertFalse(quality["can_proceed"])


if __name__ == "__main__":
    unittest.main()

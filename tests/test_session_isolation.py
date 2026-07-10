import unittest
from unittest.mock import patch, MagicMock
import sys

# Define a custom dictionary-like class to mock st.session_state
class MockSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)
    def __setattr__(self, name, value):
        self[name] = value

class TestSessionIsolation(unittest.TestCase):
    def setUp(self):
        # Create a fresh mock session state for each test
        self.session_state = MockSessionState()
        self.patcher_st = patch('streamlit.session_state', self.session_state)
        self.patcher_st.start()

        # Patch functions that perform I/O or require runtime database/API
        self.patch_get_current_account = patch('app.get_current_account')
        self.mock_get_current_account = self.patch_get_current_account.start()
        
        self.patch_get_user_leagues = patch('app.get_user_leagues')
        self.mock_get_user_leagues = self.patch_get_user_leagues.start()
        
        self.patch_get_user_roster_id = patch('app.get_user_roster_id')
        self.mock_get_user_roster_id = self.patch_get_user_roster_id.start()
        
        self.patch_get_league = patch('app.get_league')
        self.mock_get_league = self.patch_get_league.start()
        
        self.patch_persist = patch('app._persist_active_account_context')
        self.mock_persist = self.patch_persist.start()

    def tearDown(self):
        self.patcher_st.stop()
        self.patch_get_current_account.stop()
        self.patch_get_user_leagues.stop()
        self.patch_get_user_roster_id.stop()
        self.patch_get_league.stop()
        self.patch_persist.stop()

    def test_fresh_session_shows_onboarding(self):
        # A fresh session has an empty session state and no sentinel
        self.session_state.clear()
        
        # Simulate data/accounts.json containing Harry's active account
        self.mock_get_current_account.return_value = {
            "name": "1",
            "username": "harryhard",
            "league_id": "1353858597108350976"
        }
        
        # Import app here so the mock setup is fully active
        import app
        context = app.resolve_active_league_context()
        
        # Verify that the fresh session DID NOT restore harryhard or the league
        # (Must remain empty/None to force onboarding screen)
        self.assertEqual(context["username"], "")
        self.assertIsNone(context["selected_league_id"])
        self.assertEqual(self.session_state.get("username"), None)
        self.assertEqual(self.session_state.get("selected_league_id"), None)

    def test_no_harry_assumption_with_fake_user(self):
        # Verify alternate user fixture: the app does not assume harryhard
        self.session_state.clear()
        self.session_state["_identity_established"] = True
        self.session_state["username"] = "testuser_fixture"
        self.session_state["selected_league_id"] = "111111111111111111"
        self.session_state["leagues_for_user"] = [
            {"league_id": "111111111111111111", "name": "Test League", "season": "2026"}
        ]
        self.session_state["leagues_for_user_username"] = "testuser_fixture"
        
        self.mock_get_user_roster_id.return_value = 5
        
        import app
        context = app.resolve_active_league_context()
        
        self.assertEqual(context["username"], "testuser_fixture")
        self.assertEqual(context["selected_league_id"], "111111111111111111")
        self.assertEqual(context["my_roster_id"], 5)
        self.assertNotEqual(context["username"], "harryhard")

    def test_explicit_login_sets_sentinel(self):
        # Typing a username and clicking submit sets _identity_established sentinel
        self.session_state.clear()
        
        fake_leagues = [
            {"league_id": "222222222222222222", "name": "Fake League 2", "season": "2026"}
        ]
        self.mock_get_user_leagues.return_value = fake_leagues
        
        import app
        leagues = app.load_leagues_for_username("another_user")
        
        # Verify that explicit actions establish identity
        self.assertTrue(self.session_state.get("_identity_established"))
        self.assertEqual(self.session_state.get("username"), "another_user")
        self.assertEqual(leagues, fake_leagues)
        self.assertEqual(
            self.session_state.get("selected_league_id"),
            "222222222222222222",
        )
        self.assertTrue(self.session_state.get("_league_selection_established"))

    def test_multiple_leagues_require_explicit_selection(self):
        self.session_state.clear()
        self.mock_get_user_leagues.return_value = [
            {"league_id": "league-1", "name": "League One", "season": "2026"},
            {"league_id": "league-2", "name": "League Two", "season": "2026"},
        ]
        self.mock_get_current_account.return_value = {
            "name": "1",
            "username": "multi_user",
            "league_id": "league-2",
        }

        import app
        leagues = app.load_leagues_for_username("multi_user")

        self.assertEqual(len(leagues), 2)
        self.assertIsNone(self.session_state.get("selected_league_id"))
        self.assertFalse(self.session_state.get("_league_selection_established"))
        self.assertEqual(self.session_state.get("last_league_option_id"), "league-2")

    def test_username_submit_does_not_silently_restore_last_league(self):
        self.session_state.clear()
        self.session_state["_identity_established"] = True
        self.session_state["_league_selection_established"] = False
        self.session_state["username"] = "multi_user"
        self.session_state["leagues_for_user"] = [
            {"league_id": "league-1", "name": "League One", "season": "2026"},
            {"league_id": "league-2", "name": "League Two", "season": "2026"},
        ]
        self.session_state["leagues_for_user_username"] = "multi_user"
        self.mock_get_current_account.return_value = {
            "name": "1",
            "username": "multi_user",
            "league_id": "league-2",
        }

        import app
        context = app.resolve_active_league_context()

        self.assertIsNone(context["selected_league_id"])
        self.assertIsNone(self.session_state.get("selected_league_id"))

    def test_continue_last_league_is_an_explicit_selection(self):
        self.session_state.clear()
        self.session_state["username"] = "multi_user"
        self.session_state["leagues_for_user"] = [
            {"league_id": "league-1", "name": "League One", "season": "2026"},
            {"league_id": "league-2", "name": "League Two", "season": "2026"},
        ]

        import app
        app.set_selected_league("league-2", "League Two", route_to_dashboard=True)

        self.assertEqual(self.session_state.get("selected_league_id"), "league-2")
        self.assertTrue(self.session_state.get("_league_selection_established"))
        self.assertEqual(self.session_state.get("_pending_platform_route"), "dashboard")

    def test_switching_users_clears_previous_league_context(self):
        self.session_state.clear()
        self.session_state.update(
            {
                "username": "first_user",
                "selected_league_id": "old-league",
                "selected_league_name": "Old League",
                "selected_team_roster_id": 9,
                "player_quick_view_player_id": "player-1",
            }
        )
        self.mock_get_user_leagues.return_value = [
            {"league_id": "new-1", "name": "New One", "season": "2026"},
            {"league_id": "new-2", "name": "New Two", "season": "2026"},
        ]
        self.mock_get_current_account.return_value = {
            "name": "1",
            "username": "first_user",
            "league_id": "old-league",
        }

        import app
        app.load_leagues_for_username("second_user")

        self.assertEqual(self.session_state.get("username"), "second_user")
        self.assertIsNone(self.session_state.get("selected_league_id"))
        self.assertNotIn("selected_team_roster_id", self.session_state)
        self.assertNotIn("player_quick_view_player_id", self.session_state)
        self.assertEqual(self.session_state.get("last_league_option_id"), "")

    def test_explicit_league_selection_sets_sentinel(self):
        # Selecting a league also sets _identity_established sentinel
        self.session_state.clear()
        self.session_state["username"] = "another_user"
        self.session_state["leagues_for_user"] = [
            {"league_id": "333333333333333333", "name": "Fake League 3", "season": "2026"}
        ]
        
        import app
        app.set_selected_league("333333333333333333", "Fake League 3")
        
        self.assertTrue(self.session_state.get("_identity_established"))
        self.assertTrue(self.session_state.get("_league_selection_established"))
        self.assertEqual(self.session_state.get("selected_league_id"), "333333333333333333")

    def test_header_saved_league_switch_uses_existing_selection_state(self):
        self.session_state.clear()
        self.session_state.update(
            {
                "username": "multi_user",
                "selected_league_id": "league-1",
                "selected_league_name": "League One (S2026)",
                "selected_team_roster_id": 1,
                "selected_team_name": "Old Team",
                "player_quick_view_player_id": "player-1",
                "leagues_for_user": [
                    {"league_id": "league-1", "name": "League One", "season": "2026"},
                    {"league_id": "league-2", "name": "League Two", "season": "2026"},
                ],
                "account_saved_leagues_cache": [
                    {
                        "league_id": "league-2",
                        "league_name": "League Two",
                        "season": "2026",
                        "platform": "Sleeper",
                        "sleeper_username": "multi_user",
                        "roster_id": "7",
                    }
                ],
            }
        )

        import app
        with patch("app._persist_supabase_account_context"), patch("app._clear_player_quick_view") as clear_quick_view:
            app._switch_to_saved_league(
                {
                    "league_id": "league-2",
                    "league_name": "League Two",
                    "sleeper_username": "multi_user",
                    "roster_id": "7",
                },
                current_page="my_team",
            )

        self.assertEqual(self.session_state.get("selected_league_id"), "league-2")
        self.assertEqual(self.session_state.get("selected_league_name"), "League Two (S2026)")
        self.assertTrue(self.session_state.get("_league_selection_established"))
        self.assertNotIn("selected_team_roster_id", self.session_state)
        self.assertNotIn("selected_team_name", self.session_state)
        self.assertNotIn("active_league_context", self.session_state)
        self.assertNotIn("_pending_platform_route", self.session_state)
        clear_quick_view.assert_called()

    def test_header_saved_league_row_marks_current_and_metadata(self):
        import app
        html = app._league_switch_row_html(
            {
                "league_id": "league-1",
                "league_name": "League One",
                "season": "2026",
                "platform": "Sleeper",
                "team_name": "Starter Squad",
                "is_default": True,
            },
            is_current=True,
        )

        self.assertIn("league-switch-row-current", html)
        self.assertIn("League One", html)
        self.assertIn("S2026 | Sleeper | Starter Squad", html)
        self.assertIn("Current", html)
        self.assertIn("Default", html)

    def test_trade_hub_handoff_clears_quick_view_and_preserves_identity(self):
        self.session_state.clear()
        self.session_state.update(
            {
                "_identity_established": True,
                "username": "trade_test_user",
                "selected_league_id": "444444444444444444",
                "selected_league_name": "Trade Test League",
                "selected_roster_id": 7,
                "player_quick_view_player_id": "player-123",
                "player_quick_view_source_label": "My Team",
                "player_quick_view_source_note": "Trade candidate",
                "player_quick_view_status_label": "Shop",
            }
        )

        import app

        active_context = {
            "username": "trade_test_user",
            "selected_league_id": "444444444444444444",
            "selected_league_name": "Trade Test League",
            "my_roster_id": 7,
        }
        with (
            patch("app.resolve_active_league_context", return_value=active_context),
            patch("app._player_on_active_roster", return_value=True),
            patch("app._queue_platform_route") as queue_route,
            patch("app.st.rerun"),
        ):
            app._open_trade_hub_for_player_focus(
                player_row={"player_id": "player-123"},
                selected_league_id="444444444444444444",
                my_roster_id=7,
                username="trade_test_user",
            )

        for key in app.PLAYER_QUICK_VIEW_STATE_KEYS:
            self.assertNotIn(key, self.session_state)
        self.assertEqual(self.session_state["username"], "trade_test_user")
        self.assertEqual(self.session_state["selected_league_id"], "444444444444444444")
        self.assertEqual(self.session_state["selected_league_name"], "Trade Test League")
        self.assertEqual(self.session_state["selected_roster_id"], 7)
        self.assertEqual(
            self.session_state["trade_hub_focus_player_id_444444444444444444"],
            "player-123",
        )
        self.assertEqual(
            self.session_state["trade_hub_focus_mode_444444444444444444"],
            "my_player",
        )
        queue_route.assert_called_once_with("trade_hub")

    def test_trade_card_html_is_not_indented_as_markdown_code(self):
        import app

        with patch("app.st.html") as html_renderer:
            app.render_trade_idea_card(
                {
                    "partner_team_name": "Test Partner",
                    "tag": "Test Trade",
                    "my_score": 100,
                    "their_score": 100,
                    "trade_gain": 0,
                    "send_assets": [],
                    "receive_assets": [],
                },
                0,
            )

        rendered_html = html_renderer.call_args.args[0]
        self.assertTrue(rendered_html.startswith('<div class="trade-idea-card'))
        html_renderer.assert_called_once()
        self.assertFalse(
            any(line.startswith(("    ", "\t")) for line in rendered_html.splitlines())
        )
        for css_class in [
            "trade-matchup",
            "trade-side",
            "trade-detail-summary",
            "trade-score-chip-row",
            "trade-value-meter",
            "trade-delta-pill",
        ]:
            self.assertIn(css_class, rendered_html)
        self.assertEqual(rendered_html.count("<div"), rendered_html.count("</div>"))

    def test_trade_html_normalizer_removes_nested_markdown_code_indentation(self):
        import app

        raw_html = """
            <div class="trade-idea-card">
                </div>
                <div class="trade-matchup">
                    <div class="trade-side">Assets</div>
                </div>
            </div>
        """

        normalized = app._normalize_trade_html(raw_html)

        self.assertTrue(normalized.startswith('<div class="trade-idea-card">'))
        self.assertFalse(
            any(line.startswith(("    ", "\t")) for line in normalized.splitlines())
        )
        self.assertIn('<div class="trade-matchup">', normalized)

    def test_trade_result_panel_uses_normalized_html_renderer(self):
        import app

        with patch("app.st.html") as html_renderer:
            app.render_trade_result_panel([], [], "Dynasty Score")

        rendered_html = html_renderer.call_args.args[0]
        self.assertTrue(rendered_html.startswith('<div class="trade-idea-card'))
        self.assertFalse(
            any(line.startswith(("    ", "\t")) for line in rendered_html.splitlines())
        )
        self.assertIn("trade-matchup", rendered_html)
        self.assertIn("trade-value-meter", rendered_html)
        self.assertEqual(rendered_html.count("<div"), rendered_html.count("</div>"))


if __name__ == "__main__":
    unittest.main()

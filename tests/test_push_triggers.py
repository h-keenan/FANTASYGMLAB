"""modules.push_triggers — the basic automated push-trigger sweep.

Mocks requests (the Supabase service-role + Sleeper I/O boundary) and the
dashboard_engine composition call, matching the mocking convention used
across the mobile API tests.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pandas as pd

from modules import push_tokens, push_triggers


def _config() -> push_triggers.PushTriggerConfig:
    return push_triggers.PushTriggerConfig(url="https://example.supabase.co", service_role_key="service-role-key")


def test_load_push_trigger_config_reads_expected_env_vars():
    config = push_triggers.load_push_trigger_config(
        environ={"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    )
    assert config.configured
    assert config.url == "https://x.supabase.co"
    assert config.service_role_key == "srk"


def test_load_push_trigger_config_not_configured_without_service_role_key():
    config = push_triggers.load_push_trigger_config(environ={"SUPABASE_URL": "https://x.supabase.co"})
    assert not config.configured


def test_run_push_trigger_sweep_fails_soft_when_not_configured():
    stats = push_triggers.run_push_trigger_sweep(environ={})
    assert stats["ok"] is False
    assert stats["configured"] is False
    assert stats["pushes_sent"] == 0
    assert stats["errors"]


def test_fetch_push_recipients_groups_tokens_by_user():
    response = Mock(status_code=200)
    response.json.return_value = [
        {"user_id": "u1", "expo_push_token": "ExponentPushToken[a]"},
        {"user_id": "u1", "expo_push_token": "ExponentPushToken[b]"},
        {"user_id": "u2", "expo_push_token": "ExponentPushToken[c]"},
    ]
    with patch("requests.get", return_value=response):
        recipients = push_triggers.fetch_push_recipients(_config())
    assert recipients == {
        "u1": ["ExponentPushToken[a]", "ExponentPushToken[b]"],
        "u2": ["ExponentPushToken[c]"],
    }


def test_fetch_push_recipients_returns_empty_when_not_configured():
    unconfigured = push_triggers.PushTriggerConfig()
    with patch("requests.get") as mock_get:
        recipients = push_triggers.fetch_push_recipients(unconfigured)
    assert recipients == {}
    mock_get.assert_not_called()


def test_resolve_roster_for_sleeper_user_matches_owner_id():
    rosters = [{"roster_id": 1, "owner_id": "other"}, {"roster_id": 2, "owner_id": "me"}]
    match = push_triggers.resolve_roster_for_sleeper_user(rosters, "me")
    assert match == {"roster_id": 2, "owner_id": "me"}
    assert push_triggers.resolve_roster_for_sleeper_user(rosters, "nobody") is None


def test_already_notified_batch_returns_matching_ids():
    response = Mock(status_code=200)
    response.json.return_value = [{"recommendation_id": "rec1"}]
    with patch("requests.get", return_value=response) as mock_get:
        result = push_triggers.already_notified_batch(_config(), user_id="u1", recommendation_ids=["rec1", "rec2"])
    assert result == {"rec1"}
    # One round trip covers every id, not one per id.
    assert mock_get.call_count == 1
    assert mock_get.call_args.kwargs["params"]["recommendation_id"] == "in.(rec1,rec2)"


def test_already_notified_batch_empty_when_no_rows():
    response = Mock(status_code=200)
    response.json.return_value = []
    with patch("requests.get", return_value=response):
        result = push_triggers.already_notified_batch(_config(), user_id="u1", recommendation_ids=["rec1"])
    assert result == set()


def test_already_notified_batch_returns_empty_set_without_ids():
    with patch("requests.get") as mock_get:
        result = push_triggers.already_notified_batch(_config(), user_id="u1", recommendation_ids=[])
    assert result == set()
    mock_get.assert_not_called()


def test_already_notified_batch_fails_closed_on_transport_error():
    with patch("requests.get", side_effect=Exception("network down")):
        result = push_triggers.already_notified_batch(_config(), user_id="u1", recommendation_ids=["rec1", "rec2"])
    assert result == {"rec1", "rec2"}


def test_already_notified_batch_fails_closed_on_unsafe_id_characters():
    # A literal "," or ")" would corrupt the in.(...) filter — refuse to
    # send it and treat every id as already-notified rather than push
    # something the filter might have silently mismatched.
    with patch("requests.get") as mock_get:
        result = push_triggers.already_notified_batch(_config(), user_id="u1", recommendation_ids=["rec1", "a)b"])
    assert result == {"rec1", "a)b"}
    mock_get.assert_not_called()


def test_run_push_trigger_sweep_sends_once_and_dedupes_second_run():
    config_env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    fake_item = Mock(category="top_priority", headline="Trade with Rival GM", recommendation_id="rec-abc")
    fake_briefing = Mock(items=[fake_item])
    players_df = pd.DataFrame([{"player_id": "p1", "position": "RB", "dynasty_score": 50}])

    push_tokens_response = Mock(status_code=200)
    push_tokens_response.json.return_value = [{"user_id": "u1", "expo_push_token": "ExponentPushToken[a]"}]
    profiles_response = Mock(status_code=200)
    profiles_response.json.return_value = [{"user_id": "u1", "sleeper_username": "gm_dynasty"}]
    preferences_response = Mock(status_code=200)
    preferences_response.json.return_value = []
    # league-1 already has a GM stance stored, so the one-time reminder
    # doesn't fire and pollute this test's pushes_sent count.
    gm_stance_response = Mock(status_code=200)
    gm_stance_response.json.return_value = [
        {"user_id": "u1", "settings": {"team_strategy_by_league": {"league-1": "retool"}}}
    ]
    not_notified_response = Mock(status_code=200)
    not_notified_response.json.return_value = []
    already_notified_response = Mock(status_code=200)
    already_notified_response.json.return_value = [{"recommendation_id": "rec-abc"}]

    with patch(
        "modules.push_triggers.load_valued_players", return_value=(players_df, "dynasty_score")
    ):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper_leagues.get_user_leagues",
                return_value=[{"league_id": "league-1", "name": "Test League"}],
            ):
                with patch("modules.sleeper.get_league", return_value={"name": "Test League"}):
                    with patch(
                        "modules.sleeper.get_rosters",
                        return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": ["p1"]}],
                    ):
                        with patch(
                            "modules.dashboard_engine.compose_next_move_briefing",
                            return_value=fake_briefing,
                        ):
                            with patch("modules.push_triggers.recap_push_item", return_value=None):
                                with patch(
                                    "requests.get",
                                    side_effect=[
                                        push_tokens_response,
                                        profiles_response,
                                        preferences_response,
                                        gm_stance_response,
                                        not_notified_response,
                                    ],
                                ):
                                    with patch("requests.post") as mock_post:
                                        mock_post.return_value = Mock(status_code=200, json=lambda: {"data": [{"status": "ok"}]})
                                        first_stats = push_triggers.run_push_trigger_sweep(environ=config_env)

    assert first_stats["configured"] is True
    assert first_stats["accounts_checked"] == 1
    assert first_stats["leagues_checked"] == 1
    assert first_stats["pushes_sent"] == 1
    assert not first_stats["errors"]
    # First post is the Expo push send, second is the dedup-log insert.
    push_call = mock_post.call_args_list[0]
    assert push_call.args[0] == push_tokens.EXPO_PUSH_API_URL
    assert push_call.kwargs["json"][0]["to"] == "ExponentPushToken[a]"
    log_call = mock_post.call_args_list[1]
    assert "push_notification_log" in log_call.args[0]
    assert log_call.kwargs["json"]["recommendation_id"] == "rec-abc"

    # Second sweep: the log now reports this recommendation as already sent.
    with patch(
        "modules.push_triggers.load_valued_players", return_value=(players_df, "dynasty_score")
    ):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper_leagues.get_user_leagues",
                return_value=[{"league_id": "league-1", "name": "Test League"}],
            ):
                with patch("modules.sleeper.get_league", return_value={"name": "Test League"}):
                    with patch(
                        "modules.sleeper.get_rosters",
                        return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": ["p1"]}],
                    ):
                        with patch(
                            "modules.dashboard_engine.compose_next_move_briefing",
                            return_value=fake_briefing,
                        ):
                            with patch("modules.push_triggers.recap_push_item", return_value=None):
                                with patch(
                                    "requests.get",
                                    side_effect=[
                                        push_tokens_response,
                                        profiles_response,
                                        preferences_response,
                                        gm_stance_response,
                                        already_notified_response,
                                    ],
                                ):
                                    with patch("requests.post") as mock_post_second:
                                        mock_post_second.return_value = Mock(status_code=200, json=lambda: {"data": []})
                                        second_stats = push_triggers.run_push_trigger_sweep(environ=config_env)

    assert second_stats["pushes_sent"] == 0
    mock_post_second.assert_not_called()


def test_recap_push_item_none_when_no_completed_week():
    with patch("modules.league_recaps.league_history_window", return_value=(1, 1, 1)):
        with patch("modules.league_recaps.build_matchup_history_rows", return_value=[]):
            with patch("modules.league_recaps.completed_recap_week", return_value=0):
                assert push_triggers.recap_push_item("league-1", {"name": "Test League"}) is None


def test_recap_push_item_builds_a_stable_dedup_id_per_week():
    with patch("modules.league_recaps.league_history_window", return_value=(1, 3, 3)):
        with patch("modules.league_recaps.build_matchup_history_rows", return_value=[{"week": 3}]):
            with patch("modules.league_recaps.completed_recap_week", return_value=3):
                item = push_triggers.recap_push_item("league-1", {"name": "Test League"})
    assert item == {
        "league_id": "league-1",
        "league_name": "Test League",
        "category": "recap",
        "headline": "Week 3 recap is ready",
        "recommendation_id": "recap:league-1:3",
    }


def test_run_push_trigger_sweep_also_pushes_a_ready_recap():
    config_env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    players_df = pd.DataFrame([{"player_id": "p1", "position": "RB", "dynasty_score": 50}])

    push_tokens_response = Mock(status_code=200)
    push_tokens_response.json.return_value = [{"user_id": "u1", "expo_push_token": "ExponentPushToken[a]"}]
    profiles_response = Mock(status_code=200)
    profiles_response.json.return_value = [{"user_id": "u1", "sleeper_username": "gm_dynasty"}]
    preferences_response = Mock(status_code=200)
    preferences_response.json.return_value = []
    gm_stance_response = Mock(status_code=200)
    gm_stance_response.json.return_value = [
        {"user_id": "u1", "settings": {"team_strategy_by_league": {"league-1": "retool"}}}
    ]
    not_notified_response = Mock(status_code=200)
    not_notified_response.json.return_value = []

    with patch("modules.push_triggers.load_valued_players", return_value=(players_df, "dynasty_score")):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper_leagues.get_user_leagues",
                return_value=[{"league_id": "league-1", "name": "Test League"}],
            ):
                with patch("modules.sleeper.get_league", return_value={"name": "Test League"}):
                    with patch(
                        "modules.sleeper.get_rosters",
                        return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": ["p1"]}],
                    ):
                        with patch(
                            "modules.dashboard_engine.compose_next_move_briefing",
                            return_value=Mock(items=[]),
                        ):
                            with patch(
                                "modules.push_triggers.recap_push_item",
                                return_value={
                                    "league_id": "league-1",
                                    "league_name": "Test League",
                                    "category": "recap",
                                    "headline": "Week 3 recap is ready",
                                    "recommendation_id": "recap:league-1:3",
                                },
                            ):
                                with patch(
                                    "requests.get",
                                    side_effect=[
                                        push_tokens_response,
                                        profiles_response,
                                        preferences_response,
                                        gm_stance_response,
                                        not_notified_response,
                                    ],
                                ):
                                    with patch("requests.post") as mock_post:
                                        mock_post.return_value = Mock(
                                            status_code=200, json=lambda: {"data": [{"status": "ok"}]}
                                        )
                                        stats = push_triggers.run_push_trigger_sweep(environ=config_env)

    assert stats["pushes_sent"] == 1
    push_call = mock_post.call_args_list[0]
    assert push_call.kwargs["json"][0]["title"] == "Recap Ready — Test League"
    assert push_call.kwargs["json"][0]["body"] == "Week 3 recap is ready"


def test_injury_status_push_items_fires_for_risk_status():
    players_df = pd.DataFrame(
        [
            {"player_id": "p1", "name": "Hurt Guy", "injury_status": "Out"},
            {"player_id": "p2", "name": "Fine Guy", "injury_status": ""},
        ]
    )
    items = push_triggers.injury_status_push_items(
        league_id="league-1",
        league_name="Test League",
        roster_player_ids={"p1", "p2"},
        players_df=players_df,
    )
    assert items == [
        {
            "league_id": "league-1",
            "league_name": "Test League",
            "category": "injury",
            "headline": "Hurt Guy is now Out",
            "recommendation_id": "injury:p1:out",
        }
    ]


def test_injury_status_push_items_excludes_questionable():
    players_df = pd.DataFrame([{"player_id": "p1", "name": "Iffy Guy", "injury_status": "Questionable"}])
    items = push_triggers.injury_status_push_items(
        league_id="league-1",
        league_name="Test League",
        roster_player_ids={"p1"},
        players_df=players_df,
    )
    assert items == []


def test_injury_status_push_items_ignores_non_roster_players():
    players_df = pd.DataFrame([{"player_id": "other", "name": "Not Mine", "injury_status": "Out"}])
    items = push_triggers.injury_status_push_items(
        league_id="league-1",
        league_name="Test League",
        roster_player_ids={"p1"},
        players_df=players_df,
    )
    assert items == []


def test_injury_status_push_items_empty_without_column_or_roster():
    assert push_triggers.injury_status_push_items(
        league_id="league-1",
        league_name="Test League",
        roster_player_ids=set(),
        players_df=pd.DataFrame([{"player_id": "p1", "injury_status": "Out"}]),
    ) == []
    assert push_triggers.injury_status_push_items(
        league_id="league-1",
        league_name="Test League",
        roster_player_ids={"p1"},
        players_df=pd.DataFrame([{"player_id": "p1"}]),
    ) == []


def test_run_push_trigger_sweep_also_pushes_an_injury_status(monkeypatch):
    config_env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    players_df = pd.DataFrame(
        [{"player_id": "p1", "name": "Hurt Guy", "position": "RB", "dynasty_score": 50, "injury_status": "Out"}]
    )

    push_tokens_response = Mock(status_code=200)
    push_tokens_response.json.return_value = [{"user_id": "u1", "expo_push_token": "ExponentPushToken[a]"}]
    profiles_response = Mock(status_code=200)
    profiles_response.json.return_value = [{"user_id": "u1", "sleeper_username": "gm_dynasty"}]
    preferences_response = Mock(status_code=200)
    preferences_response.json.return_value = []
    gm_stance_response = Mock(status_code=200)
    gm_stance_response.json.return_value = [
        {"user_id": "u1", "settings": {"team_strategy_by_league": {"league-1": "retool"}}}
    ]
    not_notified_response = Mock(status_code=200)
    not_notified_response.json.return_value = []

    with patch("modules.push_triggers.load_valued_players", return_value=(players_df, "dynasty_score")):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper_leagues.get_user_leagues",
                return_value=[{"league_id": "league-1", "name": "Test League"}],
            ):
                with patch("modules.sleeper.get_league", return_value={"name": "Test League"}):
                    with patch(
                        "modules.sleeper.get_rosters",
                        return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": ["p1"]}],
                    ):
                        with patch(
                            "modules.dashboard_engine.compose_next_move_briefing",
                            return_value=Mock(items=[]),
                        ):
                            with patch("modules.push_triggers.recap_push_item", return_value=None):
                                with patch(
                                    "requests.get",
                                    side_effect=[
                                        push_tokens_response,
                                        profiles_response,
                                        preferences_response,
                                        gm_stance_response,
                                        not_notified_response,
                                    ],
                                ):
                                    with patch("requests.post") as mock_post:
                                        mock_post.return_value = Mock(
                                            status_code=200, json=lambda: {"data": [{"status": "ok"}]}
                                        )
                                        stats = push_triggers.run_push_trigger_sweep(environ=config_env)

    assert stats["pushes_sent"] == 1
    push_call = mock_post.call_args_list[0]
    assert push_call.kwargs["json"][0]["title"] == "Injury Update — Test League"
    assert push_call.kwargs["json"][0]["body"] == "Hurt Guy is now Out"


def test_fetch_push_preferences_defaults_missing_categories_to_enabled():
    response = Mock(status_code=200)
    response.json.return_value = [
        {"user_id": "u1", "settings": {"push_categories": {"injury": False}}},
        {"user_id": "u2", "settings": {}},
    ]
    with patch("requests.get", return_value=response):
        preferences = push_triggers.fetch_push_preferences(_config(), ["u1", "u2"])
    assert preferences["u1"] == {"top_priority": True, "watch": True, "recap": True, "injury": False}
    assert preferences["u2"] == {"top_priority": True, "watch": True, "recap": True, "injury": True}


def test_fetch_push_preferences_empty_without_ids_or_config():
    with patch("requests.get") as mock_get:
        assert push_triggers.fetch_push_preferences(_config(), []) == {}
    mock_get.assert_not_called()
    unconfigured = push_triggers.PushTriggerConfig()
    with patch("requests.get") as mock_get:
        assert push_triggers.fetch_push_preferences(unconfigured, ["u1"]) == {}
    mock_get.assert_not_called()


def test_fetch_push_preferences_fails_open_on_transport_error():
    with patch("requests.get", side_effect=Exception("network down")):
        assert push_triggers.fetch_push_preferences(_config(), ["u1"]) == {}


def test_push_item_allowed_defaults_true_without_a_settings_row():
    assert push_triggers.push_item_allowed({}, user_id="u1", category="injury") is True


def test_push_item_allowed_respects_disabled_category():
    preferences = {"u1": {"top_priority": True, "watch": True, "recap": True, "injury": False}}
    assert push_triggers.push_item_allowed(preferences, user_id="u1", category="injury") is False
    assert push_triggers.push_item_allowed(preferences, user_id="u1", category="watch") is True


def test_run_push_trigger_sweep_skips_a_disabled_category(monkeypatch):
    config_env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    players_df = pd.DataFrame(
        [{"player_id": "p1", "name": "Hurt Guy", "position": "RB", "dynasty_score": 50, "injury_status": "Out"}]
    )

    push_tokens_response = Mock(status_code=200)
    push_tokens_response.json.return_value = [{"user_id": "u1", "expo_push_token": "ExponentPushToken[a]"}]
    profiles_response = Mock(status_code=200)
    profiles_response.json.return_value = [{"user_id": "u1", "sleeper_username": "gm_dynasty"}]
    preferences_response = Mock(status_code=200)
    preferences_response.json.return_value = [
        {"user_id": "u1", "settings": {"push_categories": {"injury": False}}}
    ]

    with patch("modules.push_triggers.load_valued_players", return_value=(players_df, "dynasty_score")):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper_leagues.get_user_leagues",
                return_value=[{"league_id": "league-1", "name": "Test League"}],
            ):
                with patch("modules.sleeper.get_league", return_value={"name": "Test League"}):
                    with patch(
                        "modules.sleeper.get_rosters",
                        return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": ["p1"]}],
                    ):
                        with patch(
                            "modules.dashboard_engine.compose_next_move_briefing",
                            return_value=Mock(items=[]),
                        ):
                            with patch("modules.push_triggers.recap_push_item", return_value=None):
                                with patch(
                                    "requests.get",
                                    side_effect=[push_tokens_response, profiles_response, preferences_response],
                                ):
                                    with patch("requests.post") as mock_post:
                                        stats = push_triggers.run_push_trigger_sweep(environ=config_env)

    assert stats["pushes_sent"] == 0
    mock_post.assert_not_called()


def test_fetch_pending_trade_outcome_followups_returns_rows():
    response = Mock(status_code=200)
    response.json.return_value = [
        {"id": "outcome-1", "user_id": "u1", "league_id": "league-1", "partner_team_name": "Team Rocket"},
    ]
    with patch("requests.get", return_value=response) as mock_get:
        rows = push_triggers.fetch_pending_trade_outcome_followups(_config())
    assert rows == [{"id": "outcome-1", "user_id": "u1", "league_id": "league-1", "partner_team_name": "Team Rocket"}]
    params = mock_get.call_args.kwargs["params"]
    assert params["outcome"] == "eq.pending"
    assert params["followup_pushed_at"] == "is.null"
    assert params["shared_at"].startswith("lte.")


def test_fetch_pending_trade_outcome_followups_empty_when_not_configured():
    with patch("requests.get") as mock_get:
        rows = push_triggers.fetch_pending_trade_outcome_followups(push_triggers.PushTriggerConfig())
    assert rows == []
    mock_get.assert_not_called()


def test_mark_trade_outcome_followup_pushed_patches_the_row():
    with patch("requests.patch") as mock_patch:
        push_triggers.mark_trade_outcome_followup_pushed(_config(), outcome_id="outcome-1")
    call = mock_patch.call_args
    assert "trade_outcomes" in call.args[0]
    assert call.kwargs["params"] == {"id": "eq.outcome-1"}
    assert "followup_pushed_at" in call.kwargs["json"]


def test_run_trade_outcome_followup_sweep_sends_and_marks_pushed():
    config_env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    pending_response = Mock(status_code=200)
    pending_response.json.return_value = [
        {"id": "outcome-1", "user_id": "u1", "league_id": "league-1", "partner_team_name": "Team Rocket"},
    ]
    tokens_response = Mock(status_code=200)
    tokens_response.json.return_value = [{"user_id": "u1", "expo_push_token": "ExponentPushToken[a]"}]
    expo_response = Mock(status_code=200, json=lambda: {"data": [{"status": "ok"}]})

    with patch("requests.get", side_effect=[pending_response, tokens_response]):
        with patch("requests.post", return_value=expo_response) as mock_post:
            with patch("requests.patch") as mock_patch:
                stats = push_triggers.run_trade_outcome_followup_sweep(environ=config_env)

    assert stats["configured"] is True
    assert stats["outcomes_checked"] == 1
    assert stats["pushes_sent"] == 1
    assert not stats["errors"]
    assert mock_post.call_args.args[0] == push_tokens.EXPO_PUSH_API_URL
    assert mock_post.call_args.kwargs["json"][0]["to"] == "ExponentPushToken[a]"
    assert "Team Rocket" in mock_post.call_args.kwargs["json"][0]["body"]
    mock_patch.assert_called_once()
    assert mock_patch.call_args.kwargs["params"] == {"id": "eq.outcome-1"}


def test_run_trade_outcome_followup_sweep_marks_pushed_without_a_token():
    config_env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    pending_response = Mock(status_code=200)
    pending_response.json.return_value = [
        {"id": "outcome-1", "user_id": "u1", "league_id": "league-1", "partner_team_name": "Team Rocket"},
    ]
    tokens_response = Mock(status_code=200)
    tokens_response.json.return_value = []

    with patch("requests.get", side_effect=[pending_response, tokens_response]):
        with patch("requests.post") as mock_post:
            with patch("requests.patch") as mock_patch:
                stats = push_triggers.run_trade_outcome_followup_sweep(environ=config_env)

    assert stats["pushes_sent"] == 0
    mock_post.assert_not_called()
    mock_patch.assert_called_once()


def test_run_trade_outcome_followup_sweep_fails_soft_when_not_configured():
    stats = push_triggers.run_trade_outcome_followup_sweep(environ={})
    assert stats["ok"] is False
    assert stats["configured"] is False
    assert stats["pushes_sent"] == 0
    assert stats["errors"]


def test_fetch_gm_stance_leagues_returns_the_leagues_with_a_stored_stance():
    response = Mock(status_code=200)
    response.json.return_value = [
        {"user_id": "u1", "settings": {"team_strategy_by_league": {"league-1": "rebuild", "league-2": "contender"}}},
        {"user_id": "u2", "settings": {}},
    ]
    with patch("requests.get", return_value=response):
        result = push_triggers.fetch_gm_stance_leagues(_config(), ["u1", "u2"])
    assert result == {"u1": {"league-1", "league-2"}, "u2": set()}


def test_fetch_gm_stance_leagues_empty_when_not_configured():
    with patch("requests.get") as mock_get:
        result = push_triggers.fetch_gm_stance_leagues(push_triggers.PushTriggerConfig(), ["u1"])
    assert result == {}
    mock_get.assert_not_called()


def test_gm_stance_reminder_push_item_fires_when_league_has_no_stance():
    item = push_triggers.gm_stance_reminder_push_item(
        league_id="league-1", league_name="Test League", leagues_with_stance=set()
    )
    assert item is not None
    assert item["category"] == "gm_stance_reminder"
    assert item["recommendation_id"] == "gm_stance_reminder:league-1"
    assert item["league_name"] == "Test League"


def test_gm_stance_reminder_push_item_none_once_a_stance_is_stored():
    item = push_triggers.gm_stance_reminder_push_item(
        league_id="league-1", league_name="Test League", leagues_with_stance={"league-1"}
    )
    assert item is None


def test_run_push_trigger_sweep_sends_the_gm_stance_reminder_once():
    config_env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    players_df = pd.DataFrame([{"player_id": "p1", "position": "RB", "dynasty_score": 50}])

    push_tokens_response = Mock(status_code=200)
    push_tokens_response.json.return_value = [{"user_id": "u1", "expo_push_token": "ExponentPushToken[a]"}]
    profiles_response = Mock(status_code=200)
    profiles_response.json.return_value = [{"user_id": "u1", "sleeper_username": "gm_dynasty"}]
    preferences_response = Mock(status_code=200)
    preferences_response.json.return_value = []
    # Nobody has a stance stored for league-1 yet.
    gm_stance_response = Mock(status_code=200)
    gm_stance_response.json.return_value = [{"user_id": "u1", "settings": {}}]
    not_notified_response = Mock(status_code=200)
    not_notified_response.json.return_value = []

    with patch("modules.push_triggers.load_valued_players", return_value=(players_df, "dynasty_score")):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
            with patch(
                "modules.sleeper_leagues.get_user_leagues",
                return_value=[{"league_id": "league-1", "name": "Test League"}],
            ):
                with patch("modules.sleeper.get_league", return_value={"name": "Test League"}):
                    with patch(
                        "modules.sleeper.get_rosters",
                        return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": ["p1"]}],
                    ):
                        with patch(
                            "modules.dashboard_engine.compose_next_move_briefing",
                            return_value=Mock(items=[]),
                        ):
                            with patch("modules.push_triggers.recap_push_item", return_value=None):
                                with patch(
                                    "requests.get",
                                    side_effect=[
                                        push_tokens_response,
                                        profiles_response,
                                        preferences_response,
                                        gm_stance_response,
                                        not_notified_response,
                                    ],
                                ):
                                    with patch("requests.post") as mock_post:
                                        mock_post.return_value = Mock(
                                            status_code=200, json=lambda: {"data": [{"status": "ok"}]}
                                        )
                                        stats = push_triggers.run_push_trigger_sweep(environ=config_env)

    assert stats["pushes_sent"] == 1
    push_call = mock_post.call_args_list[0]
    assert push_call.kwargs["json"][0]["title"] == "Set Your GM Stance — Test League"
    assert push_call.kwargs["json"][0]["data"]["category"] == "gm_stance_reminder"
    assert push_call.kwargs["json"][0]["data"]["league_name"] == "Test League"

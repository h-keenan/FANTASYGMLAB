"""modules.push_triggers — the basic automated push-trigger sweep.

Mocks requests (the Supabase service-role + Sleeper I/O boundary) and the
dashboard_engine composition call, matching the mocking convention used
across the mobile API tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pandas as pd

import pytest

from modules import push_tokens, push_triggers


_real_count_recent_pushes = push_triggers.count_recent_pushes
_real_fetch_push_timezones = push_triggers.fetch_push_timezones


@pytest.fixture(autouse=True)
def _daytime_no_history(monkeypatch):
    """Default every sweep test to mid-day New York with no prior pushes, so
    the older tests keep their exact request sequence. Quiet-hours / cap /
    timezone behavior is covered by tests that override these."""

    monkeypatch.setattr(push_triggers, "fetch_push_timezones", lambda config: {})
    monkeypatch.setattr(push_triggers, "count_recent_pushes", lambda config, user_id, now=None: 0)
    monkeypatch.setattr(
        push_triggers, "_utcnow", lambda: datetime(2026, 10, 21, 17, 0, tzinfo=timezone.utc)
    )
    # Trade-idea alerts resolve the team posture from the shared rankings (own
    # tests below); here it must not consume the mocked request sequence.
    from modules import trade_hub_engine

    monkeypatch.setattr(trade_hub_engine, "roster_posture", lambda **kw: {"key": "retool"})


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
    fake_item = Mock(
        category="top_priority",
        headline="Trade with Rival GM",
        recommendation_id="rec-abc",
        route_player_id="",
        route_player_name="",
    )
    fake_briefing = Mock(items=[fake_item])
    players_df = pd.DataFrame([{"player_id": "p1", "position": "RB", "dynasty_score": 50}])

    push_tokens_response = Mock(status_code=200)
    push_tokens_response.json.return_value = [{"user_id": "u1", "expo_push_token": "ExponentPushToken[a]"}]
    profiles_response = Mock(status_code=200)
    profiles_response.json.return_value = [{"user_id": "u1", "sleeper_username": "gm_dynasty"}]
    preferences_response = Mock(status_code=200)
    preferences_response.json.return_value = []
    # league-1 already has a Team Situation declared, so the one-time GM
    # stance reminder doesn't fire and pollute this test's pushes_sent count.
    gm_stance_response = Mock(status_code=200)
    gm_stance_response.json.return_value = [{"user_id": "u1", "league_id": "league-1"}]
    gm_untouchable_response = Mock(status_code=200)
    gm_untouchable_response.json.return_value = []
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
                                        gm_untouchable_response,
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
    assert log_call.kwargs["json"][0]["recommendation_id"] == "rec-abc"

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
                                        gm_untouchable_response,
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
    # recap is intentionally still league-level routing — confirming the
    # exact dict shape above already proves no player_id/player_name keys
    # snuck in, but assert explicitly since that's the behavior under test.
    assert "player_id" not in item
    assert "player_name" not in item


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
    gm_stance_response.json.return_value = [{"user_id": "u1", "league_id": "league-1"}]
    gm_untouchable_response = Mock(status_code=200)
    gm_untouchable_response.json.return_value = []
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
                                        gm_untouchable_response,
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
    assert push_call.kwargs["json"][0]["title"] == "Recap Ready"
    assert push_call.kwargs["json"][0]["body"] == "Week 3 recap is ready"
    assert "player_id" not in push_call.kwargs["json"][0]["data"]
    assert "player_name" not in push_call.kwargs["json"][0]["data"]


def test_league_briefing_push_items_includes_player_fields_from_route_player_id():
    fake_item = Mock(
        category="top_priority",
        headline="Trade with Rival GM",
        recommendation_id="rec-abc",
        route_player_id="p9",
        route_player_name="Star Player",
    )
    fake_briefing = Mock(items=[fake_item])
    players_df = pd.DataFrame([{"player_id": "p1", "position": "RB", "dynasty_score": 50}])
    with patch("modules.sleeper.get_league", return_value={"name": "Test League"}):
        with patch(
            "modules.sleeper.get_rosters",
            return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": ["p1"]}],
        ):
            with patch("modules.dashboard_engine.compose_next_move_briefing", return_value=fake_briefing):
                items = push_triggers.league_briefing_push_items(
                    league_id="league-1",
                    sleeper_user_id="sleeper-user-1",
                    players_df=players_df,
                    score_field="dynasty_score",
                )
    assert items == [
        {
            "league_id": "league-1",
            "league_name": "Test League",
            "category": "top_priority",
            "headline": "Trade with Rival GM",
            "recommendation_id": "rec-abc",
            "player_id": "p9",
            "player_name": "Star Player",
        }
    ]


def test_league_briefing_push_items_omits_player_fields_without_route_player_id():
    fake_item = Mock(
        category="watch",
        headline="Keep an eye on this",
        recommendation_id="rec-xyz",
        route_player_id="",
        route_player_name="",
    )
    fake_briefing = Mock(items=[fake_item])
    players_df = pd.DataFrame([{"player_id": "p1", "position": "RB", "dynasty_score": 50}])
    with patch("modules.sleeper.get_league", return_value={"name": "Test League"}):
        with patch(
            "modules.sleeper.get_rosters",
            return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": ["p1"]}],
        ):
            with patch("modules.dashboard_engine.compose_next_move_briefing", return_value=fake_briefing):
                items = push_triggers.league_briefing_push_items(
                    league_id="league-1",
                    sleeper_user_id="sleeper-user-1",
                    players_df=players_df,
                    score_field="dynasty_score",
                )
    assert items == [
        {
            "league_id": "league-1",
            "league_name": "Test League",
            "category": "watch",
            "headline": "Keep an eye on this",
            "recommendation_id": "rec-xyz",
        }
    ]
    assert "player_id" not in items[0]
    assert "player_name" not in items[0]


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
            "player_id": "p1",
            "player_name": "Hurt Guy",
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
    gm_stance_response.json.return_value = [{"user_id": "u1", "league_id": "league-1"}]
    gm_untouchable_response = Mock(status_code=200)
    gm_untouchable_response.json.return_value = []
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
                                        gm_untouchable_response,
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
    assert push_call.kwargs["json"][0]["title"] == "Injury Update"
    assert push_call.kwargs["json"][0]["body"] == "Hurt Guy is now Out"
    # The routing metadata reaches the actual Expo payload, not just the
    # intermediate push_item dict — this is what mobile's routeNotificationTap
    # reads to deep-link to the player instead of only the league hub.
    assert push_call.kwargs["json"][0]["data"]["player_id"] == "p1"
    assert push_call.kwargs["json"][0]["data"]["player_name"] == "Hurt Guy"


def test_fetch_push_preferences_defaults_missing_categories_to_enabled():
    response = Mock(status_code=200)
    response.json.return_value = [
        {"user_id": "u1", "settings": {"push_categories": {"injury": False}}},
        {"user_id": "u2", "settings": {}},
    ]
    with patch("requests.get", return_value=response):
        preferences = push_triggers.fetch_push_preferences(_config(), ["u1", "u2"])
    assert preferences["u1"] == {
        "top_priority": True, "watch": True, "recap": True, "injury": False,
        "team_situation": True, "trade_followup": True, "lineup_lock": True, "waiver_reminder": True, "trade_deadline": True,
    }
    assert preferences["u2"] == {
        "top_priority": True, "watch": True, "recap": True, "injury": True,
        "team_situation": True, "trade_followup": True, "lineup_lock": True, "waiver_reminder": True, "trade_deadline": True,
    }


def test_fetch_push_preferences_empty_without_ids_or_config():
    with patch("requests.get") as mock_get:
        assert push_triggers.fetch_push_preferences(_config(), []) == {}
    mock_get.assert_not_called()
    unconfigured = push_triggers.PushTriggerConfig()
    with patch("requests.get") as mock_get:
        assert push_triggers.fetch_push_preferences(unconfigured, ["u1"]) == {}
    mock_get.assert_not_called()


def test_fetch_push_preferences_returns_none_on_read_errors():
    with patch("requests.get", side_effect=Exception("network down")):
        assert push_triggers.fetch_push_preferences(_config(), ["u1"]) is None
    with patch("requests.get", return_value=Mock(status_code=500)):
        assert push_triggers.fetch_push_preferences(_config(), ["u1"]) is None


def test_push_item_allowed_defaults_true_without_a_settings_row():
    assert push_triggers.push_item_allowed({}, user_id="u1", category="injury") is True


def test_push_item_allowed_respects_disabled_category():
    preferences = {"u1": {"top_priority": True, "watch": True, "recap": True, "injury": False}}
    assert push_triggers.push_item_allowed(
        {"u1": {"team_situation": False, "trade_followup": False}}, user_id="u1", category="gm_stance_reminder"
    ) is False
    assert push_triggers.push_item_allowed(
        {"u1": {"team_situation": False, "trade_followup": False}}, user_id="u1", category="trade_followup"
    ) is False
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

    prefs_response = Mock(status_code=200, json=lambda: [])
    with patch("requests.get", side_effect=[pending_response, tokens_response, prefs_response]):
        with patch("requests.post", return_value=expo_response) as mock_post:
            with patch("requests.patch") as mock_patch:
                stats = push_triggers.run_trade_outcome_followup_sweep(environ=config_env)

    assert stats["configured"] is True
    assert stats["outcomes_checked"] == 1
    assert stats["pushes_sent"] == 1
    assert not stats["errors"]
    expo_call = mock_post.call_args_list[0]
    assert expo_call.args[0] == push_tokens.EXPO_PUSH_API_URL
    assert expo_call.kwargs["json"][0]["to"] == "ExponentPushToken[a]"
    # Privacy: partner team name is not in push text; league_id rides in data.
    assert "Team Rocket" not in expo_call.kwargs["json"][0]["body"]
    assert expo_call.kwargs["json"][0]["data"]["league_id"] == "league-1"
    assert expo_call.kwargs["json"][0]["data"]["outcome_id"] == "outcome-1"
    log_call = mock_post.call_args_list[1]
    assert "push_notification_log" in log_call.args[0]
    assert log_call.kwargs["json"][0]["recommendation_id"] == "trade_followup:outcome-1"
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
    prefs_response = Mock(status_code=200, json=lambda: [])

    with patch("requests.get", side_effect=[pending_response, tokens_response, prefs_response]):
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
    # Rows straight off modules.team_stance.STANCE_TABLE — the GM Stance /
    # Team Situation merge (2026-09-26) retired the old
    # "team_strategy_by_league" user_settings storage this used to read.
    response = Mock(status_code=200)
    response.json.return_value = [
        {"user_id": "u1", "league_id": "league-1"},
        {"user_id": "u1", "league_id": "league-2"},
    ]
    with patch("requests.get", return_value=response):
        result = push_triggers.fetch_gm_stance_leagues(_config(), ["u1", "u2"])
    assert result == {"u1": {"league-1", "league-2"}, "u2": set()}


def test_fetch_gm_stance_leagues_empty_when_not_configured():
    with patch("requests.get") as mock_get:
        result = push_triggers.fetch_gm_stance_leagues(push_triggers.PushTriggerConfig(), ["u1"])
    assert result == {}
    mock_get.assert_not_called()


def test_fetch_gm_targets_untouchable_ids_groups_by_user_and_league():
    response = Mock(status_code=200)
    response.json.return_value = [
        {"user_id": "u1", "league_id": "league-1", "player_id": "p9"},
        {"user_id": "u1", "league_id": "league-1", "player_id": "p10"},
        {"user_id": "u1", "league_id": "league-2", "player_id": "p11"},
    ]
    with patch("requests.get", return_value=response) as mock_get:
        result = push_triggers.fetch_gm_targets_untouchable_ids(_config(), ["u1", "u2"])
    assert result == {
        "u1": {"league-1": {"p9", "p10"}, "league-2": {"p11"}},
        "u2": {},
    }
    params = mock_get.call_args.kwargs["params"]
    assert params["untouchable"] == "eq.true"


def test_fetch_gm_targets_untouchable_ids_empty_when_not_configured():
    with patch("requests.get") as mock_get:
        result = push_triggers.fetch_gm_targets_untouchable_ids(push_triggers.PushTriggerConfig(), ["u1"])
    assert result == {}
    mock_get.assert_not_called()


def test_league_briefing_push_items_threads_gm_targets_untouchable_ids_through():
    # Recommendation-compliance audit finding: league_briefing_push_items
    # never precomputes its own trade_idea_records (unlike the Dashboard/
    # mobile API/Portfolio surfaces, which all fetch GM Targets and thread
    # untouchable_player_ids into trade_hub_engine.generate_trade_idea_records_cached
    # themselves before calling compose_next_move_briefing) — it relies on
    # compose_next_move_briefing's own fallback generation. Before this
    # parameter existed, that fallback had no way to see the caller's
    # untouchable list at all, so this sweep's "Next Move" trade tile could
    # recommend sending away a player the user explicitly protected
    # elsewhere in the app, even though every other surface showing the
    # identical recommendation already respected that flag.
    players_df = pd.DataFrame([{"player_id": "p1", "position": "RB", "dynasty_score": 90}])
    fake_briefing = Mock(items=[])
    with patch("modules.sleeper.get_league", return_value={"name": "Test League"}):
        with patch(
            "modules.sleeper.get_rosters",
            return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": ["p1"]}],
        ):
            with patch(
                "modules.dashboard_engine.compose_next_move_briefing", return_value=fake_briefing
            ) as mock_compose:
                push_triggers.league_briefing_push_items(
                    league_id="league-1",
                    sleeper_user_id="sleeper-user-1",
                    players_df=players_df,
                    score_field="dynasty_score",
                    untouchable_player_ids=("p1",),
                )

    assert mock_compose.call_args.kwargs["untouchable_player_ids"] == ("p1",)


def test_league_briefing_push_items_defaults_to_no_untouchable_ids():
    players_df = pd.DataFrame([{"player_id": "p1", "position": "RB", "dynasty_score": 90}])
    fake_briefing = Mock(items=[])
    with patch("modules.sleeper.get_league", return_value={"name": "Test League"}):
        with patch(
            "modules.sleeper.get_rosters",
            return_value=[{"roster_id": 1, "owner_id": "sleeper-user-1", "players": ["p1"]}],
        ):
            with patch(
                "modules.dashboard_engine.compose_next_move_briefing", return_value=fake_briefing
            ) as mock_compose:
                push_triggers.league_briefing_push_items(
                    league_id="league-1",
                    sleeper_user_id="sleeper-user-1",
                    players_df=players_df,
                    score_field="dynasty_score",
                )

    assert mock_compose.call_args.kwargs["untouchable_player_ids"] == ()


def test_gm_stance_reminder_push_item_fires_when_league_has_no_stance():
    item = push_triggers.gm_stance_reminder_push_item(
        league_id="league-1", league_name="Test League", leagues_with_stance=set()
    )
    assert item is not None
    assert item["category"] == "gm_stance_reminder"
    assert item["recommendation_id"] == "gm_stance_reminder:league-1"
    assert item["league_name"] == "Test League"
    # gm_stance_reminder is intentionally still league-level routing — no
    # more-specific per-item target exists for it.
    assert "player_id" not in item
    assert "player_name" not in item


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
    # Nobody has a Team Situation stance stored for league-1 yet.
    gm_stance_response = Mock(status_code=200)
    gm_stance_response.json.return_value = []
    gm_untouchable_response = Mock(status_code=200)
    gm_untouchable_response.json.return_value = []
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
                                        gm_untouchable_response,
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
    assert push_call.kwargs["json"][0]["title"] == "Set Your Team Situation"
    assert push_call.kwargs["json"][0]["data"]["category"] == "gm_stance_reminder"
    assert push_call.kwargs["json"][0]["data"]["league_name"] == "Test League"


def test_delete_invalid_push_tokens_deletes_each_exact_token():
    from unittest.mock import patch as _patch

    config = push_triggers.PushTriggerConfig(url="https://x.supabase.co", service_role_key="k")
    with _patch("requests.delete") as delete:
        push_triggers.delete_invalid_push_tokens(config, ["ExponentPushToken[a]", "garbage"])
    assert delete.call_count == 1
    assert delete.call_args.kwargs["params"] == {"expo_push_token": "eq.ExponentPushToken[a]"}


# --- push safety: quiet hours, weekly cap, batching, fail-closed -------------


def test_is_quiet_hours_uses_the_device_timezone():
    now = datetime(2026, 10, 21, 3, 0, tzinfo=timezone.utc)  # 23:00 NY, 20:00 LA
    assert push_triggers.is_quiet_hours("America/New_York", now) is True
    assert push_triggers.is_quiet_hours("America/Los_Angeles", now) is False
    assert push_triggers.is_quiet_hours("", now) is True  # unknown -> New York
    assert push_triggers.is_quiet_hours("Not/AZone", now) is True


def test_is_quiet_hours_boundaries():
    # 22:00 NY (EDT = UTC-4) starts quiet hours, 08:00 NY ends them.
    assert push_triggers.is_quiet_hours("America/New_York", datetime(2026, 10, 22, 2, 0, tzinfo=timezone.utc)) is True
    assert push_triggers.is_quiet_hours("America/New_York", datetime(2026, 10, 22, 1, 59, tzinfo=timezone.utc)) is False
    assert push_triggers.is_quiet_hours("America/New_York", datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)) is False
    assert push_triggers.is_quiet_hours("America/New_York", datetime(2026, 10, 21, 11, 59, tzinfo=timezone.utc)) is True


def test_apply_weekly_cap_reserves_the_last_slot_for_injury():
    items = [{"category": "watch"}, {"category": "injury"}]
    assert push_triggers.apply_weekly_cap(items, sent_this_week=2, cap=4) == items
    assert push_triggers.apply_weekly_cap(items, sent_this_week=3, cap=4) == [{"category": "injury"}]
    assert push_triggers.apply_weekly_cap(items, sent_this_week=4, cap=4) == []


def test_build_batched_message_leads_with_injury_and_hides_league_names():
    items = [
        {"category": "watch", "headline": "Watch thing", "league_id": "l2", "league_name": "Secret League"},
        {"category": "injury", "headline": "X is now Out", "league_id": "l1", "league_name": "Other League",
         "player_id": "p1", "player_name": "X"},
        {"category": "recap", "headline": "Week 3 recap is ready", "league_id": "l1", "league_name": "Other League"},
    ]
    title, body, data = push_triggers.build_batched_message(items)
    assert title == "Injury Update"
    assert body == "X is now Out (+2 more updates)"
    assert "League" not in title + body
    assert data["league_id"] == "l1" and data["player_id"] == "p1" and data["count"] == 3


def test_count_recent_pushes_counts_distinct_sent_at_and_fails_closed(monkeypatch):
    # The autouse fixture stubs count_recent_pushes; restore the real one.


    real = _real_count_recent_pushes
    rows = [{"sent_at": "t1"}, {"sent_at": "t1"}, {"sent_at": "t2"}]
    with patch("requests.get", return_value=Mock(status_code=200, json=lambda: rows)):
        assert real(_config(), "u1") == 2
    with patch("requests.get", return_value=Mock(status_code=500)):
        assert real(_config(), "u1") is None
    with patch("requests.get", side_effect=Exception("down")):
        assert real(_config(), "u1") is None


def test_fetch_push_timezones_newest_device_wins_and_degrades():
    rows = [
        {"user_id": "u1", "timezone": "America/Chicago", "updated_at": "1"},
        {"user_id": "u1", "timezone": "America/Denver", "updated_at": "2"},
        {"user_id": "u2", "timezone": "garbage", "updated_at": "1"},
    ]
    real = _real_fetch_push_timezones
    with patch("requests.get", return_value=Mock(status_code=200, json=lambda: rows)):
        assert real(_config()) == {"u1": "America/Denver"}
    with patch("requests.get", return_value=Mock(status_code=400)):  # column not migrated yet
        assert real(_config()) == {}


def _run_injury_sweep(*, preferences_response, expo_ok=True):
    config_env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    players_df = pd.DataFrame(
        [
            {"player_id": "p1", "name": "Hurt Guy", "position": "RB", "dynasty_score": 50, "injury_status": "Out"},
            {"player_id": "p2", "name": "Other Guy", "position": "WR", "dynasty_score": 40, "injury_status": "IR"},
        ]
    )
    tokens = Mock(status_code=200, json=lambda: [{"user_id": "u1", "expo_push_token": "ExponentPushToken[a]"}])
    profiles = Mock(status_code=200, json=lambda: [{"user_id": "u1", "sleeper_username": "gm"}])
    stance = Mock(status_code=200, json=lambda: [{"user_id": "u1", "league_id": "league-1"}])
    untouch = Mock(status_code=200, json=lambda: [])
    notified = Mock(status_code=200, json=lambda: [])
    expo = Mock(status_code=200, json=lambda: {"data": [{"status": "ok"}]}) if expo_ok else Mock(status_code=500)
    with patch("modules.push_triggers.load_valued_players", return_value=(players_df, "dynasty_score")):
        with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="su1"):
            with patch("modules.sleeper_leagues.get_user_leagues", return_value=[{"league_id": "league-1"}]):
                with patch("modules.sleeper.get_league", return_value={"name": "Secret League"}):
                    with patch(
                        "modules.sleeper.get_rosters",
                        return_value=[{"roster_id": 1, "owner_id": "su1", "players": ["p1", "p2"]}],
                    ):
                        with patch("modules.dashboard_engine.compose_next_move_briefing", return_value=Mock(items=[])):
                            with patch("modules.push_triggers.recap_push_item", return_value=None):
                                with patch(
                                    "requests.get",
                                    side_effect=[tokens, profiles, preferences_response, stance, untouch, notified],
                                ):
                                    with patch("requests.post", return_value=expo) as mock_post:
                                        stats = push_triggers.run_push_trigger_sweep(environ=config_env)
    return stats, mock_post


def test_sweep_batches_multiple_items_into_one_push_and_one_log_insert():
    stats, mock_post = _run_injury_sweep(preferences_response=Mock(status_code=200, json=lambda: []))
    assert stats["pushes_sent"] == 1
    expo_msgs = mock_post.call_args_list[0].kwargs["json"]
    assert len(expo_msgs) == 1
    assert expo_msgs[0]["title"] == "Injury Update"
    assert "(+1 more update)" in expo_msgs[0]["body"]
    assert "Secret League" not in expo_msgs[0]["title"] + expo_msgs[0]["body"]
    log_rows = mock_post.call_args_list[1].kwargs["json"]
    assert {row["recommendation_id"] for row in log_rows} == {"injury:p1:out", "injury:p2:ir"}


def test_sweep_does_not_log_dedup_rows_when_send_fails():
    stats, mock_post = _run_injury_sweep(
        preferences_response=Mock(status_code=200, json=lambda: []), expo_ok=False
    )
    assert stats["pushes_sent"] == 0
    assert mock_post.call_count == 1  # Expo attempt only, no push_notification_log insert


def test_sweep_fails_closed_when_preferences_cannot_be_read():
    stats, mock_post = _run_injury_sweep(preferences_response=Mock(status_code=500))
    assert stats["ok"] is False
    assert stats["pushes_sent"] == 0
    mock_post.assert_not_called()


def test_sweep_holds_everything_during_quiet_hours(monkeypatch):
    monkeypatch.setattr(
        push_triggers, "_utcnow", lambda: datetime(2026, 10, 22, 4, 0, tzinfo=timezone.utc)  # midnight NY
    )
    stats, mock_post = _run_injury_sweep(preferences_response=Mock(status_code=200, json=lambda: []))
    assert stats["pushes_sent"] == 0
    assert stats["held_quiet_hours"] == 1
    mock_post.assert_not_called()


def test_sweep_respects_the_weekly_cap_and_fails_closed_without_a_count(monkeypatch):
    monkeypatch.setattr(push_triggers, "count_recent_pushes", lambda config, user_id, now=None: 4)
    stats, mock_post = _run_injury_sweep(preferences_response=Mock(status_code=200, json=lambda: []))
    assert stats["pushes_sent"] == 0 and stats["capped"] == 1
    mock_post.assert_not_called()

    monkeypatch.setattr(push_triggers, "count_recent_pushes", lambda config, user_id, now=None: None)
    stats, mock_post = _run_injury_sweep(preferences_response=Mock(status_code=200, json=lambda: []))
    assert stats["pushes_sent"] == 0
    mock_post.assert_not_called()


def test_trade_followup_held_in_quiet_hours_and_not_marked(monkeypatch):
    monkeypatch.setattr(
        push_triggers, "_utcnow", lambda: datetime(2026, 10, 22, 4, 0, tzinfo=timezone.utc)
    )
    config_env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    pending = Mock(status_code=200, json=lambda: [{"id": "o1", "user_id": "u1", "league_id": "l1"}])
    tokens = Mock(status_code=200, json=lambda: [{"user_id": "u1", "expo_push_token": "ExponentPushToken[a]"}])
    prefs = Mock(status_code=200, json=lambda: [])
    with patch("requests.get", side_effect=[pending, tokens, prefs]):
        with patch("requests.post") as mock_post:
            with patch("requests.patch") as mock_patch:
                stats = push_triggers.run_trade_outcome_followup_sweep(environ=config_env)
    assert stats["held"] == 1 and stats["pushes_sent"] == 0
    mock_post.assert_not_called()
    mock_patch.assert_not_called()


def test_trade_followup_opt_out_marks_pushed_without_sending():
    config_env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    pending = Mock(status_code=200, json=lambda: [{"id": "o1", "user_id": "u1", "league_id": "l1"}])
    tokens = Mock(status_code=200, json=lambda: [{"user_id": "u1", "expo_push_token": "ExponentPushToken[a]"}])
    prefs = Mock(
        status_code=200,
        json=lambda: [{"user_id": "u1", "settings": {"push_categories": {"trade_followup": False}}}],
    )
    with patch("requests.get", side_effect=[pending, tokens, prefs]):
        with patch("requests.post") as mock_post:
            with patch("requests.patch") as mock_patch:
                stats = push_triggers.run_trade_outcome_followup_sweep(environ=config_env)
    assert stats["pushes_sent"] == 0
    mock_post.assert_not_called()
    mock_patch.assert_called_once()


def test_trade_followup_fails_closed_when_preferences_unreadable():
    config_env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    pending = Mock(status_code=200, json=lambda: [{"id": "o1", "user_id": "u1", "league_id": "l1"}])
    tokens = Mock(status_code=200, json=lambda: [{"user_id": "u1", "expo_push_token": "ExponentPushToken[a]"}])
    with patch("requests.get", side_effect=[pending, tokens, Mock(status_code=500)]):
        with patch("requests.post") as mock_post:
            with patch("requests.patch") as mock_patch:
                stats = push_triggers.run_trade_outcome_followup_sweep(environ=config_env)
    assert stats["ok"] is False
    mock_post.assert_not_called()
    mock_patch.assert_not_called()


# --- lineup lock + waiver reminder -----------------------------------------

_NOW = datetime(2026, 10, 25, 16, 0, tzinfo=timezone.utc)  # Sunday 12:00 ET


def _games_frame():
    # Week 7: KC hosts DEN at 13:00 ET (17:00 UTC, one hour after _NOW);
    # BUF hosts MIA at 16:25 ET (outside the 2h window). Week 8 gives KC a game
    # so week 7 is not KC's bye.
    rows = [
        ("2026_07_DEN_KC", 7, "DEN", "KC", "2026-10-25", "13:00"),
        ("2026_07_MIA_BUF", 7, "MIA", "BUF", "2026-10-25", "16:25"),
        ("2026_08_KC_BUF", 8, "KC", "BUF", "2026-11-01", "13:00"),
    ]
    return pd.DataFrame(
        [
            {
                "game_id": gid, "season": 2026, "week": wk, "game_type": "REG",
                "away_team": away, "home_team": home, "gameday": day, "gametime": tm,
                "away_score": None, "home_score": None, "spread_line": None, "total_line": None,
            }
            for gid, wk, away, home, day, tm in rows
        ]
    )


def _league(**settings):
    return {"season": "2026", "status": "in_season", "settings": {"leg": 7, **settings}}


def _lineup_players():
    return pd.DataFrame(
        [
            {"player_id": "p1", "name": "Hurt Guy", "team": "KC", "injury_status": "Out"},
            {"player_id": "p2", "name": "Late Game", "team": "BUF", "injury_status": "Out"},
            {"player_id": "p3", "name": "Healthy", "team": "KC", "injury_status": ""},
        ]
    )


def _lineup_items(starters, **kwargs):
    return push_triggers.lineup_lock_push_items(
        league_id="L1", league_name="Secret League", league=kwargs.pop("league", _league()),
        my_roster={"players": ["p1", "p2", "p3"], "starters": starters},
        players_df=_lineup_players(), games=kwargs.pop("games", _games_frame()),
        now=kwargs.pop("now", _NOW),
    )


def test_lineup_lock_flags_out_starter_inside_window_only():
    items = _lineup_items(["p1", "p2", "p3"])
    assert [i["recommendation_id"] for i in items] == ["lineup_lock:L1:7:out:p1:out"]
    assert items[0]["category"] == "lineup_lock"
    assert "Hurt Guy" in items[0]["headline"]
    assert "Secret League" not in items[0]["headline"]


def test_lineup_lock_flags_empty_and_invalid_slots_before_next_kickoff():
    items = _lineup_items(["p3", "0", "zzz"])
    assert len(items) == 1
    assert items[0]["recommendation_id"] == "lineup_lock:L1:7:slots:2026-10-25"
    assert "2 empty or invalid" in items[0]["headline"]


def test_lineup_lock_skips_when_no_real_signal():
    assert _lineup_items(["p3"]) == []  # healthy full lineup
    assert _lineup_items(["p1"], now=_NOW - timedelta(hours=3)) == []  # kickoff too far away
    assert _lineup_items(["p1"], now=_NOW + timedelta(hours=2)) == []  # already kicked off
    assert _lineup_items(["p1"], games=None) == []  # no schedule: do not guess
    assert _lineup_items(["p1"], league=_league(best_ball=1)) == []
    assert _lineup_items(["p1"], league={**_league(), "status": "pre_draft"}) == []


def test_lineup_lock_uses_the_reserved_cap_slot():
    items = [{"category": "lineup_lock"}, {"category": "watch"}]
    assert push_triggers.apply_weekly_cap(items, sent_this_week=3, cap=4) == [{"category": "lineup_lock"}]
    assert push_triggers.apply_weekly_cap(items, sent_this_week=4, cap=4) == []


def test_new_categories_are_toggleable_and_titled():
    for key in ("lineup_lock", "waiver_reminder"):
        assert key in push_triggers.TOGGLEABLE_PUSH_CATEGORIES
        assert key in push_triggers.PUSH_TITLE_BY_CATEGORY
    prefs = {"u1": {"lineup_lock": False, "waiver_reminder": True}}
    assert not push_triggers.push_item_allowed(prefs, user_id="u1", category="lineup_lock")
    assert push_triggers.push_item_allowed(prefs, user_id="u1", category="waiver_reminder")


def _waiver_item(monkeypatch, *, now, league=None, need_fit=True, needed=("RB",), roster_settings=None):
    players = pd.DataFrame(
        [
            {"player_id": "p1", "name": "Mine", "position": "WR", "team": "KC"},
            {"player_id": "fa1", "name": "Free", "position": "RB", "team": "BUF"},
        ]
    )
    monkeypatch.setattr(push_triggers.league_value_settings, "detect_league_value_settings_from_payload", lambda lg: {})
    monkeypatch.setattr(push_triggers.dashboard_engine, "suggest_optimal_lineup", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(push_triggers.dashboard_engine, "build_team_needs_assessment", lambda *a, **k: object())
    monkeypatch.setattr(push_triggers.dashboard_engine, "get_needed_positions", lambda *a, **k: list(needed))
    monkeypatch.setattr(
        push_triggers.dashboard_engine,
        "select_top_waiver_opportunity",
        lambda *a, **k: pd.Series({"position": "RB", "priority_need_fit": need_fit}),
    )
    return push_triggers.waiver_reminder_push_item(
        league_id="L1", league_name="Secret League",
        league=league or _league(waiver_type=0, waiver_day_of_week=2),
        my_roster={"players": ["p1"], "settings": roster_settings or {}},
        rosters=[{"players": ["p1"]}], players_df=players, score_field="dynasty_score", now=now,
    )


_TUESDAY_3PM_ET = datetime(2026, 10, 27, 19, 0, tzinfo=timezone.utc)  # day before Wednesday waivers


def test_waiver_reminder_fires_evening_before_with_real_need(monkeypatch):
    item = _waiver_item(monkeypatch, now=_TUESDAY_3PM_ET)
    assert item["category"] == "waiver_reminder"
    assert item["recommendation_id"] == "waiver_reminder:L1:2026-10-28"
    assert "Secret League" not in item["headline"]


def test_waiver_reminder_skips_without_timing_or_need(monkeypatch):
    assert _waiver_item(monkeypatch, now=_TUESDAY_3PM_ET - timedelta(days=1)) is None  # wrong day
    assert _waiver_item(monkeypatch, now=_TUESDAY_3PM_ET - timedelta(hours=9)) is None  # before noon ET
    assert _waiver_item(monkeypatch, now=_TUESDAY_3PM_ET, need_fit=False) is None
    assert _waiver_item(monkeypatch, now=_TUESDAY_3PM_ET, needed=()) is None
    assert _waiver_item(monkeypatch, now=_TUESDAY_3PM_ET, league=_league(waiver_type=0)) is None
    daily = _league(waiver_type=0, waiver_day_of_week=2, daily_waivers=1)
    assert _waiver_item(monkeypatch, now=_TUESDAY_3PM_ET, league=daily) is None
    assert _waiver_item(monkeypatch, now=_TUESDAY_3PM_ET, league=_league(waiver_day_of_week=2)) is None


def test_waiver_reminder_skips_faab_league_with_no_budget(monkeypatch):
    faab_league = _league(waiver_type=2, waiver_day_of_week=2, waiver_budget=100)
    spent = {"waiver_budget_used": 100}
    assert _waiver_item(monkeypatch, now=_TUESDAY_3PM_ET, league=faab_league, roster_settings=spent) is None
    left = {"waiver_budget_used": 40}
    assert _waiver_item(monkeypatch, now=_TUESDAY_3PM_ET, league=faab_league, roster_settings=left) is not None


def test_league_briefing_push_items_never_names_trade_partner():
    fake_item = Mock(
        category="top_priority",
        headline="Team Rocket",
        recommendation_id="rec-x",
        route_player_id="",
        route_player_name="",
        presentation={"partner_team_name": "Team Rocket"},
    )
    players_df = pd.DataFrame([{"player_id": "p1", "position": "RB", "dynasty_score": 50}])
    with patch("modules.sleeper.get_league", return_value={"name": "Test League"}):
        with patch(
            "modules.sleeper.get_rosters",
            return_value=[
                {"roster_id": 1, "owner_id": "sleeper-user-1", "players": ["p1"]},
                {"roster_id": 2, "owner_id": "o2", "players": [], "metadata": {"team_name": "Team Rocket"}},
            ],
        ):
            with patch("modules.dashboard_engine.compose_next_move_briefing", return_value=Mock(items=[fake_item])):
                items = push_triggers.league_briefing_push_items(
                    league_id="league-1",
                    sleeper_user_id="sleeper-user-1",
                    players_df=players_df,
                    score_field="dynasty_score",
                )
    assert "Rocket" not in items[0]["headline"]


def test_trade_tile_value_never_falls_back_to_partner_name():
    import inspect

    from modules import dashboard_engine

    assert 'headline_idea.get("partner_team_name"), "Open Trade Hub"' not in inspect.getsource(dashboard_engine)


def _deadline_league(*, leg, deadline=11, status="in_season"):
    return {"name": "Secret League", "status": status, "settings": {"trade_deadline": deadline, "leg": leg}}


def test_trade_deadline_push_fires_at_two_one_and_zero_weeks_out():
    seen = {}
    for leg, weeks_left in ((9, 2), (10, 1), (11, 0)):
        item = push_triggers.trade_deadline_push_item(
            league_id="L1", league_name="Secret League", league=_deadline_league(leg=leg)
        )
        assert item["category"] == "trade_deadline"
        assert item["recommendation_id"] == f"trade_deadline:L1:11:{weeks_left}"
        assert "Secret League" not in item["headline"]
        seen[weeks_left] = item["headline"]
    assert len(set(seen.values())) == 3  # distinct copy per tier


def test_trade_deadline_push_is_silent_when_far_off_passed_or_unknown():
    def item(league):
        return push_triggers.trade_deadline_push_item(league_id="L1", league_name="x", league=league)

    assert item(_deadline_league(leg=7)) is None  # 4 weeks out
    assert item(_deadline_league(leg=12)) is None  # passed: trades closed
    assert item(_deadline_league(leg=9, deadline=99)) is None  # no deadline
    assert item(_deadline_league(leg=9, status="complete")) is None  # offseason
    assert item({"status": "in_season", "settings": {"trade_deadline": 11}}) is None  # week unknown


def test_trade_deadline_category_is_toggleable_titled_and_cap_reserved():
    assert "trade_deadline" in push_triggers.TOGGLEABLE_PUSH_CATEGORIES
    assert push_triggers.PUSH_TITLE_BY_CATEGORY["trade_deadline"]
    prefs = {"u1": {"trade_deadline": False}}
    assert not push_triggers.push_item_allowed(prefs, user_id="u1", category="trade_deadline")
    items = [{"category": "trade_deadline"}, {"category": "watch"}]
    assert push_triggers.apply_weekly_cap(items, sent_this_week=3, cap=4) == [{"category": "trade_deadline"}]


def test_trade_deadline_push_dedups_per_tier_in_the_sweep_log():
    # Each tier has its own recommendation_id, so the already-sent filter that
    # the sweep applies drops a repeat of the same tier but lets the next one through.
    two = push_triggers.trade_deadline_push_item(league_id="L1", league_name="x", league=_deadline_league(leg=9))
    one = push_triggers.trade_deadline_push_item(league_id="L1", league_name="x", league=_deadline_league(leg=10))
    assert two["recommendation_id"] != one["recommendation_id"]
    again = push_triggers.trade_deadline_push_item(league_id="L1", league_name="x", league=_deadline_league(leg=9))
    assert again["recommendation_id"] == two["recommendation_id"]

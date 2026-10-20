"""modules.guess_the_player_leaderboard — the league-scoped leaderboard
assembled from both Guess the Player mini-games' real, persisted streaks.

Mocks requests (the service-role Supabase I/O boundary), same mocking
convention as tests/test_community_trades.py. build_leaderboard is pure (no
I/O) and is exercised directly with plain dicts, same as
community_trades.build_community_feed_items.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

from modules import guess_the_player_leaderboard as gtpl


def _config() -> gtpl.LeaderboardConfig:
    return gtpl.LeaderboardConfig(url="https://example.supabase.co", service_role_key="service-role-key")


# --- config ---------------------------------------------------------------


def test_load_leaderboard_config_reads_expected_env_vars():
    config = gtpl.load_leaderboard_config(
        environ={"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    )
    assert config.configured
    assert config.url == "https://x.supabase.co"


def test_load_leaderboard_config_not_configured_without_service_role_key():
    config = gtpl.load_leaderboard_config(environ={"SUPABASE_URL": "https://x.supabase.co"})
    assert not config.configured


# --- fetch (service-role I/O) ---------------------------------------------


def test_fetch_league_members_queries_by_league_id():
    response = Mock(status_code=200)
    response.json.return_value = [
        {"user_id": "user-1", "sleeper_username": "alice", "team_id": "Team Alice"},
        {"user_id": "user-2", "sleeper_username": "bob", "team_id": ""},
    ]
    with patch("requests.get", return_value=response) as mock_get:
        members = gtpl.fetch_league_members(_config(), "league-123")
    assert len(members) == 2
    params = mock_get.call_args.kwargs["params"]
    assert params["league_id"] == "eq.league-123"


def test_fetch_league_members_dedupes_defensively():
    response = Mock(status_code=200)
    response.json.return_value = [
        {"user_id": "user-1", "sleeper_username": "alice", "team_id": ""},
        {"user_id": "user-1", "sleeper_username": "alice", "team_id": ""},
    ]
    with patch("requests.get", return_value=response):
        members = gtpl.fetch_league_members(_config(), "league-123")
    assert len(members) == 1


def test_fetch_league_members_returns_empty_when_not_configured():
    with patch("requests.get") as mock_get:
        members = gtpl.fetch_league_members(gtpl.LeaderboardConfig(), "league-123")
    assert members == []
    mock_get.assert_not_called()


def test_fetch_league_members_fails_closed_on_error_status():
    response = Mock(status_code=500)
    with patch("requests.get", return_value=response):
        members = gtpl.fetch_league_members(_config(), "league-123")
    assert members == []


def test_fetch_league_members_fails_closed_on_exception():
    with patch("requests.get", side_effect=Exception("boom")):
        members = gtpl.fetch_league_members(_config(), "league-123")
    assert members == []


def test_fetch_streaks_queries_in_clause_for_user_ids():
    response = Mock(status_code=200)
    response.json.return_value = [
        {"user_id": "user-1", "current_streak": 5, "best_streak": 9},
    ]
    with patch("requests.get", return_value=response) as mock_get:
        by_user = gtpl.fetch_streaks(_config(), gtpl.STAT_LINE_STREAKS_TABLE, ["user-1", "user-2"])
    assert by_user == {"user-1": {"user_id": "user-1", "current_streak": 5, "best_streak": 9}}
    params = mock_get.call_args.kwargs["params"]
    assert params["user_id"] == "in.(user-1,user-2)"


def test_fetch_streaks_returns_empty_for_no_user_ids():
    with patch("requests.get") as mock_get:
        by_user = gtpl.fetch_streaks(_config(), gtpl.STAT_LINE_STREAKS_TABLE, [])
    assert by_user == {}
    mock_get.assert_not_called()


def test_fetch_profiles_selects_display_name():
    response = Mock(status_code=200)
    response.json.return_value = [{"user_id": "user-1", "display_name": "Alice"}]
    with patch("requests.get", return_value=response) as mock_get:
        by_user = gtpl.fetch_profiles(_config(), ["user-1"])
    assert by_user == {"user-1": {"user_id": "user-1", "display_name": "Alice"}}
    params = mock_get.call_args.kwargs["params"]
    assert params["select"] == "user_id,display_name"


# --- build_leaderboard (pure) ----------------------------------------------


def test_build_leaderboard_ranks_by_current_then_best_streak():
    members = [
        {"user_id": "user-1", "sleeper_username": "alice", "team_id": "Team Alice"},
        {"user_id": "user-2", "sleeper_username": "bob", "team_id": "Team Bob"},
        {"user_id": "user-3", "sleeper_username": "carol", "team_id": "Team Carol"},
    ]
    streaks_by_user = {
        "user-1": {"current_streak": 3, "best_streak": 10},
        "user-2": {"current_streak": 5, "best_streak": 5},
        # user-3 intentionally has no streak row at all.
    }
    entries = gtpl.build_leaderboard(
        members,
        league_id="league-123",
        streaks_by_user=streaks_by_user,
        viewer_user_id="user-2",
    )

    assert [entry["display_name"] for entry in entries] == ["Team Bob", "Team Alice", "Team Carol"]
    assert [entry["rank"] for entry in entries] == [1, 2, 3]

    carol = entries[2]
    assert carol["current_streak"] == 0
    assert carol["best_streak"] == 0

    bob = entries[0]
    assert bob["is_viewer"] is True
    assert entries[1]["is_viewer"] is False
    assert entries[2]["is_viewer"] is False


def test_build_leaderboard_ties_break_on_best_streak_then_name():
    members = [
        {"user_id": "user-1", "sleeper_username": "zeta", "team_id": ""},
        {"user_id": "user-2", "sleeper_username": "alpha", "team_id": ""},
    ]
    streaks_by_user = {
        "user-1": {"current_streak": 4, "best_streak": 4},
        "user-2": {"current_streak": 4, "best_streak": 6},
    }
    entries = gtpl.build_leaderboard(members, league_id="league-123", streaks_by_user=streaks_by_user)
    # Same current_streak -> higher best_streak ranks first.
    assert [entry["display_name"] for entry in entries] == ["alpha", "zeta"]


def test_build_leaderboard_name_fallback_chain():
    members = [
        {"user_id": "user-1", "sleeper_username": "", "team_id": ""},
        {"user_id": "user-2", "sleeper_username": "has-username", "team_id": ""},
        {"user_id": "user-3", "sleeper_username": "ignored", "team_id": "Has Team Id"},
    ]
    profiles_by_user = {"user-3": {"display_name": "Has Display Name"}}
    entries = gtpl.build_leaderboard(
        members,
        league_id="league-123",
        streaks_by_user={},
        profiles_by_user=profiles_by_user,
    )
    by_user_display = {entry["display_name"] for entry in entries}
    assert "Manager" in by_user_display
    assert "has-username" in by_user_display
    assert "Has Display Name" in by_user_display  # profile beats team_id/sleeper_username


def test_build_leaderboard_member_id_is_opaque_and_stable():
    members = [{"user_id": "user-1", "sleeper_username": "alice", "team_id": ""}]
    entries_a = gtpl.build_leaderboard(members, league_id="league-123", streaks_by_user={})
    entries_b = gtpl.build_leaderboard(members, league_id="league-123", streaks_by_user={})
    entries_other_league = gtpl.build_leaderboard(members, league_id="league-999", streaks_by_user={})

    assert entries_a[0]["member_id"] == entries_b[0]["member_id"]
    assert entries_a[0]["member_id"] != entries_other_league[0]["member_id"]
    assert "user_id" not in entries_a[0]
    assert entries_a[0]["member_id"] != "user-1"


def test_build_leaderboard_skips_members_without_user_id():
    members = [{"user_id": "", "sleeper_username": "ghost"}]
    entries = gtpl.build_leaderboard(members, league_id="league-123", streaks_by_user={})
    assert entries == []

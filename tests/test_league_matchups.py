"""GET /v1/leagues/{id}/matchups: the league-wide matchups list, with mocked Sleeper data."""

from unittest.mock import Mock, patch

from tests.test_mobile_api_service import _MATCHUP_ROSTERS, _client, _matchup_world  # noqa: F401


def _rosters():
    rosters = [dict(r) for r in _MATCHUP_ROSTERS]
    for roster in rosters:
        if roster["roster_id"] == 1:
            roster["settings"] = {"wins": 5, "losses": 2, "fpts": 700}
        if roster["roster_id"] == 2:
            roster["settings"] = {"wins": 3, "losses": 4, "fpts": 640}
    for rid, wins, losses in ((3, 4, 3), (4, 2, 5)):
        rosters.append({"roster_id": rid, "owner_id": f"owner{rid}", "players": [], "settings": {"wins": wins, "losses": losses}})
    return rosters


HEADERS = {"Authorization": "Bearer good-token"}


def test_league_matchups_requires_auth_and_validates(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/v1/leagues/abc/matchups").status_code == 401

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    with patch("requests.get", return_value=auth_user_response):
        bad_week = client.get("/v1/leagues/abc/matchups?week=40", headers=HEADERS)
        bad_lens = client.get("/v1/leagues/abc/matchups?lens=Vibes", headers=HEADERS)
    assert bad_week.status_code == 422
    assert bad_lens.status_code == 422


def test_league_matchups_returns_every_pair_with_live_points_streak_and_win_probability(monkeypatch):
    client = _client(monkeypatch)
    my_starters = [f"mine{i}" for i in range(1, 9)]
    my_points = [20.5, 15.0, 10.2, 5.5, 8.0, 12.0, 9.0, 3.0]
    opp_starters = [f"opp{i}" for i in range(1, 9)]
    opp_points = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    matchups = [
        {"roster_id": 3, "matchup_id": 1, "starters": [], "starters_points": [], "points": 0},
        {"roster_id": 4, "matchup_id": 1, "starters": [], "starters_points": [], "points": 0},
        {"roster_id": 1, "matchup_id": 3, "starters": my_starters, "starters_points": my_points, "points": sum(my_points)},
        {"roster_id": 2, "matchup_id": 3, "starters": opp_starters, "starters_points": opp_points, "points": sum(opp_points)},
    ]
    streaks = {1: {"current_streak": 3}, 2: {"current_streak": -2}}

    with _matchup_world(matchups, rosters=_rosters()):
        with patch("modules.sleeper.get_matchups", return_value=matchups) as get_matchups, patch(
            "modules.team_streaks.league_current_streaks_cached", return_value=streaks
        ):
            response = client.get("/v1/leagues/abc/matchups", headers=HEADERS)
            # One Sleeper matchups read for the whole league-week, however many pairs.
            assert get_matchups.call_count == 1

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["week"] == body["current_week"]
    assert body["max_week"] == 18
    assert "as_of" in body and "poll_after_seconds" in body
    assert len(body["matchups"]) == 2
    # The caller's own pair leads.
    first = body["matchups"][0]
    assert first["matchup_id"] == 3
    mine, theirs = first["sides"]
    assert mine["is_mine"] is True and theirs["is_mine"] is False
    assert mine["team_name"] == "My Squad"
    assert mine["owner_name"] == "Me"
    assert mine["record_label"] == "5-2"
    assert mine["standing_rank"] == 1
    assert mine["streak"] == 3 and mine["streak_label"] == "▲3W"
    assert theirs["streak_label"] == "▼2L"
    assert mine["points"] == round(sum(my_points), 2)
    assert theirs["points"] == round(sum(opp_points), 2)
    # No projections in this fixture: odds and projected totals are honestly absent, never a guessed 50/50.
    assert mine["win_probability"] is None and theirs["win_probability"] is None
    assert mine["projected_total"] is None
    # An unstarted pair has no live points or odds yet.
    quiet = body["matchups"][1]["sides"]
    assert [side["points"] for side in quiet] == [None, None]
    assert [side["win_probability"] for side in quiet] == [None, None]
    assert quiet[0]["streak_label"] == ""


def test_league_matchups_uses_the_blended_win_probability_for_both_sides(monkeypatch):
    client = _client(monkeypatch)
    matchups = [
        {"roster_id": 1, "matchup_id": 3, "starters": ["mine1"], "starters_points": [12.0], "points": 12.0},
        {"roster_id": 2, "matchup_id": 3, "starters": ["opp1"], "starters_points": [4.0], "points": 4.0},
    ]
    blended = {"available": True, "probability": 0.7, "my_projected_total": 118.4, "opponent_projected_total": 101.2}
    with _matchup_world(matchups, rosters=_rosters()):
        with patch("modules.matchup_win_probability.compute_live_win_probability", return_value=blended) as odds:
            response = client.get("/v1/leagues/abc/matchups", headers=HEADERS)
            assert odds.call_count == 1  # the same function /matchup calls, once per pair
    mine, theirs = response.json()["matchups"][0]["sides"]
    assert mine["win_probability"] == 0.7
    assert theirs["win_probability"] == 0.3
    assert (mine["projected_total"], theirs["projected_total"]) == (118.4, 101.2)


def test_league_matchups_week_param_selects_the_week_and_reports_no_data(monkeypatch):
    client = _client(monkeypatch)
    with _matchup_world([]):
        with patch("modules.sleeper.get_matchups", return_value=[]) as get_matchups:
            response = client.get("/v1/leagues/abc/matchups?week=5", headers=HEADERS)
            assert get_matchups.call_args.args[1] == 5
    body = response.json()
    assert response.status_code == 200
    assert body["week"] == 5
    assert body["matchups"] == []
    assert body["reason"] == "no_matchup_data"


def test_streak_badge_labels():
    from modules import league_matchups

    assert league_matchups.streak_badge_label(3) == "▲3W"
    assert league_matchups.streak_badge_label(-2) == "▼2L"
    assert league_matchups.streak_badge_label(0) == ""
    assert league_matchups.streak_badge_label(None) == ""
    assert league_matchups.streak_badge_label("x") == ""

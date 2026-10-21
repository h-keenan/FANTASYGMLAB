"""Real production bug, 2026-10-21 (coridian_, live): a user's saved
league (Supabase public.saved_leagues) keeps pointing at last season's
now-frozen league_id forever once their real league rolls over on
Sleeper -- nothing re-points it. Downstream, this silently fed:
  - a stale, prior-season roster view (services.mobile_api_service's
    _resolve_my_roster resolves "my roster" strictly by owner_id WITHIN
    whichever league_id it's handed -- no cross-user mixing, just the
    wrong season's frozen snapshot);
  - a Guess the Player leaderboard that only matches leaguemates who
    happen to share the viewer's own exact (stale-or-fresh) league_id
    (modules.guess_the_player_leaderboard.fetch_league_members queries
    saved_leagues by exact league_id).

Real, live-verified example (not synthetic): Sleeper username
"lukamagic777777" (user_id 1250330298407723008), league "Revivalry" --
2025 league_id 1250325243881345024 (status complete) rolled over to 2026
league_id 1325866097718620160 (status in_season), confirmed via Sleeper's
own previous_league_id link. These tests use that exact real id pair as
fixture data.
"""

from unittest.mock import patch

from modules import sleeper_leagues

REVIVALRY_2025_ID = "1250325243881345024"
REVIVALRY_2026_ID = "1325866097718620160"
WAR_ROOM_2026_ID = "1353858597108350976"
USERNAME = "lukamagic777777"
USER_ID = "1250330298407723008"


def _response(payload, status_code=200):
    class _Resp:
        def __init__(self):
            self.status_code = status_code

        def json(self):
            return payload

    return _Resp()


def _real_shaped_requests_get(url, timeout=None):
    if url == f"https://api.sleeper.app/v1/user/{USERNAME}":
        return _response({"user_id": USER_ID})
    if url == f"https://api.sleeper.app/v1/user/{USER_ID}/leagues/nfl/2026":
        return _response(
            [
                {"league_id": WAR_ROOM_2026_ID, "season": "2026", "name": "The War Room"},
                {
                    "league_id": REVIVALRY_2026_ID,
                    "season": "2026",
                    "name": "Revivalry",
                    "previous_league_id": REVIVALRY_2025_ID,
                },
            ]
        )
    if url == f"https://api.sleeper.app/v1/user/{USER_ID}/leagues/nfl/2025":
        return _response(
            [
                {
                    "league_id": REVIVALRY_2025_ID,
                    "season": "2025",
                    "name": "Revivalry",
                    "previous_league_id": None,
                },
            ]
        )
    raise AssertionError(f"unexpected Sleeper URL in this test: {url}")


class TestResolveCurrentSeasonLeagueId:
    def test_walks_previous_league_id_chain_forward(self):
        leagues = [
            {"league_id": REVIVALRY_2026_ID, "season": "2026", "previous_league_id": REVIVALRY_2025_ID},
            {"league_id": REVIVALRY_2025_ID, "season": "2025", "previous_league_id": None},
        ]

        assert (
            sleeper_leagues.resolve_current_season_league_id(REVIVALRY_2025_ID, leagues)
            == REVIVALRY_2026_ID
        )

    def test_returns_original_id_unchanged_when_already_current(self):
        leagues = [
            {"league_id": REVIVALRY_2026_ID, "season": "2026", "previous_league_id": REVIVALRY_2025_ID},
        ]

        assert (
            sleeper_leagues.resolve_current_season_league_id(REVIVALRY_2026_ID, leagues)
            == REVIVALRY_2026_ID
        )

    def test_returns_original_id_unchanged_when_no_chain_found(self):
        # A deleted/unavailable league, or a bogus id -- never guess.
        assert sleeper_leagues.resolve_current_season_league_id("nonexistent", []) == "nonexistent"

    def test_never_infinite_loops_on_a_cyclical_previous_league_id(self):
        leagues = [
            {"league_id": "a", "previous_league_id": "b"},
            {"league_id": "b", "previous_league_id": "a"},
        ]

        # Must terminate; exact landing id isn't the point, not hanging is.
        result = sleeper_leagues.resolve_current_season_league_id("a", leagues)
        assert result in {"a", "b"}


class TestResolveSavedLeagueRollover:
    def test_resolves_a_stale_saved_league_id_to_its_current_season_continuation(self):
        with patch("modules.sleeper_leagues.requests.get", side_effect=_real_shaped_requests_get):
            resolved = sleeper_leagues.resolve_saved_league_rollover(
                REVIVALRY_2025_ID, USERNAME, season=2026
            )

        assert resolved == REVIVALRY_2026_ID

    def test_leaves_an_already_current_season_league_id_unchanged(self):
        with patch("modules.sleeper_leagues.requests.get", side_effect=_real_shaped_requests_get):
            resolved = sleeper_leagues.resolve_saved_league_rollover(
                REVIVALRY_2026_ID, USERNAME, season=2026
            )

        assert resolved == REVIVALRY_2026_ID

    def test_leaves_an_unrelated_stale_league_id_unchanged_when_no_chain_links_to_it(self):
        # This user's OWN leagues don't chain back to some other league_id
        # that merely happens to also be stale -- never guess a resolution
        # that Sleeper's own data doesn't support.
        with patch("modules.sleeper_leagues.requests.get", side_effect=_real_shaped_requests_get):
            resolved = sleeper_leagues.resolve_saved_league_rollover(
                "some-other-leagues-stale-id", USERNAME, season=2026
            )

        assert resolved == "some-other-leagues-stale-id"

    def test_returns_original_id_unchanged_on_a_lookup_failure(self):
        with patch("modules.sleeper_leagues.requests.get", side_effect=Exception("network down")):
            resolved = sleeper_leagues.resolve_saved_league_rollover(
                REVIVALRY_2025_ID, USERNAME, season=2026
            )

        assert resolved == REVIVALRY_2025_ID

    def test_returns_original_id_unchanged_for_missing_inputs(self):
        assert sleeper_leagues.resolve_saved_league_rollover("", USERNAME) == ""
        assert sleeper_leagues.resolve_saved_league_rollover(REVIVALRY_2025_ID, "") == REVIVALRY_2025_ID

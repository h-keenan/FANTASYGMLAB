"""Real production bug, 2026-10-21 (coridian_, live, real affected account):
a saved league (public.saved_leagues) keeps pointing at last season's now-
frozen league_id forever once the real Sleeper league rolls over to a new
one -- nothing re-points it. This silently fed a stale, prior-season
roster view (services.mobile_api_service._resolve_my_roster resolves "my
roster" strictly by owner_id WITHIN whichever league_id it's handed) and,
via modules.guess_the_player_leaderboard's own direct saved_leagues query,
a leaderboard that only matches leaguemates sharing the viewer's own exact
(stale-or-fresh) league_id.

Real, live-verified example: Sleeper username "lukamagic777777", league
"Revivalry" -- 2025 league_id 1250325243881345024 (status complete) rolled
over to 2026 league_id 1325866097718620160 (status in_season), linked via
Sleeper's own previous_league_id. These tests use that exact real id pair.

These exercise services/mobile_api_service.py's
_apply_league_rollover_resolution / _fetch_saved_leagues_cached directly
(not through the full HTTP+auth stack) since the resolution logic itself
is the thing under test, not request plumbing already covered elsewhere.
"""

from unittest.mock import Mock, patch

from services import mobile_api_service

REVIVALRY_2025_ID = "1250325243881345024"
REVIVALRY_2026_ID = "1325866097718620160"
USERNAME = "lukamagic777777"
CONFIG = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}


def test_apply_league_rollover_resolution_corrects_a_stale_row_and_migrates_it():
    row = {
        "league_id": REVIVALRY_2025_ID,
        "league_name": "Revivalry",
        "sleeper_username": USERNAME,
        "is_default": True,
        "owner_id": "1250330298407723008",
        "roster_id": "5",
        "team_id": "5",
    }

    with patch(
        "services.mobile_api_service.sleeper_leagues.resolve_saved_league_rollover",
        return_value=REVIVALRY_2026_ID,
    ) as resolve_mock, patch(
        "services.mobile_api_service.account_store.migrate_saved_league",
        return_value=(True, ""),
    ) as migrate_mock:
        resolved_rows = mobile_api_service._apply_league_rollover_resolution(
            CONFIG, "access-token", "user-1", [row]
        )

    resolve_mock.assert_called_once_with(REVIVALRY_2025_ID, USERNAME)
    assert resolved_rows == [{**row, "league_id": REVIVALRY_2026_ID}]
    migrate_mock.assert_called_once()
    _, kwargs = migrate_mock.call_args
    assert kwargs["user_id"] == "user-1"
    assert kwargs["old_league_id"] == REVIVALRY_2025_ID
    assert kwargs["new_league_id"] == REVIVALRY_2026_ID
    assert kwargs["sleeper_username"] == USERNAME
    assert kwargs["is_default"] is True


def test_apply_league_rollover_resolution_leaves_a_current_season_row_untouched():
    row = {"league_id": REVIVALRY_2026_ID, "sleeper_username": USERNAME, "league_name": "Revivalry"}

    with patch(
        "services.mobile_api_service.sleeper_leagues.resolve_saved_league_rollover",
        return_value=REVIVALRY_2026_ID,
    ), patch("services.mobile_api_service.account_store.migrate_saved_league") as migrate_mock:
        resolved_rows = mobile_api_service._apply_league_rollover_resolution(
            CONFIG, "access-token", "user-1", [row]
        )

    assert resolved_rows == [row]
    migrate_mock.assert_not_called()


def test_apply_league_rollover_resolution_skips_rows_without_a_sleeper_username():
    # No per-league sleeper_username captured (e.g. a row saved before that
    # column was ever populated) -- never guess which Sleeper account to
    # resolve against, never make a network call for it.
    row = {"league_id": REVIVALRY_2025_ID, "league_name": "Revivalry"}

    with patch(
        "services.mobile_api_service.sleeper_leagues.resolve_saved_league_rollover"
    ) as resolve_mock:
        resolved_rows = mobile_api_service._apply_league_rollover_resolution(
            CONFIG, "access-token", "user-1", [row]
        )

    assert resolved_rows == [row]
    resolve_mock.assert_not_called()


def test_apply_league_rollover_resolution_still_returns_the_resolved_id_when_the_migration_write_fails():
    # The corrected id must be used for THIS request/response regardless of
    # whether persisting it to Supabase succeeds -- a failed write affects
    # only what's saved for next time, never this response.
    row = {"league_id": REVIVALRY_2025_ID, "sleeper_username": USERNAME, "league_name": "Revivalry"}

    with patch(
        "services.mobile_api_service.sleeper_leagues.resolve_saved_league_rollover",
        return_value=REVIVALRY_2026_ID,
    ), patch(
        "services.mobile_api_service.account_store.migrate_saved_league",
        side_effect=Exception("supabase down"),
    ):
        resolved_rows = mobile_api_service._apply_league_rollover_resolution(
            CONFIG, "access-token", "user-1", [row]
        )

    assert resolved_rows[0]["league_id"] == REVIVALRY_2026_ID


def test_apply_league_rollover_resolution_handles_mixed_stale_and_current_rows():
    stale_row = {"league_id": REVIVALRY_2025_ID, "sleeper_username": USERNAME, "league_name": "Revivalry"}
    other_row = {"league_id": "unrelated-league", "sleeper_username": "someone-else"}

    def _fake_resolve(league_id, sleeper_username):
        if league_id == REVIVALRY_2025_ID:
            return REVIVALRY_2026_ID
        return league_id

    with patch(
        "services.mobile_api_service.sleeper_leagues.resolve_saved_league_rollover",
        side_effect=_fake_resolve,
    ), patch("services.mobile_api_service.account_store.migrate_saved_league", return_value=(True, "")):
        resolved_rows = mobile_api_service._apply_league_rollover_resolution(
            CONFIG, "access-token", "user-1", [stale_row, other_row]
        )

    assert resolved_rows[0]["league_id"] == REVIVALRY_2026_ID
    assert resolved_rows[1]["league_id"] == "unrelated-league"


def test_fetch_saved_leagues_cached_applies_rollover_resolution_end_to_end():
    stale_row = {"league_id": REVIVALRY_2025_ID, "sleeper_username": USERNAME, "league_name": "Revivalry"}

    with patch(
        "services.mobile_api_service.account_store.fetch_saved_leagues",
        return_value=([stale_row], ""),
    ), patch(
        "services.mobile_api_service.sleeper_leagues.resolve_saved_league_rollover",
        return_value=REVIVALRY_2026_ID,
    ), patch("services.mobile_api_service.account_store.migrate_saved_league", return_value=(True, "")):
        rows, error = mobile_api_service._fetch_saved_leagues_cached(CONFIG, "access-token", "user-1")

    assert error == ""
    assert rows[0]["league_id"] == REVIVALRY_2026_ID


def test_fetch_saved_leagues_cached_short_circuits_on_error_without_resolving():
    with patch(
        "services.mobile_api_service.account_store.fetch_saved_leagues",
        return_value=([], "Could not reach Supabase table storage."),
    ), patch(
        "services.mobile_api_service.sleeper_leagues.resolve_saved_league_rollover"
    ) as resolve_mock:
        rows, error = mobile_api_service._fetch_saved_leagues_cached(CONFIG, "access-token", "user-1")

    assert rows == []
    assert error == "Could not reach Supabase table storage."
    resolve_mock.assert_not_called()


def test_resolve_league_rollover_cached_fails_open_to_original_id_on_any_error():
    with patch(
        "services.mobile_api_service.sleeper_leagues.resolve_saved_league_rollover",
        side_effect=Exception("network down"),
    ):
        resolved = mobile_api_service._resolve_league_rollover_cached(REVIVALRY_2025_ID, USERNAME)

    assert resolved == REVIVALRY_2025_ID


def test_resolve_league_rollover_cached_returns_original_id_for_missing_inputs():
    assert mobile_api_service._resolve_league_rollover_cached("", USERNAME) == ""
    assert (
        mobile_api_service._resolve_league_rollover_cached(REVIVALRY_2025_ID, "")
        == REVIVALRY_2025_ID
    )

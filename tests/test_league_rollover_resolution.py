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


# --- resolve_league_path_id --------------------------------------------
#
# 3rd real production fix attempt on the same user-visible symptom
# tonight (coridian_, 2026-10-21, live-confirmed against production with a
# disposable test account): PR #1312's _apply_league_rollover_resolution
# above only ever ran when enumerating a user's saved-leagues LIST. It
# never touched the ~40 OTHER mobile API endpoints that take `league_id`
# directly as a URL path parameter (my-roster, dashboard, trade-hub,
# waivers, matchup, etc.) -- so a client hitting one of those with a
# league_id it already had in hand from BEFORE the rollover was noticed
# (a saved-league row fetched earlier, a deep link, cached local state)
# got served last season's frozen data with no resolution check at all.
# resolve_league_path_id is the shared FastAPI dependency that closes that
# gap; these tests exercise it directly, using the same real Revivalry
# id pair as every other rollover test in this repo.

USER = {"id": "user-1", "_access_token": "access-token"}


def test_resolve_league_path_id_resolves_a_stale_complete_league_for_the_real_repro():
    """The exact repro this bug fix was validated against: a caller whose
    OWN linked profile.sleeper_username is the real Revivalry member, and
    whose saved league_id path param is still the frozen 2025 id."""

    with patch("modules.sleeper.get_league", return_value={"status": "complete"}), patch(
        "services.mobile_api_service._fetch_profile_fields",
        return_value={"sleeper_username": USERNAME},
    ), patch(
        "services.mobile_api_service.sleeper_leagues.resolve_saved_league_rollover",
        return_value=REVIVALRY_2026_ID,
    ) as resolve_mock:
        resolved = mobile_api_service.resolve_league_path_id(REVIVALRY_2025_ID, user=USER)

    assert resolved == REVIVALRY_2026_ID
    resolve_mock.assert_called_once_with(REVIVALRY_2025_ID, USERNAME)


def test_resolve_league_path_id_skips_the_rollover_lookup_entirely_for_a_non_complete_league():
    """Cost control: a league Sleeper reports as pre_draft/drafting/
    in_season cannot possibly be stale (no newer id can exist yet for it),
    so this must never even reach the Sleeper leagues-list lookup -- the
    overwhelmingly common case pays zero extra network cost."""

    with patch("modules.sleeper.get_league", return_value={"status": "in_season"}), patch(
        "services.mobile_api_service._fetch_profile_fields"
    ) as profile_mock, patch(
        "services.mobile_api_service.sleeper_leagues.resolve_saved_league_rollover"
    ) as resolve_mock:
        resolved = mobile_api_service.resolve_league_path_id(REVIVALRY_2026_ID, user=USER)

    assert resolved == REVIVALRY_2026_ID
    profile_mock.assert_not_called()
    resolve_mock.assert_not_called()


def test_resolve_league_path_id_is_a_noop_when_the_league_status_is_unknown():
    """A missing/unreachable league object (empty dict -- no `status` key,
    the shape a mocked or transport-failed sleeper.get_league returns)
    must never be treated as "stale" by default -- only an EXPLICIT
    `status == "complete"` opts a league into the extra lookup."""

    with patch("modules.sleeper.get_league", return_value={}), patch(
        "services.mobile_api_service.sleeper_leagues.resolve_saved_league_rollover"
    ) as resolve_mock:
        resolved = mobile_api_service.resolve_league_path_id(REVIVALRY_2025_ID, user=USER)

    assert resolved == REVIVALRY_2025_ID
    resolve_mock.assert_not_called()


def test_resolve_league_path_id_is_a_noop_for_a_caller_with_no_linked_sleeper_username():
    """A signed-in user who has never linked Sleeper (or has no saved
    leagues either) can't be resolved against anything -- never guess,
    just return the id unchanged, same as a public/unsaved league view."""

    with patch("modules.sleeper.get_league", return_value={"status": "complete"}), patch(
        "services.mobile_api_service._fetch_profile_fields", return_value={"sleeper_username": ""}
    ), patch(
        "services.mobile_api_service._fetch_saved_leagues_cached", return_value=([], "")
    ), patch(
        "services.mobile_api_service.sleeper_leagues.resolve_saved_league_rollover"
    ) as resolve_mock:
        resolved = mobile_api_service.resolve_league_path_id(REVIVALRY_2025_ID, user=USER)

    assert resolved == REVIVALRY_2025_ID
    resolve_mock.assert_not_called()


def test_resolve_league_path_id_is_safe_for_a_league_the_caller_has_no_real_connection_to():
    """Public/leaguemate-shared league_id safety: a candidate username
    that exists but has no real chain link back to this id is an
    unconditional no-op, never a wrong guess (resolve_saved_league_rollover
    itself enforces this; this test locks in that resolve_league_path_id
    passes the real id through to it rather than short-circuiting)."""

    with patch("modules.sleeper.get_league", return_value={"status": "complete"}), patch(
        "services.mobile_api_service._fetch_profile_fields",
        return_value={"sleeper_username": "someone-unrelated"},
    ), patch(
        "services.mobile_api_service.sleeper_leagues.resolve_saved_league_rollover",
        return_value="some-other-leagues-stale-id",
    ) as resolve_mock:
        resolved = mobile_api_service.resolve_league_path_id(
            "some-other-leagues-stale-id", user=USER
        )

    assert resolved == "some-other-leagues-stale-id"
    resolve_mock.assert_called_once_with("some-other-leagues-stale-id", "someone-unrelated")


def test_resolve_league_path_id_falls_back_to_a_saved_leagues_row_username():
    """profile.sleeper_username empty, but the caller has a saved_leagues
    row with its own per-league username (the "linked a second Sleeper
    account" case _resolve_my_roster already handles) -- that row's
    username is a valid fallback resolution candidate."""

    with patch("modules.sleeper.get_league", return_value={"status": "complete"}), patch(
        "services.mobile_api_service._fetch_profile_fields", return_value={"sleeper_username": ""}
    ), patch(
        "services.mobile_api_service._fetch_saved_leagues_cached",
        return_value=([{"league_id": REVIVALRY_2025_ID, "sleeper_username": USERNAME}], ""),
    ), patch(
        "services.mobile_api_service.sleeper_leagues.resolve_saved_league_rollover",
        return_value=REVIVALRY_2026_ID,
    ) as resolve_mock:
        resolved = mobile_api_service.resolve_league_path_id(REVIVALRY_2025_ID, user=USER)

    assert resolved == REVIVALRY_2026_ID
    resolve_mock.assert_called_once_with(REVIVALRY_2025_ID, USERNAME)


def test_resolve_league_path_id_fails_open_on_any_unexpected_error():
    """A transport blip, a malformed league object, a Supabase hiccup --
    nothing in this dependency may ever turn into a 500 or a wrong league;
    the original path param always reaches the route unchanged."""

    with patch("modules.sleeper.get_league", side_effect=Exception("boom")):
        resolved = mobile_api_service.resolve_league_path_id(REVIVALRY_2025_ID, user=USER)

    assert resolved == REVIVALRY_2025_ID


def test_resolve_league_path_id_returns_the_id_unchanged_for_an_unauthenticated_shaped_user():
    assert mobile_api_service.resolve_league_path_id(REVIVALRY_2025_ID, user={}) == REVIVALRY_2025_ID
    assert mobile_api_service.resolve_league_path_id("", user=USER) == ""


# --- end-to-end: GET /v1/leagues/{league_id}/my-roster ------------------
#
# The exact HTTP-level repro: a stale path param reaching the real route,
# not just the dependency function in isolation.


def test_my_roster_endpoint_resolves_a_stale_rolled_over_league_id_in_the_url(monkeypatch):
    """This is the literal bug report: GET a saved league's my-roster
    using the STALE 2025 league_id exactly as a client would have it in
    hand, for an account whose linked Sleeper username (the real
    Revivalry member) has since rolled over to the 2026 league. Must
    resolve forward and return the CURRENT season's roster -- never the
    frozen 2025 one -- with no client-visible error."""

    import pytest

    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from unittest.mock import Mock

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    client = TestClient(mobile_api_service.app)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-revivalry", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": USERNAME}]

    with patch("modules.sleeper.get_league", return_value={"status": "complete"}):
        with patch("requests.get", side_effect=[auth_user_response, profile_response]):
            with patch(
                "services.mobile_api_service.sleeper_leagues.resolve_saved_league_rollover",
                return_value=REVIVALRY_2026_ID,
            ):
                with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
                    with patch(
                        "modules.sleeper.get_rosters",
                        return_value=[
                            {"roster_id": 5, "owner_id": "sleeper-user-1", "players": ["p1", "p2"]},
                        ],
                    ) as get_rosters_mock:
                        response = client.get(
                            f"/v1/leagues/{REVIVALRY_2025_ID}/my-roster",
                            headers={"Authorization": "Bearer good-token"},
                        )

    assert response.status_code == 200
    body = response.json()
    assert body["reason"] == ""
    assert body["roster"]["roster_id"] == 5
    # The REAL point of this test: Sleeper's roster lookup must have run
    # against the RESOLVED, current-season id -- never the stale one the
    # client sent in the URL.
    get_rosters_mock.assert_called_once_with(REVIVALRY_2026_ID)


def test_my_roster_endpoint_leaves_a_current_season_league_id_untouched(monkeypatch):
    """Control case: a league_id that's already current-season (status
    != "complete") must reach sleeper.get_rosters verbatim, with no
    rollover lookup attempted at all."""

    import pytest

    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from unittest.mock import Mock

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    client = TestClient(mobile_api_service.app)

    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-revivalry-2", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": "free", "sleeper_username": USERNAME}]

    with patch("modules.sleeper.get_league", return_value={"status": "in_season"}):
        with patch("requests.get", side_effect=[auth_user_response, profile_response]):
            with patch(
                "services.mobile_api_service.sleeper_leagues.resolve_saved_league_rollover"
            ) as resolve_mock:
                with patch("modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"):
                    with patch(
                        "modules.sleeper.get_rosters",
                        return_value=[
                            {"roster_id": 9, "owner_id": "sleeper-user-1", "players": ["p1"]},
                        ],
                    ) as get_rosters_mock:
                        response = client.get(
                            f"/v1/leagues/{REVIVALRY_2026_ID}/my-roster",
                            headers={"Authorization": "Bearer good-token"},
                        )

    assert response.status_code == 200
    body = response.json()
    assert body["roster"]["roster_id"] == 9
    resolve_mock.assert_not_called()
    get_rosters_mock.assert_called_once_with(REVIVALRY_2026_ID)

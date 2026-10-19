"""coridian_, 2026-10-19: real-production perf audit finding.

modules.sleeper_leagues.resolve_sleeper_user_id used to maintain its own,
completely UNCACHED Sleeper username -> user_id lookup (_resolve_user_id),
duplicating modules.sleeper.get_user_id's logic almost exactly — except
get_user_id has carried an @lru_cache for this exact (effectively
permanent) mapping the whole time. resolve_sleeper_user_id is called from
services.mobile_api_service._resolve_my_roster on nearly every
league-scoped request (Dashboard, Trade Hub, Waivers, My Team, Trade
Finder, Portfolio's own per-league fan-out) — a real, uncached Sleeper
network round trip on every single one, for a value that never changes.
"""

from unittest.mock import patch

from modules import sleeper, sleeper_leagues


def test_resolve_sleeper_user_id_reuses_get_user_ids_cache_instead_of_a_second_uncached_lookup():
    # A unique-per-test-run username avoids any cross-test pollution from
    # get_user_id's process-global @lru_cache (shared by the whole pytest
    # process, same as every other call site that already relies on it).
    username = "perf-audit-cache-check-20261019"
    sleeper.get_user_id.cache_clear()

    fetch_mock = (
        lambda label, url, **kwargs: {"user_id": "resolved-user-id-123"} if label == "sleeper_user_lookup" else None
    )

    with patch("modules.sleeper._request_json", side_effect=fetch_mock) as mocked:
        first = sleeper_leagues.resolve_sleeper_user_id(username)
        second = sleeper_leagues.resolve_sleeper_user_id(username)
        # Also prove it's the SAME cache get_user_id itself hits — not a
        # second, independently-keyed one — by calling that directly too.
        third = sleeper.get_user_id(username)

    assert first == "resolved-user-id-123"
    assert second == "resolved-user-id-123"
    assert third == "resolved-user-id-123"
    assert mocked.call_count == 1, "expected only the FIRST call to hit the network at all"

    sleeper.get_user_id.cache_clear()

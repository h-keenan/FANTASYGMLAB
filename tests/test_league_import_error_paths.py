"""League import / sync error paths (docs/audits/2026-11-league-import-error-paths.md).

Every provider response is mocked (requests.get / fetch hooks); nothing here touches Sleeper, ESPN, Fleaflicker or MFL.
"""

from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import Mock, patch

import pytest
import requests

from modules import provider_errors, sleeper, sleeper_budget, sleeper_cache, sleeper_leagues
from modules import external_league_common as elc
from modules.external_league_common import ExternalLeagueError, SnapshotCache


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(sleeper.time, "sleep", lambda _s: None)
    sleeper_cache.reset_for_tests()
    sleeper_budget.reset_for_tests()
    sleeper._FAILURE_KIND_BY_URL.clear()
    for fn in (
        sleeper._get_league_cached,
        sleeper._get_rosters_cached,
        sleeper._get_users_cached,
        sleeper.get_user_id,
        sleeper.get_league_drafts,
        sleeper.get_draft,
        sleeper.get_draft_picks,
    ):
        fn.cache_clear()
    yield
    sleeper_cache.reset_for_tests()


def resp(status=200, payload=None, bad_json=False):
    r = Mock()
    r.status_code = status
    if bad_json:
        r.json.side_effect = ValueError("not json")
    else:
        r.json.return_value = payload
    return r


# ---------------------------------------------------------------- username / league list lookup


def _router(user, by_year):
    """requests.get stand-in: `user` answers /user/<name>, `by_year` maps year -> response or exception."""

    def fake(url, timeout=0):
        if "/leagues/nfl/" in url:
            out = by_year[int(url.rsplit("/", 1)[1])]
        else:
            out = user
        if isinstance(out, Exception):
            raise out
        return out

    return fake


YEAR = 2026


@pytest.mark.parametrize(
    "user,expected",
    [
        (resp(503), "unavailable"),
        (resp(500), "unavailable"),
        (requests.Timeout("slow"), "unavailable"),
        (requests.ConnectionError("down"), "unavailable"),
        (resp(200, bad_json=True), "unavailable"),
        (resp(200, ["not", "a", "user"]), "unavailable"),
        (resp(429), "rate_limited"),
        (resp(200, None), "user_not_found"),
        (resp(404), "user_not_found"),
    ],
)
def test_username_lookup_failure_modes(user, expected):
    with patch("modules.sleeper_leagues.requests.get", side_effect=_router(user, {})):
        result = sleeper_leagues.lookup_user_leagues("someone", season=YEAR)
    assert result.status == expected
    assert result.leagues == []


def test_zero_leagues_is_no_leagues_not_an_error():
    user = resp(200, {"user_id": "u1"})
    with patch("modules.sleeper_leagues.requests.get", side_effect=_router(user, {YEAR: resp(200, []), YEAR - 1: resp(200, [])})):
        result = sleeper_leagues.lookup_user_leagues("someone", season=YEAR)
    assert (result.status, result.partial) == ("no_leagues", False)


def test_one_season_failing_while_other_is_empty_is_unavailable_not_no_leagues():
    user = resp(200, {"user_id": "u1"})
    with patch("modules.sleeper_leagues.requests.get", side_effect=_router(user, {YEAR: resp(200, []), YEAR - 1: resp(503)})):
        result = sleeper_leagues.lookup_user_leagues("someone", season=YEAR)
    assert result.status == "unavailable"


def test_rate_limited_league_list_with_nothing_else_is_rate_limited():
    user = resp(200, {"user_id": "u1"})
    with patch("modules.sleeper_leagues.requests.get", side_effect=_router(user, {YEAR: resp(429), YEAR - 1: resp(429)})):
        result = sleeper_leagues.lookup_user_leagues("someone", season=YEAR)
    assert result.status == "rate_limited"
    assert "limiting" in sleeper_leagues.league_lookup_customer_message(result.status)


def test_partial_lookup_returns_leagues_but_says_partial():
    user = resp(200, {"user_id": "u1"})
    leagues = [{"league_id": "L1", "name": "A"}]
    with patch("modules.sleeper_leagues.requests.get", side_effect=_router(user, {YEAR: resp(200, leagues), YEAR - 1: resp(500)})):
        result = sleeper_leagues.lookup_user_leagues("someone", season=YEAR)
    assert result.status == "ok" and result.partial is True
    assert [lg["league_id"] for lg in result.leagues] == ["L1"]


def test_complete_lookup_is_not_partial():
    user = resp(200, {"user_id": "u1"})
    leagues = [{"league_id": "L1", "name": "A"}]
    with patch("modules.sleeper_leagues.requests.get", side_effect=_router(user, {YEAR: resp(200, leagues), YEAR - 1: resp(200, [])})):
        result = sleeper_leagues.lookup_user_leagues("someone", season=YEAR)
    assert result.partial is False


def test_malformed_league_list_shapes_are_unavailable_and_junk_entries_skipped():
    user = resp(200, {"user_id": "u1"})
    with patch("modules.sleeper_leagues.requests.get", side_effect=_router(user, {YEAR: resp(200, {"oops": 1}), YEAR - 1: resp(200, {"oops": 1})})):
        assert sleeper_leagues.lookup_user_leagues("someone", season=YEAR).status == "unavailable"
    mixed = [None, "x", {"name": "no id"}, {"league_id": "L9", "name": "ok"}]
    with patch("modules.sleeper_leagues.requests.get", side_effect=_router(user, {YEAR: resp(200, mixed), YEAR - 1: resp(200, [])})):
        result = sleeper_leagues.lookup_user_leagues("someone", season=YEAR)
    assert [lg["league_id"] for lg in result.leagues] == ["L9"]


def test_empty_username_status():
    assert sleeper_leagues.lookup_user_leagues("   ").status == "empty_username"


# ---------------------------------------------------------------- user id: failures are never cached


def test_transient_user_lookup_failure_is_not_cached_and_retries():
    seq = [resp(503)] * 9 + [resp(200, {"user_id": "u7"})]
    with patch("modules.sleeper.requests.get", side_effect=seq):
        assert sleeper.get_user_id("Zed") is None  # Sleeper down: None for this call only
    with patch("modules.sleeper.requests.get", return_value=resp(200, {"user_id": "u7"})):
        assert sleeper.get_user_id("Zed") == "u7"  # recovered: a cached failure would still say None


def test_get_user_id_checked_raises_typed_errors_and_none_means_not_found():
    with patch("modules.sleeper.requests.get", return_value=resp(503)):
        with pytest.raises(provider_errors.ProviderUnavailableError):
            sleeper.get_user_id_checked("nobody-a")
    with patch("modules.sleeper.requests.get", return_value=resp(429)):
        with pytest.raises(provider_errors.ProviderRateLimitedError):
            sleeper.get_user_id_checked("nobody-b")
    with patch("modules.sleeper.requests.get", return_value=resp(200, ["junk"])):
        with pytest.raises(provider_errors.ProviderBadResponseError):
            sleeper.get_user_id_checked("nobody-c")
    with patch("modules.sleeper.requests.get", return_value=resp(200, None)):
        assert sleeper.get_user_id_checked("nobody-d") is None


def test_flag_off_restores_legacy_user_lookup(monkeypatch):
    monkeypatch.setenv(provider_errors.TYPED_ERRORS_FLAG, "0")
    with patch("modules.sleeper.requests.get", return_value=resp(503)):
        assert sleeper.get_user_id_checked("legacy-user") is None


# ---------------------------------------------------------------- rosters / league: typed errors


def test_rosters_checked_provider_down_raises_unavailable():
    with patch("modules.sleeper.requests.get", return_value=resp(503)):
        with pytest.raises(provider_errors.ProviderUnavailableError):
            sleeper.get_rosters_checked("LDOWN")


def test_rosters_checked_timeout_raises_unavailable():
    with patch("modules.sleeper.requests.get", side_effect=requests.Timeout("t")):
        with pytest.raises(provider_errors.ProviderUnavailableError):
            sleeper.get_rosters_checked("LTIME")


def test_rosters_checked_rate_limit_raises_rate_limited():
    with patch("modules.sleeper.requests.get", return_value=resp(429)):
        with pytest.raises(provider_errors.ProviderRateLimitedError):
            sleeper.get_rosters_checked("LRATE")


def test_rosters_checked_malformed_json_raises_bad_response():
    with patch("modules.sleeper.requests.get", return_value=resp(200, bad_json=True)):
        with pytest.raises(provider_errors.ProviderBadResponseError):
            sleeper.get_rosters_checked("LJSON")


def test_rosters_checked_wrong_shape_raises_bad_response():
    with patch("modules.sleeper.requests.get", return_value=resp(200, {"error": "x"})):
        with pytest.raises(provider_errors.ProviderBadResponseError):
            sleeper.get_rosters_checked("LSHAPE")


def test_empty_pre_draft_league_returns_empty_list_not_an_error():
    with patch("modules.sleeper.requests.get", return_value=resp(200, [])):
        assert sleeper.get_rosters_checked("LEMPTY") == []


def test_null_rosters_body_is_league_not_found():
    with patch("modules.sleeper.requests.get", return_value=resp(200, None)):
        with pytest.raises(provider_errors.LeagueNotFoundError):
            sleeper.get_rosters_checked("LNULL")


def test_unknown_league_id_is_league_not_found():
    with patch("modules.sleeper.requests.get", return_value=resp(200, None)):
        with pytest.raises(provider_errors.LeagueNotFoundError):
            sleeper.get_league_checked("NOPE1")
    with patch("modules.sleeper.requests.get", return_value=resp(404)):
        with pytest.raises(provider_errors.LeagueNotFoundError):
            sleeper.get_league_checked("NOPE2")


def test_league_checked_outage_is_unavailable_not_not_found():
    with patch("modules.sleeper.requests.get", return_value=resp(502)):
        with pytest.raises(provider_errors.ProviderUnavailableError):
            sleeper.get_league_checked("LOUT")


def test_stale_cache_after_failed_refresh_is_served_and_labelled_with_its_age(monkeypatch):
    monkeypatch.setattr(sleeper_cache, "_fresh_floor", 0.0)
    url = f"{sleeper.SLEEPER_BASE}/league/LSTALE/rosters"
    with patch("modules.sleeper.requests.get", return_value=resp(200, [{"roster_id": 1, "owner_id": "u1", "players": ["1"]}])):
        first = sleeper.get_rosters_checked("LSTALE")
    assert first[0]["roster_id"] == 1
    time.sleep(0.02)
    sleeper_cache._fresh_floor = time.time()  # nothing fetched so far counts as fresh; it still serves as stale-on-error
    sleeper_budget.begin_request()
    with patch("modules.sleeper.requests.get", return_value=resp(503)):
        second = sleeper.get_rosters_checked("LSTALE")
    assert second[0]["roster_id"] == 1
    assert sleeper_budget.stale_as_of() is not None, "stale data must carry its age (sleeper_data_as_of)"
    assert url


def test_flag_off_restores_legacy_empty_on_outage(monkeypatch):
    monkeypatch.setenv(provider_errors.TYPED_ERRORS_FLAG, "0")
    with patch("modules.sleeper.requests.get", return_value=resp(503)):
        assert sleeper.get_rosters_checked("LLEGACY") == []
        assert sleeper.get_league_checked("LLEGACY") == {}


# ---------------------------------------------------------------- partial rosters


def test_partial_rosters_are_sanitized_and_orphans_kept():
    payload = [
        {"roster_id": 1, "owner_id": "u1", "players": None, "starters": None},
        {"roster_id": 2, "owner_id": None, "players": ["4046", None]},
        None,
        "garbage",
        {"roster_id": 3, "players": ["1"], "starters": ["1"]},
    ]
    with patch("modules.sleeper.requests.get", return_value=resp(200, payload)):
        rosters = sleeper.get_rosters_checked("LPART")
    assert [r["roster_id"] for r in rosters] == [1, 2, 3]
    assert rosters[0]["players"] == [] and rosters[0]["starters"] == []
    assert rosters[1]["owner_id"] is None  # orphan team stays visible, just matches nobody
    assert rosters[2].get("owner_id") is None


def test_sanitize_flag_off_returns_payload_unchanged(monkeypatch):
    monkeypatch.setenv(provider_errors.ROSTER_SANITIZE_FLAG, "0")
    payload = [{"roster_id": 1, "players": None}, None]
    assert sleeper.sanitize_rosters(payload) == payload


def test_unknown_player_ids_pass_through_untouched():
    payload = [{"roster_id": 1, "owner_id": "u1", "players": ["999999999", "retired-guy"]}]
    with patch("modules.sleeper.requests.get", return_value=resp(200, payload)):
        assert sleeper.get_rosters_checked("LUNK")[0]["players"] == ["999999999", "retired-guy"]


def test_format_change_mid_season_is_read_live_not_pinned():
    first = {"league_id": "LFMT", "settings": {"type": 0}, "scoring_settings": {"rec": 0.5}}
    second = {"league_id": "LFMT", "settings": {"type": 2}, "scoring_settings": {"rec": 1.0}}
    with patch("modules.sleeper.requests.get", return_value=resp(200, first)):
        assert sleeper.get_league_checked("LFMT")["settings"]["type"] == 0
    sleeper_cache.clear_local()
    with patch("modules.sleeper.requests.get", return_value=resp(200, second)):
        assert sleeper.get_league_checked("LFMT")["settings"]["type"] == 2


# ---------------------------------------------------------------- drafts: failure never cached


def test_failed_drafts_read_is_not_cached_forever():
    with patch("modules.sleeper.requests.get", return_value=resp(503)):
        assert sleeper.get_league_drafts("LDRAFT") == []
    with patch("modules.sleeper.requests.get", return_value=resp(200, [{"draft_id": "d1"}])):
        assert sleeper.get_league_drafts("LDRAFT") == [{"draft_id": "d1"}]


def test_failed_draft_picks_and_draft_reads_are_not_cached():
    with patch("modules.sleeper.requests.get", return_value=resp(200, bad_json=True)):
        assert sleeper.get_draft("D1") == {}
        assert sleeper.get_draft_picks("D1") == []
    with patch("modules.sleeper.requests.get", return_value=resp(200, {"draft_id": "D1"})):
        assert sleeper.get_draft("D1") == {"draft_id": "D1"}
    with patch("modules.sleeper.requests.get", return_value=resp(200, [{"pick_no": 1}])):
        assert sleeper.get_draft_picks("D1") == [{"pick_no": 1}]


# ---------------------------------------------------------------- imported platforms: failed refresh


def _boom(reason):
    def loader(_key):
        raise ExternalLeagueError(reason, "msg")

    return loader


def test_snapshot_cache_serves_stale_snapshot_when_refresh_is_unavailable():
    cache = SnapshotCache(ttl=0.0)
    snap = {"league": {"name": "L"}, "rosters": [], "users": []}
    assert cache.get("mfl:1:2026", lambda _k: snap) is snap
    sleeper_budget.begin_request()
    assert cache.get("mfl:1:2026", _boom("mfl_unavailable")) is snap
    assert sleeper_budget.stale_as_of() is not None


def test_snapshot_cache_serves_stale_on_rate_limit():
    cache = SnapshotCache(ttl=0.0)
    snap = {"league": {}, "rosters": [], "users": []}
    cache.get("fleaflicker:1:2026", lambda _k: snap)
    assert cache.get("fleaflicker:1:2026", _boom("fleaflicker_rate_limited")) is snap


@pytest.mark.parametrize("reason", ["private_league", "league_not_found"])
def test_snapshot_cache_never_serves_stale_for_a_league_that_went_private_or_missing(reason):
    cache = SnapshotCache(ttl=0.0)
    cache.get("mfl:1:2026", lambda _k: {"league": {}, "rosters": [], "users": []})
    assert cache.get("mfl:1:2026", _boom(reason)) is None


def test_snapshot_cache_with_nothing_cached_returns_none_on_failure():
    assert SnapshotCache(ttl=0.0).get("mfl:9:2026", _boom("mfl_unavailable")) is None


def test_snapshot_stale_flag_off_restores_legacy_none(monkeypatch):
    monkeypatch.setenv(provider_errors.STALE_SNAPSHOT_FLAG, "0")
    cache = SnapshotCache(ttl=0.0)
    cache.get("mfl:1:2026", lambda _k: {"league": {}, "rosters": [], "users": []})
    assert cache.get("mfl:1:2026", _boom("mfl_unavailable")) is None


def test_fleaflicker_429_has_its_own_reason():
    from modules import fleaflicker_leagues

    with patch("modules.fleaflicker_leagues.requests.get", return_value=resp(429)):
        with pytest.raises(ExternalLeagueError) as caught:
            fleaflicker_leagues._default_fetch("FetchLeagueRosters", {})
    assert caught.value.reason == "fleaflicker_rate_limited"
    assert "limiting" in caught.value.message


def test_fleaflicker_5xx_and_bad_json_stay_unavailable():
    from modules import fleaflicker_leagues

    for r in (resp(503), resp(200, bad_json=True)):
        with patch("modules.fleaflicker_leagues.requests.get", return_value=r):
            with pytest.raises(ExternalLeagueError) as caught:
                fleaflicker_leagues._default_fetch("FetchLeagueRosters", {})
        assert caught.value.reason == "fleaflicker_unavailable"


def test_espn_classifies_429_as_rate_limited():
    from modules import espn_leagues

    class Boom(Exception):
        status_code = 429

    assert espn_leagues._classify_load_error(Boom()).reason == "espn_rate_limited"
    assert espn_leagues._classify_load_error(RuntimeError("timeout")).reason == "espn_unavailable"


def test_mfl_429_is_rate_limited():
    from modules import mfl_leagues

    with patch("modules.mfl_leagues.requests.get", return_value=resp(429)):
        with pytest.raises(ExternalLeagueError) as caught:
            mfl_leagues._default_fetch("league", {"L": "1"}, 2026) if _mfl_takes_season(mfl_leagues) else mfl_leagues._default_fetch("2026", {"L": "1"})
    assert caught.value.reason == "mfl_rate_limited"


def _mfl_takes_season(module):
    import inspect

    return len(inspect.signature(module._default_fetch).parameters) >= 3


# ---------------------------------------------------------------- API mapping


def test_provider_error_handler_maps_to_status_reason_and_retry_after():
    from services import mobile_api_service as api

    request = Mock()
    request.method = "GET"
    request.url.path = "/v1/leagues/L1/dashboard"
    for exc, status, retry in (
        (provider_errors.ProviderUnavailableError(), 503, "5"),
        (provider_errors.ProviderRateLimitedError(), 429, "60"),
        (provider_errors.ProviderBadResponseError(), 502, "5"),
    ):
        response = asyncio.run(api._provider_error_handler(request, exc))
        body = json.loads(response.body)
        assert response.status_code == status
        assert body["ok"] is False and body["reason"] == exc.reason and body["retryable"] is True
        assert body["error"] == exc.message and "Sleeper" in body["error"]
        assert response.headers["retry-after"] == retry
    not_found = asyncio.run(api._provider_error_handler(request, provider_errors.LeagueNotFoundError()))
    assert not_found.status_code == 404 and "retry-after" not in not_found.headers
    assert json.loads(not_found.body)["error"] == "League not found."


def test_resolve_my_roster_outage_raises_instead_of_claiming_not_a_member(monkeypatch):
    from services import mobile_api_service as api

    monkeypatch.setattr(api.auth_supabase, "get_supabase_config", lambda: {})
    monkeypatch.setattr(api, "_fetch_saved_leagues_cached", lambda *a, **k: ([], None))
    monkeypatch.setattr(api, "_free_league_allowed", lambda *a, **k: True)
    user = {"id": "uid", "_access_token": "t"}
    profile = {"sleeper_username": "me", "entitlement": "free"}
    with patch("modules.sleeper.requests.get", return_value=resp(503)):
        with pytest.raises(provider_errors.ProviderError):
            api._resolve_my_roster(user, "LRESOLVE", profile=profile)


def test_resolve_my_roster_real_non_member_still_reads_not_a_member(monkeypatch):
    from services import mobile_api_service as api

    monkeypatch.setattr(api.auth_supabase, "get_supabase_config", lambda: {})
    monkeypatch.setattr(api, "_fetch_saved_leagues_cached", lambda *a, **k: ([], None))
    monkeypatch.setattr(api, "_free_league_allowed", lambda *a, **k: True)

    def fake(url, timeout=0):
        if "/user/" in url:
            return resp(200, {"user_id": "me-id"})
        return resp(200, [{"roster_id": 1, "owner_id": "someone-else", "players": []}])

    with patch("modules.sleeper.requests.get", side_effect=fake):
        roster, reason = api._resolve_my_roster({"id": "uid", "_access_token": "t"}, "LNM", profile={"sleeper_username": "me", "entitlement": "free"})
    assert roster is None and reason == "not_a_member_of_league"


def test_lookup_sleeper_leagues_response_carries_partial_and_rate_limited_message(monkeypatch):
    from services import mobile_api_service as api

    monkeypatch.setattr(api.auth_supabase, "get_supabase_config", lambda: {})
    ok = sleeper_leagues.LeagueLookupResult([{"league_id": "L1", "name": "A", "season": "2026", "total_rosters": 12}], "ok", partial=True)
    monkeypatch.setattr(api.sleeper_leagues, "lookup_user_leagues", lambda *a, **k: ok)
    out = api.lookup_sleeper_leagues(username="x", referral_code="", user={"id": "u"})
    assert out["partial"] is True and "missing leagues" in out["partial_message"]
    limited = sleeper_leagues.LeagueLookupResult([], "rate_limited")
    monkeypatch.setattr(api.sleeper_leagues, "lookup_user_leagues", lambda *a, **k: limited)
    out = api.lookup_sleeper_leagues(username="x", referral_code="", user={"id": "u"})
    assert out["ok"] is False and out["status"] == "rate_limited" and "limiting" in out["message"]


def test_league_missing_error_distinguishes_outage_from_unknown_league():
    from fastapi import HTTPException

    from services import mobile_api_service as api

    with patch("modules.sleeper.requests.get", return_value=resp(503)):
        assert sleeper.get_league("LDIAG1") == {}
    assert isinstance(api._league_missing_error("LDIAG1"), provider_errors.ProviderUnavailableError)
    with patch("modules.sleeper.requests.get", return_value=resp(200, None)):
        assert sleeper.get_league("LDIAG2") == {}
    err = api._league_missing_error("LDIAG2")
    assert isinstance(err, HTTPException) and err.status_code == 404 and err.detail == "League not found."
    assert isinstance(api._league_missing_error("never-fetched"), HTTPException)
    assert isinstance(api._league_missing_error("espn:1:2026"), HTTPException)


def test_save_league_reports_provider_unavailable_not_league_not_found(monkeypatch):
    from services import mobile_api_service as api

    with patch("modules.sleeper.requests.get", return_value=resp(503)):
        sleeper.get_league("LSAVE")
    assert sleeper.diagnose_league_failure("LSAVE").reason == "provider_unavailable"
    monkeypatch.setenv(provider_errors.TYPED_ERRORS_FLAG, "0")
    assert sleeper.diagnose_league_failure("LSAVE") is None

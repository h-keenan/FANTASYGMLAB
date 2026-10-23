"""Free league cap on EVERY league-scoped endpoint (paywall audit 2026-10, gaps 1 and 2).

`require_league_access` (services/mobile_api_service.py) is the one shared
gate: a Free account may use its saved league(s), or -- only while it has none
saved -- the single unsaved league claimed in modules.free_tier_ledger. Pro,
Front Office and trialing accounts are untouched. Fixtures come from
tests/test_paywall_leaks.py (real FastAPI app, fake auth/profile, fakeredis).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from modules import free_tier_ledger
from tests.test_paywall_leaks import AUTH, _hub, free_env  # noqa: F401  (fixture re-export)

# (method, path template) for the endpoints that do not resolve "my roster"
# and therefore had no league gate at all before the shared dependency.
GATED_ENDPOINTS = [
    ("GET", "/v1/leagues/{lid}/users"),
    ("GET", "/v1/leagues/{lid}/rosters"),
    ("GET", "/v1/leagues/{lid}/team-profiles"),
    ("GET", "/v1/leagues/{lid}/team-rankings"),
    ("GET", "/v1/leagues/{lid}/playoff-odds"),
    ("GET", "/v1/leagues/{lid}/draft-center"),
    ("GET", "/v1/leagues/{lid}/draft-picks"),
    ("GET", "/v1/leagues/{lid}/live-draft"),
    ("GET", "/v1/leagues/{lid}/live-draft/d1"),
    ("GET", "/v1/leagues/{lid}/live-draft/d1/trade-evaluator"),
    ("POST", "/v1/leagues/{lid}/live-draft/d1/trade-evaluator"),
    ("GET", "/v1/leagues/{lid}/rankings"),
    ("GET", "/v1/leagues/{lid}/idp/values"),
    ("GET", "/v1/leagues/{lid}/players/p1/rank"),
    ("GET", "/v1/leagues/{lid}/recap"),
    ("GET", "/v1/leagues/{lid}/history"),
    ("GET", "/v1/leagues/{lid}/storylines"),
    ("GET", "/v1/leagues/{lid}/managers/tendencies"),
    ("GET", "/v1/leagues/{lid}/managers/1/tendencies"),
    ("GET", "/v1/leagues/{lid}/guess-the-player/leaderboard"),
    ("POST", "/v1/leagues/{lid}/matchup/what-if"),
]

LOCKED_KEYS = {"ok", "reason", "league_locked", "league_id", "is_premium", "upsell"}


def _call(client, method, template, league):
    path = template.format(lid=league)
    if method == "POST":
        return client.post(path, headers=AUTH, json={})
    return client.get(path, headers=AUTH)


def _is_locked(response) -> bool:
    if response.status_code != 200:
        return False
    body = response.json()
    return isinstance(body, dict) and body.get("league_locked") is True and body.get("reason") == "free_league_cap"


@pytest.fixture
def env(free_env):  # noqa: F811
    # Routes the gate lets through run against thin mocks and may 4xx/5xx;
    # these tests only care whether the LOCK fired.
    client, state = free_env
    client.raise_server_exceptions = False
    return client, state


@pytest.mark.parametrize("method,template", GATED_ENDPOINTS)
def test_free_with_saved_league_cannot_read_another_league(env, method, template):
    client, _ = env  # saved: ["abc"]
    locked = _call(client, method, template, "other-league")
    assert locked.status_code == 200
    body = locked.json()
    assert set(body) == LOCKED_KEYS
    assert body["reason"] == "free_league_cap" and body["is_premium"] is False
    assert body["upsell"]["title"] and body["upsell"]["body"]
    assert not _is_locked(_call(client, method, template, "abc"))


@pytest.mark.parametrize("method,template", GATED_ENDPOINTS)
def test_free_with_no_saved_league_gets_exactly_one_league(env, method, template):
    client, state = env
    state["saved"] = []
    assert not _is_locked(_call(client, method, template, "first"))
    assert _is_locked(_call(client, method, template, "second"))
    assert not _is_locked(_call(client, method, template, "first"))


def test_claim_is_shared_between_gated_and_roster_resolved_endpoints(env):
    client, state = env
    state["saved"] = []
    assert not _is_locked(client.get("/v1/leagues/first/rankings", headers=AUTH))
    # Roster-resolved routes honour the same single claim.
    assert _hub(client, league="first", strategy="retool")["reason"] == ""
    assert _hub(client, league="second", strategy="retool")["reason"] == "free_league_cap"
    assert _is_locked(client.get("/v1/leagues/second/rankings", headers=AUTH))


def test_saving_a_league_replaces_the_unsaved_claim(env):
    client, state = env
    state["saved"] = []
    assert not _is_locked(client.get("/v1/leagues/first/rankings", headers=AUTH))
    # The user now saves a DIFFERENT league: the save route releases the claim.
    state["saved"] = ["saved-one"]
    free_tier_ledger.release_league_claims("user-123")
    assert _is_locked(client.get("/v1/leagues/first/rankings", headers=AUTH))
    assert not _is_locked(client.get("/v1/leagues/saved-one/rankings", headers=AUTH))


def test_a_stale_claim_cannot_be_used_once_a_league_is_saved(env):
    client, state = env
    state["saved"] = []
    assert not _is_locked(client.get("/v1/leagues/stale/rankings", headers=AUTH))
    # Even WITHOUT the release, no spare capacity means no claimed league.
    state["saved"] = ["saved-one"]
    assert _is_locked(client.get("/v1/leagues/stale/rankings", headers=AUTH))


def test_removing_the_saved_league_frees_the_slot_for_a_new_one(env):
    client, state = env
    state["saved"] = []
    assert not _is_locked(client.get("/v1/leagues/old/rankings", headers=AUTH))
    free_tier_ledger.release_league_claims("user-123")  # what save/remove do
    assert not _is_locked(client.get("/v1/leagues/new/rankings", headers=AUTH))
    assert _is_locked(client.get("/v1/leagues/old/rankings", headers=AUTH))


@pytest.mark.parametrize("entitlement", ["premium", "pro", "front_office"])
@pytest.mark.parametrize("method,template", GATED_ENDPOINTS)
def test_paid_accounts_are_never_league_locked(env, method, template, entitlement):
    client, state = env
    state["entitlement"] = entitlement
    for league in ("abc", "other-league", "third", "fourth"):
        assert not _is_locked(_call(client, method, template, league))


def test_trialing_account_is_never_league_locked(env, monkeypatch):
    client, _ = env
    # A running trial reads as entitlement "premium" plus a future trial end.
    monkeypatch.setattr(
        "services.mobile_api_service._fetch_profile_fields",
        lambda *a, **k: {
            "entitlement": "premium",
            "sleeper_username": "gm_dynasty",
            "status": "ok",
            "trial_ends_at": "2999-01-01T00:00:00+00:00",
        },
    )
    for league in ("a", "b", "c"):
        assert not _is_locked(client.get(f"/v1/leagues/{league}/rankings", headers=AUTH))


def test_locked_league_does_no_expensive_work(env):
    client, _ = env
    with patch("modules.league_value_settings.build_valued_players_frame_cached") as valued, patch(
        "modules.league_rankings.build_league_rankings_frame_cached"
    ) as ranked, patch("modules.manager_tendencies.league_tendencies_cached") as tendencies:
        for path in (
            "/v1/leagues/other-league/rankings",
            "/v1/leagues/other-league/team-rankings",
            "/v1/leagues/other-league/managers/tendencies",
            "/v1/leagues/other-league/draft-center",
        ):
            assert _is_locked(client.get(path, headers=AUTH))
    assert not valued.called and not ranked.called and not tendencies.called


def test_locked_check_costs_one_profile_and_one_saved_leagues_read(env, monkeypatch):
    client, _ = env
    calls = {"profile": 0, "saved": 0}

    def profile(*a, **k):
        calls["profile"] += 1
        return {"entitlement": "free", "sleeper_username": "gm_dynasty", "status": "ok"}

    def saved(*a, **k):
        calls["saved"] += 1
        return ([{"league_id": "abc", "sleeper_username": "gm_dynasty"}], "")

    monkeypatch.setattr("services.mobile_api_service._fetch_profile_fields", profile)
    monkeypatch.setattr("services.mobile_api_service._fetch_saved_leagues_cached", saved)
    assert _is_locked(client.get("/v1/leagues/other-league/rankings", headers=AUTH))
    assert calls == {"profile": 1, "saved": 1}


def test_add_league_flows_and_league_metadata_stay_open(env):
    client, _ = env
    for path in ("/v1/import/preview", "/v1/espn/leagues/preview"):
        assert not _is_locked(client.post(path, headers=AUTH, json={}))
    assert not _is_locked(client.get("/v1/sleeper/leagues?username=gm_dynasty", headers=AUTH))
    # League header + warm-up polling used while adding a league.
    assert not _is_locked(client.get("/v1/leagues/other-league", headers=AUTH))
    assert not _is_locked(client.get("/v1/leagues/other-league/warmup-status", headers=AUTH))


def test_trade_analyzer_on_the_saved_league_still_works(env):
    client, _ = env
    r = client.post(
        "/v1/leagues/abc/trade-analyzer", headers=AUTH, json={"send_player_ids": ["my1"], "receive_player_ids": ["x"]}
    )
    assert not _is_locked(r)


def test_free_ledger_claim_unit_semantics():
    free_tier_ledger.reset_memory_for_testing()
    assert free_tier_ledger.claim_league("u", "a", 1) is True
    assert free_tier_ledger.claim_league("u", "b", 1) is False
    assert free_tier_ledger.claim_league("u", "a", 0) is False  # a league got saved
    free_tier_ledger.release_league_claims("u")
    assert free_tier_ledger.claim_league("u", "b", 1) is True
    assert free_tier_ledger.claim_league("u", "a", 1) is False

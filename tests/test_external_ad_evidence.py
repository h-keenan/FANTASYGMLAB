"""Identity, availability provenance and claim evidence on the ad API.

Fixture data only: no data/players.db, no network, no news store.
"""

from __future__ import annotations

import copy
from datetime import timedelta

import pytest

import external_ad_fixtures as F
from modules import external_ad_api as A
from modules import external_ad_evidence as EV

NOW = F.NOW  # 2026-12-08 15:00 UTC; clock week 15, regular season
HURT = F.BOARD[0]  # Alex Hurt, sleeper id 100, listed Out


def _official(**over):
    row = dict(F.OFFICIAL_ROWS[0])
    row.update(over)
    return row


def _ctx(*, official=None, events=None, news=None, week=15, phase="regular", dump=None, dp=None, dp_reason=None):
    ctx = EV.EvidenceContext(
        now=NOW, clock_season=2026, clock_week=week, clock_phase=phase,
        identity=EV.IdentityResolver(F.ID_DUMP if dump is None else dump, F.DP_ROWS if dp is None else dp, dp_unavailable_reason=dp_reason),
    )
    if official is not None:
        ctx.official = EV.OfficialIndex(official, 2026)
        ctx.official_unavailable_reason = None
    latest = {}
    for e in events or []:
        latest[e["player_id"]] = e
    ctx.observations = latest
    ctx.news = news or {}
    ctx.news_unavailable_reason = None if news else "no_availability_headlines_in_the_last_48_hours"
    return ctx


def _claim(ctx, row=HURT, week=15, season=2026):
    ident = A.identity_for(row, ctx)
    avail = EV.build_availability(row, ident, ctx, season=season, week=week)
    claim, reason = EV.build_availability_claim(avail, ident, ctx)
    return avail, claim, reason


def _news(speculative=False, url="https://www.rotowire.com/football/news/x", domain="rotowire.com"):
    return {"100": [{"headline": "Alex Hurt hurt", "url": url, "publisher_domain": domain, "published_ts": 1796680800,
                     "first_seen_at": "2026-12-07T22:10:00+00:00", "event_type": "INJURY", "speculative": speculative}]}


# --- identity ---------------------------------------------------------------


def test_identity_maps_only_ids_present_in_sources_and_explains_nulls():
    ctx = _ctx()
    full = A.identity_for(HURT, ctx)
    assert full["player_id"] == "100" and full["id_namespace"] == "sleeper"
    assert (full["name"], full["team"], full["position"]) == ("Alex Hurt", "AAA", "WR")
    assert full["ids"] == {
        "sleeper_id": "100", "gsis_id": "00-0034001", "espn_id": "4000100", "yahoo_id": "31000",
        "pfr_id": "HurtAl00", "fantasypros_id": "20100", "sportradar_id": "sr-100", "rotowire_id": "9100",
    }
    assert full["ids_unavailable_reasons"] == {}
    partial = A.identity_for(F.BOARD[1], ctx)  # Bo Backup
    assert partial["ids"]["gsis_id"] is None and partial["ids_unavailable_reasons"]["gsis_id"] == "id_not_mapped_in_sources"
    assert "gsis_id" not in partial["id_sources"]
    unknown = A.identity_for({"player_id": "999", "name": "Nobody", "team": "AAA", "position": "WR"}, ctx)
    assert all(v is None for k, v in unknown["ids"].items() if k != "sleeper_id")
    assert set(unknown["ids_unavailable_reasons"].values()) == {"player_not_in_crosswalk_sources"}


def test_identity_never_guesses_when_sources_disagree_or_ids_collide_or_are_malformed():
    dump = {
        "1": {"player_id": "1", "gsis_id": "00-0000001", "espn_id": "5"},
        "2": {"player_id": "2", "gsis_id": "00-0000002", "espn_id": "5"},  # espn 5 shared
        "3": {"player_id": "3", "gsis_id": "BAD"},
    }
    dp = {"1": {"sleeper_id": "1", "gsis_id": "00-0000999"}}  # disagrees with the dump
    r = EV.IdentityResolver(dump, dp)
    one = r.resolve("1")
    assert one["ids"]["gsis_id"] is None and one["ids_unavailable_reasons"]["gsis_id"] == "sources_disagree"
    assert one["ids"]["espn_id"] is None and one["ids_unavailable_reasons"]["espn_id"] == "id_shared_by_multiple_players"
    assert r.resolve("3")["ids_unavailable_reasons"]["gsis_id"] == "gsis_malformed"


def test_identity_reports_missing_dynastyprocess_table_for_dp_only_ids():
    r = EV.IdentityResolver(F.ID_DUMP, None, dp_unavailable_reason="dynastyprocess_id_table_not_cached_on_this_server")
    ident = r.resolve("100")
    assert ident["ids"]["pfr_id"] is None
    assert ident["ids_unavailable_reasons"]["pfr_id"] == "dynastyprocess_id_table_not_cached_on_this_server"
    assert ident["ids"]["gsis_id"] == "00-0034001"  # still served from the Sleeper dump


# --- one fixture per status level -------------------------------------------


def test_confirmed_official_fresh_is_auto_publish_eligible():
    ctx = _ctx(official=[_official()], events=F.STATUS_EVENTS)
    avail, claim, _ = _claim(ctx)
    assert avail["source_type"] == "official_team_report" and avail["is_official"] is True
    assert avail["verified_at"] == "2026-12-07T21:30:00+00:00" and avail["observed_at"] is None
    assert avail["source_url"].endswith("injuries_2026.csv")
    assert claim["claim_status"] == "confirmed" and claim["confidence"] == "high"
    assert claim["auto_publish_eligible"] is True and claim["auto_publish"]["blockers"] == []
    assert claim["auto_publish"]["evidence_age_hours"] == pytest.approx(17.5)
    assert any(e["is_official"] and e["source_type"] == "official_team_report" for e in claim["evidence"])


def test_confirmed_but_official_row_has_no_timestamp_is_not_eligible():
    ctx = _ctx(official=[_official(date_modified="")], events=F.STATUS_EVENTS)
    avail, claim, _ = _claim(ctx)
    assert claim["claim_status"] == "confirmed"
    assert claim["auto_publish_eligible"] is False
    assert "official_source_timestamp_unavailable" in claim["auto_publish"]["blockers"]
    assert avail["unavailable_reason"] is None
    official = avail["sources"][0]
    assert official["verified_at"] is None and official["unavailable_reasons"]["verified_at"] == "report_row_has_no_date_modified"


def test_confirmed_but_stale_is_not_eligible():
    stale = (NOW - timedelta(hours=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _, claim, _ = _claim(_ctx(official=[_official(date_modified=stale)]))
    assert claim["claim_status"] == "confirmed" and claim["auto_publish_eligible"] is False
    assert claim["auto_publish"]["fresh"] is False
    assert "official_source_older_than_freshness_window" in claim["auto_publish"]["blockers"]


def test_official_and_platform_disagreement_is_reported_never_eligible():
    _, claim, _ = _claim(_ctx(official=[_official(report_status="Questionable")], events=F.STATUS_EVENTS))
    assert claim["claim_status"] == "reported" and claim["auto_publish_eligible"] is False
    assert "sources_disagree" in claim["auto_publish"]["blockers"]


def test_out_on_official_and_ir_on_sleeper_agree():
    row = {**HURT, "injury_status": "IR"}
    _, claim, _ = _claim(_ctx(official=[_official()]), row=row)
    assert claim["claim_status"] == "confirmed" and claim["auto_publish_eligible"] is True


def test_platform_only_is_reported_and_explains_missing_official_row():
    avail, claim, _ = _claim(_ctx(official=[], events=F.STATUS_EVENTS))
    assert avail["source_type"] == "platform_status" and avail["is_official"] is False
    assert avail["source_url"] is None and avail["unavailable_reason"] is None
    assert avail["observed_at"] == "2026-12-06T08:30:00+00:00" and avail["verified_at"] is None
    assert "official_team_report" in avail["sources_not_available"]
    assert claim["claim_status"] == "reported" and claim["confidence"] == "medium"
    assert claim["auto_publish_eligible"] is False and "claim_not_confirmed" in claim["auto_publish"]["blockers"]


def test_news_only_reported_headline_is_reported_and_speculative_is_unverified():
    ctx = _ctx(official=[], news=_news())
    row = {**HURT, "injury_status": None}  # no platform status: news is the only source
    avail, claim, _ = _claim(ctx, row=row)
    assert avail["source_type"] is None and avail["designation"] is None and avail["unavailable_reason"]
    assert claim["claim_status"] == "reported" and claim["confidence"] == "low" and claim["auto_publish_eligible"] is False
    assert claim["evidence"][0]["url"] == "https://www.rotowire.com/football/news/x"
    _, spec, _ = _claim(_ctx(official=[], news=_news(speculative=True)), row=row)
    assert spec["claim_status"] == "unverified" and spec["auto_publish_eligible"] is False


def test_no_source_gives_no_claim_and_a_reason_not_a_healthy_inference():
    row = {**HURT, "injury_status": None}
    avail, claim, reason = _claim(_ctx(official=[]), row=row)
    assert claim is None and reason and "not evidence the player is healthy" in avail["unavailable_reason"]


def test_official_report_not_yet_published_for_the_week_is_explained():
    rows = [_official(week="14")]
    avail, claim, _ = _claim(_ctx(official=rows, events=F.STATUS_EVENTS))
    assert "official_reports_loaded_through_week_14_not_yet_week_15" == avail["sources_not_available"]["official_team_report"]
    assert claim["claim_status"] == "reported"


def test_platform_status_never_applies_to_a_preview_week():
    avail, claim, reason = _claim(_ctx(official=[], events=F.STATUS_EVENTS), week=16)
    assert avail["source_type"] is None and claim is None and reason
    assert "platform_status" in avail["sources_not_available"]


# --- unverified / news-only can never become confirmed or eligible ----------


def test_finalize_claim_downgrades_confirmed_without_official_evidence():
    for evidence in (
        [],
        [{"source_type": "news_report", "source": "nfl.com", "url": "https://www.nfl.com/x", "timestamp": NOW.isoformat(), "is_official": False}],
        [{"source_type": "platform_status", "source": "Sleeper", "url": None, "timestamp": NOW.isoformat(), "is_official": True}],  # lying flag, wrong type
        [{"source_type": "official_team_report", "source": "x", "url": None, "timestamp": NOW.isoformat(), "is_official": False}],
    ):
        c = EV.finalize_claim(
            claim_type="availability_designation", subject_id="100", claim_text="t", claim_status="confirmed", evidence=evidence,
            method="m", confidence="high", required_for_auto_publish=True, now=NOW, applies_week=15, clock_week=15, clock_phase="regular",
        )
        assert c["claim_status"] == "reported" and c["auto_publish_eligible"] is False


def test_official_domain_news_headline_does_not_confirm():
    news = _news(url="https://www.nfl.com/news/alex-hurt", domain="nfl.com")
    row = {**HURT, "injury_status": None}
    _, claim, _ = _claim(_ctx(official=[], news=news), row=row)
    assert claim["claim_status"] != "confirmed" and claim["auto_publish_eligible"] is False
    assert all(e["is_official"] is False for e in claim["evidence"])


def test_eligibility_requires_regular_season_and_current_week():
    _, offseason, _ = _claim(_ctx(official=[_official()], phase="offseason"))
    assert offseason["auto_publish_eligible"] is False and "season_phase_not_regular" in offseason["auto_publish"]["blockers"]
    _, other_week, _ = _claim(_ctx(official=[_official()], week=14))
    assert other_week["auto_publish_eligible"] is False and "claim_week_is_not_the_current_week" in other_week["auto_publish"]["blockers"]


def test_conflicting_official_rows_are_never_confirmed_as_a_designation():
    rows = [_official(report_status="Out"), _official(report_status="Questionable", date_modified="2026-12-07T22:00:00Z")]
    _, claim, _ = _claim(_ctx(official=rows))
    assert claim["claim_status"] == "reported" and claim["auto_publish_eligible"] is False


def test_future_dated_official_timestamp_is_not_fresh():
    future = (NOW + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _, claim, _ = _claim(_ctx(official=[_official(date_modified=future)]))
    assert claim["auto_publish_eligible"] is False and "official_source_timestamp_in_future" in claim["auto_publish"]["blockers"]


# --- endpoint level ---------------------------------------------------------


def _patch_providers(monkeypatch, *, official=None, events=None, news=None, dp=None):
    monkeypatch.setattr(A, "load_board", lambda db, fmt: (F.BOARD, F.BOARD_AS_OF))
    monkeypatch.setattr(A, "load_games", lambda: F.games())
    monkeypatch.setattr(A, "load_defense", lambda season: F.DEFENSE)
    monkeypatch.setattr(A, "load_trending", lambda: F.TRENDING)
    monkeypatch.setattr(A, "load_roster_pct", lambda ids: F.ROSTER_PCT)
    monkeypatch.setattr(A, "clock_info", lambda today=None: {"season": 2026, "phase": "regular", "week": 15, "source": "sleeper"})
    monkeypatch.setattr(A, "load_identity_sources", lambda: (F.ID_DUMP, F.DP_ROWS if dp is None else dp, None))
    monkeypatch.setattr(A, "load_official_reports", lambda season: (F.OFFICIAL_ROWS if official is None else official, None))
    monkeypatch.setattr(A, "load_status_events", lambda season: (F.STATUS_EVENTS if events is None else events, None))
    monkeypatch.setattr(A, "load_news_reports", lambda db, now: (F.NEWS_REPORTS if news is None else news, None))


def test_waiver_alert_endpoint_carries_identity_availability_and_claims(monkeypatch):
    _patch_providers(monkeypatch)
    out = A.endpoint_waiver_replacements(db_path="x", fmt="superflex", limit=5, now=NOW)
    it = out["items"][0]
    assert it["injured_player"]["identity"]["ids"]["gsis_id"] == "00-0034001"
    assert it["injured_player"]["availability"]["is_official"] is True
    alert = next(c for c in it["claims"] if c["claim_type"] == "availability_designation")
    assert alert["claim_status"] == "confirmed" and alert["auto_publish_eligible"] is True
    assert it["auto_publish_eligible"] is True and it["auto_publish_blockers"] == []
    trending = [c for c in it["claims"] if c["claim_type"] == "trending_add"]
    assert trending and all(c["claim_status"] == "reported" and not c["auto_publish_eligible"] for c in trending)
    assert all(r["identity"]["player_id"] == r["player_id"] for r in it["replacements"])
    assert out["evidence_contract"]["official_reports"]["loaded"] is True
    # existing fields are untouched and keep their order; new keys only follow them
    assert list(it["injured_player"])[:6] == ["player_id", "name", "position", "team", "injury_status", "position_rank"]
    assert list(it["replacements"][0])[:8] == ["player_id", "name", "position", "team", "trending_adds_24h", "trending_rank", "roster_pct", "same_team"]


def test_waiver_alert_without_official_data_is_reported_not_eligible(monkeypatch):
    _patch_providers(monkeypatch, official=[], news={})
    it = A.endpoint_waiver_replacements(db_path="x", fmt="superflex", limit=5, now=NOW)["items"][0]
    assert it["injured_player"]["availability"]["source_type"] == "platform_status"
    assert it["auto_publish_eligible"] is False
    assert any("claim_not_confirmed" in b for b in it["auto_publish_blockers"])


def test_lineup_items_never_become_auto_publishable_from_a_model_or_schedule(monkeypatch):
    _patch_providers(monkeypatch)
    out = A.endpoint_lineup_decisions(db_path="x", fmt="superflex", week=15, season=2026, limit=10, now=NOW)
    assert out["items"]
    for it in out["items"]:
        types = {c["claim_type"]: c for c in it["claims"]}
        assert types["recommendation"]["claim_status"] == "unverified" and types["recommendation"]["method"] == "model_inference"
        assert types["matchup"]["claim_status"] == "reported"
        assert it["auto_publish_eligible"] is False and it["auto_publish_blockers"]
        assert it["player"]["identity"]["player_id"] == it["player"]["player_id"]
        assert it["player"]["availability"]["applies_to"]["game_id"] == it["game_id"]


def test_lineup_preview_week_has_no_platform_availability_claim(monkeypatch):
    _patch_providers(monkeypatch)
    out = A.endpoint_lineup_decisions(db_path="x", fmt="superflex", week=16, season=2026, limit=10, now=NOW)
    for it in out["items"]:
        assert all(c["claim_type"] != "availability_designation" or c["claim_status"] != "confirmed" for c in it["claims"])
        assert it["player"]["availability"]["sources_not_available"].get("platform_status") or it["player"]["availability"]["source_type"] is None


def test_all_other_player_items_carry_identity_and_demo_says_why_not(monkeypatch):
    _patch_providers(monkeypatch)
    monkeypatch.setattr(A, "load_rookie_adp", lambda: F.ROOKIE_ADP)
    monkeypatch.setattr(A, "load_sleeper_players", lambda: F.SLEEPER_PLAYERS)
    monkeypatch.setattr(A, "load_depth_snapshots", lambda: F.DEPTH_SNAPSHOTS)
    monkeypatch.setattr(A, "load_rating_snapshots", lambda days: {"latest": F.LATEST_RATINGS, "baseline": F.BASELINE_RATINGS, "latest_date": "2026-12-07", "baseline_date": "2026-11-30"})
    for out in (
        A.endpoint_value_changes(db_path="x", fmt="superflex", days=7, limit=5, now=NOW),
        A.endpoint_rookies(db_path="x", fmt="superflex", limit=5, now=NOW),
        A.endpoint_changes(db_path="x", fmt="superflex", limit=5, now=NOW),
    ):
        assert out["items"]
        for it in out["items"]:
            assert it["player"]["identity"]["player_id"] == it["player"]["player_id"]
            assert it["player"]["identity"]["ids"]["sleeper_id"] == it["player"]["player_id"]
    demo = A.endpoint_demo_scenarios(scenario_type=None, now=NOW)
    assert all(i["identity"] is None and i["identity_unavailable_reason"] for i in demo["items"])


def test_no_endpoint_output_ever_has_an_eligible_claim_that_is_not_confirmed_and_official(monkeypatch):
    """Property over several evidence worlds: eligible => confirmed => official evidence."""

    worlds = [
        dict(),
        dict(official=[]),
        dict(official=[], news={}),
        dict(official=[_official(date_modified="")]),
        dict(official=[_official(report_status="Doubtful")]),
        dict(official=[_official()], news=_news(url="https://www.nfl.com/n", domain="nfl.com")),
    ]
    for world in worlds:
        _patch_providers(monkeypatch, **world)
        outs = [
            A.endpoint_waiver_replacements(db_path="x", fmt="superflex", limit=10, now=NOW),
            A.endpoint_lineup_decisions(db_path="x", fmt="superflex", week=15, season=2026, limit=10, now=NOW),
        ]
        for out in outs:
            for it in out["items"]:
                for c in it["claims"]:
                    if c["auto_publish_eligible"]:
                        assert c["claim_status"] == "confirmed" and EV.has_official_evidence(c["evidence"])
                    if c["claim_status"] == "unverified":
                        assert c["auto_publish_eligible"] is False
                if it["auto_publish_eligible"]:
                    required = [c for c in it["claims"] if c["required_for_auto_publish"]]
                    assert required and all(c["claim_status"] == "confirmed" for c in required)


def test_evidence_inputs_are_not_mutated(monkeypatch):
    _patch_providers(monkeypatch)
    before = copy.deepcopy((F.OFFICIAL_ROWS, F.ID_DUMP, F.DP_ROWS, F.NEWS_REPORTS, F.STATUS_EVENTS))
    A.endpoint_waiver_replacements(db_path="x", fmt="superflex", limit=5, now=NOW)
    assert before == (F.OFFICIAL_ROWS, F.ID_DUMP, F.DP_ROWS, F.NEWS_REPORTS, F.STATUS_EVENTS)


def test_providers_fail_soft_with_reasons(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "_REPO_ROOT", tmp_path)
    assert A.load_official_reports(2026) == ([], "official_report_file_for_2026_not_present_on_this_server")
    assert A.load_status_events(2026)[1].startswith("status_change_log_for_2026")
    dump, dp, reason = A.load_identity_sources()
    assert dp == {} and reason == "dynastyprocess_id_table_not_cached_on_this_server"

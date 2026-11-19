"""College football prospect scouting — data model, aggregation, and the
crowd -> draft-class-strength wiring (modules.trade_ideas._rookie_class_strength_multiplier).
"""

from __future__ import annotations

from modules import college_scouting as cs
from modules import trade_ideas


def test_no_fabricated_prospect_data_exists_in_production_code():
    """There must be no importable fabricated/placeholder prospect catalog
    anywhere in modules.college_scouting — a fabricated name presented
    alongside real players would be indistinguishable from a real scouting
    subject. This app has no licensed recruiting/draft feed yet, so the
    only honest behavior is an empty catalog until real data exists."""

    assert not hasattr(cs, "PLACEHOLDER_PROSPECTS")
    assert not hasattr(cs, "PLACEHOLDER_PROSPECTS_BY_ID")


def test_filter_scouting_relevant_prospects_drops_defensive_and_ot_rows():
    """The central filter must reject every non-QB/RB/WR/TE position,
    regardless of casing, and keep well-formed fantasy-relevant rows."""

    rows = [
        {"id": "p1", "name": "Keeper", "position": "QB", "school": "X", "draft_year": 2026},
        {"id": "p2", "name": "lowercase wr", "position": "wr", "school": "Y", "draft_year": 2026},
        {"id": "p3", "name": "Tackle", "position": "OT", "school": "Z", "draft_year": 2026},
        {"id": "p4", "name": "Edge Rusher", "position": "EDGE", "school": "Z", "draft_year": 2026},
        {"id": "p5", "name": "Corner", "position": "CB", "school": "Z", "draft_year": 2026},
        {"id": "p6", "name": "Safety", "position": "S", "school": "Z", "draft_year": 2026},
        {"id": "p7", "name": "No Position"},
    ]
    filtered = cs._filter_scouting_relevant_prospects(rows)
    assert {row["id"] for row in filtered} == {"p1", "p2"}


def test_fetch_all_prospects_filters_fake_supabase_defensive_row(monkeypatch):
    """Even if Supabase returns a row with a defensive/OT position (bad or
    future data), fetch_all_prospects must never surface it."""

    fake_rows = [
        {"id": "real-qb", "name": "Real QB", "position": "QB", "school": "X", "draft_year": 2026},
        {"id": "fake-cb", "name": "Fake CB", "position": "CB", "school": "Y", "draft_year": 2026},
        {"id": "fake-edge", "name": "Fake EDGE", "position": "EDGE", "school": "Y", "draft_year": 2026},
        {"id": "fake-ot", "name": "Fake OT", "position": "OT", "school": "Y", "draft_year": 2026},
        {"id": "fake-s", "name": "Fake S", "position": "S", "school": "Y", "draft_year": 2026},
    ]

    class _FakeResponse:
        status_code = 200

        def json(self):
            return fake_rows

    monkeypatch.setattr(cs.auth_supabase, "is_configured", lambda config: True)
    monkeypatch.setattr(cs.requests, "get", lambda *args, **kwargs: _FakeResponse())

    prospects, error = cs.fetch_all_prospects({}, "token")
    assert error == ""
    positions = {p["position"] for p in prospects}
    assert positions == {"QB"}
    assert positions <= cs.SCOUTING_RELEVANT_POSITIONS


def test_fetch_all_prospects_returns_empty_not_fabricated_when_not_configured(monkeypatch):
    """When Supabase isn't configured, fetch_all_prospects must return an
    empty list and a reason string — never invented names/positions/schools.
    This replaces the old PLACEHOLDER_PROSPECTS fallback, which has been
    removed entirely from production code."""

    monkeypatch.setattr(cs.auth_supabase, "is_configured", lambda config: False)
    prospects, error = cs.fetch_all_prospects({}, "token")
    assert prospects == []
    assert error == "not_configured"


def test_fetch_all_prospects_returns_empty_not_fabricated_when_unreachable(monkeypatch):
    """Same honesty guarantee when Supabase is configured but the request
    fails (network error, 4xx/5xx, bad JSON) — empty list, never fake data."""

    monkeypatch.setattr(cs.auth_supabase, "is_configured", lambda config: True)

    def _raise(*args, **kwargs):
        raise ConnectionError("boom")

    monkeypatch.setattr(cs.requests, "get", _raise)
    prospects, error = cs.fetch_all_prospects({}, "token")
    assert prospects == []
    assert error == "not_available"


def test_fetch_all_prospects_legitimately_empty_table_is_not_an_error(monkeypatch):
    """A real, migrated, reachable table that simply has zero rows yet is a
    valid success state, not a failure — it must not be treated as
    'unavailable' or trigger any fallback."""

    class _FakeResponse:
        status_code = 200

        def json(self):
            return []

    monkeypatch.setattr(cs.auth_supabase, "is_configured", lambda config: True)
    monkeypatch.setattr(cs.requests, "get", lambda *args, **kwargs: _FakeResponse())
    prospects, error = cs.fetch_all_prospects({}, "token")
    assert prospects == []
    assert error == ""


def test_build_prospect_views_never_returns_non_fantasy_position(monkeypatch):
    """End-to-end through build_prospect_views: inject a fake defensive row
    via the same mapping path the mobile scouting endpoint uses, and assert
    no non-QB/RB/WR/TE position ever reaches the rendered rows."""

    fake_rows = [
        {"id": "real-wr", "name": "Real WR", "position": "WR", "school": "X", "draft_year": 2026},
        {"id": "fake-s", "name": "Fake Safety", "position": "S", "school": "Y", "draft_year": 2026},
    ]

    class _FakeResponse:
        status_code = 200

        def json(self):
            return fake_rows

    monkeypatch.setattr(cs.auth_supabase, "is_configured", lambda config: True)
    monkeypatch.setattr(cs.requests, "get", lambda *args, **kwargs: _FakeResponse())

    prospects, _ = cs.fetch_all_prospects({}, "token")
    rows = cs.build_prospect_views(prospects, [])
    assert all(row["position"] in cs.SCOUTING_RELEVANT_POSITIONS for row in rows)
    assert {row["id"] for row in rows} == {"real-wr"}


def test_normalize_grade_rejects_out_of_range_and_bad_input():
    assert cs.normalize_grade(3) == 3
    assert cs.normalize_grade("4") == 4
    assert cs.normalize_grade(0) is None
    assert cs.normalize_grade(6) is None
    assert cs.normalize_grade(None) is None
    assert cs.normalize_grade("not-a-number") is None


def test_normalize_round_projection_optional_and_bounded():
    assert cs.normalize_round_projection(None) is None
    assert cs.normalize_round_projection("") is None
    assert cs.normalize_round_projection(1) == 1
    assert cs.normalize_round_projection(7) == 7
    assert cs.normalize_round_projection(8) is None
    assert cs.normalize_round_projection(0) is None


def test_aggregate_prospect_scouting_pools_valid_reports_only():
    reports = [
        {"user_id": "u1", "prospect_id": "p1", "grade": 5, "round_projection": 1},
        {"user_id": "u2", "prospect_id": "p1", "grade": 3, "round_projection": 2},
        # invalid grade should be skipped, not crash or count as a neutral 3.
        {"user_id": "u3", "prospect_id": "p1", "grade": 99},
        # a different prospect with no reports at all should never appear.
        {"user_id": "u4", "prospect_id": "p2", "grade": None},
    ]
    agg = cs.aggregate_prospect_scouting(reports)
    assert set(agg.keys()) == {"p1"}
    assert agg["p1"]["scout_count"] == 2
    assert agg["p1"]["avg_grade"] == 4.0
    assert agg["p1"]["avg_round_projection"] == 1.5
    assert agg["p1"]["grade_distribution"][5] == 1
    assert agg["p1"]["grade_distribution"][3] == 1


def test_build_prospect_views_marks_my_report_and_watchlist():
    prospects = [
        {"id": "p1", "name": "A", "position": "QB", "school": "X", "draft_year": 2026},
        {"id": "p2", "name": "B", "position": "RB", "school": "Y", "draft_year": 2026},
    ]
    reports = [
        {"user_id": "me", "prospect_id": "p1", "grade": 4, "round_projection": 1, "note": "sleeper"},
        {"user_id": "someone-else", "prospect_id": "p1", "grade": 2},
    ]
    rows = cs.build_prospect_views(
        prospects, reports, my_user_id="me", watchlist_prospect_ids=["p2"]
    )
    by_id = {row["id"]: row for row in rows}
    assert by_id["p1"]["aggregate"]["scout_count"] == 2
    assert by_id["p1"]["aggregate"]["avg_grade"] == 3.0
    assert by_id["p1"]["my_report"]["grade"] == 4
    assert by_id["p1"]["on_watchlist"] is False
    assert by_id["p2"]["my_report"] is None
    assert by_id["p2"]["on_watchlist"] is True


# ---------------------------------------------------------------------------
# Integration with the existing draft-class-strength calculation
# ---------------------------------------------------------------------------


def test_no_crowd_signal_leaves_existing_class_strength_behavior_unchanged():
    """Every existing caller of _rookie_class_strength_multiplier passes no
    crowd_class_strength_by_year at all — this must be byte-for-byte the
    same result as before the crowdsourced signal existed."""

    assert trade_ideas._rookie_class_strength_multiplier(2026) == 1.15
    assert trade_ideas._rookie_class_strength_multiplier(2099) == 1.0


# ---------------------------------------------------------------------------
# In-process caching of the Supabase prospects/reports fetch. Before this,
# modules.college_scouting_ui's College Scouting page (and the mobile
# scouting endpoint) called fetch_all_prospects/fetch_all_scouting_reports
# directly on every single render/request — two uncached Supabase round
# trips per view of a slow-moving, identical-for-every-caller shared
# catalog. Same bug class as the Player Detail News blocking-RSS fetch
# (#958) and the NFL-schedule CSV re-parse (#960); same fix idiom (an
# in-process TTL cache verified by network-call count, not just behavior).
# ---------------------------------------------------------------------------


def _fake_response(rows):
    class _FakeResponse:
        status_code = 200

        def json(self):
            return rows

    return _FakeResponse()


def test_get_cached_all_prospects_does_not_refetch_within_the_ttl_window(monkeypatch):
    cs._reset_cache_for_tests()
    monkeypatch.setattr(cs.auth_supabase, "is_configured", lambda config: True)
    calls = {"n": 0}

    def _get(*args, **kwargs):
        calls["n"] += 1
        return _fake_response([{"id": "p1", "name": "QB1", "position": "QB", "school": "X", "draft_year": 2026}])

    monkeypatch.setattr(cs.requests, "get", _get)

    first, first_error = cs.get_cached_all_prospects({}, "token", now=1000.0)
    second, second_error = cs.get_cached_all_prospects({}, "token", now=1000.0 + cs.CACHE_TTL_SECONDS - 1)

    assert calls["n"] == 1
    assert first_error == "" and second_error == ""
    assert first == second
    cs._reset_cache_for_tests()


def test_get_cached_all_prospects_refetches_once_the_ttl_expires(monkeypatch):
    cs._reset_cache_for_tests()
    monkeypatch.setattr(cs.auth_supabase, "is_configured", lambda config: True)
    calls = {"n": 0}

    def _get(*args, **kwargs):
        calls["n"] += 1
        return _fake_response([{"id": "p1", "name": "QB1", "position": "QB", "school": "X", "draft_year": 2026}])

    monkeypatch.setattr(cs.requests, "get", _get)

    cs.get_cached_all_prospects({}, "token", now=1000.0)
    cs.get_cached_all_prospects({}, "token", now=1000.0 + cs.CACHE_TTL_SECONDS + 1)

    assert calls["n"] == 2
    cs._reset_cache_for_tests()


def test_get_cached_all_prospects_does_not_cache_a_failed_fetch(monkeypatch):
    """An unreachable table must not poison the cache as empty-forever —
    the very next call should try again, not just reuse the failure."""

    cs._reset_cache_for_tests()
    monkeypatch.setattr(cs.auth_supabase, "is_configured", lambda config: True)
    calls = {"n": 0}

    def _get(*args, **kwargs):
        calls["n"] += 1
        raise ConnectionError("boom")

    monkeypatch.setattr(cs.requests, "get", _get)

    cs.get_cached_all_prospects({}, "token", now=1000.0)
    cs.get_cached_all_prospects({}, "token", now=1000.1)

    assert calls["n"] == 2
    cs._reset_cache_for_tests()


def test_get_cached_all_scouting_reports_does_not_refetch_within_the_ttl_window(monkeypatch):
    cs._reset_cache_for_tests()
    monkeypatch.setattr(cs.auth_supabase, "is_configured", lambda config: True)
    calls = {"n": 0}

    def _get(*args, **kwargs):
        calls["n"] += 1
        return _fake_response([{"user_id": "u1", "prospect_id": "p1", "grade": 4}])

    monkeypatch.setattr(cs.requests, "get", _get)

    cs.get_cached_all_scouting_reports({}, "token", now=2000.0)
    cs.get_cached_all_scouting_reports({}, "token", now=2000.0 + cs.CACHE_TTL_SECONDS - 1)

    assert calls["n"] == 1
    cs._reset_cache_for_tests()


# ---------------------------------------------------------------------------
# Prospect detail sheet (stats + profile)
# ---------------------------------------------------------------------------
_STATS_ROW = {
    "prospect_id": "p1",
    "class_year": 3,
    "height_in": 76,
    "weight_lb": 220,
    "hometown": "New Orleans, LA",
    "school_logo_url": "https://example.test/tx.png",
    "seasons": [
        {"season": 2025, "team": "Texas", "passing": {"yds": 2000, "td": 15, "int": 5}},
        {"season": 2026, "team": "Texas", "passing": {"yds": 3000, "td": 25, "int": 5}, "rushing": {"yds": 200, "td": 3}},
    ],
    "advanced": {"season": 2026, "ppa": {"avg": {"all": 0.4}}, "usage": {"overall": 0.3}},
    "game_log": {"season": 2026, "games": [{"week": 1, "opponent": "Ohio State", "passing": {"yds": 250, "td": 2}}, {"week": 2}]},
    "recruiting": {"stars": 5, "national_rank": 1},
    "source": "College Football Data API (...)",
    "source_url": "https://collegefootballdata.com/player/1",
    "ingested_at": "2026-11-16T09:00:00+00:00",
}
_PROSPECT = {"id": "p1", "name": "Arch Manning", "position": "QB", "school": "Texas", "draft_year": 2027}


def test_college_fantasy_points_is_derived_from_cfbd_lines_only():
    assert cs.college_fantasy_points({"passing": {"yds": 250, "td": 2, "int": 1}}) == 16.0  # 10 + 8 - 2
    assert cs.college_fantasy_points({"receiving": {"rec": 7, "yds": 100, "td": 1}}) == 23.0
    assert cs.college_fantasy_points({}) is None and cs.college_fantasy_points(None) is None


def test_profile_free_gets_basics_and_a_lock_not_advanced():
    body = cs.build_prospect_profile(_PROSPECT, _STATS_ROW, is_pro=False)
    assert [s["season"] for s in body["seasons"]] == [2026, 2025]  # newest first
    assert body["seasons"][0]["fantasy_points"] == 248.0  # 120 + 100 - 10 passing, 20 + 18 rushing
    assert body["advanced"] is None and body["advanced_locked"] is True and body["advanced_available"] is True
    assert body["weekly"]["games"][0] == {"week": 1, "opponent": "Ohio State", "passing": {"yds": 250, "td": 2}, "fantasy_points": 18.0}
    assert body["weekly"]["games"][1]["fantasy_points"] is None  # no stat line: no invented zero
    assert body["bio"]["hometown"] == "New Orleans, LA" and body["recruiting"]["stars"] == 5
    assert body["source"]["name"] == "College Football Data" and body["source"]["as_of"] == "2026-11-16"


def test_profile_pro_gets_advanced_and_no_row_is_an_honest_empty():
    body = cs.build_prospect_profile(_PROSPECT, _STATS_ROW, is_pro=True)
    assert body["advanced"]["usage"] == {"overall": 0.3} and body["advanced_locked"] is False
    empty = cs.build_prospect_profile(_PROSPECT, None, is_pro=True)
    assert empty["stats_available"] is False and empty["seasons"] == [] and empty["weekly"] is None
    assert empty["advanced"] is None and empty["advanced_locked"] is False and empty["recruiting"] is None


def test_profile_hand_off_fields_for_a_drafted_prospect():
    drafted = {**_PROSPECT, "drafted": True, "nfl_team": "NYG", "draft_round": 1, "draft_pick": 3, "sleeper_player_id": "12345"}
    p = cs.build_prospect_profile(drafted, None, is_pro=False)["prospect"]
    assert p["drafted"] is True and p["sleeper_player_id"] == "12345" and p["nfl_team"] == "NYG"

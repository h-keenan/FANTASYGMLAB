"""League Memory / Weekly Recap V1 — deterministic editorial layer over History."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from modules import league_history as history
from modules import league_recaps
from modules import transaction_grades
from modules.notification_center import compose_activity_inbox
from modules.ui_architecture import PLATFORM_DESTINATIONS


ROOT = Path(__file__).resolve().parents[1]

PROFILES = {
    "1": {"team_name": "War Room", "username": "alpha", "owner_name": "Alpha"},
    "2": {"team_name": "Lakefront", "username": "beta", "owner_name": "Beta"},
    "3": {"team_name": "Quiet Club", "username": "gamma", "owner_name": "Gamma"},
}
PLAYERS = {
    "p1": {"name": "Ja'Marr Chase", "position": "WR", "team": "CIN"},
    "p2": {"name": "Breece Hall", "position": "RB", "team": "NYJ"},
    "p3": {"name": "Trey McBride", "position": "TE", "team": "ARI"},
}


def _tx(raw, *, week=7, season="2025", league_id="L1"):
    return history.normalize_transaction(
        raw,
        league_id=league_id,
        season=season,
        week=week,
        profiles=PROFILES,
        player_lookup=PLAYERS,
    )


def _trade(week=7):
    return _tx(
        {
            "transaction_id": f"t-{week}",
            "type": "trade",
            "status": "complete",
            "status_updated": 1_700_000_000_000,
            "roster_ids": [1, 2],
            "adds": {"p1": 2, "p2": 1},
            "drops": {"p2": 2, "p1": 1},
            "draft_picks": [],
        },
        week=week,
    )


def _waiver(week=7, bid=42, tx_id=""):
    return _tx(
        {
            "transaction_id": tx_id or f"w-{week}-{bid}",
            "type": "waiver",
            "status": "complete",
            "status_updated": 1_700_000_100_000,
            "roster_ids": [1],
            "adds": {"p3": 1},
            "drops": {},
            "settings": {"waiver_bid": bid},
            "draft_picks": [],
        },
        week=week,
    )


def _matchups(week=7):
    return [
        {"week": week, "roster_id": 1, "matchup_id": 10, "points": 148.4, "team_name": "War Room"},
        {"week": week, "roster_id": 2, "matchup_id": 10, "points": 110.2, "team_name": "Lakefront"},
        {"week": week, "roster_id": 3, "matchup_id": 11, "points": 91.0, "team_name": "Quiet Club"},
        {"week": week, "roster_id": 4, "matchup_id": 11, "points": 88.5, "team_name": "Other"},
    ]


def test_completed_week_requires_last_scored_and_points():
    league = {"settings": {"last_scored_leg": 7, "leg": 8}}
    assert league_recaps.completed_recap_week(league, _matchups(7)) == 7
    assert league_recaps.completed_recap_week({"settings": {"leg": 8}}, _matchups(7)) == 0
    incomplete = [
        {"week": 8, "roster_id": 1, "matchup_id": 1, "points": 0},
        {"week": 8, "roster_id": 2, "matchup_id": 1, "points": 0},
    ]
    assert league_recaps.completed_recap_week(
        {"settings": {"last_scored_leg": 8}}, incomplete
    ) == 0


def test_fingerprint_is_stable_and_changes_with_events():
    first = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_trade(), _waiver()],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    second = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_trade(), _waiver()],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    assert first["fingerprint"] == second["fingerprint"]
    changed = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_trade()],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    assert changed["fingerprint"] != first["fingerprint"]


def test_busy_week_omits_nothing_supported_and_does_not_fabricate():
    recap = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_trade(), _waiver(), _waiver(bid=11)],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    types = {story["story_type"] for story in recap["stories"]}
    assert league_recaps.STORY_PERFORMANCE in types
    assert league_recaps.STORY_MATCHUP in types
    assert league_recaps.STORY_WAIVER in types
    assert league_recaps.STORY_TRADE in types
    assert recap["stories"][0]["metric_value"] == "148.4"
    waiver = next(story for story in recap["stories"] if story["story_type"] == "waiver")
    assert "$42" in waiver["metric_value"]
    trade = next(story for story in recap["stories"] if story["story_type"] == "trade")
    assert trade["editorial_label"] == "Too Early to Tell"
    assert trade["historical_value_available"] is False
    assert all(lens["lens"] != league_recaps.VALUE_LENS_AT_TRADE for lens in trade["value_lenses"])


def test_no_trades_week_and_quiet_activity():
    recap = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_waiver()],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    types = {story["story_type"] for story in recap["stories"]}
    assert "trade" not in types
    assert "activity" not in types
    assert "waiver" in types


def test_most_active_requires_repeated_moves():
    extra = _tx(
        {
            "transaction_id": "fa-7",
            "type": "free_agent",
            "status": "complete",
            "roster_ids": [1],
            "adds": {"p2": 1},
            "drops": {},
            "settings": {"waiver_bid": 1},
            "draft_picks": [],
        }
    )
    recap = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_waiver(), extra],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    activity = next(story for story in recap["stories"] if story["story_type"] == "activity")
    assert activity["primary_team"] == "War Room"
    assert activity["metric_value"] == "2"


def test_archive_orders_this_week_then_previous():
    archive = league_recaps.archive_weeks(latest=7, available=(3, 5, 7, 2))
    assert archive["this_week"] == [7]
    assert archive["previous_weeks"] == [5, 3, 2]


def test_split_archive_pill_overflow_caps_pinned_count_and_keeps_every_week():
    """The week-picker pill row grows by one every completed week all season
    and used to hard-clip once it ran out of room (#244). Deep into a
    season, only the most recent weeks stay pinned as pills; the rest moves
    to the "More weeks" overflow select -- never dropped outright."""

    archive = league_recaps.archive_weeks(latest=14, available=range(1, 15))
    pinned, overflow = league_recaps.split_archive_pill_overflow(
        archive["previous_weeks"], pinned_count=7
    )
    assert pinned == [13, 12, 11, 10, 9, 8, 7]
    assert overflow == [6, 5, 4, 3, 2, 1]
    assert set(pinned) | set(overflow) == set(archive["previous_weeks"])


def test_split_archive_pill_overflow_no_overflow_when_under_budget():
    pinned, overflow = league_recaps.split_archive_pill_overflow([5, 4, 3], pinned_count=8)
    assert pinned == [5, 4, 3]
    assert overflow == []


def test_split_archive_pill_overflow_clamps_negative_budget_to_zero():
    pinned, overflow = league_recaps.split_archive_pill_overflow([5, 4, 3], pinned_count=-1)
    assert pinned == []
    assert overflow == [5, 4, 3]


def test_get_or_build_weekly_recap_cache_hit_skips_expensive_build():
    """A repeated call with no new data must hit the session cache and never
    re-run build_weekly_recap's story-generator passes at all — the cache
    lookup has to gate the expensive call, not just run alongside it."""

    session: dict = {}
    first = league_recaps.get_or_build_weekly_recap(
        session,
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_trade(), _waiver()],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    with patch("modules.league_recaps.build_weekly_recap") as mock_build:
        second = league_recaps.get_or_build_weekly_recap(
            session,
            league_id="L1",
            season="2025",
            week=7,
            transactions=[_trade(), _waiver()],
            matchups=_matchups(),
            profiles=PROFILES,
        )
    mock_build.assert_not_called()
    assert second == first
    assert len(session[league_recaps.SESSION_CACHE_KEY]) == 1


def test_get_or_build_weekly_recap_cache_miss_still_builds_and_updates():
    """Sanity check for the reordering: a genuine change (a new transaction)
    must still take the build path and refresh the cached entry."""

    session: dict = {}
    first = league_recaps.get_or_build_weekly_recap(
        session,
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_trade()],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    with patch(
        "modules.league_recaps.build_weekly_recap", wraps=league_recaps.build_weekly_recap
    ) as spy_build:
        second = league_recaps.get_or_build_weekly_recap(
            session,
            league_id="L1",
            season="2025",
            week=7,
            transactions=[_trade(), _waiver()],
            matchups=_matchups(),
            profiles=PROFILES,
        )
    spy_build.assert_called_once()
    assert second["fingerprint"] != first["fingerprint"]
    assert len(session[league_recaps.SESSION_CACHE_KEY]) == 2


def test_build_matchup_history_rows_matches_sequential_calls():
    """Parallelizing the per-week fetches must not change the combined
    result vs. the old one-week-at-a-time loop: same rows, same order,
    every week fetched exactly once."""

    calls: list[tuple[str, int]] = []

    def fetch(league_id, week):
        calls.append((league_id, week))
        return [
            {"roster_id": 1, "matchup_id": week, "points": float(week)},
            {"roster_id": 2, "matchup_id": week, "points": float(week) + 10},
            {"roster_id": 0, "matchup_id": week, "points": 5.0},  # dropped: no roster_id
        ]

    rows = league_recaps.build_matchup_history_rows("L1", 4, fetch_matchups=fetch)

    expected_rows: list[dict] = []
    for week in range(1, 5):
        expected_rows.append({"week": week, "roster_id": 1, "matchup_id": week, "points": float(week)})
        expected_rows.append({"week": week, "roster_id": 2, "matchup_id": week, "points": float(week) + 10})
    assert rows == expected_rows
    assert sorted(calls) == [("L1", week) for week in range(1, 5)]
    assert len(calls) == 4


def test_build_matchup_history_rows_preserves_week_order_despite_timing():
    """Weeks that finish fetching out of order (slower calls for earlier
    weeks) must still be assembled in week order, not completion order."""

    def slow_fetch(league_id, week):
        # Earlier weeks sleep longer, so if row order followed completion
        # order instead of week number this would come back shuffled.
        time.sleep(0.02 * (6 - week))
        return [{"roster_id": 1, "matchup_id": week, "points": float(week)}]

    rows = league_recaps.build_matchup_history_rows("L1", 5, fetch_matchups=slow_fetch)
    assert [row["week"] for row in rows] == [1, 2, 3, 4, 5]


def test_performance_low_story_is_the_weeks_floor_score():
    recap = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    story = next(
        item for item in recap["stories"] if item["story_type"] == league_recaps.STORY_PERFORMANCE_LOW
    )
    assert story["title"] in league_recaps.LOW_PERFORMANCE_STORY_TITLES
    # Lowest score across both pairings in _matchups(): 91.0 vs 88.5 -> 88.5
    # is the league floor (110.2 is not, since 88.5 < 110.2).
    assert story["primary_team"] == "Other"
    assert story["metric_value"] == "88.5"


def test_matchup_close_story_is_smallest_margin():
    recap = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    story = next(
        item for item in recap["stories"] if item["story_type"] == league_recaps.STORY_MATCHUP_CLOSE
    )
    # Pair 10 margin = 148.4-110.2 = 38.2; pair 11 margin = 91.0-88.5 = 2.5.
    assert story["metric_value"] == "2.5"
    assert story["primary_team"] == "Quiet Club"
    assert story["secondary_team"] == "Other"


def test_waiver_low_story_is_cheapest_add_and_requires_two_claims():
    single = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_waiver(bid=42)],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    types = {story["story_type"] for story in single["stories"]}
    assert league_recaps.STORY_WAIVER_LOW not in types

    multi = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_waiver(bid=42), _waiver(bid=3, tx_id="w-cheap")],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    high = next(story for story in multi["stories"] if story["story_type"] == league_recaps.STORY_WAIVER)
    low = next(story for story in multi["stories"] if story["story_type"] == league_recaps.STORY_WAIVER_LOW)
    assert "$42" in high["metric_value"]
    assert "$3" in low["metric_value"]
    assert low["title"] != high["title"]


def test_activity_low_story_is_least_active_and_requires_a_spread():
    recap = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_trade(), _waiver(), _waiver(bid=11)],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    types = {story["story_type"] for story in recap["stories"]}
    assert league_recaps.STORY_ACTIVITY_LOW in types
    low = next(story for story in recap["stories"] if story["story_type"] == league_recaps.STORY_ACTIVITY_LOW)
    assert low["primary_team"] == "Lakefront"
    assert low["metric_value"] == "1"

    # A single active manager (test_most_active_requires_repeated_moves'
    # fixture) has nothing to contrast against -> no "least active" story.
    extra = _tx(
        {
            "transaction_id": "fa-7",
            "type": "free_agent",
            "status": "complete",
            "roster_ids": [1],
            "adds": {"p2": 1},
            "drops": {},
            "settings": {"waiver_bid": 1},
            "draft_picks": [],
        }
    )
    lone_manager = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_waiver(), extra],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    lone_types = {story["story_type"] for story in lone_manager["stories"]}
    assert league_recaps.STORY_ACTIVITY_LOW not in lone_types


def test_trade_story_includes_full_asset_lists_with_player_ids():
    recap = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_trade()],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    trade = next(story for story in recap["stories"] if story["story_type"] == "trade")
    # Truncated summary fields other code reads stay intact.
    assert len(trade["players"]) <= 4
    assert "left_assets" in trade and "right_assets" in trade
    all_assets = trade["left_assets"] + trade["right_assets"]
    assert all_assets
    for asset in all_assets:
        assert asset["kind"] == "player"
        assert asset["player_id"]
        assert asset["name"]
        assert "position" in asset and "team" in asset


def test_non_trade_stories_carry_roster_ids_for_mobile_navigation():
    """Every non-trade story exposes the roster_id(s) it centers on so the
    mobile Recap screen can navigate its card to TeamRoster (coridian_'s
    "all of these should be tappable" ask). Two-team stories (matchup,
    matchup_close) expose both winner (primary) and loser (secondary).
    Trade stories deliberately keep the field empty — they already have
    their own tap target (the trade-detail modal).
    """

    movement = {
        "available": True,
        "power_riser": {"team_name": "War Room", "roster_id": 1, "power_delta": 3},
    }
    recap = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_trade(), _waiver(), _waiver(bid=11)],
        matchups=_matchups(),
        profiles=PROFILES,
        movement=movement,
    )
    by_type = {story["story_type"]: story for story in recap["stories"]}

    performance = by_type[league_recaps.STORY_PERFORMANCE]
    assert performance["primary_roster_id"] == "1"
    assert performance["secondary_roster_id"] == ""

    performance_low = by_type[league_recaps.STORY_PERFORMANCE_LOW]
    assert performance_low["primary_roster_id"] == "4"

    matchup = by_type[league_recaps.STORY_MATCHUP]
    assert matchup["primary_roster_id"] == "1"
    assert matchup["secondary_roster_id"] == "2"

    matchup_close = by_type[league_recaps.STORY_MATCHUP_CLOSE]
    assert matchup_close["primary_roster_id"] == "3"
    assert matchup_close["secondary_roster_id"] == "4"

    waiver = by_type[league_recaps.STORY_WAIVER]
    assert waiver["primary_roster_id"] == "1"

    activity = by_type[league_recaps.STORY_ACTIVITY]
    assert activity["primary_roster_id"] == "1"

    activity_low = by_type[league_recaps.STORY_ACTIVITY_LOW]
    assert activity_low["primary_roster_id"] == "2"

    riser = by_type[league_recaps.STORY_RISER]
    assert riser["primary_roster_id"] == "1"

    # Trade already has its own tap target (trade-detail modal) — no fake
    # roster id manufactured for it.
    trade = by_type[league_recaps.STORY_TRADE]
    assert trade["primary_roster_id"] == ""
    assert trade["secondary_roster_id"] == ""


def test_waiver_low_story_roster_id_matches_cheapest_claim():
    recap = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_waiver(bid=42), _waiver(bid=3, tx_id="w-cheap")],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    low = next(story for story in recap["stories"] if story["story_type"] == league_recaps.STORY_WAIVER_LOW)
    assert low["primary_roster_id"] == "1"

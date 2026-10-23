"""League History v1 — normalize Sleeper transactions into a readable timeline."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

from modules import league_history as history
from modules import transaction_grades
from modules.ui_architecture import PLATFORM_DESTINATIONS


ROOT = Path(__file__).resolve().parents[1]

PROFILES = {
    "1": {
        "team_name": "War Room",
        "username": "alpha",
        "owner_name": "Alpha Manager",
        "avatar_url": "https://sleepercdn.com/avatars/aaa",
    },
    "2": {
        "team_name": "Lakefront",
        "username": "beta",
        "owner_name": "Beta Manager",
        "avatar_url": "",
    },
}

PLAYERS = {
    "p1": {"name": "Ja'Marr Chase", "position": "WR", "team": "CIN"},
    "p2": {"name": "Breece Hall", "position": "RB", "team": "NYJ"},
    "p3": {"name": "Trey McBride", "position": "TE", "team": "ARI"},
}


def _normalize(raw, *, week=4, season="2026", league_id="L-now"):
    return history.normalize_transaction(
        raw,
        league_id=league_id,
        season=season,
        week=week,
        profiles=PROFILES,
        player_lookup=PLAYERS,
    )


def _logo(url, name, css_class="dg-lh-logo"):
    return f"<div class='{css_class}'>{name[:2]}</div>"


def test_prior_season_traversal_and_missing_previous():
    leagues = {
        "L-26": {
            "season": "2026",
            "previous_league_id": "L-25",
            "status": "in_season",
            "settings": {"leg": 8},
        },
        "L-25": {
            "season": "2025",
            "previous_league_id": "L-24",
            "status": "complete",
            "settings": {"last_scored_leg": 17, "playoff_week_start": 15},
        },
        "L-24": {
            "season": "2024",
            "previous_league_id": "",
            "status": "complete",
            "settings": {"last_scored_leg": 17},
        },
    }
    chain = history.walk_season_chain("L-26", leagues.get)
    assert [item["season"] for item in chain] == ["2026", "2025", "2024"]
    orphan = history.walk_season_chain(
        "solo",
        lambda _lid: {"season": "2026", "previous_league_id": "", "settings": {"leg": 3}},
    )
    assert len(orphan) == 1
    cycled = history.walk_season_chain(
        "loop",
        lambda lid: {"season": "2026", "previous_league_id": lid, "settings": {"leg": 1}},
    )
    assert len(cycled) == 1


def test_local_filter_does_not_need_refetch():
    calls = {"n": 0}

    def fetch_league(_league_id):
        return {"season": "2026", "settings": {"leg": 2}}

    def fetch_transactions(_league_id, week):
        calls["n"] += 1
        if week != 1:
            return []
        return [
            {
                "transaction_id": "t1",
                "type": "trade",
                "status": "complete",
                "adds": {"p1": 1, "p2": 2},
                "roster_ids": [1, 2],
                "draft_picks": [
                    {"season": "2027", "round": 1, "owner_id": 1, "previous_owner_id": 2}
                ],
            },
            {
                "transaction_id": "w1",
                "type": "waiver",
                "status": "complete",
                "adds": {"p3": 1},
                "settings": {"waiver_bid": 5},
            },
            {
                "transaction_id": "f1",
                "type": "free_agent",
                "status": "complete",
                "adds": {"p2": 2},
            },
        ]

    payload = history.collect_season_transactions(
        "L-now",
        fetch_league=fetch_league,
        fetch_transactions=fetch_transactions,
    )
    first_calls = calls["n"]
    normalized = history.normalize_season_payload(
        payload, profiles=PROFILES, player_lookup=PLAYERS
    )
    assert [row["type"] for row in history.filter_history(normalized, history.FILTER_TRADES)] == [
        "trade"
    ]
    assert [row["type"] for row in history.filter_history(normalized, history.FILTER_WAIVERS)] == [
        "waiver"
    ]
    assert [
        row["type"] for row in history.filter_history(normalized, history.FILTER_FREE_AGENTS)
    ] == ["free_agent"]
    assert all(row.get("draft_picks") for row in history.filter_history(normalized, history.FILTER_PICKS))
    assert calls["n"] == first_calls == 2


def test_cache_isolation_by_league_and_season():
    def fetch_league(league_id):
        return {"season": "2026" if league_id == "A" else "2025", "settings": {"leg": 1}}

    def fetch_transactions(league_id, week):
        return [
            {
                "transaction_id": f"{league_id}-{week}",
                "type": "free_agent",
                "status": "complete",
                "adds": {"p1": 1},
            }
        ]

    payload_a = history.collect_season_transactions(
        "A", fetch_league=fetch_league, fetch_transactions=fetch_transactions
    )
    payload_b = history.collect_season_transactions(
        "B", fetch_league=fetch_league, fetch_transactions=fetch_transactions
    )
    assert payload_a["season"] == "2026"
    assert payload_b["season"] == "2025"
    assert payload_a["transactions"][0]["transaction_id"] == "A-1"
    assert payload_b["transactions"][0]["transaction_id"] == "B-1"


def test_first_load_fetch_count_vs_payload_reuse():
    calls = {"n": 0}

    def fetch_league(_league_id):
        return {"season": "2026", "status": "in_season", "settings": {"leg": 3}}

    def fetch_transactions(_league_id, week):
        calls["n"] += 1
        return []

    first = history.collect_season_transactions(
        "L", fetch_league=fetch_league, fetch_transactions=fetch_transactions
    )
    first_n = calls["n"]
    assert first_n == 3
    history.filter_history(
        history.normalize_season_payload(first, profiles=PROFILES, player_lookup=PLAYERS),
        history.FILTER_TRADES,
    )
    assert calls["n"] == first_n


_GRADE_LOOKUP = {
    "star": {"current_value": 5200, "name": "Star"},
    "ok": {"current_value": 4800, "name": "Solid"},
}


def _graded_trade(transaction_id, timestamp, *, receive_id="star", send_id="ok"):
    return {
        "type": "trade",
        "transaction_id": transaction_id,
        "week": 4,
        "timestamp": timestamp,
        "sides": [
            {
                "team_name": "War Room",
                "receives": [
                    {"player_id": receive_id, "name": receive_id, "kind": "player"}
                ],
            },
            {
                "team_name": "Lakefront",
                "receives": [
                    {"player_id": send_id, "name": send_id, "kind": "player"}
                ],
            },
        ],
    }


def test_collect_season_transactions_fetches_every_week_exactly_once_in_order():
    """Parallelizing the per-week transaction fetch must not change the
    combined result vs. the old one-week-at-a-time loop: same transactions,
    same dedupe/ordering, every week fetched exactly once — mirrors
    modules.league_recaps.build_matchup_history_rows' own
    test_build_matchup_history_rows_matches_sequential_calls for the
    sibling fix."""

    def fetch_league(_league_id):
        return {"season": "2026", "status": "in_season", "settings": {"leg": 4}}

    calls: list[tuple[str, int]] = []

    def fetch_transactions(league_id, week):
        calls.append((league_id, week))
        return [
            {
                "transaction_id": f"tx-{week}",
                "type": "free_agent",
                "status": "complete",
                "adds": {"p1": 1},
            }
        ]

    payload = history.collect_season_transactions(
        "L1", fetch_league=fetch_league, fetch_transactions=fetch_transactions
    )

    assert sorted(calls) == [("L1", week) for week in range(1, 5)]
    assert len(calls) == 4
    assert [item["transaction_id"] for item in payload["transactions"]] == [
        "tx-1",
        "tx-2",
        "tx-3",
        "tx-4",
    ]
    assert [item["_history_week"] for item in payload["transactions"]] == [1, 2, 3, 4]


def test_collect_season_transactions_preserves_week_order_despite_timing():
    """Weeks that finish fetching out of order (slower calls for earlier
    weeks) must still be assembled in week order, not completion order —
    same guard as league_recaps' sibling fix."""

    def fetch_league(_league_id):
        return {"season": "2026", "status": "in_season", "settings": {"leg": 5}}

    def slow_fetch_transactions(_league_id, week):
        # Earlier weeks sleep longer, so if order followed completion
        # order instead of week number this would come back shuffled.
        time.sleep(0.02 * (6 - week))
        return [{"transaction_id": f"tx-{week}", "type": "free_agent", "status": "complete", "adds": {}}]

    payload = history.collect_season_transactions(
        "L1", fetch_league=fetch_league, fetch_transactions=slow_fetch_transactions
    )
    assert [item["_history_week"] for item in payload["transactions"]] == [1, 2, 3, 4, 5]


def test_collect_season_transactions_fetches_weeks_concurrently_not_sequentially():
    """The real bug this fixes: a full season's worth of per-week Sleeper
    calls (up to 18) used to run one at a time, so a single
    GET /v1/leagues/{id}/history or /storylines request (services/
    mobile_api_service.py — both call this function with zero caching of
    their own) paid the full sum of every week's latency. Proven here with
    a slow fake fetcher: wall-clock time must be close to ONE week's
    latency, not the sum of all of them."""

    league = {"season": "2026", "status": "in_season", "settings": {"leg": 8}}
    per_call_seconds = 0.05
    week_count = 8

    def fetch_transactions(_league_id, _week):
        time.sleep(per_call_seconds)
        return []

    started = time.perf_counter()
    history.collect_season_transactions(
        "L1", fetch_league=lambda _league_id: league, fetch_transactions=fetch_transactions
    )
    elapsed = time.perf_counter() - started

    # Sequential would take >= week_count * per_call_seconds (0.4s here);
    # concurrent (up to 8 workers) should land near one call's latency.
    # Generous bound to absorb scheduling jitter in CI.
    assert elapsed < per_call_seconds * (week_count / 2)

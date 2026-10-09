"""modules.pick_flow: real per-roster future-pick flow (acquired vs. sent,
1st-rounders tracked separately) off Sleeper's own transaction history — the
data half of the "Pick Hoarder"/"Pick Seller" team badge. Same fake-fetcher
pattern tests/test_manager_activity.py uses: pins the aggregation against
realistic raw Sleeper transaction shapes rather than the live Sleeper API.
"""

from __future__ import annotations

from unittest.mock import patch

from modules import pick_flow


def test_pick_flow_counts_first_round_pick_changing_hands():
    """A trade sends roster 2's future 1st to roster 1 — roster 1 gets
    firsts_acquired, roster 2 gets firsts_sent, both get picks_acquired/sent
    tallied too."""
    trade = {
        "transaction_id": "tx1",
        "type": "trade",
        "status": "complete",
        "status_updated": 1000,
        "roster_ids": [1, 2],
        "adds": {},
        "drops": {},
        "draft_picks": [
            {"owner_id": 1, "previous_owner_id": 2, "round": 1, "season": "2027"},
        ],
    }
    with patch("modules.sleeper.get_league", return_value={"season": "2026", "settings": {"leg": 1}}):
        with patch(
            "modules.sleeper.get_transactions",
            side_effect=lambda league_id, week: [trade] if week == 1 else [],
        ):
            with patch("modules.sleeper.get_league_roster_profiles", return_value={}):
                counts = pick_flow.league_pick_flow_counts("L1")

    assert counts[1] == {"picks_acquired": 1, "picks_sent": 0, "firsts_acquired": 1, "firsts_sent": 0}
    assert counts[2] == {"picks_acquired": 0, "picks_sent": 1, "firsts_acquired": 0, "firsts_sent": 1}


def test_pick_flow_counts_non_first_round_pick_does_not_count_as_a_first():
    trade = {
        "transaction_id": "tx2",
        "type": "trade",
        "status": "complete",
        "status_updated": 2000,
        "roster_ids": [1, 2],
        "adds": {},
        "drops": {},
        "draft_picks": [
            {"owner_id": 1, "previous_owner_id": 2, "round": 3, "season": "2027"},
        ],
    }
    with patch("modules.sleeper.get_league", return_value={"season": "2026", "settings": {"leg": 1}}):
        with patch(
            "modules.sleeper.get_transactions",
            side_effect=lambda league_id, week: [trade] if week == 1 else [],
        ):
            with patch("modules.sleeper.get_league_roster_profiles", return_value={}):
                counts = pick_flow.league_pick_flow_counts("L1")

    assert counts[1]["picks_acquired"] == 1
    assert counts[1]["firsts_acquired"] == 0
    assert counts[2]["picks_sent"] == 1
    assert counts[2]["firsts_sent"] == 0


def test_pick_flow_counts_empty_league_id_short_circuits():
    assert pick_flow.league_pick_flow_counts("") == {}


def test_classify_pick_flow_hoarder_when_more_firsts_acquired_than_sent():
    assert pick_flow.classify_pick_flow(2, 0) == "Pick Hoarder"
    assert pick_flow.classify_pick_flow(1, 0) == "Pick Hoarder"


def test_classify_pick_flow_seller_when_more_firsts_sent_than_acquired():
    assert pick_flow.classify_pick_flow(0, 1) == "Pick Seller"
    assert pick_flow.classify_pick_flow(1, 2) == "Pick Seller"


def test_classify_pick_flow_no_badge_when_even():
    assert pick_flow.classify_pick_flow(0, 0) is None
    assert pick_flow.classify_pick_flow(1, 1) is None

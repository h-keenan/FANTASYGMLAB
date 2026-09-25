"""modules.manager_activity: real per-manager transaction-activity count off
Sleeper's own transaction history — pins the aggregation against realistic
raw Sleeper transaction shapes (modules.league_history's normalize input),
using fake fetchers rather than the live Sleeper API or the real players
table (this module never touches players.db at all).
"""

from __future__ import annotations

from unittest.mock import patch

from modules import manager_activity


def test_manager_activity_counts_one_per_involved_roster_per_transaction():
    """A trade between rosters 1 and 2 counts once for each side; a waiver
    claim only counts for the roster that made it."""
    trade = {
        "transaction_id": "tx1",
        "type": "trade",
        "status": "complete",
        "status_updated": 1000,
        "roster_ids": [1, 2],
        "adds": {"p1": 1, "p2": 2},
        "drops": {"p2": 1, "p1": 2},
        "draft_picks": [],
    }
    waiver = {
        "transaction_id": "tx2",
        "type": "waiver",
        "status": "complete",
        "status_updated": 2000,
        "roster_ids": [1],
        "adds": {"p3": 1},
        "drops": {},
        "draft_picks": [],
    }
    with patch("modules.sleeper.get_league", return_value={"season": "2026", "settings": {"leg": 1}}):
        with patch(
            "modules.sleeper.get_transactions",
            side_effect=lambda league_id, week: [trade, waiver] if week == 1 else [],
        ):
            with patch("modules.sleeper.get_league_roster_profiles", return_value={}):
                counts = manager_activity.manager_activity_counts("L1")

    assert counts == {1: 2, 2: 1}


def test_manager_activity_counts_ignores_incomplete_and_unsupported_types():
    pending = {
        "transaction_id": "tx3",
        "type": "trade",
        "status": "pending",
        "roster_ids": [1, 2],
        "adds": {},
        "drops": {},
    }
    commish = {
        "transaction_id": "tx4",
        "type": "commissioner",
        "status": "complete",
        "roster_ids": [1],
        "adds": {"p1": 1},
        "drops": {},
    }
    with patch("modules.sleeper.get_league", return_value={"season": "2026", "settings": {"leg": 1}}):
        with patch(
            "modules.sleeper.get_transactions",
            side_effect=lambda league_id, week: [pending, commish] if week == 1 else [],
        ):
            with patch("modules.sleeper.get_league_roster_profiles", return_value={}):
                counts = manager_activity.manager_activity_counts("L1")

    assert counts == {}


def test_manager_activity_counts_empty_league_id_short_circuits():
    assert manager_activity.manager_activity_counts("") == {}

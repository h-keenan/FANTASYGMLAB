"""modules.team_trade_history: real per-team buy/sell tendency from Sleeper's
own transaction history — the data half of "Decision Memory". Context only
(not wired into modules.trade_ideas yet), so these tests just pin the
classification logic itself against realistic already-normalized
transaction shapes (modules.league_history.normalize_transaction's output),
not the live Sleeper fetch.
"""

from __future__ import annotations

from unittest.mock import patch

from modules import team_trade_history


PLAYER_LOOKUP = {
    "star_rb": {"name": "Star RB", "position": "RB", "team": "SF", "value_score": 9000},
    "star_wr": {"name": "Star WR", "position": "WR", "team": "MIA", "value_score": 8500},
    "young_wr": {"name": "Young WR", "position": "WR", "team": "DET", "value_score": 3000},
    "depth_rb": {"name": "Depth RB", "position": "RB", "team": "NYJ", "value_score": 2000},
}


def _trade(*, tx_id: str, sides: list[dict], draft_picks: list[dict] | None = None) -> dict:
    return {
        "transaction_id": tx_id,
        "type": "trade",
        "status": "complete",
        "sides": sides,
        "draft_picks": draft_picks or [],
    }


def test_sell_signal_gave_up_more_value_and_got_picks_back():
    """Roster 1 sends its star RB, receives a cheap depth piece plus a pick
    — real "sell for future value" shape."""
    tx = _trade(
        tx_id="t1",
        sides=[
            {
                "roster_id": 1,
                "receives": [{"kind": "player", "player_id": "depth_rb"}],
                "drops": [{"kind": "player", "player_id": "star_rb"}],
            },
            {
                "roster_id": 2,
                "receives": [{"kind": "player", "player_id": "star_rb"}],
                "drops": [{"kind": "player", "player_id": "depth_rb"}],
            },
        ],
        draft_picks=[{"to_roster_id": 1, "from_roster_id": 2}],
    )
    counts = team_trade_history.classify_trade_legs([tx], player_lookup=PLAYER_LOOKUP)
    assert counts[1] == {"sell": 1, "buy": 0}
    assert counts[2] == {"sell": 0, "buy": 1}


def test_no_signal_for_a_pure_even_player_swap_with_no_picks():
    tx = _trade(
        tx_id="t2",
        sides=[
            {
                "roster_id": 1,
                "receives": [{"kind": "player", "player_id": "star_wr"}],
                "drops": [{"kind": "player", "player_id": "star_rb"}],
            },
            {
                "roster_id": 2,
                "receives": [{"kind": "player", "player_id": "star_rb"}],
                "drops": [{"kind": "player", "player_id": "star_wr"}],
            },
        ],
    )
    counts = team_trade_history.classify_trade_legs([tx], player_lookup=PLAYER_LOOKUP)
    assert counts == {}


def test_non_trade_and_incomplete_transactions_are_ignored():
    waiver = {"transaction_id": "w1", "type": "waiver", "status": "complete", "sides": [], "draft_picks": []}
    pending_trade = _trade(tx_id="t3", sides=[{"roster_id": 1, "receives": [], "drops": []}])
    pending_trade["status"] = "pending"
    counts = team_trade_history.classify_trade_legs([waiver, pending_trade], player_lookup=PLAYER_LOOKUP)
    assert counts == {}


def test_tendency_from_counts_requires_the_minimum_and_a_clear_lean():
    assert team_trade_history.tendency_from_counts({"sell": 2, "buy": 0}) == team_trade_history.SELLER
    assert team_trade_history.tendency_from_counts({"sell": 1, "buy": 0}) == team_trade_history.NEUTRAL
    assert team_trade_history.tendency_from_counts({"sell": 2, "buy": 2}) == team_trade_history.NEUTRAL
    assert team_trade_history.tendency_from_counts({"buy": 3, "sell": 1}) == team_trade_history.BUYER


def test_league_trade_tendencies_scans_real_transaction_fetchers_and_classifies():
    trade = {
        "transaction_id": "tx1",
        "type": "trade",
        "status": "complete",
        "status_updated": 1000,
        "roster_ids": [1, 2],
        "adds": {"depth_rb": 1, "star_rb": 2},
        "drops": {"star_rb": 1, "depth_rb": 2},
        "draft_picks": [{"season": "2027", "round": 1, "owner_id": 1, "previous_owner_id": 2}],
    }
    with patch("modules.sleeper.get_league", return_value={"season": "2026", "settings": {"leg": 1}}):
        with patch("modules.sleeper.get_transactions", side_effect=lambda league_id, week: [trade] if week == 1 else []):
            with patch("modules.sleeper.get_league_roster_profiles", return_value={}):
                result = team_trade_history.league_trade_tendencies("L1", player_lookup=PLAYER_LOOKUP)

    assert result[1]["sell_count"] == 1
    assert result[1]["tendency"] == team_trade_history.NEUTRAL  # below MIN_SIGNAL_TRADES
    assert result[2]["buy_count"] == 1

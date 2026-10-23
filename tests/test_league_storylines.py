"""League Storylines v1 — deterministic activity intelligence on History data."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from modules import league_history as history
from modules import league_storylines as storylines
from modules.ui_architecture import PLATFORM_DESTINATIONS


ROOT = Path(__file__).resolve().parents[1]

PROFILES = {
    "1": {"team_name": "War Room", "username": "alpha", "owner_name": "Alpha", "avatar_url": ""},
    "2": {"team_name": "Lakefront", "username": "beta", "owner_name": "Beta", "avatar_url": ""},
    "3": {"team_name": "Northside", "username": "gamma", "owner_name": "Gamma", "avatar_url": ""},
}
PLAYERS = {
    "p1": {"name": "Ja'Marr Chase", "position": "WR", "team": "CIN"},
    "p2": {"name": "Breece Hall", "position": "RB", "team": "NYJ"},
    "p3": {"name": "Trey McBride", "position": "TE", "team": "ARI"},
}


def _tx(**kwargs):
    payload = {
        "status": "complete",
        "roster_ids": [1, 2],
        "adds": {},
        "drops": {},
        "draft_picks": [],
        "status_updated": 1_700_000_000_000,
        "_history_week": 4,
    }
    payload.update(kwargs)
    return payload


def _normalized(rows, *, season="2026", league_id="L-now"):
    return history.normalize_season_payload(
        {"league_id": league_id, "season": season, "transactions": rows},
        profiles=PROFILES,
        player_lookup=PLAYERS,
    )


def _logo(url, name, css_class="dg-lh-logo"):
    return f"<div class='{css_class}'>{name[:2]}</div>"


def test_roster_turnover_does_not_double_count_same_player_add_drop():
    txs = _normalized(
        [
            _tx(
                transaction_id="w-swap",
                type="waiver",
                roster_ids=[1],
                adds={"p1": 1},
                drops={"p2": 1},
            ),
            _tx(
                transaction_id="same",
                type="free_agent",
                roster_ids=[2],
                adds={"p3": 2},
                drops={"p3": 2},
            ),
        ]
    )
    turnover = storylines.roster_turnover(txs)
    assert turnover[1] == 2
    assert turnover[2] == 1
    report = storylines.build_league_storylines(txs, profiles=PROFILES)
    assert report["roster_turnover"]["team_name"] == "War Room"


def test_ties_are_deterministic_by_team_name():
    txs = _normalized(
        [
            _tx(transaction_id="t-a", type="trade", adds={"p1": 2, "p2": 1}),
            _tx(
                transaction_id="w-a",
                type="waiver",
                roster_ids=[1],
                adds={"p3": 1},
                settings={"waiver_bid": 3},
            ),
            _tx(
                transaction_id="w-b",
                type="waiver",
                roster_ids=[2],
                adds={"p2": 2},
                settings={"waiver_bid": 3},
            ),
        ]
    )
    activity = storylines.transaction_activity_by_roster(txs)
    assert activity[1]["total"] == activity[2]["total"] == 2
    report = storylines.build_league_storylines(txs, profiles=PROFILES)
    assert report["most_active"]["team_name"] == "Lakefront"
    assert report["most_active"]["tied"] is True


def test_prior_season_and_malformed_transaction():
    prior = _normalized(
        [_tx(transaction_id="old", type="trade", adds={"p1": 2}, _history_week=12)],
        season="2025",
        league_id="L-25",
    )
    report = storylines.build_league_storylines(prior, profiles=PROFILES, season="2025")
    assert report["season"] == "2025"
    assert report["most_active"]["metric"] == 1
    assert history.normalize_transaction(
        {"type": "nope", "status": "complete"},
        league_id="L",
        season="2025",
        week=1,
        profiles=PROFILES,
        player_lookup=PLAYERS,
    ) is None
    skipped = storylines.build_league_storylines(
        [{"type": "trade", "status": "failed", "transaction_id": "x", "sides": []}],
        profiles=PROFILES,
    )
    assert skipped["most_active"] is None


def test_quietest_busiest_week_and_most_moved_player():
    rows = []
    for index in range(3):
        rows.append(
            _tx(
                transaction_id=f"t{index}",
                type="trade",
                adds={"p1": 2},
                _history_week=7,
                status_updated=1_700_000_000_000 + index,
            )
        )
    rows.append(
        _tx(
            transaction_id="solo",
            type="free_agent",
            roster_ids=[1],
            adds={"p3": 1},
            _history_week=2,
        )
    )
    txs = _normalized(rows)
    report = storylines.build_league_storylines(txs, profiles=PROFILES, season="2026")
    assert report["quietest"]["team_name"] == "Northside"
    assert report["quietest"]["metric"] == 0
    assert report["busiest_week"]["week"] == 7
    assert report["busiest_week"]["count"] == 3
    assert report["most_traded_player"]["count"] == 3
    assert report["most_traded_player"]["player"]["name"] == "Ja'Marr Chase"

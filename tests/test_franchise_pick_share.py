"""Franchise score = roster value + draft capital: picks must stay a minor share of a team's franchise score.

The old team-rankings test used a 2-team league with 2,000-point players, where one team's pick capital was as large as
its whole roster, so the franchise rank flipped on a 3% knife-edge whenever the pick curve moved. These tests pin the
cause (pick capital is a small share of franchise value at realistic roster values), under both the previous and the
market-calibrated pick curve.
"""

from __future__ import annotations

import pandas as pd
import pytest

from modules import trade_ideas
from modules.league_rankings import safe_pick_value
from scripts.profile_trade_hub import FixtureSpec, build_fixture

DRAFT_STATUS = {"draft_year": 2026, "current_year_picks_active": True}
KEY = trade_ideas.EARLY_FIRST_TOP_END_ENV_KEY


def _capital_shares(teams: int) -> pd.Series:
    fixture = build_fixture(FixtureSpec("franchise-share", teams, 26, "1 QB", strategy="contender"))
    picks = trade_ideas.list_draft_pick_assets(
        "fixture-league",
        fixture["summary"],
        league_settings=fixture["settings"],
        draft_status=DRAFT_STATUS,
        adapter=fixture["adapter"],
    )
    capital = pd.Series(0.0, index=[int(r) for r in fixture["summary"]["roster_id"]])
    for pick in picks:
        capital[int(pick["owner_roster_id"])] += safe_pick_value(pick)
    summary = fixture["summary"].copy()
    roster_value = pd.to_numeric(summary.get("raw_roster_score"), errors="coerce").fillna(
        pd.to_numeric(summary["total_score"], errors="coerce")
    )
    roster_value.index = [int(r) for r in summary["roster_id"]]
    return capital / (roster_value + capital)


@pytest.mark.parametrize("flag", ["0", "1"])
def test_picks_are_a_minor_share_of_franchise_in_a_realistic_league(monkeypatch, flag):
    monkeypatch.setenv(KEY, flag)
    shares = _capital_shares(12)
    assert len(shares) == 12
    assert (shares < 0.15).all(), shares.round(3).to_dict()


@pytest.mark.parametrize("flag", ["0", "1"])
def test_small_league_with_realistic_players_keeps_picks_under_half_of_franchise(monkeypatch, flag):
    monkeypatch.setenv(KEY, flag)
    shares = _capital_shares(2)
    assert len(shares) == 2
    assert (shares < 0.50).all(), shares.round(3).to_dict()

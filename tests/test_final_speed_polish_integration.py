"""Contracts that #303 / #304 / #305 must all survive on the integration branch."""

from __future__ import annotations

from pathlib import Path

from modules import share_card_renderer
from modules import share_recommendation_cards as share
from modules.player_eligibility import (
    filter_current_fantasy_players,
    is_current_fantasy_asset,
)


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_eligibility_owner_still_excludes_stale_listed_veteran():
    from datetime import datetime, timezone

    now = datetime(2026, 7, 13, tzinfo=timezone.utc)
    retired = {
        "player_id": "138",
        "name": "Stale Veteran",
        "full_name": "Stale Veteran",
        "sport": "nfl",
        "active": True,
        "status": "Active",
        "team": "PIT",
        "position": "QB",
        "fantasy_positions": ["QB"],
        "years_exp": 18,
        "news_updated": 1643296817250,
        "depth_chart_order": 0,
        "depth_chart_position": "",
        "stats_season": None,
        "fantasycalc_value": 0,
        "age": 39,
        "injury_status": "",
    }
    assert is_current_fantasy_asset(retired, now=now) is False
    import pandas as pd

    kept = filter_current_fantasy_players(pd.DataFrame([retired]), now=now)
    assert kept.empty
    owner = (ROOT / "modules" / "player_eligibility.py").read_text(encoding="utf-8")
    assert "roethlisberger" not in owner.casefold()

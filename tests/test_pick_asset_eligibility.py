"""Roster pick boards must not invent expired or redraft future capital."""

from __future__ import annotations

import pandas as pd

from modules import trade_ideas


class _Adapter:
    def __init__(self, *, season: int, traded=None):
        self.season = season
        self.traded = traded or []

    def get_league(self, league_id):
        return {"season": self.season, "settings": {"draft_rounds": 2}}

    def get_traded_picks(self, league_id):
        return list(self.traded)

    def get_rosters(self, league_id):
        return [
            {"roster_id": 1, "owner_id": "u1"},
            {"roster_id": 2, "owner_id": "u2"},
        ]


def _summary():
    return pd.DataFrame(
        [
            {"roster_id": 1, "team_name": "One", "total_score": 90},
            {"roster_id": 2, "team_name": "Two", "total_score": 80},
        ]
    )


def _seasons(picks):
    return sorted({int(p["season"]) for p in picks})


def test_redraft_does_not_synthesize_prior_or_future_picks():
    adapter = _Adapter(
        season=2025,
        traded=[{"season": "2025", "round": 1, "roster_id": 1, "owner_id": 2}],
    )
    picks = trade_ideas.list_draft_pick_assets(
        "league",
        _summary(),
        league_settings={"league_format": "Redraft"},
        draft_status={"draft_year": 2025, "current_year_picks_active": True, "draft_completed": False},
        adapter=adapter,
    )
    # Calendar year is 2026 in this run: 2025 is expired even if Sleeper season lags.
    assert picks == []


def test_redraft_current_year_pre_draft_is_actionable():
    year = 2026
    adapter = _Adapter(season=year)
    picks = trade_ideas.list_draft_pick_assets(
        "league",
        _summary(),
        league_settings={"league_format": "Redraft"},
        draft_status={
            "draft_year": year,
            "current_year_picks_active": True,
            "draft_completed": False,
        },
        adapter=adapter,
    )
    assert _seasons(picks) == [year]
    assert all(p["round"] in {1, 2} for p in picks)
    assert not any(p["season"] == year + 1 for p in picks)


def test_redraft_current_year_post_draft_is_not_actionable():
    year = 2026
    adapter = _Adapter(
        season=year,
        traded=[{"season": str(year), "round": 1, "roster_id": 1, "owner_id": 2}],
    )
    picks = trade_ideas.list_draft_pick_assets(
        "league",
        _summary(),
        league_settings={"league_format": "Redraft"},
        draft_status={
            "draft_year": year,
            "current_year_picks_active": False,
            "draft_completed": True,
        },
        adapter=adapter,
    )
    assert picks == []


def test_dynasty_future_picks_remain_after_current_draft_completes():
    year = 2026
    adapter = _Adapter(season=year)
    picks = trade_ideas.list_draft_pick_assets(
        "league",
        _summary(),
        league_settings={"league_format": "Dynasty"},
        draft_status={
            "draft_year": year,
            "current_year_picks_active": False,
            "draft_completed": True,
        },
        adapter=adapter,
    )
    assert _seasons(picks) == [year + 1, year + 2]


def test_keeper_is_not_treated_as_redraft_for_future_picks():
    year = 2026
    adapter = _Adapter(season=year)
    picks = trade_ideas.list_draft_pick_assets(
        "league",
        _summary(),
        league_settings={"league_format": "Dynasty", "_keeper_mode": True},
        draft_status={
            "draft_year": year,
            "current_year_picks_active": False,
            "draft_completed": True,
        },
        adapter=adapter,
    )
    assert _seasons(picks) == [year + 1, year + 2]


def test_redraft_without_draft_status_does_not_invent_a_board():
    adapter = _Adapter(season=2026)
    picks = trade_ideas.list_draft_pick_assets(
        "league",
        _summary(),
        league_settings={"league_format": "Redraft"},
        adapter=adapter,
    )
    assert picks == []

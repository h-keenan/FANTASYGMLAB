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


class _StatusAdapter(_Adapter):
    def __init__(self, *, season: int, status: str, traded=None):
        super().__init__(season=season, traded=traded)
        self.status = status

    def get_league(self, league_id):
        return {"season": self.season, "status": self.status, "settings": {"draft_rounds": 2}}


def _pick_id(pick):
    return f"{pick['season']}:{pick['round']}:{pick['original_roster_id']}"


def _freeze_now(monkeypatch, when):
    import datetime as _dt

    class _Frozen(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(when.year, when.month, when.day)

    monkeypatch.setattr(trade_ideas, "datetime", _Frozen)


def test_in_season_league_without_draft_status_does_not_offer_spent_picks(monkeypatch):
    """Regression (logic audit 2026-10): Trade Hub, Trade Finder, Trade
    Analyzer and power-rank draft capital pass no draft_status. In October a
    dynasty league's own rookie draft is long done (Sleeper status
    "in_season"), yet those callers still listed that season's spent picks
    and left out the second future season, so a 2028 pick id from
    GET .../draft-picks could not be resolved."""

    import datetime as _dt

    _freeze_now(monkeypatch, _dt.date(2026, 10, 21))
    year = 2026
    for status in ("in_season", "complete"):
        picks = trade_ideas.list_draft_pick_assets(
            "league",
            _summary(),
            league_settings={"league_format": "Dynasty"},
            adapter=_StatusAdapter(season=year, status=status),
        )
        assert _seasons(picks) == [year + 1, year + 2], status

    draft_center = trade_ideas.list_draft_pick_assets(
        "league",
        _summary(),
        league_settings={"league_format": "Dynasty"},
        draft_status={"draft_year": year, "current_year_picks_active": False, "draft_completed": True},
        adapter=_StatusAdapter(season=year, status="in_season"),
    )
    no_status = trade_ideas.list_draft_pick_assets(
        "league",
        _summary(),
        league_settings={"league_format": "Dynasty"},
        adapter=_StatusAdapter(season=year, status="in_season"),
    )
    assert {_pick_id(p) for p in no_status} == {_pick_id(p) for p in draft_center}
    assert [p["score"] for p in no_status] == [p["score"] for p in draft_center]


def test_pre_draft_league_without_draft_status_keeps_current_year_picks(monkeypatch):
    import datetime as _dt

    _freeze_now(monkeypatch, _dt.date(2026, 3, 1))
    picks = trade_ideas.list_draft_pick_assets(
        "league",
        _summary(),
        league_settings={"league_format": "Dynasty"},
        adapter=_StatusAdapter(season=2026, status="pre_draft"),
    )
    assert _seasons(picks) == [2026, 2027]


def test_future_discount_counts_from_next_draft_not_calendar_year(monkeypatch):
    """Between January and the rookie draft the calendar year equals the
    upcoming draft's year; the old calendar formula then also gave the
    following season's picks years_out=0 (no future discount)."""

    import datetime as _dt

    _freeze_now(monkeypatch, _dt.date(2027, 2, 15))
    picks = trade_ideas.list_draft_pick_assets(
        "league",
        _summary(),
        league_settings={"league_format": "Dynasty"},
        adapter=_StatusAdapter(season=2027, status="pre_draft"),
    )
    firsts = {
        int(p["season"]): p
        for p in picks
        if p["round"] == 1 and p["original_roster_id"] == 1
    }
    assert firsts[2027]["years_out"] == 0
    assert firsts[2028]["years_out"] == 1
    assert firsts[2028]["score"] < firsts[2027]["score"]

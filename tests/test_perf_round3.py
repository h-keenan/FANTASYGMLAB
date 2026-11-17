"""Round-3 performance changes: single-roster need model for the waiver guardrail."""

from __future__ import annotations

import pandas as pd

from modules import nfl_schedule, waivers_logic
from modules import roster_value_model as rvm
from tests.test_team_needs_model import SETTINGS, TEAMS, UNIVERSE, _league, _row


def test_league_needs_subset_is_identical_to_the_full_table_for_those_rosters():
    """``only_roster_ids`` (the trade-idea waiver guardrail reads one roster) skips the other rosters'
    lineup-model runs without changing the assessed roster's answer, and a cached full table serves it."""
    frame, rosters = _league()
    kwargs = dict(valued=frame, rosters=rosters, league={"total_rosters": TEAMS}, settings=SETTINGS, score_field="dynasty_score")
    rvm._LEAGUE_NEEDS_CACHE.clear()
    subset = rvm.league_needs(**kwargs, only_roster_ids=[3])
    assert set(subset.by_roster) == {"3"}
    rvm._LEAGUE_NEEDS_CACHE.clear()
    full = rvm.league_needs(**kwargs)
    assert len(full.by_roster) > 1
    assert subset.for_roster(3) == full.for_roster(3)
    assert rvm.league_needs(**kwargs, only_roster_ids=[3]) is full  # a cached full table serves a subset
    rvm._LEAGUE_NEEDS_CACHE.clear()


def test_waiver_pick_is_identical_with_a_single_roster_need_model(monkeypatch):
    """The trade-idea waiver guardrail's pick (``select_top_waiver_opportunity``) does not change."""
    monkeypatch.setattr(nfl_schedule, "team_bye_week", lambda team, season, **kw: 99)
    monkeypatch.setattr(waivers_logic, "default_played_ids", lambda league: None)
    owned_frame, rosters = _league()
    owned = set(owned_frame["player_id"])
    rows = []
    for pos, (n, top, bottom) in UNIVERSE.items():
        for i in range(n):
            pid = f"{pos}{i}"
            rows.append(_row(pid, pos, 9000 * (1 - i / n) + 200, top - (top - bottom) * i / (n - 1)))
    valued = pd.DataFrame(rows)
    free_agents = valued[~valued["player_id"].isin(owned)].reset_index(drop=True)
    my_team = valued[valued["player_id"].isin(rosters[-1]["players"])]
    real = rvm.league_needs

    def pick(subset: bool):
        rvm._LEAGUE_NEEDS_CACHE.clear()
        if not subset:
            monkeypatch.setattr(rvm, "league_needs", lambda **kw: real(**{k: v for k, v in kw.items() if k != "only_roster_ids"}))
        try:
            return {
                pos: waivers_logic.select_top_waiver_opportunity(
                    free_agents, my_team, SETTINGS, "dynasty_score", needed_positions=[pos],
                    rosters=rosters, roster_id=rosters[-1]["roster_id"], valued=valued, posture="rebuild",
                )
                for pos in ("QB", "RB", "WR", "TE")
            }
        finally:
            monkeypatch.setattr(rvm, "league_needs", real)
            rvm._LEAGUE_NEEDS_CACHE.clear()

    narrow, wide = pick(True), pick(False)
    assert any(not v.empty for v in narrow.values())
    for pos in narrow:
        pd.testing.assert_series_equal(narrow[pos], wide[pos])

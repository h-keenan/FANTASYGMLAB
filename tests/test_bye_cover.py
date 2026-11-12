import pandas as pd
import pytest

from modules import bye_cover, dashboard_workflow, daily_gm_briefing, nfl_schedule
from modules.team_eval import suggest_optimal_lineup

SETTINGS = {"qb_count": 1, "rb_count": 1, "wr_count": 2, "te_count": 1, "regular_flex_count": 0, "wrrb_flex_count": 0}
LEAGUE = {"status": "in_season", "season": "2026", "settings": {"leg": 7}}
BYES = {"AAA": 9, "BBB": 5, "CCC": 12, "DDD": 7}


@pytest.fixture(autouse=True)
def _schedule(monkeypatch):
    monkeypatch.setattr(nfl_schedule, "team_bye_week", lambda team, season, games=None: BYES.get(team))


def _p(pid, name, pos, team, score, **extra):
    return {"player_id": pid, "name": name, "position": pos, "team": team, "dynasty_score": score,
            "status": "Active", "injury_status": "", "player_tier": "", **extra}


def _roster(extra=()):
    return pd.DataFrame(
        [
            _p("1", "Quinn QB", "QB", "BBB", 90),
            _p("2", "Rick RB", "RB", "BBB", 80),
            _p("3", "Wade WR", "WR", "AAA", 85),
            _p("4", "Walt WR", "WR", "BBB", 70),
            _p("5", "Tim TE", "TE", "BBB", 60),
            *extra,
        ]
    )


def _fas():
    return pd.DataFrame(
        [
            _p("10", "Fits One", "WR", "BBB", 40),
            _p("11", "Same Bye", "WR", "AAA", 45),
            _p("12", "Hurt Guy", "WR", "BBB", 50, injury_status="Out"),
            _p("13", "Fits Two", "WR", "CCC", 30),
            _p("14", "Wrong Pos", "RB", "BBB", 55),
            _p("15", "No Team", "WR", "", 35),
        ]
    )


def _build(roster, **kw):
    lineup = suggest_optimal_lineup(roster, SETTINGS, score_field="dynasty_score")
    args = dict(league=LEAGUE, roster_df=roster, lineup_df=lineup, free_agents_df=_fas(),
                league_settings=SETTINGS, score_field="dynasty_score", games=pd.DataFrame({"week": [1]}))
    args.update(kw)
    return bye_cover.build_bye_cover_tile(**args)


def test_uncovered_starter_bye_alerts_with_healthy_nonbye_fillins():
    tile = _build(_roster())
    assert tile["label"] == "Bye Week Cover"
    assert tile["value"] == "Your WR1 (Wade WR) is on bye in Week 9"
    assert tile["route_player_id"] == "3"
    names = [p["name"] for p in tile["mentioned_players"]]
    assert names == ["Fits One", "Fits Two"]  # no same-bye, injured, wrong-position or teamless FA
    assert "Look at the waiver wire for a fill-in: Fits One, Fits Two." in tile["note"]
    assert tile["presentation"]["bye_cover"]["week"] == 9
    assert tile["weeks_away"] == 2


def test_bench_player_covering_the_slot_means_no_alert():
    assert _build(_roster([_p("6", "Bench WR", "WR", "BBB", 50)])) is None


def test_bench_wr_on_same_bye_does_not_cover():
    tile = _build(_roster([_p("6", "Bench WR", "WR", "AAA", 50)]))
    assert tile is not None and tile["route_player_id"] == "3"


def test_flex_slot_accepts_other_positions():
    settings = {**SETTINGS, "regular_flex_count": 1}
    roster = _roster([_p("6", "Rob RB", "RB", "AAA", 65)])  # RB2 starts in the FLEX slot, bye Wk 9
    roster.loc[roster.player_id == "3", "team"] = "BBB"  # WR1 is fine
    lineup = suggest_optimal_lineup(roster, settings, score_field="dynasty_score")
    tile = _build(roster, lineup_df=lineup, league_settings=settings)
    assert tile["value"] == "Your RB2 (Rob RB) is on bye in Week 9"
    assert "Wrong Pos" in [p["name"] for p in tile["mentioned_players"]]  # a RB, accepted by FLEX


def test_bye_outside_horizon_or_in_past_is_ignored():
    assert _build(_roster(), league={**LEAGUE, "settings": {"leg": 1}}) is None  # byes Wk 5/9 are beyond Wk 1+3
    assert _build(_roster(), league={**LEAGUE, "settings": {"leg": 10}}) is None  # already past


def test_this_week_is_urgent_and_immediate():
    tile = _build(_roster(), league={**LEAGUE, "settings": {"leg": 9}})
    assert tile["weeks_away"] == 0 and tile["tone"] == "risk"


def test_no_alert_offseason_best_ball_or_without_schedule(monkeypatch):
    assert _build(_roster(), league={**LEAGUE, "status": "complete"}) is None
    assert _build(_roster(), league={**LEAGUE, "settings": {"leg": 7, "best_ball": 1}}) is None
    assert _build(_roster(), games=pd.DataFrame()) is None
    monkeypatch.setattr(nfl_schedule, "team_bye_week", lambda *a, **k: None)
    assert _build(_roster()) is None


def test_ruled_out_starter_is_left_to_injury_alert():
    roster = _roster()
    roster.loc[roster.player_id == "3", "injury_status"] = "Out"
    assert _build(roster) is None


def test_no_fillins_says_so_instead_of_inventing():
    tile = _build(_roster(), free_agents_df=_fas().iloc[0:0])
    assert tile["mentioned_players"] == []
    assert "No healthy WR on waivers" in tile["note"]


def test_label_flows_through_the_briefing_pipeline():
    tile = _build(_roster())
    need = {"label": "Biggest Team Need", "value": "WR", "note": "Thin at WR", "route_key": "my_team"}
    briefing = dashboard_workflow.organize_dashboard_items(
        [need, tile], immediate_labels=frozenset({bye_cover.LABEL})
    )
    daily_gm_briefing.clear_compose_memo()
    out = daily_gm_briefing.compose_daily_gm_briefing(briefing, league_id="L", roster_id="1")
    item = next(i for i in out.items if i.supporting_context == "Bye Week Cover")
    assert item.category == "watch"
    assert item.presentation["bye_cover"]["week"] == 9
    assert [p["name"] for p in item.mentioned_players] == ["Fits One", "Fits Two"]


def test_starter_on_bye_next_week_alerts_as_urgent():
    tile = _build(_roster(), league={**LEAGUE, "settings": {"leg": 8}})
    assert tile["value"] == "Your WR1 (Wade WR) is on bye in Week 9"
    assert tile["weeks_away"] == 1 and tile["tone"] == "risk"


@pytest.mark.parametrize("settings", [{}, {"leg": 0}, {"leg": None}])
def test_league_without_a_current_week_never_alerts(settings):
    assert _build(_roster(), league={**LEAGUE, "settings": settings}) is None

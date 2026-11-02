"""Trade Hub / Finder gate consistency with the Trade Analyzer.

Validation on real Sleeper dynasty leagues found: (1) the Hub gate let the whole
FAIR band (-400..+500) through, including packages the Analyzer words as giving
up value; (2) a Hub card's gain disagreed with the Analyzer for the same package
because the Hub priced picks without the teams' real records.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

from modules import trade_grade, trade_hub_engine, trade_ideas, trade_value_bands
from tests.test_trade_hub_engine import SETTINGS, _player, _rosters


def _verdict(ui, score, model=True):
    return SimpleNamespace(ui_verdict=ui, trade_score=score, lineup_model={"available": True} if model else None)


@pytest.mark.parametrize(
    "ui,score,expected",
    [
        ("ACCEPT", 1800, True),
        ("ACCEPT", 500, True),
        ("FAIR", 499, True),
        ("FAIR", 150, True),
        ("FAIR", 0, True),
        ("FAIR", -150, True),
        # "Slight value edge to them": the Analyzer's FAIR, but not a recommendation.
        ("FAIR", -151, False),
        ("FAIR", -399, False),
        ("COUNTER", -402, False),
        ("DECLINE", -1500, False),
    ],
)
def test_suggestion_bar_is_the_even_rung_of_the_one_score_ladder(ui, score, expected):
    assert trade_grade.clears_suggestion_bar(_verdict(ui, score)) is expected
    # The edge is the ladder's own constant, not a number private to the gate.
    assert trade_value_bands.band_for_score(-trade_value_bands.EDGE).id == "even"


def test_legacy_verdicts_without_a_lineup_model_keep_their_own_rules():
    assert trade_grade.clears_suggestion_bar(_verdict("FAIR", -600, model=False)) is True
    assert trade_grade.clears_suggestion_bar(_verdict("COUNTER", -600, model=False)) is False


def test_ungradable_idea_is_kept_like_the_analyzer_returning_no_verdict():
    assert trade_grade.clears_suggestion_bar(None) is True


def test_gate_rejects_a_fair_band_loss_and_stamps_the_analyzers_gain(monkeypatch):
    my_team = pd.DataFrame([_player("a", "WR", value=50)])
    gate = trade_ideas._UserSideAnalyzerGate(
        my_team_df=my_team, all_players_df=my_team, strategy="contender",
        league_settings=SETTINGS, score_field="dynasty_score",
    )
    gate._current_context = {"x": 1}

    def fake_grade(**kwargs):
        verdict = SimpleNamespace(
            ui_verdict="FAIR", trade_score=-300, value_delta=-153, band="FAIR / PREFERENCE", lineup_model={"available": True},
            posture=None, posture_assessment=None, posture_note="",
        )
        return {"lineup_model": {}}, verdict

    monkeypatch.setattr(trade_grade, "grade_trade_for_user", fake_grade)
    idea = {"send_assets": [], "receive_assets": [], "trade_gain": 198}
    assert gate.passes(idea) is False
    # The card's gain is the Analyzer's own value delta; the engine's figure is kept.
    assert idea["trade_gain"] == -153 and idea["engine_trade_gain"] == 198

    even = {"send_assets": [], "receive_assets": [], "trade_gain": 10}

    def fair_even(**kwargs):
        return {"lineup_model": {}}, SimpleNamespace(
            ui_verdict="FAIR", trade_score=-20, value_delta=-30, band="FAIR / PREFERENCE", lineup_model={"available": True},
            posture=None, posture_assessment=None, posture_note="",
        )

    monkeypatch.setattr(trade_grade, "grade_trade_for_user", fair_even)
    assert gate.passes(even) is True and even["trade_gain"] == -30


def test_hub_hands_the_search_each_rosters_real_record_so_picks_price_like_the_analyzer():
    """Pick values blend a team's real wins/losses (trade_ideas._pick_team_context).
    The Hub used to hand the search bare rosters, so its picks ignored records and
    the pick the Analyzer resolves by pick_id (full rosters) was priced differently."""

    rosters = _rosters()
    for roster in rosters:
        roster["settings"] = {"wins": 6, "losses": 1, "ties": 0}
    players_df = pd.DataFrame([_player("my-qb", "QB", value=80), _player("opp-rb", "RB", value=70)])
    summary = pd.DataFrame(
        [{"league_id": "league-1", "roster_id": 1, "owner_id": "u1", "team_name": "Mine", "total_score": 80}]
    )
    with patch("modules.sleeper.get_rosters", return_value=rosters), patch("modules.sleeper.get_users", return_value=[]):
        with patch("modules.trade_ideas.build_trade_ideas", return_value=[]) as mock_build:
            trade_hub_engine.generate_trade_idea_records(
                league_id="league-1", my_roster_id=1, players_df=players_df, rosters=rosters,
                league_settings=SETTINGS, score_field="dynasty_score", team_strategy="contender",
                df_summary=summary,
            )
    sent = mock_build.call_args.kwargs["prefetched_rosters"]
    assert sent and all(r["settings"] == {"wins": 6, "losses": 1, "ties": 0} for r in sent)


def test_a_pick_prices_the_same_in_the_engine_and_the_pick_id_resolution(monkeypatch):
    from modules import trade_ideas as ti

    monkeypatch.setattr(ti, "_season_progress_fraction", lambda league: 0.8)

    rosters = [
        {"roster_id": 1, "players": [], "settings": {"wins": 0, "losses": 7, "ties": 0}},
        {"roster_id": 2, "players": [], "settings": {"wins": 7, "losses": 0, "ties": 0}},
    ]
    summary = pd.DataFrame(
        {"roster_id": [1, 2], "total_score": [60000.0, 40000.0], "team_name": ["A", "B"]}
    )
    adapter = SimpleNamespace(
        get_rosters=lambda league_id: rosters,
        get_league=lambda league_id: {"settings": {"draft_rounds": 3}, "season": "2026", "status": "in_season"},
        get_traded_picks=lambda league_id: [],
    )
    full = ti._build_roster_pick_assets("L", rosters, summary, league_settings=SETTINGS, adapter=adapter)
    listed = ti.list_draft_pick_assets("L", summary, league_settings=SETTINGS, adapter=adapter)
    by_id = {f"{p['season']}:{p['round']}:{p['original_roster_id']}": p["score"] for p in listed}
    for assets in full.values():
        for pick in assets:
            assert by_id[f"{pick['season']}:{pick['round']}:{pick['original_roster_id']}"] == pick["score"]
    # And the record really matters (so dropping it would be a different price).
    bare = ti._build_roster_pick_assets(
        "L", [{"roster_id": r["roster_id"], "players": []} for r in rosters], summary,
        league_settings=SETTINGS, adapter=adapter,
    )
    key = lambda a: (a["season"], a["round"], a["original_roster_id"])
    with_rec = {key(p): p["score"] for a in full.values() for p in a}
    without = {key(p): p["score"] for a in bare.values() for p in a}
    assert with_rec != without


def test_gate_and_analyzer_attach_the_same_weekly_projection_baselines(monkeypatch):
    """The Analyzer endpoint grades on a frame with proj_ppg/proj_sd; the Hub gate
    must too (one shared helper), or the two score the same package differently."""

    from modules import player_projections
    from services import mobile_api_service as svc

    monkeypatch.setattr(
        player_projections,
        "baseline_weekly_points",
        lambda rows, **kw: {str(r["player_id"]): {"ppg": 12.5, "sd": 4.0} for r in rows},
    )
    valued = pd.DataFrame([_player("a", "WR", value=50), _player("b", "RB", value=40), _player("fa", "WR", value=10)])
    pool = valued[valued["player_id"] == "fa"]
    via_gate, pool_gate = trade_grade.attach_projection_baselines(valued, pool, {"a"}, "dynasty_score")
    via_api, pool_api = svc._attach_projection_ppg(valued, pool, {"a"}, "dynasty_score")
    pd.testing.assert_series_equal(via_gate["proj_ppg"], via_api["proj_ppg"])
    assert pool_gate["proj_sd"].tolist() == pool_api["proj_sd"].tolist() == [4.0]
    # Never raises: a failing baseline source leaves the frames untouched.
    monkeypatch.setattr(player_projections, "baseline_weekly_points", lambda *a, **k: 1 / 0)
    same, _ = trade_grade.attach_projection_baselines(valued, pool, {"a"}, "dynasty_score")
    assert "proj_ppg" not in same.columns

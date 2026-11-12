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


def test_with_a_lineup_model_the_bar_reads_only_the_score_and_agrees_with_its_own_rung():
    """No label check: for every score the verdict's UI rung is a function of that score, and the
    bar (score >= -EDGE) is exactly "that rung is FAIR/ACCEPT and not the edge-to-them band"."""

    for score in trade_value_bands.GOLDEN_SCORES:
        rung = trade_value_bands.band_for_score(score)
        verdict = _verdict(rung.ui_verdict, score)
        assert trade_grade.clears_suggestion_bar(verdict) is (
            rung.ui_verdict in trade_grade.PASSING_UI_VERDICTS and rung.id != "edge_them"
        ), score
        # The score alone decides; whatever UI string rides along cannot change the answer.
        assert trade_grade.clears_suggestion_bar(_verdict("ACCEPT", score)) is trade_grade.clears_suggestion_bar(
            _verdict("DECLINE", score)
        )


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


# ---------------------------------------------------------------------------
# Hub / Finder grade with the Analyzer's pick context (modules.trade_cautions)
#
# Owner report: a Hub idea could say SMASH ACCEPT where the Analyzer says
# ACCEPT, because only the Analyzer passed ``pick_context`` (the pick-glut
# caution softens exactly that rung).

from modules import trade_analyzer_fit, trade_cautions, trade_offer_analyzer as toa  # noqa: E402
from tests import test_trade_cautions as tc  # noqa: E402


def _glut_fit(*args, **kwargs):
    return tc._fit()


def _glut_idea():
    return {"send_assets": list(tc.OWNER_SEND), "receive_assets": list(tc.OWNER_GET), "trade_gain": 1873}


def _gate(pick_context=None):
    my_team = pd.DataFrame([_player("a", "WR", value=50)])
    gate = trade_ideas._UserSideAnalyzerGate(
        my_team_df=my_team, all_players_df=my_team, strategy="rebuild", league_settings=SETTINGS,
        score_field="dynasty_score", pick_context=pick_context,
    )
    gate._current_context = {"x": 1}
    return gate


def test_grade_trade_for_user_uses_the_pick_context_like_the_analyzer(monkeypatch):
    monkeypatch.setattr(trade_analyzer_fit, "evaluate_trade_analyzer_fit", _glut_fit)
    kwargs = dict(
        my_team_df=None, all_players_df=None, send_assets=tc.OWNER_SEND, receive_assets=tc.OWNER_GET,
        strategy="rebuild", lineup_settings=None, score_field="value_score",
    )
    _, bare = trade_grade.grade_trade_for_user(**kwargs)
    _, with_ctx = trade_grade.grade_trade_for_user(**kwargs, pick_context=tc._held_five_firsts())
    analyzer = tc._verdict()
    assert bare.band == "SMASH ACCEPT"  # what Hub used to say
    assert with_ctx.band == analyzer.band == "ACCEPT" and with_ctx.ui_verdict == analyzer.ui_verdict
    assert [c["code"] for c in with_ctx.cautions] == ["pick_glut"]
    # Words and a one-step softening only: the numbers are the Analyzer's, unchanged.
    assert (with_ctx.value_delta, with_ctx.trade_score) == (bare.value_delta, bare.trade_score)


def test_the_gate_stamps_the_same_verdict_the_analyzer_gives(monkeypatch):
    monkeypatch.setattr(trade_analyzer_fit, "evaluate_trade_analyzer_fit", _glut_fit)
    idea = _glut_idea()
    assert _gate(tc._held_five_firsts()).passes(idea) is True
    assert idea["analyzer_label"] == tc._verdict().band == "ACCEPT"
    assert idea["analyzer_verdict"] == tc._verdict().ui_verdict
    assert idea["analyzer_value_delta"] == tc._verdict().value_delta
    # Without the context (the old behaviour) the same idea read SMASH ACCEPT.
    old = _glut_idea()
    _gate(None).passes(old)
    assert old["analyzer_label"] == "SMASH ACCEPT"


def test_the_gate_hands_its_pick_context_to_the_grader(monkeypatch):
    seen = {}

    def fake_grade(**kwargs):
        seen.update(kwargs)
        return None, None

    monkeypatch.setattr(trade_grade, "grade_trade_for_user", fake_grade)
    ctx = tc._held_five_firsts()
    _gate(ctx).passes({"send_assets": [], "receive_assets": []})
    assert seen["pick_context"] is ctx


def test_hub_pick_context_is_the_analyzers_context_for_the_same_pick_table():
    picks = {
        1: [tc._pick(2027, 1), tc._pick(2027, 1, score=2500), tc._pick(2028, 1), {"asset_type": "player"}],
        2: [tc._pick(2027, 1, owner="2"), tc._pick(2028, 2, owner="2")],
    }
    mine = {"roster_id": 1, "players": ["a", "b", "c", "d", "e", "f"], "reserve": [], "taxi": []}
    overflow = {"league": {"roster_positions": ["SLOT"] * 10, "settings": {}}, "my_roster": mine}
    got = trade_ideas.hub_pick_context(picks, 1, overflow)
    flat = [p for rows in picks.values() for p in rows if p.get("asset_type") == "pick"]
    expected = trade_cautions.build_pick_context(
        flat, 1, open_roster_spots=trade_cautions.open_roster_spots(overflow["league"], mine)
    )
    assert got == expected and got["held_firsts"] == 3 and got["open_roster_spots"] == 4


def test_hub_pick_context_with_unknown_room_or_no_picks():
    picks = {1: [tc._pick(2027, 1)]}
    # Unknown roster room never blocks the caution: the picks still count.
    ctx = trade_ideas.hub_pick_context(picks, 1, None)
    assert ctx["held_firsts"] == 1 and ctx["open_roster_spots"] is None
    assert trade_ideas.hub_pick_context({}, 1, None) is None
    assert trade_ideas.hub_pick_context({1: [{"asset_type": "player"}]}, 1, None) is None
    # A broken overflow spec degrades to no context (logged), never an exception.
    assert trade_ideas.hub_pick_context(picks, 1, {}) is None


def test_the_hub_and_finder_builders_hand_the_gate_a_pick_context():
    """Both gate constructors (build_trade_ideas and the target-player offers) pass the
    pick context; a regression to the old no-context gate would fail here."""

    import inspect

    from modules import trade_target_offers

    assert "pick_context=hub_pick_context(" in inspect.getsource(trade_ideas._build_trade_ideas_impl)
    assert "pick_context=ti.hub_pick_context(" in inspect.getsource(trade_target_offers)

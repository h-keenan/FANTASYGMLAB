"""Engine failures are reported, not swallowed (modules.model_status).

Each test forces the failure the old bare ``except Exception`` used to hide and
asserts the explicit marker; none of them changes a number or a verdict.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pandas as pd
import pytest

from modules import model_status, trade_grade, trade_hub_engine, trade_posture, verdict_assumptions


def test_model_status_vocabulary():
    s = model_status.ok()
    assert s == {"degraded": False, "reasons": []}
    model_status.add(s, "lineup_model_failed")
    model_status.add(s, "lineup_model_failed")  # once
    assert s["degraded"] is True and model_status.codes(s) == ["lineup_model_failed"]
    assert model_status.merge(s, model_status.from_codes(["teams_skipped"]))["reasons"][1]["code"] == "teams_skipped"
    assert RuntimeError not in model_status.LOOKUP_ERRORS


# --- roster_posture -----------------------------------------------------------

ROSTER = {"roster_id": 1, "settings": {"wins": 5, "losses": 1}}


def _posture(frame_or_exc, **kw):
    kwargs = dict(league_id="L", roster=ROSTER, lens="Dynasty", players_db_path="x", client_strategy="")
    kwargs.update(kw)
    if isinstance(frame_or_exc, BaseException):
        with patch.object(trade_hub_engine.league_rankings, "build_league_rankings_frame_cached", side_effect=frame_or_exc):
            return trade_hub_engine.roster_posture(**kwargs)
    return trade_hub_engine.roster_posture(rankings_frame=frame_or_exc, **kwargs)


def test_posture_lookup_failure_is_marked_and_still_falls_back_to_client():
    posture = _posture(OSError("redis down"), client_strategy="contender")
    assert posture["source"] == "client" and posture["key"] == "contender"
    assert posture["degraded_reason"] == "posture_lookup_failed"
    assert model_status.codes(posture["model_status"]) == ["posture_lookup_failed"]
    # Clients see it on the public posture that rides on every card.
    assert trade_posture.public_posture(posture)["degraded_reason"] == "posture_lookup_failed"


def test_posture_without_a_rankings_row_is_not_degraded():
    # A new league / empty frame is a normal named path, not a failure.
    posture = _posture(pd.DataFrame())
    assert posture["source"] == "client" and "degraded_reason" not in posture
    assert "degraded_reason" not in trade_posture.public_posture(posture)


def test_posture_lookup_bug_propagates():
    with pytest.raises(RuntimeError):
        _posture(RuntimeError("bug"))


def test_posture_from_rankings_is_not_degraded():
    frame = pd.DataFrame([{"roster_id": 1, "strategy": "contender", "power_rank": 1}])
    posture = _posture(frame)
    assert posture["source"] == "auto" and "degraded_reason" not in posture


# --- attach_projection_baselines ----------------------------------------------


def _frames():
    valued = pd.DataFrame(
        [
            {"player_id": "a", "position": "WR", "dynasty_score": 50},
            {"player_id": "fa", "position": "WR", "dynasty_score": 10},
        ]
    )
    return valued, valued[valued["player_id"] == "fa"].copy()


def test_projection_baseline_failure_is_logged_and_marks_the_frames(monkeypatch, caplog):
    from modules import player_projections

    monkeypatch.setattr(player_projections, "baseline_weekly_points", lambda *a, **k: 1 / 0)
    valued, pool = _frames()
    with caplog.at_level("WARNING"):
        out, pool_out = trade_grade.attach_projection_baselines(valued, pool, {"a"}, "dynasty_score")
    assert "projection baselines unavailable" in caplog.text
    assert "proj_ppg" not in out.columns
    assert model_status.frame_codes(out) == ["projection_baselines_failed"]
    assert model_status.frame_codes(pool_out) == ["projection_baselines_failed"]
    assert model_status.frame_codes(valued) == []  # the caller's frame is not mutated


def test_no_weekly_history_is_not_a_failure(monkeypatch):
    from modules import player_projections

    monkeypatch.setattr(player_projections, "baseline_weekly_points", lambda *a, **k: {})
    valued, pool = _frames()
    out, _ = trade_grade.attach_projection_baselines(valued, pool, {"a"}, "dynasty_score")
    assert model_status.frame_codes(out) == []


def test_projection_baseline_bug_propagates(monkeypatch):
    from modules import player_projections

    def boom(*a, **k):
        raise RuntimeError("bug")

    monkeypatch.setattr(player_projections, "baseline_weekly_points", boom)
    valued, pool = _frames()
    with pytest.raises(RuntimeError):
        trade_grade.attach_projection_baselines(valued, pool, {"a"}, "dynasty_score")


def test_the_fit_reports_degraded_baselines_carried_on_its_frames():
    from tests.test_trade_lineup_model import _evaluate, _pick, _thin_roster
    from modules import trade_analyzer_fit
    import tests.test_trade_lineup_model as t

    roster = pd.DataFrame(_thin_roster())
    model_status.mark_frame(roster, "projection_baselines_failed")
    universe = pd.concat([roster, t._universe()], ignore_index=True)
    model_status.mark_frame(universe, "projection_baselines_failed")
    send = [t._asset(roster.set_index("player_id", drop=False).loc["Jones"].to_dict())]
    fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
        roster, universe, send, [_pick(4800)], None, "retool", t.SETTINGS, "dynasty_score"
    )
    assert model_status.codes(fit["model_status"]) == ["projection_baselines_failed"]
    clean, _ = _evaluate(_thin_roster(), ["Jones"], [], receive_assets=[_pick(4800)])
    assert clean["model_status"]["degraded"] is False
    # Reporting only: the numbers are identical.
    assert fit["trade_score"] == clean["trade_score"]


# --- the Hub/Finder gate -------------------------------------------------------


def test_gate_does_not_suggest_an_idea_the_engine_could_not_grade(monkeypatch):
    from modules import trade_ideas

    verdict = Mock(ui_verdict="FAIR", trade_score=300, value_delta=100, band="FAIR", lineup_model=None)
    verdict.posture = {}
    verdict.posture_assessment = {}
    verdict.posture_note = ""

    def gate(status):
        monkeypatch.setattr(
            trade_ideas.trade_grade, "grade_trade_for_user", lambda **k: ({"model_status": status}, verdict)
        )
        g = trade_ideas._UserSideAnalyzerGate(
            my_team_df=pd.DataFrame([{"player_id": "a"}]),
            all_players_df=pd.DataFrame([{"player_id": "a"}]),
            strategy="retool",
            league_settings={},
            score_field="value_score",
        )
        g._current_context = {"x": 1}
        return g.passes({"send_assets": [], "receive_assets": []})

    assert gate(model_status.ok()) is True
    assert gate(model_status.from_codes(["lineup_model_failed"])) is False


# --- assumptions line ------------------------------------------------------------


def test_assumptions_line_carries_the_limited_data_note():
    kwargs = dict(lens="Dynasty", settings={}, strategy="retool")
    clean = verdict_assumptions.build_verdict_assumptions(**kwargs)
    assert "Limited data" not in clean["line"]
    bad = verdict_assumptions.build_verdict_assumptions(
        model_status=model_status.from_codes(["lineup_model_failed"]), **kwargs
    )
    assert "Limited data" in bad["line"]
    assert any(i["key"] == "limited_data" for i in bad["items"])

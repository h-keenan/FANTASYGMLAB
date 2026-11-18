"""Live draft context (handshake item 8): stance, ages, needs, rookie ADP and class strength."""

from __future__ import annotations

import pandas as pd

from modules import live_draft, live_draft_context

PROFILE = {
    "teams": {
        "1": {
            "posture": {"key": "rebuild", "label": "Rebuild"},
            "needs": {"needs": ["TE", "K"], "surplus_ids": {}},
            "age": {
                "core_avg": 28.9,
                "cliff_ids": ["a", "b"],
                "by_position": {
                    "RB": {"count": 4, "phase_mix": {"cliff": 2, "declining": 1, "prime": 1}},
                    "WR": {"count": 5, "phase_mix": {"prime": 4, "declining": 1}},
                },
            },
        }
    }
}


def ctx(**kw):
    return live_draft_context.build_context(profile=PROFILE, my_roster_id=1, **kw)


def test_context_reads_stance_needs_and_aging_rooms():
    c = ctx()
    assert c["strategy"] == "rebuild" and c["strategy_source"] == "auto"
    assert c["needs"] == ["TE"], "K is not a draft position"
    assert set(c["aging_rooms"]) == {"RB"}, "WR has only one declining player"
    declared = ctx(declared_stance="competing")
    assert declared["strategy"] == "contender" and declared["strategy_source"] == "declared"
    assert live_draft_context.build_context(profile=PROFILE, my_roster_id=9) is None


def pool():
    rows = []
    for i, (pos, age) in enumerate([("RB", 22), ("RB", 29), ("TE", 24), ("WR", 24)]):
        rows.append({"player_id": str(i), "name": f"P{i} Name", "position": pos, "age": age, "team": "X", "dynasty_score": 100 - i, "value_score": 100 - i, "years_exp": 3, "active": True, "status": "Active", "fantasycalc_value": 100 - i})
    return pd.DataFrame(rows)


def rank(settings):
    board = live_draft.build_live_draft_rankings(
        pool(), roster_df=pd.DataFrame(), league_settings=settings, score_field="dynasty_score"
    )
    return board.set_index("player_id")


def test_settings_change_needs_and_age_tilt_only_with_context(monkeypatch):
    monkeypatch.delenv(live_draft_context.LIVE_DRAFT_CONTEXT_ENV_KEY, raising=False)
    base_settings = {"league_format": "Dynasty"}
    before = rank(base_settings)
    after = rank(live_draft_context.apply_to_settings(base_settings, ctx()))
    # Aging RB room: the 22-year-old RB gains, the 29-year-old RB loses.
    assert after.loc["0", "age_strategy_adjustment"] > before.loc["0", "age_strategy_adjustment"]
    assert after.loc["1", "age_strategy_adjustment"] < before.loc["1", "age_strategy_adjustment"]
    # True need TE only: roster fit follows the profile, not the roster count.
    assert after.loc["2", "roster_fit_score"] > before.loc["2", "roster_fit_score"] - 5
    assert live_draft.roster_position_needs(pd.DataFrame(), live_draft_context.apply_to_settings(base_settings, ctx())) == ["TE"]
    # Always inside the existing cap.
    assert (after["age_strategy_adjustment"].abs() <= 4.5).all()


def test_flag_off_restores_the_previous_board(monkeypatch):
    base_settings = {"league_format": "Dynasty"}
    before = rank(base_settings)
    monkeypatch.setenv(live_draft_context.LIVE_DRAFT_CONTEXT_ENV_KEY, "0")
    settings = live_draft_context.apply_to_settings(base_settings, ctx())
    assert settings == base_settings
    assert live_draft_context.notes_for({"position": "TE"}, ctx()) == []
    assert live_draft_context.summary(ctx()) is None
    after = rank(settings)
    pd.testing.assert_frame_equal(before, after)


def test_notes_name_each_factor():
    c = ctx(rookie_draft=True, class_read=live_draft_context.class_strength(2026, 1.15, None, [{"draft_year": 2026, "position": "WR"}] * 3))
    notes = live_draft_context.notes_for({"position": "TE", "name": "Brock Bowers", "adp_delta": 5.0, "adp_verdict": "value"}, c)
    assert any("true TE need" in n for n in notes)
    assert any("B. Bowers" in n and "5 spots above his ADP" in n for n in notes)
    assert any("2026 class reads strong" in n for n in notes)
    rb = live_draft_context.notes_for({"position": "RB", "name": "Aaron Cook"}, c)
    assert any("RB room is aging (3 of 4" in n for n in rb)


def test_class_strength_needs_a_basis():
    assert live_draft_context.class_strength(2031, None, None, []) is None
    only_counts = live_draft_context.class_strength(2031, None, None, [{"draft_year": 2031, "position": "QB"}])
    assert only_counts["label"] is None and only_counts["prospects_tracked"] == {"QB": 1}
    weak = live_draft_context.class_strength(2027, 0.9, None, [])
    assert weak["label"] == "weak"


def test_summary_is_compact_and_explains():
    c = ctx(rookie_draft=True, class_read=live_draft_context.class_strength(2026, 1.15, None, []))
    s = live_draft_context.summary(c)
    assert s["parts"][0] == "Rebuilding" and "need TE" in s["parts"]
    assert any("younger" in line for line in s["lines"])

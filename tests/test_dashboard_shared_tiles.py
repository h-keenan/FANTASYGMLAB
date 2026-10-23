"""The trade-independent Dashboard tiles are computed once per input set, so
the deferred first paint and the follow-up full call share them."""

from __future__ import annotations

import pandas as pd

from modules import dashboard_engine, league_value_settings


def _registered_frame(key: str = "valued_players_frame:abc") -> pd.DataFrame:
    frame = pd.DataFrame({"player_id": ["1", "2"]})
    league_value_settings._remember_valued_frame_cache_key(frame, key)
    return frame


def _call(frame, compute, **overrides):
    kwargs = dict(
        players_df=frame,
        league_id="L1",
        roster_id=1,
        roster_player_ids={"1"},
        all_rostered_player_ids={"1", "2"},
        league_settings={"type": 2},
        score_field="dynasty_score",
        injury_display_context={"injured_starters": 0},
    )
    kwargs.update(overrides)
    return dashboard_engine._shared_trade_independent_tiles(compute, **kwargs)


def test_second_call_with_same_inputs_reuses_the_first_result():
    frame = _registered_frame()
    calls = []

    def compute():
        calls.append(1)
        return {"need_tile": {"headline": "x"}, "news_tiles": []}

    first = _call(frame, compute)
    second = _call(frame, compute)
    assert first == second
    assert len(calls) == 1


def test_any_changed_input_recomputes():
    frame = _registered_frame()
    calls = []

    def compute():
        calls.append(1)
        return {"n": len(calls)}

    _call(frame, compute)
    _call(frame, compute, roster_player_ids={"1", "2"})
    _call(frame, compute, injury_display_context={"injured_starters": 1})
    _call(frame, compute, score_field="redraft_score")
    assert len(calls) == 4


def test_unregistered_frame_is_never_shared():
    frame = pd.DataFrame({"player_id": ["1"]})
    calls = []

    def compute():
        calls.append(1)
        return {}

    _call(frame, compute)
    _call(frame, compute)
    assert len(calls) == 2

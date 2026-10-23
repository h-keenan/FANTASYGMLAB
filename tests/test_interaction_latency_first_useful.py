"""Regression tests for interaction-latency / first-useful-content (PR #157)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pandas as pd

from modules import interaction_latency
from modules import prepared_player_frame
from modules import recommendation_trust_ux


ROOT = Path(__file__).resolve().parents[1]


def test_fit_context_memo_hits_and_clears_on_league_hygiene():
    state: dict = {}
    calls = {"n": 0}

    def builder():
        calls["n"] += 1
        return {
            "roster_player_ids": {"p1"},
            "roster_df": pd.DataFrame({"player_id": ["p1"]}),
            "metrics": {"strengths": ["QB"]},
            "assessment": {"needs": []},
        }

    signature = interaction_latency.build_fit_context_signature(
        league_id="L1",
        roster_id="1",
        score_field="dynasty_score",
        league_settings_key="ppr",
        frame_signature="v1",
    )
    first, hit1 = interaction_latency.get_or_build_fit_context(
        state, signature=signature, builder=builder
    )
    second, hit2 = interaction_latency.get_or_build_fit_context(
        state, signature=signature, builder=builder
    )
    assert hit1 is False
    assert hit2 is True
    assert calls["n"] == 1
    assert first["roster_player_ids"] == second["roster_player_ids"]
    assert first["roster_df"].empty
    assert second["roster_df"].empty

    prepared_player_frame.clear_league_scoped_prepared_memos(state)
    assert interaction_latency.FIT_CONTEXT_KEY not in state
    _, hit3 = interaction_latency.get_or_build_fit_context(
        state, signature=signature, builder=builder
    )
    assert hit3 is False
    assert calls["n"] == 2


def test_stale_fit_signature_misses():
    state: dict = {}
    builder = Mock(
        return_value={
            "roster_player_ids": set(),
            "roster_df": pd.DataFrame(),
            "metrics": {},
            "assessment": None,
        }
    )
    sig_a = interaction_latency.build_fit_context_signature(
        league_id="A",
        roster_id="1",
        score_field="dynasty_score",
        league_settings_key="ppr",
    )
    sig_b = interaction_latency.build_fit_context_signature(
        league_id="B",
        roster_id="1",
        score_field="dynasty_score",
        league_settings_key="ppr",
    )
    interaction_latency.get_or_build_fit_context(state, signature=sig_a, builder=builder)
    interaction_latency.get_or_build_fit_context(state, signature=sig_b, builder=builder)
    assert builder.call_count == 2

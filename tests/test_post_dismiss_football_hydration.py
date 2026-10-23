"""Post-dismiss football hydration + widget-state ownership (#217)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import canonical_player_ranking as ranking
from modules import prepared_player_frame


ROOT = Path(__file__).resolve().parents[1]


def test_attach_canonical_ranks_emits_timing_breakdown():
    frame = pd.DataFrame(
        [
            {"player_id": "a", "position": "RB", "dynasty_score": 100, "active": True},
            {"player_id": "b", "position": "RB", "dynasty_score": 90, "active": True},
            {"player_id": "c", "position": "WR", "dynasty_score": 80, "active": True},
        ]
    )
    timing: dict[str, float] = {}
    ranked = ranking.attach_canonical_ranks(
        frame,
        scoring_format="PPR",
        score_field="dynasty_score",
        timing_out=timing,
    )
    assert list(ranked["canonical_overall_rank"]) == [1, 2, 3]
    assert "total_ms" in timing
    assert "sort_and_positional_ms" in timing
    assert "merge_assign_ms" in timing


def test_process_scoped_prepared_frame_reused_across_sessions():
    prepared_player_frame.clear_process_valued_ranked_frames()
    prepared_player_frame.clear_valued_ranked_frame({})
    calls = {"n": 0}

    def builder() -> pd.DataFrame:
        calls["n"] += 1
        return pd.DataFrame({"player_id": ["1"], "dynasty_score": [10]})

    sig = prepared_player_frame.build_frame_signature(
        public_fingerprint="pub",
        valuation_lens="Dynasty",
        score_field="dynasty_score",
        league_settings_key="settings",
        scoring_format="PPR",
        scoring_supported=True,
        archetype_id="balanced",
        season="2025",
        row_count=1,
    )
    state_a: dict = {}
    first, hit_a = prepared_player_frame.get_or_build_valued_ranked_frame(
        state_a, signature=sig, builder=builder
    )
    state_b: dict = {}
    second, hit_b = prepared_player_frame.get_or_build_valued_ranked_frame(
        state_b, signature=sig, builder=builder
    )
    assert hit_a is False
    assert hit_b is True
    assert calls["n"] == 1
    assert list(first["player_id"]) == list(second["player_id"])
    prepared_player_frame.clear_process_valued_ranked_frames()

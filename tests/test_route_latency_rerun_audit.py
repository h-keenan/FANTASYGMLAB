"""Contracts for route-latency / warm-rerun performance audit (PR #152)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import prepared_player_frame
from modules import session_integrity


ROOT = Path(__file__).resolve().parents[1]


def test_prepared_player_frame_reuses_identical_signature():
    prepared_player_frame.clear_process_valued_ranked_frames()
    state: dict = {}
    calls = {"n": 0}

    def builder() -> pd.DataFrame:
        calls["n"] += 1
        return pd.DataFrame(
            {
                "player_id": ["1", "2"],
                "dynasty_score": [100, 90],
                "canonical_overall_rank": [1, 2],
            }
        )

    signature = prepared_player_frame.build_frame_signature(
        public_fingerprint="pub",
        valuation_lens="Dynasty",
        score_field="dynasty_score",
        league_settings_key="settings",
        scoring_format="PPR",
        scoring_supported=True,
        archetype_id="balanced",
        season="2025",
        row_count=2,
    )
    first, hit_first = prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=signature, builder=builder
    )
    second, hit_second = prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=signature, builder=builder
    )
    assert hit_first is False
    assert hit_second is True
    assert calls["n"] == 1
    assert list(first["player_id"]) == list(second["player_id"])
    # Mutation isolation: editing the returned frame must not poison the memo.
    second.loc[0, "dynasty_score"] = 1
    third, hit_third = prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=signature, builder=builder
    )
    assert hit_third is True
    assert int(third.loc[0, "dynasty_score"]) == 100


def test_prepared_player_frame_misses_when_signature_changes():
    prepared_player_frame.clear_process_valued_ranked_frames()
    state: dict = {}
    calls = {"n": 0}

    def builder() -> pd.DataFrame:
        calls["n"] += 1
        return pd.DataFrame({"player_id": [str(calls["n"])], "dynasty_score": [calls["n"]]})

    base_kwargs = dict(
        public_fingerprint="pub",
        valuation_lens="Dynasty",
        score_field="dynasty_score",
        league_settings_key="settings",
        scoring_format="PPR",
        scoring_supported=True,
        archetype_id="balanced",
        season="2025",
        row_count=2,
    )
    sig_a = prepared_player_frame.build_frame_signature(**base_kwargs)
    sig_b = prepared_player_frame.build_frame_signature(
        **{**base_kwargs, "valuation_lens": "Rebuild"}
    )
    prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=sig_a, builder=builder
    )
    prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=sig_b, builder=builder
    )
    assert calls["n"] == 2


def test_prepared_shell_and_shared_context_reuse():
    state: dict = {}
    builds = {"shell": 0, "shared": 0}

    def shell_builder():
        builds["shell"] += 1
        return {"active_team_strategy": "contender", "shell_team_row": {"power_rank": 1}}

    def shared_builder():
        builds["shared"] += 1
        return {"league_summary": "ok"}

    signature = "frame|league|roster|score|settings|0|1"
    first, hit = prepared_player_frame.get_or_build_shell_chrome(
        state, signature=signature, builder=shell_builder
    )
    second, hit2 = prepared_player_frame.get_or_build_shell_chrome(
        state, signature=signature, builder=shell_builder
    )
    assert hit is False and hit2 is True
    assert builds["shell"] == 1
    assert first["active_team_strategy"] == "contender"

    shared_a, _ = prepared_player_frame.get_or_build_shared_league_context(
        state,
        signature=signature,
        flags=(True, True, True, True),
        builder=shared_builder,
    )
    shared_b, hit_shared = prepared_player_frame.get_or_build_shared_league_context(
        state,
        signature=signature,
        flags=(True, True, True, True),
        builder=shared_builder,
    )
    assert hit_shared is True
    assert builds["shared"] == 1
    assert shared_a["league_summary"] == shared_b["league_summary"]


def test_prepared_memos_do_not_modify_football_logic_modules():
    """Prepared-memo PRs must not touch Trust engines.

    Valuation calibration audits may intentionally edit rankings / trade_ideas.
    """
    diff_names = {
        line.strip()
        for line in __import__("subprocess")
        .run(
            ["git", "diff", "--name-only", "main"],
            capture_output=True,
            text=True,
            check=False,
        )
        .stdout.splitlines()
        if line.strip()
    }
    forbidden = {
        "modules/trust_engine.py",
    }
    assert not diff_names.intersection(forbidden)

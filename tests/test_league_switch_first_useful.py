"""Contracts for league-switch first-useful-workspace performance (PR #156)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import prepared_player_frame
from modules import session_integrity
from modules import trade_hub_first_useful


ROOT = Path(__file__).resolve().parents[1]


def test_league_switch_retains_valued_frame_clears_league_scoped():
    state = {
        prepared_player_frame.FRAME_KEY: pd.DataFrame({"player_id": ["1"]}),
        prepared_player_frame.SIGNATURE_KEY: "sig",
        prepared_player_frame.SHELL_BUNDLE_KEY: {"league": "A"},
        prepared_player_frame.SHELL_SIGNATURE_KEY: "shell|A",
        prepared_player_frame.SHARED_CONTEXT_KEY: {
            "frame|shell|A|1|score|settings|0|1|1|1|1|1": {"league_id": "A"},
            "frame|shell|B|1|score|settings|0|1|1|1|1|1": {"league_id": "B"},
        },
    }
    trade_hub_first_useful.get_or_build_presentation_board(
        state,
        signature="board|A",
        builder=lambda: {"eligible_ideas": [{"tag": "A"}]},
    )
    prepared_player_frame.clear_league_scoped_prepared_memos(
        state, previous_league_id="A"
    )
    assert prepared_player_frame.FRAME_KEY in state
    assert state[prepared_player_frame.SIGNATURE_KEY] == "sig"
    assert prepared_player_frame.SHELL_BUNDLE_KEY not in state
    assert prepared_player_frame.SHARED_CONTEXT_KEY in state
    assert "frame|shell|A|1|score|settings|0|1|1|1|1|1" in state[
        prepared_player_frame.SHARED_CONTEXT_KEY
    ]
    assert not state.get(trade_hub_first_useful.PRESENTATION_CACHE_KEY)


def test_scoring_format_change_still_misses_frame_via_signature():
    state: dict = {}
    calls = {"n": 0}

    def builder():
        calls["n"] += 1
        return pd.DataFrame({"player_id": [str(calls["n"])], "dynasty_score": [1]})

    sig_ppr = prepared_player_frame.build_frame_signature(
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
    sig_half = prepared_player_frame.build_frame_signature(
        public_fingerprint="pub",
        valuation_lens="Dynasty",
        score_field="dynasty_score",
        league_settings_key="settings",
        scoring_format="Half-PPR",
        scoring_supported=True,
        archetype_id="balanced",
        season="2025",
        row_count=1,
    )
    prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=sig_ppr, builder=builder
    )
    prepared_player_frame.clear_league_scoped_prepared_memos(state, previous_league_id="A")
    prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=sig_half, builder=builder
    )
    assert calls["n"] == 2


def test_account_logout_still_clears_valued_frame():
    state = {
        prepared_player_frame.FRAME_KEY: pd.DataFrame({"player_id": ["1"]}),
        prepared_player_frame.SIGNATURE_KEY: "sig",
        prepared_player_frame.SHELL_BUNDLE_KEY: {"x": 1},
        trade_hub_first_useful.PRESENTATION_CACHE_KEY: {"k": {}},
    }
    session_integrity.clear_account_bound_transient_state(state)
    assert prepared_player_frame.FRAME_KEY not in state
    assert trade_hub_first_useful.PRESENTATION_CACHE_KEY not in state


def test_trade_hub_memo_isolated_across_leagues():
    state: dict = {}
    trade_hub_first_useful.get_or_build_presentation_board(
        state,
        signature="board|A",
        builder=lambda: {"eligible_ideas": [{"tag": "A1"}], "league": "A"},
    )
    prepared_player_frame.clear_league_scoped_prepared_memos(
        state, previous_league_id="A"
    )
    assert not state.get(trade_hub_first_useful.PRESENTATION_CACHE_KEY)
    board, hit = trade_hub_first_useful.get_or_build_presentation_board(
        state,
        signature="board|B",
        builder=lambda: {"eligible_ideas": [{"tag": "B1"}], "league": "B"},
    )
    assert hit is False
    assert board["eligible_ideas"][0]["tag"] == "B1"


def test_no_football_modules_touched():
    """League-switch presentation PRs must not touch Trust engines.

    Valuation calibration audits may intentionally edit rankings / trade_ideas.
    """
    diff_names = {
        line.strip()
        for line in __import__("subprocess")
        .run(
            ["git", "diff", "--name-only", "origin/main"],
            capture_output=True,
            text=True,
            check=True,
        )
        .stdout.splitlines()
        if line.strip()
    }
    forbidden = {
        "modules/trust_engine.py",
        "modules/trust_enforcement.py",
    }
    assert not diff_names.intersection(forbidden)

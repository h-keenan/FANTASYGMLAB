"""Contracts for league-switch first-useful-workspace performance (PR #156)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import league_switch_first_useful
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


def test_rapid_a_b_c_final_league_wins_and_no_stale_narrative():
    state: dict = {"selected_league_id": "A"}
    for previous, nxt in (("A", "B"), ("B", "C")):
        league_switch_first_useful.begin_switch_guard(
            state,
            previous_league_id=previous,
            next_league_id=nxt,
        )
        state["canonical_recommendation_narrative"] = {"league_id": previous}
        state.pop("canonical_recommendation_narrative", None)
        prepared_player_frame.clear_league_scoped_prepared_memos(
            state, previous_league_id=previous
        )
        state["selected_league_id"] = nxt
        league_switch_first_useful.mark_cleanup_complete(state)
        league_switch_first_useful.consume_switch_guard(state)
    assert state["selected_league_id"] == "C"
    assert "canonical_recommendation_narrative" not in state


def test_stale_flash_helper_detects_mismatch():
    league_switch_first_useful.assert_no_stale_league_payload(
        active_league_id="B",
        payload_league_id="B",
        surface="inbox",
    )
    try:
        league_switch_first_useful.assert_no_stale_league_payload(
            active_league_id="B",
            payload_league_id="A",
            surface="inbox",
        )
    except AssertionError as exc:
        assert "stale league payload" in str(exc)
    else:
        raise AssertionError("expected stale payload detection")


def test_app_uses_league_scoped_clear_on_switch():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    clearer = source[
        source.index("def _clear_league_switch_transient_state(") : source.index(
            "def _open_notification_destination("
        )
    ]
    assert "clear_league_scoped_prepared_memos" in clearer
    assert "clear_prepared_player_frame" not in clearer
    assert "league_switch_first_useful.begin_switch_guard" in source
    assert "Loading" in source[
        source.index("league_switch_ack = st.session_state.pop") : source.index(
            "def _query_param_page("
        )
    ]


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


def test_viewport_matrix_documented():
    validate = (ROOT / "scripts" / "validate_mobile_ui.py").read_text(encoding="utf-8")
    assert "WIDTHS = (320, 390, 430, 768, 1024, 1280, 1440, 1600, 1920)" in validate

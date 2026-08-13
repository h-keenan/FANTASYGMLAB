"""Post-dismiss football hydration + widget-state ownership (#217)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import canonical_player_ranking as ranking
from modules import prepared_player_frame


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_loading_dismissed_still_before_players_and_prepared():
    main = APP.index("def main():")
    dismiss = APP.index('"loading_dismissed"', main)
    players = APP.index('"players_ready"', main)
    prepared = APP.index('"prepared_frame_ready"', main)
    football = APP.index('"football_context_ready"', prepared)
    assert dismiss < players < prepared < football
    assert '"game_plan_first_useful"' in APP


def test_auth_save_flush_is_after_football_not_at_dismiss():
    # Use the post-PAGE_READY usable paint (not early guest launch).
    page_ready = APP.index("StartupPhase.PAGE_READY")
    dismiss = APP.index('runtime_trace.mark("first_usable_paint")', page_ready)
    deferred = APP.index("POST_USABLE_SAVE_AFTER_FOOTBALL_KEY", dismiss)
    football = APP.index('"football_context_ready"', deferred)
    flush = APP.index('"post_usable_auth_save_flushed"', football)
    assert "st.rerun()" not in APP[dismiss:deferred + 200]
    assert football < flush
    assert "flush_durable_auth_persistence" in APP[flush - 500 : flush + 200]
    assert "st.rerun()" not in APP[flush - 300 : flush + 400]


def test_valued_shell_deferred_on_dashboard_until_after_game_plan_route():
    assert "defer_valued_shell_for_game_plan" in APP
    enrich_def = APP.index("def _enrich_valued_shell_chrome()")
    football = APP.index('"football_context_ready"', enrich_def)
    dashboard_call = APP.index("render_home_dashboard(", football)
    post_dashboard_enrich = APP.index(
        "if defer_valued_shell_for_game_plan:",
        dashboard_call,
    )
    assert enrich_def < football < dashboard_call < post_dashboard_enrich


def test_game_plan_first_useful_milestone_at_dashboard_useful_marker():
    useful = APP.index('data-fgl-dashboard-useful="1"')
    milestone = APP.index('"game_plan_first_useful"', useful - 50)
    assert abs(milestone - useful) < 1600


def test_trade_hub_target_selectbox_uses_session_state_without_index():
    start = APP.index('target_selectbox_key = f"player_trade_hub_target_player_')
    block = APP[start : start + 700]
    assert "st.session_state[target_selectbox_key]" in block
    assert "index=default_target_index" not in block
    assert "key=target_selectbox_key" in block


def test_return_explorer_and_team_select_omit_conflicting_index():
    explorer = APP.split("def render_trade_return_explorer")[1][:2500]
    assert "index=default_index" not in explorer
    team_block_start = APP.index('team_select_key = f"league_team_select_')
    team_block = APP[team_block_start : team_block_start + 2000]
    assert "index=default_idx" not in team_block
    assert "key=team_select_key" in team_block


def test_league_switch_clears_player_trade_hub_target_keys():
    start = APP.index("def _clear_league_namespaced_trade_hub_focus")
    body = APP[start : start + 500]
    assert "player_trade_hub_target_player_" in body
    assert "player_trade_hub_mode_" in body


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

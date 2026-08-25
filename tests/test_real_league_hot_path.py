"""Real-league Dashboard and Trade Hub modal hot-path contracts."""

from pathlib import Path

import pandas as pd

from modules import hot_path_profile
from modules import prepared_player_frame
from modules.navigation_state import resolve_resume_destination


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_hot_path_profile_ranks_top_spans_with_percentages():
    hot_path_profile.begin("fixture")
    hot_path_profile.record("slow", 800.0, cache_status="miss")
    hot_path_profile.record("fast", 200.0, cache_status="hit")
    payload = hot_path_profile.report(top_n=10)
    assert payload["span_sum_ms"] == 1000.0
    assert payload["top"][0]["name"] == "slow"
    assert "unaccounted_ms" in payload
    assert "python_complete_ms" in payload
    assert payload["top"][0]["pct_of_wall"] > 0
    assert payload["top"][1]["name"] == "fast"


def test_warm_rerun_reuses_session_valued_frame_without_disk_hydrate():
    state: dict = {}
    frame = pd.DataFrame({"player_id": ["1", "2"], "dynasty_score": [1.0, 2.0]})
    signature = prepared_player_frame.build_frame_signature(
        public_fingerprint="pub",
        valuation_lens="Dynasty",
        score_field="dynasty_score",
        league_settings_key="settings",
        scoring_format="PPR",
        scoring_supported=True,
        archetype_id="balanced",
        season="2026",
        row_count=2,
    )
    prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=signature, builder=lambda: frame.copy()
    )
    cached, cached_sig = prepared_player_frame.session_valued_ranked_frame(state)
    assert cached is not None
    assert cached_sig == signature
    hydrate = APP.split("# --- Football hydration", 1)[1][:8000]
    assert "session_valued_ranked_frame" in hydrate
    assert "reuse_prepared_without_disk" in hydrate
    assert "frame_signature_prefix" in hydrate
    assert "signature_matches_prefix" in hydrate
    assert 'cache_status"] = "session_reuse"' in hydrate
    assert "process_valued_frame_for_inputs" in hydrate
    assert 'cache_status"] = "process_hit"' in hydrate
    assert "cached_valued_sig" in hydrate


def test_what_changed_is_gated_after_game_plan():
    block = APP.split("def _render_what_changed()", 1)[1][:900]
    assert "See what changed" in block
    assert "Since your last check-in" in block
    assert "render_deferred_section_gate" in block
    assert "Game Plan stays first" in block


def test_trade_dialog_skips_unrelated_shell_work():
    enrich = APP.split("defer_valued_shell_for_game_plan =", 1)[1][:500]
    assert "_trade_dialog_open" in enrich
    refresh = APP.split("maybe_refresh_players_after_shell(", 1)[0][-500:]
    assert "dg_trade_detail_active" in refresh


def test_resume_route_still_prefers_trade_hub_over_league_hydrate():
    allowed = {"dashboard", "trade_hub"}
    assert (
        resolve_resume_destination(
            pending_page="dashboard",
            pending_source="league_selection",
            query_page="trade_hub",
            session_page="",
            allowed=allowed,
        )
        == "trade_hub"
    )


def test_share_png_still_waits_for_share_active():
    ui = (ROOT / "modules/share_recommendation_ui.py").read_text(encoding="utf-8")
    detail = (ROOT / "modules/trade_hub_ui.py").read_text(encoding="utf-8")
    assert "share_active" in ui
    assert "render_share_card_png" in ui
    assert "render_share_card_png" not in detail


def test_roster_digest_reuses_session_map_before_sleeper_fetch():
    digest = APP.split("def _rostered_universe_digest(", 1)[1][:1600]
    assert "_session_roster_player_map" in digest
    assert "session_reuse" in digest
    assert "get_rosters(league_id)" in digest


def test_trade_dialog_skips_live_draft_and_startup_context_lookup():
    discovery = APP.split("def _maybe_refresh_live_draft_discovery()", 1)[1][:400]
    assert "if _trade_dialog_open:" in discovery
    startup = APP.split("reuse_startup_context = bool(", 1)[1][:900]
    assert "_trade_dialog_open" in startup
    assert "session_reuse" in startup


def test_modal_open_does_not_add_timed_fragment():
    assert "@st.fragment" in APP
    assert "run_every=" not in APP.split("def _trade_hub_visible_feed()", 1)[1][:800]
    workflow = (ROOT / "modules/dashboard_workflow.py").read_text(encoding="utf-8")
    assert "run_every=" not in workflow


def test_no_timed_fragment_reintroduced_for_dashboard_or_modal():
    workflow = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
    assert "run_every=" not in workflow
    assert "@st.fragment" not in workflow
    assert "opacity: 1 !important" not in APP

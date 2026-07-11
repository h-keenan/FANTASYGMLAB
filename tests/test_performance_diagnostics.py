from pathlib import Path
from unittest.mock import patch

import app
from modules import performance, sleeper


def test_performance_debug_flag_is_opt_in():
    assert not performance.debug_enabled(environ={})
    assert performance.debug_enabled(environ={"DYNASTYGM_DEBUG_PERF": "true"})
    assert performance.debug_enabled(environ={"DYNASTYGM_DEBUG_PERF": "1"})


def test_performance_labels_redact_sensitive_words():
    entry = performance.record_timing("token refresh for user@example.com", 12.34, category="secret")
    assert entry["label"] == "[redacted]"
    assert entry["category"] == "[redacted]"
    assert "user@example.com" not in str(entry)
    assert "token" not in str(entry).casefold()


def test_performance_diagnostics_do_not_include_secret_values():
    with patch.object(performance, "session_timings", return_value=[{"label": "[redacted]", "elapsed_ms": 7.0}]):
        diagnostics = performance.redacted_diagnostics()
    text = str(diagnostics)
    assert "sk_test_" not in text
    assert "whsec_" not in text
    assert "SUPABASE_ANON_KEY" not in text
    assert "access_token" not in text


def test_sleeper_api_calls_are_timed_without_ids_in_labels():
    source = Path("modules/sleeper.py").read_text(encoding="utf-8")
    for label in (
        "sleeper_league",
        "sleeper_league_rosters",
        "sleeper_league_users",
        "sleeper_draft_picks",
        "sleeper_players_fetch",
    ):
        assert label in source
    assert "_request_json(" in source
    assert "performance.time_block(label, category=\"sleeper\")" in source


def test_cached_public_data_load_has_single_entry_point():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "public_player_data_load" in source
    assert "ensure_players()" in source
    assert "build_players_table(DB_PATH, refresh=True)" in source
    assert "load_players(DB_PATH)" in source


def test_gm_feedback_and_quick_view_do_not_call_heavy_builders_directly():
    source = Path("app.py").read_text(encoding="utf-8")
    gm_start = source.index("def render_mobile_navigation_shell")
    gm_end = source.index("def _render_premium_entitlement_diagnostics")
    feedback_start = source.index("def render_global_feedback_entry")
    feedback_end = source.index("free_agent_priority_badge =")
    gm_source = source[gm_start:gm_end]
    feedback_source = source[feedback_start:feedback_end]
    quick_view_start = source.index("def render_player_quick_view_modal")
    quick_view_end = source.index("def render_team_identity_card")
    quick_view_source = source[quick_view_start:quick_view_end]

    for heavy_call in ("build_trade_ideas(", "build_league_summary(", "cached_trade_ideas("):
        assert heavy_call not in gm_source
        assert heavy_call not in feedback_source
        assert heavy_call not in quick_view_source


def test_app_records_route_level_and_expensive_builder_timings():
    source = Path("app.py").read_text(encoding="utf-8")
    for label in (
        "app_rerun_total_",
        "shared_league_context_generation",
        "trade_hub_board_generation",
        "my_team_advice_generation",
        "player_quick_view_render",
        "draft_pick_assets_generation",
    ):
        assert label in source


def test_live_draft_polling_has_isolated_timing():
    source = Path("modules/live_draft.py").read_text(encoding="utf-8")
    assert "live_draft_poll_picks" in source
    assert "performance.time_block" in source

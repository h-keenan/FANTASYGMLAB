"""Architectural contracts for startup critical-path ordering."""

from pathlib import Path

from modules import startup_coordinator


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_shell_chrome_bundle_does_not_call_team_direction_on_critical_path():
    start = APP.index("def _build_shell_chrome_bundle()")
    end = APP.index("identity_shell_signature = (", start)
    bundle = APP[start:end]
    assert "cached_team_direction_summary(" not in bundle
    assert "get_shell_league_context()" in bundle


def test_identity_shell_bundle_skips_league_summary():
    start = APP.index("def _build_identity_shell_chrome_bundle()")
    end = APP.index("def _build_shell_chrome_bundle()", start)
    bundle = APP[start:end]
    assert "get_shell_league_context()" not in bundle
    assert "cached_league_summary(" not in bundle
    assert "get_roster_profile(" in bundle


def test_shell_context_uses_league_summary_not_direction_or_core_fallback():
    start = APP.index("def cached_league_shell_context(")
    end = APP.index("def cached_league_context(", start)
    body = APP[start:end]
    assert "cached_league_summary(" in body
    assert "cached_team_direction_summary(" not in body
    assert "cached_league_intelligence_frame(" not in body


def test_secondary_sidebar_work_is_gated_behind_startup_complete():
    assert "League scoring overrides" in APP
    sidebar = APP.split("# SIDEBAR", 1)[1].split(
        "league_value_settings = st.session_state.get(",
        1,
    )[0]
    active_gate = sidebar.index("if startup.active:")
    news = sidebar.index("Global News")
    assert active_gate < news


def test_gap_milestones_dismiss_before_heavy_football_work():
    labels = startup_coordinator.STARTUP_MILESTONE_LABELS
    for key in (
        "shell_chrome_ready",
        "workspace_chrome_ready",
        "loading_dismissed",
        "players_ready",
        "prepared_frame_ready",
        "football_context_ready",
    ):
        assert key in labels
    main = APP.index("def main():")
    league = APP.index('"league_restored"', main)
    shell = APP.index('"shell_chrome_ready"', main)
    chrome = APP.index('"workspace_chrome_ready"', main)
    dismiss = APP.index('"loading_dismissed"', main)
    players = APP.index('"players_ready"', main)
    frame = APP.index('"prepared_frame_ready"', main)
    assert league < shell < chrome < dismiss < players < frame


def test_first_usable_still_precedes_dashboard_and_live_draft():
    page_ready = APP.index("StartupPhase.PAGE_READY")
    first_usable = APP.index('runtime_trace.mark("first_usable_paint")', page_ready)
    dashboard = APP.index('if current_page == "dashboard":', page_ready)
    live_draft = APP.index('time_block("live_draft_discovery"', page_ready)
    assert first_usable < dashboard
    assert first_usable < live_draft


def test_decision_memory_and_gm_targets_do_not_own_loading_dismissal():
    dismiss = APP.index('runtime_trace.mark("first_usable_paint")')
    dashboard_call = APP.index("render_home_dashboard(", dismiss)
    dm_route = APP.index('if current_page == "gm_targets":', dismiss)
    assert dismiss < dashboard_call < dm_route
    dashboard_fn = APP[
        APP.index("def render_home_dashboard(") : APP.index("STARTUP_DRAFT_STRATEGIES")
    ]
    assert "decision_memory.dashboard_recent_events" in dashboard_fn or "decision_change_history" in dashboard_fn


def test_ensure_players_prefers_persisted_baseline():
    start = APP.index("def ensure_players(")
    end = APP.index("def cached_sleeper_player_directory(", start)
    body = APP[start:end]
    assert "ensure_players_for_startup" in body
    assert "allow_network_refresh" in body

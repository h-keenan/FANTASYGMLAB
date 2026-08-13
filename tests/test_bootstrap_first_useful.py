"""Bootstrap first-useful contracts: server timing markers + deferred secondary."""

from __future__ import annotations

from pathlib import Path

from modules import dashboard_workflow


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
LOADING = (ROOT / "modules" / "dashboard_loading_state.py").read_text(encoding="utf-8")


def test_useful_marker_exposes_server_hydrate_and_cache_timings():
    assert 'data-fgl-dashboard-useful="1"' in APP
    assert "data-fgl-gp-cache=" in APP
    assert "data-fgl-hydrate-to-useful-ms=" in APP
    assert "data-fgl-dashboard-ms=" in APP
    assert "_dashboard_hydrate_started_mono" in LOADING


def test_post_useful_sections_are_deferred_via_fragment():
    assert "POST_USEFUL_MOUNTED_KEY" in WORKFLOW
    assert "@st.fragment(run_every=timedelta(milliseconds=250))" in WORKFLOW
    game_plan = WORKFLOW.index("render_todays_game_plan()")
    fragment = WORKFLOW.index("_deferred_post_useful_sections")
    what_changed = WORKFLOW.index("render_what_changed()")
    assert game_plan < fragment
    assert game_plan < what_changed
    deferred = WORKFLOW[WORKFLOW.index("def _deferred_post_useful_sections") :]
    assert "return" in deferred[:400]


def test_hydrate_clears_deferred_secondary_flags():
    begin = LOADING[LOADING.index("def begin_hydrate") : LOADING.index("def bind_placeholder_slot")]
    assert 'pop("_dashboard_secondary_mounted"' in begin
    assert dashboard_workflow.POST_USEFUL_MOUNTED_KEY == "_dashboard_secondary_mounted"


def test_refresh_still_scheduled_after_dashboard_first_useful():
    football = APP.index('"football_context_ready"')
    dashboard = APP.index("render_home_dashboard(", football)
    refresh = APP.index("maybe_refresh_players_after_shell(", dashboard)
    assert football < dashboard < refresh
    assert "background=True" in APP[refresh : refresh + 400]

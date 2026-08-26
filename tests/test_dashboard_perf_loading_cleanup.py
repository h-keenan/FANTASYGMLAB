"""Dashboard performance + loading-state ownership contracts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules import dashboard_loading_state as dls
from modules import app_styles


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_first_useful_contract_documented():
    src = (ROOT / "modules" / "dashboard_loading_state.py").read_text(encoding="utf-8")
    assert "First useful Dashboard contract" in src
    assert "Today's Game Plan" in src
    assert "Deep Analysis" in src
    assert "clear context-sensitive" in src.casefold() or "Clear-then-hydrate" in src or "option B" in src


def test_should_clear_on_league_switch_and_league_mismatch():
    state = {dls.LAST_USEFUL_LEAGUE_KEY: "league-a"}
    assert dls.should_clear_stale_dashboard(state, league_id="league-b") is True
    state["_league_switch_ack"] = {"phase": "loading"}
    assert dls.should_clear_stale_dashboard(state, league_id="league-a") is True
    warm = {
        dls.LAST_USEFUL_LEAGUE_KEY: "league-a",
        "_game_plan_package_signature": "sig",
    }
    assert dls.should_clear_stale_dashboard(warm, league_id="league-a") is False


def test_hydrate_placeholder_clears_from_bound_slot_on_useful():
    state: dict = {"_league_switch_first_useful_guard": {"to": "b"}}
    slot = MagicMock()
    dls.bind_placeholder_slot(slot)
    assert dls.begin_hydrate(state, league_id="league-b", league_name="League B") is True
    dls.render_hydrate_placeholder(state, league_name="League B")
    assert slot.markdown.call_count == 1
    dls.mark_first_useful(state, league_id="league-b")
    assert slot.markdown.call_count == 2
    idle_html = slot.markdown.call_args.args[0]
    assert "data-fgl-hydrate-slot='idle'" in idle_html
    slot.empty.assert_not_called()
    dls.bind_placeholder_slot(None)


def test_begin_hydrate_and_placeholder_render():
    state: dict = {"_league_switch_first_useful_guard": {"to": "b"}}
    assert dls.begin_hydrate(state, league_id="league-b", league_name="League B") is True
    assert dls.current_phase(state) == dls.PHASE_HYDRATING
    with patch.object(dls.st, "markdown") as markdown:
        dls.render_hydrate_placeholder(state, league_name="League B")
        dls.render_hydrate_placeholder(state, league_name="League B")
    assert markdown.call_count == 1
    html = markdown.call_args.args[0]
    assert "data-fgl-dashboard-hydrating" in html
    assert "dashboard-hydrate-skeleton" in html
    assert "League B" in html
    assert "Your Game Plan" in html
    assert "Building the Game Plan" in html
    switch_state = {
        "_league_switch_first_useful_guard": {"to": "b"},
        dls.LAST_USEFUL_LEAGUE_KEY: "league-a",
    }
    assert dls.begin_hydrate(switch_state, league_id="league-b", league_name="League B") is True
    switch_state.pop(dls.PLACEHOLDER_RENDERED_KEY, None)
    with patch.object(dls.st, "markdown") as switch_md:
        dls.render_hydrate_placeholder(switch_state, league_name="League B")
    switch_html = switch_md.call_args.args[0]
    assert "Prior recommendations are cleared" in switch_html
    assert "Updating Dashboard" in switch_html


def test_mark_first_useful_sets_phase_and_fingerprint():
    state: dict = {dls.PHASE_KEY: dls.PHASE_HYDRATING}
    dls.mark_first_useful(
        state,
        league_id="league-a",
        content_fp=dls.content_fingerprint(
            league_id="league-a",
            prepared_frame_signature="frame-1",
            score_field="value_score",
        ),
    )
    assert dls.current_phase(state) == dls.PHASE_USEFUL
    assert state[dls.LAST_USEFUL_LEAGUE_KEY] == "league-a"
    assert "league-a" in state[dls.LAST_USEFUL_FP_KEY]
    opening = {dls.PHASE_KEY: dls.PHASE_HYDRATING, "_opening_selected_league": True}
    dls.mark_first_useful(opening, league_id="league-a")
    assert "_opening_selected_league" not in opening


def test_app_wires_hydrate_before_football_and_prefs_after_useful():
    assert "dashboard_loading_state" in APP
    assert "begin_hydrate" in APP
    assert "bind_placeholder_slot(st.empty())" in APP
    assert "render_hydrate_placeholder" in APP
    assert "collapse_placeholder_slot()" in APP
    # Prefs deferred after first useful, not before Game Plan fingerprint work.
    prefs_block = APP.split("Orientation preferences hydrate AFTER Game Plan", 1)[1][:800]
    assert "refresh_authenticated_preferences" not in prefs_block
    useful_block = APP.split("mark_first_useful(", 1)[1].split(
        "def _render_guest_continuity", 1
    )[0]
    assert "refresh_authenticated_preferences" in useful_block


def test_hydrate_css_not_in_app_css():
    styles = (ROOT / "modules" / "dashboard_workflow_styles.py").read_text(encoding="utf-8")
    assert "dashboard-hydrate-placeholder" in styles
    assert "dashboard-hydrate-placeholder" not in app_styles.APP_CSS


def test_no_new_blanket_overlay_or_sleep():
    src = (ROOT / "modules" / "dashboard_loading_state.py").read_text(encoding="utf-8")
    assert "sleep(" not in src
    assert "dg-startup-shell" not in src
    # Policy is clear-then-hydrate, not cosmetic opacity override of Streamlit stale.
    assert "opacity: 1 !important" not in src
    assert ".element-container" not in src


def test_prepared_frame_still_skipped_without_league():
    hydrate = APP.split("# --- Football hydration", 1)[1].split(
        "# Enrich strategy/ranks after prepared frame", 1
    )[0]
    assert 'prepared_frame_signature = "guest_no_league"' in hydrate
    assert "if not selected_league_id:" in hydrate

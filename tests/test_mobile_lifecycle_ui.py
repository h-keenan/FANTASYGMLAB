"""POST-318 mobile lifecycle / render-ownership contracts."""

from __future__ import annotations

from pathlib import Path

from modules import lifecycle_render_trace
from modules import render_ownership
from modules import route_render_ownership
from modules import startup_coordinator
from modules import trade_hub_first_useful
from modules.ui_primitives import AUTO_STRATEGY_HELP_TITLE


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
TRADE_HUB = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
OVERLAY = (ROOT / "modules" / "mobile_interaction_overlay_styles.py").read_text(
    encoding="utf-8"
)
WORKFLOW = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
LOADING = (ROOT / "modules" / "dashboard_loading_state.py").read_text(encoding="utf-8")


def test_trade_strategy_selector_has_one_app_owner():
    hub = APP[APP.index('if current_page == "trade_hub"') : APP.index("# TRADE ANALYZER")]
    assert hub.count("render_trade_strategy_selector(") == 1
    selector = TRADE_HUB.split("def render_trade_strategy_selector", 1)[1].split(
        "\ndef ", 1
    )[0]
    assert selector.count("render_auto_strategy_help(") == 1
    assert AUTO_STRATEGY_HELP_TITLE == "What is Auto?"


def test_what_is_auto_is_claimed_once_per_run():
    primitives = (ROOT / "modules" / "ui_primitives.py").read_text(encoding="utf-8")
    assert "OWNER_WHAT_IS_AUTO" in primitives
    state: dict = {}
    render_ownership.begin_script_run(state)
    assert render_ownership.claim(state, render_ownership.OWNER_WHAT_IS_AUTO) is True
    assert render_ownership.claim(state, render_ownership.OWNER_WHAT_IS_AUTO) is False
    assert render_ownership.count(state, render_ownership.OWNER_WHAT_IS_AUTO) == 2


def test_trade_hub_board_loading_has_one_caption_owner_without_spinner():
    hub = APP[APP.index("def render_top_trade_opportunities()") : APP.index(
        "def render_search_around_player()"
    )]
    assert hub.count("LOADING_TRADE_IDEAS") == 1
    assert "Building the trade board" not in hub
    assert "st.spinner(" not in hub
    assert "OWNER_TRADE_HUB_LOADING" in hub
    assert "presentation_board_cached(" in hub


def test_build_trade_ideas_is_not_invoked_from_route_chrome():
    restore = APP.split("runtime_trace.mark(\"route_restore_complete\")", 1)[1][:2500]
    assert "cached_trade_ideas(" not in restore
    assert "_sync_platform_query_page(" in APP
    assert "_sync_platform_query_page(page_key)" in APP.split(
        "def _commit_platform_destination", 1
    )[1][:800]


def test_dashboard_hero_has_one_canonical_owner():
    briefing = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    assert briefing.count('render_section_header("Today\'s Game Plan"') == 1
    assert "OWNER_DASHBOARD_HERO" in briefing
    assert "_refresh_row" in briefing
    assert "width:100%!important" not in briefing.replace(" ", "")


def test_warm_navigation_skips_full_bootstrap_loader_when_session_complete():
    state = {startup_coordinator.STARTUP_COMPLETE_KEY: True, "selected_league_id": "L1"}
    assert startup_coordinator.session_has_usable_bootstrap_prerequisites(state) is True
    coordinator = startup_coordinator.StartupCoordinator.begin(state)
    assert coordinator.active is False


def test_trade_dialog_flag_does_not_reset_startup_complete():
    assert "reset_startup_coordinator" not in APP.split(
        "dg_trade_detail_active", 1
    )[0][-400:]
    assert "STARTUP_COMPLETE_KEY" in APP
    hub = APP[APP.index('if current_page == "trade_hub"') : APP.index("# TRADE ANALYZER")]
    assert "reset_startup_coordinator" not in hub


def test_secondary_player_search_entry_point_is_unique():
    hub = APP[APP.index('if current_page == "trade_hub"') : APP.index("# TRADE ANALYZER")]
    assert hub.count("Search Around a Player") == 2  # expander + section header
    assert "Search return paths from one of your players" not in hub
    assert "OWNER_SECONDARY_SEARCH" in hub
    assert "FIND_BUTTON_LABEL" in (ROOT / "modules" / "trade_hub_player_search.py").read_text(
        encoding="utf-8"
    )


def test_orb_safe_area_clearance_is_owned_by_overlay():
    assert "--dg-mobile-shell-clearance" in OVERLAY
    assert "padding-block-end: var(--dg-mobile-shell-clearance)" in OVERLAY
    assert '[data-testid="stMain"]' in OVERLAY
    assert "bottom: var(--dg-mobile-shell-clearance)" in OVERLAY
    assert "scroll-padding-bottom: var(--space-md)" in OVERLAY
    assert "st-key-mobile_gm_sheet_trigger_" in OVERLAY


def test_no_new_timed_fragment_or_stale_overlay():
    assert "@st.fragment" not in WORKFLOW
    assert "run_every=" not in WORKFLOW
    begin = LOADING[LOADING.index("def begin_hydrate") : LOADING.index("def bind_placeholder_slot")]
    assert "True" not in begin.split("_dashboard_defer_secondary_once")[1][:80]
    assert "route_render_ownership" in APP
    assert "enter_after_chrome(" in APP


def test_lifecycle_phases_are_monotonic_and_once():
    state: dict = {}
    lifecycle_render_trace.begin(state)
    lifecycle_render_trace.mark(state, "T1_auth_session_complete")
    first = lifecycle_render_trace.mark(state, "T1_auth_session_complete")
    second = lifecycle_render_trace.mark(state, "T2_route_resolved")
    assert first == lifecycle_render_trace.snapshot(state)["T1_auth_session_complete"]
    assert second >= first
    for phase in lifecycle_render_trace.PHASES:
        assert f'"{phase}"' in (ROOT / "modules" / "lifecycle_render_trace.py").read_text(
            encoding="utf-8"
        )


def test_presentation_board_peek_does_not_count_as_hit():
    state: dict = {}
    assert (
        trade_hub_first_useful.presentation_board_cached(state, signature="sig")
        is False
    )
    trade_hub_first_useful.get_or_build_presentation_board(
        state, signature="sig", builder=lambda: {"eligible_ideas": []}
    )
    assert trade_hub_first_useful.presentation_board_cached(state, signature="sig") is True


def test_route_body_owner_clears_on_change():
    class _Slot:
        def __init__(self) -> None:
            self.emptied = 0

        def empty(self) -> None:
            self.emptied += 1

        def container(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    state = {route_render_ownership.LAST_ROUTE_KEY: "dashboard"}
    slot = _Slot()
    route_render_ownership.enter_after_chrome(state, "trade_hub", slot=slot)
    assert slot.emptied == 1
    assert route_render_ownership.route_changed_this_run(state) is True
    route_render_ownership.exit_route_body(state)


def test_explicit_rerun_inventory_not_increased_by_lifecycle_pass():
    from scripts.measure_interaction_rerun_architecture import count_explicit_reruns

    assert count_explicit_reruns() <= 58

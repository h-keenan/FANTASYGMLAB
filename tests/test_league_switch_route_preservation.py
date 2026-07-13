from pathlib import Path

from modules.navigation_state import preserved_league_switch_destination


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_league_switch_preserves_all_supported_destinations():
    destinations = (
        "dashboard",
        "my_team",
        "rankings",
        "trade_hub",
        "waivers",
        "startup_draft_center",
        "live_draft",
        "premium",
        "about_disclaimer",
        "terms",
        "privacy",
        "no_affiliation",
        "settings",
        "feedback",
        "account",
    )
    for destination in destinations:
        assert preserved_league_switch_destination(destination) == destination


def test_session_and_query_routes_are_preserved_when_callback_page_is_missing():
    assert preserved_league_switch_destination(session_page="trade_hub") == "trade_hub"
    assert preserved_league_switch_destination(query_page="waivers") == "waivers"


def test_only_missing_route_falls_back_to_dashboard():
    assert preserved_league_switch_destination() == "dashboard"
    assert preserved_league_switch_destination("  ", session_page=None, query_page="") == "dashboard"


def test_switch_callback_removes_forced_dashboard_allowlist_and_restores_route():
    app = source("app.py")
    section = app.split("def _switch_to_saved_league", 1)[1].split(
        "def render_header_league_switcher", 1
    )[0]
    assert "preserved_league_switch_destination" in section
    assert "route_to_dashboard=False" in section
    assert "current_page not in" not in section
    assert 'st.session_state["platform_nav_page"] = preserved_page' in section
    assert 'st.session_state["_pending_platform_route"] = preserved_page' in section
    assert 'st.query_params["page"] = preserved_page' in section


def test_switch_clears_cross_league_transient_state_and_closes_sheet():
    app = source("app.py")
    section = app.split("def _switch_to_saved_league", 1)[1].split(
        "def render_header_league_switcher", 1
    )[0]
    assert "_clear_league_switch_transient_state()" in section
    assert 'st.session_state["_mobile_destination_sheet_open"] = False' in app
    assert 'st.session_state["_league_actions_epoch"]' in section
    assert "_clear_player_quick_view()" in app


def test_live_draft_route_keeps_existing_no_active_draft_state():
    assert preserved_league_switch_destination("live_draft") == "live_draft"
    live_ui = source("modules/live_draft_ui.py")
    assert "No Sleeper drafts were found for this league yet." in live_ui


def test_startup_draft_center_route_is_preserved_for_router_normalization():
    assert (
        preserved_league_switch_destination("startup_draft_center")
        == "startup_draft_center"
    )
    app = source("app.py")
    assert 'if startup_mode and normalized == "draft_summary"' in app
    assert 'if not startup_mode and normalized == "startup_draft_center"' in app


def test_query_parameter_tracks_preserved_destination_without_duplicate_navigation_write():
    app = source("app.py")
    section = app.split("def _switch_to_saved_league", 1)[1].split(
        "def render_header_league_switcher", 1
    )[0]
    assert section.count('st.query_params["page"] = preserved_page') == 1
    assert section.count('st.session_state["_pending_platform_route"] = preserved_page') == 1

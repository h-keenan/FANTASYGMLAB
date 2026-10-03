"""Non-Dashboard hydrate placeholders: shape-matched skeletons, not bare spinners.

`modules/dashboard_loading_state.py`'s clear-then-hydrate card used to be
hardcoded to `route == "dashboard"`. Several other surfaces (Trade Hub
search, Player Quick View's weekly-points chart, league-loading, player
news, acquisition search) previously showed a bare `st.spinner(...)` with no
reserved-height placeholder, causing a layout jump when real content of a
different height replaced the collapsed spinner. These tests cover the
generalized `begin_hydrate`/`render_hydrate_placeholder` routes and the
`hydrate_placeholder()` context manager built on top of them, plus that
app.py's known spinner sites were actually migrated.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules import dashboard_loading_state as dls


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_begin_hydrate_is_always_active_for_non_dashboard_routes():
    # Unlike Dashboard, non-Dashboard routes have no cross-rerun
    # "did context change" question -- callers only reach this from inside
    # a branch that is about to run a real blocking fetch.
    state: dict = {}
    assert dls.begin_hydrate(state, route=dls.ROUTE_TRADE_HUB_SEARCH) is True
    assert dls.begin_hydrate(state, route=dls.ROUTE_PLAYER_NEWS) is True
    # Dashboard's own phase bookkeeping must be untouched by a non-Dashboard call.
    assert dls.PHASE_KEY not in state


def test_render_hydrate_placeholder_uses_cards_shape_for_trade_hub_search():
    dls.bind_placeholder_slot(None, route=dls.ROUTE_TRADE_HUB_SEARCH)
    with patch.object(dls.st, "markdown") as markdown:
        dls.render_hydrate_placeholder(
            {},
            route=dls.ROUTE_TRADE_HUB_SEARCH,
            title="Searching realistic return packages...",
        )
    html = markdown.call_args.args[0]
    assert "dashboard-hydrate-placeholder--cards" in html
    assert "dashboard-hydrate-skeleton" in html
    assert html.count("dashboard-hydrate-skeleton-row") == 3
    assert "Searching realistic return packages..." in html


def test_render_hydrate_placeholder_uses_chart_shape_for_weekly_points():
    dls.bind_placeholder_slot(None, route=dls.ROUTE_PLAYER_QUICK_VIEW_WEEKLY_POINTS)
    with patch.object(dls.st, "markdown") as markdown:
        dls.render_hydrate_placeholder(
            {},
            route=dls.ROUTE_PLAYER_QUICK_VIEW_WEEKLY_POINTS,
            title="Loading 2025 weekly points…",
        )
    html = markdown.call_args.args[0]
    assert "dashboard-hydrate-placeholder--chart" in html
    assert html.count("dashboard-hydrate-skeleton-row") == 1


def test_render_hydrate_placeholder_uses_list_shape_for_league_loading_and_news():
    for route in (dls.ROUTE_LEAGUE_LOADING, dls.ROUTE_PLAYER_NEWS, dls.ROUTE_NFL_HEADLINES_FALLBACK):
        dls.bind_placeholder_slot(None, route=route)
        with patch.object(dls.st, "markdown") as markdown:
            dls.render_hydrate_placeholder({}, route=route, title="Loading...")
        html = markdown.call_args.args[0]
        assert "dashboard-hydrate-placeholder--list" in html
        assert html.count("dashboard-hydrate-skeleton-row") == 4


def test_render_hydrate_placeholder_unknown_route_falls_back_to_generic_shape():
    dls.bind_placeholder_slot(None, route="some_future_surface")
    with patch.object(dls.st, "markdown") as markdown:
        dls.render_hydrate_placeholder({}, route="some_future_surface", title="Loading...")
    html = markdown.call_args.args[0]
    assert "dashboard-hydrate-placeholder--generic" in html
    assert html.count("dashboard-hydrate-skeleton-row") == 1


def test_render_hydrate_placeholder_escapes_title_and_subtitle():
    hostile = "<img src=x onerror=alert(1)>"
    dls.bind_placeholder_slot(None, route=dls.ROUTE_PLAYER_NEWS)
    with patch.object(dls.st, "markdown") as markdown:
        dls.render_hydrate_placeholder(
            {}, route=dls.ROUTE_PLAYER_NEWS, title=hostile, subtitle=hostile
        )
    html = markdown.call_args.args[0]
    assert hostile not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html


def test_dashboard_route_rendering_is_unaffected_by_generalization():
    # route="dashboard" (the default) must still render the original
    # "Your Game Plan" card, not a shape-matched skeleton.
    state = {"_league_switch_first_useful_guard": {"to": "b"}}
    assert dls.begin_hydrate(state, league_id="league-b", league_name="League B") is True
    with patch.object(dls.st, "markdown") as markdown:
        dls.render_hydrate_placeholder(state, league_name="League B")
    html = markdown.call_args.args[0]
    assert "Your Game Plan" in html
    assert "dashboard-hydrate-placeholder--" not in html


def test_hydrate_placeholder_context_manager_binds_renders_and_clears():
    slot = MagicMock()
    with patch.object(dls.st, "empty", return_value=slot):
        with dls.hydrate_placeholder(
            dls.ROUTE_TRADE_HUB_SEARCH,
            title="Searching realistic return packages...",
            state={},
        ):
            slot.markdown.assert_called_once()
            html = slot.markdown.call_args.args[0]
            assert "dashboard-hydrate-placeholder--cards" in html
    slot.empty.assert_called_once()


def test_hydrate_placeholder_clears_even_when_body_raises():
    slot = MagicMock()
    with patch.object(dls.st, "empty", return_value=slot):
        try:
            with dls.hydrate_placeholder(dls.ROUTE_PLAYER_NEWS, state={}):
                raise RuntimeError("boom")
        except RuntimeError:
            pass
    slot.empty.assert_called_once()


def test_app_migrated_known_spinner_sites_to_hydrate_placeholder():
    assert 'with st.spinner("Searching realistic return packages..."):' not in APP
    assert 'with st.spinner(f"Loading {selected_season} weekly points…"):' not in APP
    assert "with st.spinner(product_copy.LOADING_LEAGUES):" not in APP
    assert 'with st.spinner("Loading player-specific news..."):' not in APP
    assert 'with st.spinner("Checking fallback NFL headlines..."):' not in APP
    assert 'with st.spinner("Searching acquisition paths..."):' not in APP

    assert APP.count("_dash_load.hydrate_placeholder(") >= 6
    assert "dashboard_loading_state.ROUTE_TRADE_HUB_SEARCH" in APP or "_dash_load.ROUTE_TRADE_HUB_SEARCH" in APP
    assert "_dash_load.ROUTE_TRADE_HUB_ACQUISITION_SEARCH" in APP
    assert "_dash_load.ROUTE_PLAYER_QUICK_VIEW_WEEKLY_POINTS" in APP
    assert "_dash_load.ROUTE_LEAGUE_LOADING" in APP
    assert "_dash_load.ROUTE_PLAYER_NEWS" in APP
    assert "_dash_load.ROUTE_NFL_HEADLINES_FALLBACK" in APP

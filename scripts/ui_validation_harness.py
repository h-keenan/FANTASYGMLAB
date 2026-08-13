"""Deterministic fixture-backed UI surfaces for CI browser validation.
Standings board fixture coverage is exercised on the league surface."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
while str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from modules import (
    application_shell,
    brand_identity,
    comparative_metrics,
    daily_gm_briefing,
    daily_gm_briefing_ui,
    decision_change_history,
    decision_change_history_ui,
    dashboard_orientation,
    dashboard_workflow,
    football_assets,
    league_workspace_ui,
    legal_pages,
    live_draft_ui,
    player_cards,
    player_history,
    player_quick_view,
    trade_hub_ui,
    ui_primitives,
    waivers_ui,
    workspace_ui,
    account_ui,
)
from modules.app_styles import APP_CSS
from modules.dashboard_workflow_styles import DASHBOARD_WORKFLOW_CSS
from modules.executive_command_header_styles import (
    COMMAND_COLUMN_WEIGHTS,
    EXECUTIVE_COMMAND_HEADER_CSS,
)
from modules.mobile_visual_polish_styles import MOBILE_VISUAL_POLISH_CSS
from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS
from modules.waivers_presentation_styles import WAIVERS_PRESENTATION_CSS
from modules.trade_analyzer_styles import TRADE_ANALYZER_CSS
from modules import trade_analyzer_builder
from modules.player_asset_explorer_styles import PLAYER_ASSET_EXPLORER_CSS
from modules.ux_polish_styles import FOUNDER_BETA_UX_CSS
from modules.html_rendering import inject_global_styles, render_html_fragment


SURFACES = {
    "dashboard",
    "league",
    "trade",
    "my-team",
    "waivers",
    "navigation",
    "live-draft",
    "player-dossier",
    "header-geometry",
    "design-system",
    "guest-landing",
    "trade-analyzer",
}

HEADER_LEAGUE_FIXTURES = {
    "short": "A",
    "normal": "12 Team SF",
    "long": "The Extremely Serious Dynasty Football League",
    "default": "Synthetic Founder Beta League",
}


def _fixture_notification_open(item) -> None:
    st.session_state["_fixture_notification_destination"] = _text(getattr(item, "href_hint", ""))
    st.session_state["_fixture_notification_player_id"] = _text(getattr(item, "player_id", ""))
    st.session_state["_fixture_notification_id"] = _text(getattr(item, "id", ""))


def _fixture_open_destination(destination: str) -> None:
    dest = _text(destination)
    st.session_state["_fixture_notification_destination"] = dest
    st.session_state["_fixture_open_ack"] = dest
    st.session_state["fixture_notifications_inbox_open"] = False


def _render_fixture_ack_markers() -> None:
    dest = _text(st.session_state.get("_fixture_notification_destination"))
    player = _text(st.session_state.get("_fixture_notification_player_id"))
    league_choice = _text(st.session_state.get("_fixture_league_choice"))
    gm_dest = _text(st.session_state.get("_fixture_gm_destination"))
    if dest:
        st.markdown(
            f"<div data-fixture-notification-destination='{dest}' "
            f"data-fixture-notification-player='{player}'>Opened {dest}</div>",
            unsafe_allow_html=True,
        )
    if league_choice:
        st.markdown(
            f"<div data-fixture-league-choice='{league_choice}'>League: {league_choice}</div>",
            unsafe_allow_html=True,
        )
    if gm_dest:
        st.markdown(
            f"<div data-fixture-gm-destination='{gm_dest}'>Destination: {gm_dest}</div>",
            unsafe_allow_html=True,
        )


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


def _workspace(
    title: str,
    note: str,
    *,
    default_league_key: str = "default",
    default_header_alerts: int = 0,
) -> None:
    from modules import notification_center

    notify_mode = str(st.query_params.get("notify") or "populated").strip().lower()
    inbox_open = str(st.query_params.get("inbox") or "").strip().lower() == "open"
    league_key = str(
        st.query_params.get("header_league") or default_league_key
    ).strip().lower()
    league_name = HEADER_LEAGUE_FIXTURES.get(
        league_key,
        _text(st.query_params.get("header_league"), HEADER_LEAGUE_FIXTURES["default"]),
    )
    try:
        header_alerts = max(
            0,
            int(str(st.query_params.get("header_alerts") or default_header_alerts)),
        )
    except ValueError:
        header_alerts = max(0, int(default_header_alerts))
    fixture_tiles = []
    if notify_mode != "quiet":
        fixture_tiles = [
            {
                "label": "Top Trade Opportunity",
                "value": "Rhamondre Stevenson",
                "note": "You move from TE surplus.",
                "recommendation_id": "fixture-trade-notify-1",
                "route_key": "trade_hub",
                "route_player_id": "6794",
                "route_focus_mode": "target_player",
                "recommendation_narrative": {
                    "recommendation_id": "fixture-trade-notify-1",
                    "kind": "trade",
                    "action": "Buy need-position upgrade",
                    "target_label": "Rhamondre Stevenson",
                    "reason": "You move from TE surplus.",
                    "evidence": "Partner surplus at RB.",
                    "is_active_recommendation": True,
                },
            },
            {
                "label": "Top Waiver Opportunity",
                "value": "Add reliable depth",
                "note": "Available fixture player with a current role.",
                "recommendation_id": "fixture-waiver-notify-1",
                "route_key": "waivers",
                "player_id": "4046",
            },
            {
                "label": "Injury Alert",
                "value": "Rhamondre Stevenson",
                "note": "Questionable for Week 7.",
                "route_key": "player_quick_view",
                "route_player_id": "6794",
                "player_id": "6794",
            },
            {
                "label": "Biggest Team Need",
                "value": "QB",
                "note": "Fixture roster pressure at quarterback.",
                "route_key": "league_overview",
            },
        ]
    notification_center.publish_activity_inventory(
        st.session_state,
        fixture_tiles,
        league_id="synthetic-founder-beta-league",
        roster_id="1",
        entitlement="premium",
        live_draft_active=False,
    )
    notifications = notification_center.list_founder_beta_notifications(
        session=st.session_state
    )
    if notify_mode == "stale":
        notification_center.publish_activity_inventory(
            st.session_state,
            [],
            league_id="synthetic-founder-beta-league",
            roster_id="1",
            entitlement="premium",
            live_draft_active=False,
        )
        stale_item = notification_center.mark_stale(
            notification_center.NotificationItem(
                id="rec:fixture-trade-notify-1",
                category="Trades",
                title="Acquire RB depth",
                body="Canonical trade headline for notification deep-link validation.",
                href_hint="trade_hub",
                recommendation_id="fixture-trade-notify-1",
                player_id="6794",
                league_id="synthetic-founder-beta-league",
                provenance="dashboard_inventory|Top Trade Opportunity",
                source_kind="canonical",
            ),
            reason="Recommendation updated",
        )
        notifications = (stale_item,) + tuple(
            item for item in notifications if item.source_kind == "product"
        )
    # Deterministic Alerts (N) / Alerts (99+) width fixtures for header geometry CI.
    if header_alerts > notification_center.unread_count(notifications):
        pad = []
        current = notification_center.unread_count(notifications)
        for index in range(current, header_alerts):
            pad.append(
                notification_center.NotificationItem(
                    id=f"header-geometry-pad-{index}",
                    category="League",
                    title=f"Header geometry pad {index + 1}",
                    body="Synthetic unread used only for Alerts trigger width QA.",
                    unread=True,
                    source_kind="canonical",
                )
            )
        notifications = tuple(notifications) + tuple(pad)
    with st.container(key="executive_workspace_shell"):
        render_html_fragment(
            application_shell.executive_workspace_shell_html(
                application_shell.ExecutiveWorkspaceShell(
                    page_title=title,
                    page_note=note,
                    league_name=league_name,
                    team_name="Fixture Football Operations",
                    platform="Sleeper",
                    account_label="Fixture Account",
                    entitlement_label="Premium",
                    has_league=True,
                    metrics=(),
                    notification_unread=notification_center.unread_count(notifications),
                )
            )
        )
        with st.container(key="executive_command_actions"):
            league_col, alerts_col, profile_col = st.columns(
                list(COMMAND_COLUMN_WEIGHTS),
                gap=None,
                vertical_alignment="top",
            )
            with league_col:
                with st.container(key="executive_command_cell_league_fixture"):
                    with st.popover(
                        "League",
                        key="top_league_actions_fixture",
                    ):
                        st.caption("Select a league")
                        st.button(
                            "Synthetic Founder Beta League",
                            key="fixture_league_select_primary",
                            use_container_width=True,
                            on_click=lambda: st.session_state.update(
                                _fixture_league_choice="Synthetic Founder Beta League"
                            ),
                        )
                        st.button(
                            "Fixture Alt League",
                            key="fixture_league_select_alt",
                            use_container_width=True,
                            on_click=lambda: st.session_state.update(
                                _fixture_league_choice="Fixture Alt League",
                                _fixture_open_ack="league",
                            ),
                        )
            with alerts_col:
                if inbox_open:
                    st.session_state["fixture_notifications_inbox_open"] = True
                notification_center.render_notification_center(
                    items=notifications,
                    key_prefix="fixture_notifications",
                    on_open_destination=_fixture_open_destination,
                )
            with profile_col:
                with st.container(key="executive_command_cell_profile_fixture"):
                    with st.popover(
                        "You",
                        key="fixture_profile_popover",
                    ):
                        st.caption("Fixture Account · Premium · Founder Beta")
                        st.caption("Account, Premium, and Feedback.")
                        with st.expander("Send feedback", expanded=False):
                            st.caption("Founder Beta feedback fixture.")



def _marker(surface: str, sections: tuple[str, ...]) -> None:
    joined = ",".join(sections).replace('"', "&quot;")
    st.markdown(
        f'<div data-ui-surface="{surface}" data-ui-sections="{joined}"></div>',
        unsafe_allow_html=True,
    )


def _tiles(items: list[dict], *, key_prefix: str = "home_command_tiles") -> None:
    cards = []
    for item in items:
        wide = bool(item.get("wide"))
        priority = str(item.get("priority") or ("primary" if wide else "secondary"))
        tone = str(item.get("tone") or "trade").lower()
        weight = (
            " home-command-card-primary home-command-card-wide"
            if priority == "primary" or wide
            else " home-command-card-secondary"
        )
        tone_class = f" home-command-card-{tone}" if tone else ""
        cards.append(
            f"<article class='home-command-card dg-ui-card{weight}{tone_class}'>"
            f"<div class='home-command-card-label'>{item['label']}</div>"
            f"<div class='home-command-card-value'>{item['value']}</div>"
            f"<p class='home-command-card-note'>{item['note']}</p></article>"
        )
    render_html_fragment(
        f"<div class='home-command-grid' data-tile-key-prefix='{key_prefix}'>"
        + "".join(cards)
        + "</div>"
    )


def _navigation() -> None:
    _marker("navigation", ("Where to go", "Core", "Support"))
    _workspace("Dashboard", "Navigation fixture behind the Founder command menu.")
    ui_primitives.render_section_header(
        "Founder workspace",
        eyebrow="Active page",
        subtitle="Underlying content must remain visually separate from the open command menu.",
    )
    _tiles([
        {"label": "Visible page content", "value": "Dashboard briefing", "note": "The menu surface must prevent this text from bleeding through."},
    ])
    with st.container(key="mobile_gm_sheet_trigger_fixture"):
        render_html_fragment(brand_identity.gm_orb_floating_trigger_html())
        st.button(
            brand_identity.GM_ORB_ARIA_LABEL,
            help=brand_identity.GM_ORB_HELP,
            type="primary",
            key="mobile_gm_sheet_open_fixture",
            on_click=lambda: st.session_state.update(
                _fixture_gm_open=not bool(st.session_state.get("_fixture_gm_open"))
            ),
        )
    if not st.session_state.get("_fixture_gm_open"):
        return
    from modules import gm_sheet_dismiss

    if gm_sheet_dismiss.consume_gm_sheet_dismiss(key="gm_sheet_dismiss_fixture"):
        st.session_state["_fixture_gm_open"] = False
        return
    with st.container():
        render_html_fragment(
            "<div class='mobile-gm-sheet-marker'></div>"
            "<div class='mobile-gm-destination-panel'>"
            "<div class='mobile-gm-panel-header'>"
            "<div class='mobile-gm-sheet-kicker'>FantasyGM Lab</div>"
            "<div class='mobile-gm-sheet-title'>Where to go</div>"
            "<div class='mobile-gm-current-page'>Current: Dashboard</div>"
            "</div><div class='mobile-gm-sheet-note'>Founder Beta · Core routes first. Experimental routes are early access when enabled.</div>"
            "</div>"
        )
        with st.container(key="mobile_sheet_close"):
            st.button(
                "Close",
                key="mobile_sheet_close_fixture",
                help="Close navigation",
                on_click=lambda: st.session_state.update(_fixture_gm_open=False),
            )
        st.caption("Core")
        st.button("Dashboard", key="mobile_sheet_nav_dashboard_fixture", type="primary", use_container_width=True)
        st.button("My Team", key="mobile_sheet_nav_my_team_fixture", use_container_width=True)
        st.button("Trade Hub", key="mobile_sheet_nav_trade_fixture", use_container_width=True,
            on_click=lambda: st.session_state.update(
                _fixture_gm_open=False,
                _fixture_gm_destination="trade_hub",
            ),
        )
        st.button("Waivers", key="mobile_sheet_nav_waivers_fixture", use_container_width=True)
        st.caption("Support")
        st.button(
            "League Overview",
            key="mobile_sheet_nav_league_fixture",
            use_container_width=True,
            on_click=lambda: st.session_state.update(
                _fixture_gm_open=False,
                _fixture_gm_destination="rankings",
            ),
        )
        st.button("Players", key="mobile_sheet_nav_players_fixture", use_container_width=True)
        st.caption("Experimental · Early access")
        st.markdown(
            "<div class='mobile-gm-experimental-note'>Early access capability. Available when enabled for your account.</div>",
            unsafe_allow_html=True,
        )
        st.button("Labs [EXPERIMENTAL]", key="mobile_sheet_nav_labs_fixture", use_container_width=True)


def _header_geometry() -> None:
    """Long-content header fixtures for command-bar geometry CI.

    Keep the executive shell at the top of the viewport (no page chrome above it)
    so mobile unreclaimed-top checks stay valid. Query overrides:
    header_league=short|normal|long, header_alerts=0|1|12|120.
    """

    _marker(
        "header-geometry",
        (
            "Header Geometry",
            "Switch League",
            "Alerts",
            "You",
        ),
    )
    _workspace(
        "Header Geometry",
        "Command-bar width contract fixture.",
        default_league_key="long",
        default_header_alerts=12,
    )


def _dashboard() -> None:
    briefing_mode = str(st.query_params.get("briefing") or "populated").strip().lower()
    _marker(
        "dashboard",
        (
            "Today's Game Plan",
            "What Changed",
            "Deep Analysis",
        ),
    )
    # Production path renders the GM orb inside the same main vertical tree as
    # Dashboard content. Include it here so overlay CSS regressions that collapse
    # ancestor stVerticalBlock via unscoped :has() fail CI (#244).
    with st.container(key="mobile_gm_sheet_trigger_dashboard"):
        render_html_fragment(brand_identity.gm_orb_floating_trigger_html())
        st.button(
            brand_identity.GM_ORB_ARIA_LABEL,
            help=brand_identity.GM_ORB_HELP,
            type="primary",
            key="mobile_gm_sheet_open_dashboard",
        )
    _workspace("Dashboard", "Daily command center for the next move window.")
    if briefing_mode == "quiet":
        items = []
    elif briefing_mode == "single":
        items = [
            {
                "label": "Top Trade Opportunity",
                "value": "Acquire RB depth",
                "note": "Canonical trade headline used for single-priority briefing validation.",
                "recommendation_id": "fixture-trade-1",
                "route_key": "trade_hub",
            },
        ]
    elif briefing_mode == "free":
        items = [
            {
                "label": "Biggest Team Need",
                "value": "Strengthen QB depth",
                "note": "The current starter room has the clearest upgrade path.",
                "recommendation_id": "fixture-need-1",
            },
            {
                "label": "Top Trade Opportunity",
                "value": "Explore a balanced swap",
                "note": "A synthetic recommendation used only for layout validation.",
                "recommendation_id": "fixture-trade-1",
                "route_key": "trade_hub",
            },
            {
                "label": "Top Waiver Opportunity",
                "value": "Add reliable depth",
                "note": "Available fixture player with a current role.",
                "recommendation_id": "fixture-waiver-1",
                "route_key": "waivers",
            },
            {
                "label": "Injury Alert",
                "value": "1 injured starter",
                "note": "A projected starter is unavailable this week.",
            },
        ]
    else:
        items = [
            {"label": "Roster Pressure", "value": "2 Over", "note": "Cut or trade now to clear the Sleeper roster limit."},
            {"label": "Injury Alert", "value": "1 injured starter", "note": "A projected starter is unavailable this week."},
            {"label": "Biggest Team Need", "value": "Strengthen QB depth", "note": "The current starter room has the clearest upgrade path."},
            {"label": "Depth Upgrade", "value": "Optimize flex", "note": "Additional recommendation kept behind progressive disclosure."},
            {"label": "Top Trade Opportunity", "value": "Explore a balanced swap", "note": "A synthetic recommendation used only for layout validation."},
            {"label": "Top Waiver Opportunity", "value": "Add reliable depth", "note": "Available fixture player with a current role."},
        ]
    briefing = dashboard_workflow.organize_dashboard_items(
        items,
        immediate_labels=frozenset({"Roster Pressure", "Injury Alert"}),
    )
    entitlement = "free" if briefing_mode == "free" else "premium"
    game_plan = daily_gm_briefing.compose_daily_gm_briefing(
        briefing,
        league_id="synthetic-founder-beta-league",
        roster_id="1",
        valuation_lens="dynasty_value",
        scoring_format="Half-PPR",
        entitlement=entitlement,
    )
    if briefing_mode == "loading":
        def _render_todays_game_plan() -> None:
            ui_primitives.render_section_header("Today's Game Plan", weight="primary")
            st.caption("Refreshing today's priorities from the current league context…")

        def _render_what_changed() -> None:
            decision_change_history_ui.render_what_changed_section(
                (),
                key_prefix=f"fixture_what_changed_{briefing_mode}",
            )
    else:
        def _render_todays_game_plan() -> None:
            daily_gm_briefing_ui.render_todays_game_plan(
                game_plan,
                open_item=lambda _item: None,
                key_prefix=f"fixture_daily_gm_{briefing_mode}",
            )

        def _render_what_changed() -> None:
            changed_mode = str(st.query_params.get("changed") or "populated").strip().lower()
            if changed_mode == "quiet":
                events = ()
            else:
                # Deterministic fixture events — not produced by football recomputation.
                now = 1_700_000_000.0
                events = (
                    decision_change_history.DecisionChangeEvent(
                        event_id="fixture-priority-1",
                        recommendation_id="fixture-trade-notify-1",
                        league_id="synthetic-founder-beta-league",
                        roster_id="1",
                        timestamp=now - 18 * 60,
                        lifecycle_transition="current->changed",
                        reason="priority_changed",
                        category="Trades",
                        target_label="Rhamondre Stevenson",
                        player_id="6794",
                        destination="trade_hub",
                        previous_state={"target_label": "Josh Jacobs"},
                        current_state={"target_label": "Rhamondre Stevenson"},
                        summary_headline="Top priority changed",
                        summary_detail="Rhamondre Stevenson is now your leading trade target.",
                        why_label="Recommendation priority changed",
                    ),
                    decision_change_history.DecisionChangeEvent(
                        event_id="fixture-waiver-resolved-1",
                        recommendation_id="fixture-waiver-notify-1",
                        league_id="synthetic-founder-beta-league",
                        roster_id="1",
                        timestamp=now - 2 * 3600,
                        lifecycle_transition="current->resolved",
                        reason="recommendation_resolved",
                        category="Waivers",
                        target_label="Brashard Smith",
                        player_id="4046",
                        destination="waivers",
                        previous_state={"target_label": "Brashard Smith"},
                        current_state=None,
                        summary_headline="Waiver opportunity resolved",
                        summary_detail="Brashard Smith is no longer available in this league.",
                        why_label="Player availability changed",
                    ),
                )
                st.session_state[decision_change_history.DECISION_HISTORY_EVENTS_KEY] = [
                    event.to_dict() for event in events
                ]
                st.session_state[
                    decision_change_history.DECISION_HISTORY_LEAGUE_SCOPE_KEY
                ] = "synthetic-founder-beta-league"
            decision_change_history_ui.render_what_changed_section(
                events[: decision_change_history.MAX_DASHBOARD_EVENTS],
                open_event=lambda _event: None,
                key_prefix=f"fixture_what_changed_{briefing_mode}",
            )
    league_frame = pd.DataFrame([
        {"roster_id": "1", "team_name": "Fixture Football Operations", "owner_name": "Fixture Manager", "avg_age": 25.8, "starter_score": 91, "bench_score": 75, "injury_impact_score": 2},
        {"roster_id": "2", "team_name": "Young Core", "owner_name": "Alex", "avg_age": 23.9, "starter_score": 84, "bench_score": 81, "injury_impact_score": 0},
        {"roster_id": "3", "team_name": "Veteran Window", "owner_name": "Casey", "avg_age": 28.1, "starter_score": 97, "bench_score": 68, "injury_impact_score": 5},
    ])
    comparisons = comparative_metrics.dashboard_comparison_payloads(league_frame, "1")
    dashboard_workflow.render_dashboard_workflow(
        briefing,
        snapshot_items=[
            {"label": "Record", "value": "7-3", "note": "Current season", "tappable": False},
            {"label": "Health", "value": "Stable", "note": "Roster availability", "comparison": comparisons["Health"]},
            {"label": "Average Age", "value": "25.8", "note": "Active roster profile", "comparison": comparisons["Average Age"]},
            {"label": "Starter Strength", "value": "#2", "note": "Projected lineup rank", "comparison": comparisons["Starter Strength"]},
            {"label": "Bench Strength", "value": "#2", "note": "Depth rank", "comparison": comparisons["Bench Strength"]},
        ],
        render_tiles=_tiles,
        render_snapshot=lambda snapshot: workspace_ui.render_summary_tiles(
            snapshot,
            key_prefix="ci_dashboard_snapshot",
            detail_dialog_renderer=workspace_ui.render_canonical_summary_tile_detail_dialog,
        ),
        render_orientation=lambda: dashboard_orientation.render_orientation_if_applicable(
            authenticated=True,
            page_ready=True,
            route="dashboard",
            platform="sleeper",
            league_identity="synthetic-founder-beta-league",
            active_roster_available=True,
            startup_mode=False,
            on_open_my_team=lambda: None,
            persistently_dismissed=False,
            on_dont_show_again=lambda: None,
        ),
        render_todays_game_plan=_render_todays_game_plan,
        render_what_changed=_render_what_changed,
        # Real Deep Analysis nav DOM (#236) — synthetic single-button fixtures
        # previously hid empty-shell / dual-border / floating-label regressions.
        render_quick_actions=lambda actions: workspace_ui.render_home_quick_actions(
            actions,
            commit_platform_destination=lambda route_key, source="dashboard_quick_action": (
                st.session_state.update(
                    {
                        "_fixture_deep_analysis_route": route_key,
                        "_fixture_deep_analysis_source": source,
                    }
                )
            ),
        ),
        render_league_pulse=lambda: _tiles(
            [{"label": "Market", "value": "Balanced", "note": "No fixture manager is dominating current activity."}]
        ),
        render_full_recommendations_lock=(
            (lambda: st.caption("Upgrade for full recommendation inventory."))
            if briefing_mode == "free"
            else None
        ),
    )
    # #240/#241 browser-visibility markers — prove top-level DOM receipt.
    st.markdown(
        '<div data-fgl-dashboard-root="1" hidden aria-hidden="true"></div>'
        '<div data-fgl-dashboard-useful="1" hidden aria-hidden="true"></div>'
        '<div data-fgl-dashboard-complete="1" hidden aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    try:
        from modules import dashboard_visibility
        from modules import auth_supabase
        from modules import auth_restore_lifecycle

        auth_restore_lifecycle.ensure_startup_session(st.session_state)
        canary = dashboard_visibility.render_dashboard_canary(st.session_state)

        # Simulate deferred durable-auth flush without st.rerun().
        st.session_state.setdefault(
            auth_supabase.DURABLE_AUTH_PENDING_SAVE_KEY,
            {
                "tok": "fixture",
                "rtok": "fixture",
                "expires_at": 9999999999,
            },
        )
        flush = account_ui.flush_durable_auth_persistence(
            st.session_state,
            config={
                "enabled": True,
                "url": "https://example.supabase.co",
                "anon_key": "fixture-anon-key",
            },
        )
        _ = flush
        dashboard_visibility.mount_browser_visibility_probe(
            st.session_state,
            route="dashboard",
            canary_token=canary,
        )
    except Exception:
        pass


def _league() -> None:
    _marker(
        "league",
        (
            "Standings",
            "Power Rankings",
            "Franchise Value",
            "Draft Capital",
            "How to read these boards",
            "League Insights",
        ),
    )
    _workspace("League Overview", "Competitive context across the current league.")
    ui_primitives.render_section_header(
        "2026 Standings",
        eyebrow="Where you stand",
        subtitle="Through Week 8. Actual results — separate from Power Rankings strength.",
    )
    from modules import league_standings

    standings_bundle = league_standings.build_league_standings_bundle(
        rosters=[
            {
                "roster_id": "fixture-mine",
                "settings": {
                    "wins": 7,
                    "losses": 1,
                    "ties": 0,
                    "fpts": 1240,
                    "fpts_decimal": 40,
                    "fpts_against": 980,
                    "fpts_against_decimal": 10,
                },
            },
            {
                "roster_id": "fixture-partner",
                "settings": {
                    "wins": 5,
                    "losses": 3,
                    "ties": 0,
                    "fpts": 1185,
                    "fpts_decimal": 0,
                    "fpts_against": 1110,
                    "fpts_against_decimal": 20,
                },
            },
            {
                "roster_id": "fixture-three",
                "settings": {
                    "wins": 4,
                    "losses": 4,
                    "ties": 0,
                    "fpts": 1112,
                    "fpts_decimal": 0,
                    "fpts_against": 1120,
                    "fpts_against_decimal": 0,
                },
            },
            {
                "roster_id": "fixture-four",
                "settings": {
                    "wins": 2,
                    "losses": 6,
                    "ties": 0,
                    "fpts": 980,
                    "fpts_decimal": 50,
                    "fpts_against": 1200,
                    "fpts_against_decimal": 0,
                },
            },
        ],
        roster_profiles={
            "fixture-mine": {
                "team_name": "War Room Synthetic",
                "owner_username": "founder",
                "owner_name": "Founder",
                "avatar_url": "",
            },
            "fixture-partner": {
                "team_name": "Lakefront Franchise",
                "owner_username": "partner",
                "owner_name": "Partner",
                "avatar_url": "",
            },
            "fixture-three": {
                "team_name": "Northside Assets",
                "owner_username": "",
                "owner_name": "Manager Three",
                "avatar_url": "",
            },
            "fixture-four": {
                "team_name": "South Pier",
                "owner_username": "south",
                "owner_name": "Manager Four",
                "avatar_url": "",
            },
        },
        league={
            "season": "2026",
            "settings": {"leg": 8, "playoff_teams": 3},
            "metadata": {},
        },
    )
    power_frame = pd.DataFrame(
        [
            {
                "roster_id": "fixture-mine",
                "team_name": "War Room Synthetic",
                "owner_username": "founder",
                "owner_name": "Founder",
                "avatar_url": "",
                "power_rank": 1,
                "power_score": 12400,
                "franchise_rank": 2,
                "franchise_score": 13100,
                "starter_rank": 1,
                "bench_rank": 3,
                "draft_capital_rank": 4,
                "draft_capital": 4200,
                "first_rounders": 1,
                "pick_count": 4,
                "strategy_display": "Compete",
                "archetype_label": "Flexible contender",
                "mode": "competitive",
                "injured_starters": 0,
                "trading_style": "Aggressive Trader",
                "roster_philosophy": "Win-Now",
                "asset_behavior": "Pick Seller",
                "activity_level": "High Activity",
            },
            {
                "roster_id": "fixture-partner",
                "team_name": "Lakefront Franchise",
                "owner_username": "partner",
                "owner_name": "Partner",
                "avatar_url": "",
                "power_rank": 2,
                "power_score": 11850,
                "franchise_rank": 1,
                "franchise_score": 14200,
                "starter_rank": 2,
                "bench_rank": 1,
                "draft_capital_rank": 2,
                "draft_capital": 6100,
                "first_rounders": 2,
                "pick_count": 6,
                "strategy_display": "Reboot",
                "archetype_label": "Pick-rich rebuilder",
                "mode": "rebuild",
                "injured_starters": 0,
                "trading_style": "Patient Trader",
                "roster_philosophy": "Rebuild",
                "asset_behavior": "Pick Buyer",
                "activity_level": "Medium Activity",
            },
            {
                "roster_id": "fixture-three",
                "team_name": "Northside Assets",
                "owner_username": "",
                "owner_name": "Manager Three",
                "avatar_url": "",
                "power_rank": 3,
                "power_score": 11120,
                "franchise_rank": 3,
                "franchise_score": 12050,
                "starter_rank": 4,
                "bench_rank": 2,
                "draft_capital_rank": 1,
                "draft_capital": 7800,
                "first_rounders": 3,
                "pick_count": 7,
                "strategy_display": "Balanced",
                "archetype_label": "Contender",
                "mode": "competitive",
                "injured_starters": 1,
                "trading_style": "Selective Trader",
                "roster_philosophy": "Balanced",
                "asset_behavior": "Hold Core",
                "activity_level": "Low Activity",
            },
        ]
    )

    def _fixture_injury(row):
        # Exception-only attention for dense-list visual validation.
        try:
            return int(row.get("injured_starters") or 0) > 0
        except (TypeError, ValueError):
            return False

    def _injury_label(_row):
        return "Injury watch"

    def _tap(row):
        roster_id = str(row.get("roster_id") or "").strip()
        if not roster_id:
            return "", ""
        return (
            " team-card-tappable",
            f" data-roster-id='{roster_id}' role='button' tabindex='0'",
        )

    def _tap_grid(*, html: str, key_prefix: str):
        render_html_fragment(html)
        return None

    league_workspace_ui.render_standings_board(
        standings_bundle,
        team_tap_markup=_tap,
        render_team_card_tap_grid=_tap_grid,
        open_league_team_from_tap=lambda _clicked: False,
        team_logo_html=lambda *_args, **_kwargs: "<div class='dg-ranked-logo'>WR</div>",
        current_roster_id="fixture-mine",
    )
    st.caption("Standings = actual results. Boards below = roster strength, dynasty value, and draft capital.")
    ui_primitives.render_section_header(
        "Power Rankings",
        eyebrow="Who is strongest",
        subtitle="Current lineup strength appears before supporting education.",
    )
    league_workspace_ui.render_power_rankings_board(
        power_frame,
        "Starter-Weighted Score",
        rank_column="power_rank",
        score_column="power_score",
        has_meaningful_team_injury_impact=_fixture_injury,
        team_injury_display_label=_injury_label,
        team_tap_markup=_tap,
        render_team_card_tap_grid=_tap_grid,
        open_league_team_from_tap=lambda _clicked: False,
        team_logo_html=lambda *_args, **_kwargs: "<div class='dg-ranked-logo'>WR</div>",
        current_roster_id="fixture-mine",
    )
    ui_primitives.render_section_header(
        "Franchise Value",
        eyebrow="Dynasty value",
        subtitle="Total roster value plus owned draft capital.",
    )
    league_workspace_ui.render_power_rankings_board(
        power_frame,
        "Roster Value + Draft Capital",
        rank_column="franchise_rank",
        score_column="franchise_score",
        has_meaningful_team_injury_impact=_fixture_injury,
        team_injury_display_label=_injury_label,
        team_tap_markup=_tap,
        render_team_card_tap_grid=_tap_grid,
        open_league_team_from_tap=lambda _clicked: False,
        team_logo_html=lambda *_args, **_kwargs: "<div class='dg-ranked-logo'>WR</div>",
        current_roster_id="fixture-mine",
    )
    ui_primitives.render_section_header(
        "Draft Capital",
        eyebrow="Future capital",
        subtitle="Who controls upcoming picks.",
    )
    league_workspace_ui.render_power_rankings_board(
        power_frame,
        "Draft Capital Score",
        rank_column="draft_capital_rank",
        score_column="draft_capital",
        has_meaningful_team_injury_impact=_fixture_injury,
        team_injury_display_label=_injury_label,
        team_tap_markup=_tap,
        render_team_card_tap_grid=_tap_grid,
        open_league_team_from_tap=lambda _clicked: False,
        team_logo_html=lambda *_args, **_kwargs: "<div class='dg-ranked-logo'>WR</div>",
        current_roster_id="fixture-mine",
    )
    ui_primitives.render_section_header(
        "Team comparison",
        eyebrow="League structure",
        subtitle="Scan power, franchise, archetype, and activity without a spreadsheet.",
    )
    league_workspace_ui.render_team_comparison_board(
        power_frame,
        team_tap_markup=_tap,
        render_team_card_tap_grid=_tap_grid,
        open_league_team_from_tap=lambda _clicked: False,
        team_logo_html=lambda *_args, **_kwargs: "<div class='dg-ranked-logo'>WR</div>",
        current_roster_id="fixture-mine",
    )
    disclosure = workspace_ui.client_disclosure_html(
        "How to read these boards",
        workspace_ui.concept_band_html(
            [
                {
                    "label": "Power Rank",
                    "title": "Current strength",
                    "body": "Starter quality and usable depth.",
                    "tone": "power",
                }
            ]
        ),
        css_class="league-overview-how-to-read",
    )
    render_html_fragment(disclosure)
    ui_primitives.render_section_header(
        "League Insights",
        eyebrow="Worth noticing",
        subtitle="Primary posture signals, then supporting extremes.",
    )
    st.caption("Primary signals")
    workspace_ui.render_analysis_cards(
        [
            {
                "label": "Pressure Teams",
                "title": "Bottom-tier rosters with the most immediate strain",
                "tone": "weakness",
                "items": ["War Room Synthetic | Power #4"],
            }
        ]
    )
    st.caption("Supporting extremes")
    league_workspace_ui.render_league_intelligence_cards(
        [
            {
                "label": "Youngest Core",
                "team_name": "Lakefront Franchise",
                "owner_handle": "@partner",
                "roster_id": "fixture-partner",
                "avatar_url": "",
                "metric": "24.1 avg age",
                "note": "Youngest starter room in the fixture league.",
            },
            {
                "label": "Most Injured Roster",
                "team_name": "Northside Assets",
                "owner_handle": "Manager Three",
                "roster_id": "fixture-three",
                "avatar_url": "",
                "metric": "Impact 1,200",
                "note": "Highest current injury drag.",
            },
        ],
        team_tap_markup=_tap,
        render_team_card_tap_grid=_tap_grid,
        open_league_team_from_tap=lambda _clicked: False,
        team_logo_html=lambda *_args, **_kwargs: "<div class='dg-intel-logo-wrap'>NA</div>",
        current_roster_id="fixture-mine",
    )
    league_workspace_ui.render_team_rank_cards({
        "power_rank": 4, "franchise_rank": 2, "roster_value_rank": 3,
        "starter_rank": 5, "bench_rank": 2, "age_rank": 6, "draft_capital_rank": 1,
    })


def _trade_analyzer() -> None:
    inject_global_styles(TRADE_ANALYZER_CSS)
    _marker("trade-analyzer", ("You receive", "You send", "Analyze Trade"))
    _workspace("Trade Analyzer", "Evaluate an offer you received.")
    st.markdown(
        "<div class='toa-partner-block'><div class='toa-block-title'>Partner</div></div>",
        unsafe_allow_html=True,
    )
    st.selectbox(
        "Team that sent this offer",
        ["Lakefront Franchise | Alex", "Harbor Club | Jordan"],
        key="fixture_trade_receive_partner",
    )
    if "fixture_toa_receive" not in st.session_state:
        st.session_state["fixture_toa_receive"] = []
    if "fixture_toa_send" not in st.session_state:
        st.session_state["fixture_toa_send"] = []
    pool_receive = [
        {"asset_type": "player", "player_id": "r1", "name": "Synthetic Young WR", "position": "WR", "team": "MIA", "score": 4200, "owner_roster_id": "partner"},
        {"asset_type": "pick", "label": "2027 1st", "name": "2027 1st", "season": 2027, "round": 1, "score": 1800, "owner_roster_id": "partner"},
    ]
    pool_send = [
        {"asset_type": "player", "player_id": "s1", "name": "Synthetic Veteran RB", "position": "RB", "team": "NE", "score": 3100, "owner_roster_id": "me"},
        {"asset_type": "player", "player_id": "s2", "name": "Depth WR", "position": "WR", "team": "CHI", "score": 900, "owner_roster_id": "me"},
    ]
    st.markdown("<div class='toa-builder-marker'></div>", unsafe_allow_html=True)
    receive_col, send_col = st.columns(2)
    with receive_col:
        st.markdown("<div class='toa-block toa-block-receive'><div class='toa-block-title'>You receive</div></div>", unsafe_allow_html=True)
        if not st.session_state["fixture_toa_receive"]:
            st.markdown("<div class='toa-empty-package'>No assets selected to receive.</div>", unsafe_allow_html=True)
        for idx, asset in enumerate(st.session_state["fixture_toa_receive"]):
            cols = st.columns([5, 1])
            cols[0].markdown(trade_analyzer_builder.chip_html(asset), unsafe_allow_html=True)
            if cols[1].button("×", key=f"fixture_toa_rm_r_{idx}"):
                st.session_state["fixture_toa_receive"].pop(idx)
                st.rerun()
        if st.button("+ Add asset", key="fixture_toa_add_receive", use_container_width=True):
            st.session_state["fixture_toa_receive_open"] = not st.session_state.get("fixture_toa_receive_open")
        if st.session_state.get("fixture_toa_receive_open"):
            for asset in pool_receive:
                identity = trade_analyzer_builder.asset_identity(asset)
                if identity in trade_analyzer_builder.package_identities(st.session_state["fixture_toa_receive"]):
                    continue
                cols = st.columns([5, 1])
                cols[0].markdown(trade_analyzer_builder.result_row_html(asset), unsafe_allow_html=True)
                if cols[1].button("Add", key=f"fixture_toa_add_r_{identity}", use_container_width=True):
                    mutation = trade_analyzer_builder.try_add_asset(
                        asset,
                        package_key=trade_analyzer_builder.RECEIVE_KEY,
                        send_assets=st.session_state["fixture_toa_send"],
                        receive_assets=st.session_state["fixture_toa_receive"],
                        partner_roster_id="partner",
                    )
                    st.session_state["fixture_toa_receive"] = mutation.receive_assets
                    st.session_state["fixture_toa_send"] = mutation.send_assets
                    st.session_state["fixture_toa_receive_open"] = False
                    st.rerun()
    with send_col:
        st.markdown("<div class='toa-block toa-block-send'><div class='toa-block-title'>You send</div></div>", unsafe_allow_html=True)
        if not st.session_state["fixture_toa_send"]:
            st.markdown("<div class='toa-empty-package'>No assets selected to send.</div>", unsafe_allow_html=True)
        for idx, asset in enumerate(st.session_state["fixture_toa_send"]):
            cols = st.columns([5, 1])
            cols[0].markdown(trade_analyzer_builder.chip_html(asset), unsafe_allow_html=True)
            if cols[1].button("×", key=f"fixture_toa_rm_s_{idx}"):
                st.session_state["fixture_toa_send"].pop(idx)
                st.rerun()
        if st.button("+ Add asset", key="fixture_toa_add_send", use_container_width=True):
            st.session_state["fixture_toa_send_open"] = not st.session_state.get("fixture_toa_send_open")
        if st.session_state.get("fixture_toa_send_open"):
            for asset in pool_send:
                identity = trade_analyzer_builder.asset_identity(asset)
                if identity in trade_analyzer_builder.package_identities(st.session_state["fixture_toa_send"]):
                    continue
                cols = st.columns([5, 1])
                cols[0].markdown(trade_analyzer_builder.result_row_html(asset), unsafe_allow_html=True)
                if cols[1].button("Add", key=f"fixture_toa_add_s_{identity}", use_container_width=True):
                    mutation = trade_analyzer_builder.try_add_asset(
                        asset,
                        package_key=trade_analyzer_builder.SEND_KEY,
                        send_assets=st.session_state["fixture_toa_send"],
                        receive_assets=st.session_state["fixture_toa_receive"],
                        my_roster_id="me",
                    )
                    st.session_state["fixture_toa_receive"] = mutation.receive_assets
                    st.session_state["fixture_toa_send"] = mutation.send_assets
                    st.session_state["fixture_toa_send_open"] = False
                    st.rerun()
    st.button("Analyze Trade", key="fixture_toa_analyze", type="primary", use_container_width=True)


def _trade() -> None:
    _marker("trade", ("Value change", "Review package"))
    _workspace("Trade Hub", "Negotiation workspace for team-specific trade ideas.")
    idea = {
        "partner_roster_id": "fixture-partner",
        "partner_team_name": "Lakefront Franchise",
        "tag": "Get Younger + Pick",
        "my_score": 8540,
        "their_score": 9028,
        "trade_gain": 488,
        "fit_grade": "Strong",
        "market_realism_label": "Plausible",
        "trade_confidence_label": "Medium",
        "reasoning_summary": "Adds a younger weekly starter and future flexibility without sacrificing lineup stability.",
        "_display_section": "Age Optimization",
        "send_assets": [{"asset_type": "player", "player_id": "6794", "name": "Synthetic Veteran RB"}],
        "receive_assets": [
            {"asset_type": "player", "player_id": "8155", "name": "Synthetic Young WR"},
            {"asset_type": "pick", "name": "2027 2nd"},
        ],
    }
    def detail_assets(assets: list[dict]) -> str:
        return "<div class='trade-assets'>" + "".join(
            (
                "<article class='trade-asset-row trade-asset-row-player player-card-tappable' "
                f"data-player-id='{asset.get('player_id')}' role='button' tabindex='0' "
                f"aria-label='Open dossier for {asset.get('name')}'>"
                f"<div class='trade-asset-name'>{asset.get('name')}</div>"
                "<div class='trade-asset-meta'>Fixture team | Age 26 | Starter</div></article>"
            )
            if asset.get("asset_type") == "player"
            else (
                "<article class='trade-asset-row trade-asset-row-pick'>"
                f"<div class='trade-asset-name'>{asset.get('name')}</div></article>"
            )
            for asset in assets
        ) + "</div>"

    def dossier(player_id: str, **_kwargs) -> None:
        name = "Synthetic Veteran RB" if player_id == "6794" else "Synthetic Young WR"
        st.markdown(
            f"<div data-trade-dossier-player='{player_id}'><h3>{name}</h3></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            player_quick_view.snapshot_html(
                player_quick_view.DossierSnapshot(
                    dynasty_value="7,800",
                    rank="#18",
                    tier="Starter",
                    recommendation="Hold",
                    trend="Stable",
                    recommendation_note="Synthetic dossier fixture using the canonical snapshot model.",
                )
            ),
            unsafe_allow_html=True,
        )

    trade_hub_ui.render_trade_idea_card(
        idea, 0, key_prefix="ci_trade_board", format_score=lambda value: f"{float(value):,.0f}",
        tidy_label=lambda value: str(value).replace("_", " ").title(),
        trade_target_reason=lambda _: "Synthetic target rationale.",
        trade_partner_reason=lambda _: "Synthetic partner rationale.",
        trade_confidence_reason=lambda _: "Synthetic confidence rationale.",
        trade_value_verdict=lambda _: "Balanced", trade_display_confidence_label=lambda _: "Medium",
        injury_display_context=lambda _: {"risk": False}, glyph_chip_html=lambda *args, **kwargs: "",
        assets_html=detail_assets,
        render_tappable_player_html=player_cards.render_tappable_player_html,
        render_player_dossier=dossier,
    )


def _my_team() -> None:
    _marker("my-team", ("Roster Posture", "Roster Core", "Position Groups", "Draft Capital"))
    _workspace("My Team", "Roster construction, pressure points, and the next handoff.")
    ui_primitives.render_section_header("Roster Posture", eyebrow="Construction", subtitle="Archetype, strategy, and league ranks.")
    _tiles([
        {"label": "Outlook", "value": "Balanced Contender", "note": "Strong current roster with manageable gaps."},
        {"label": "Power", "value": "#4", "note": "Starter unit #3."},
    ])
    ui_primitives.render_section_header("Strength & Pressure", eyebrow="What matters", subtitle="Existing strengths and short-term coverage needs.")
    _tiles([
        {"label": "Strength", "value": "WR foundation", "note": "Existing team metrics mark this room as a relative strength."},
        {"label": "Pressure point", "value": "RB coverage", "note": "Short-term coverage need from the existing roster-needs assessment."},
    ])
    ui_primitives.render_section_header("Roster Actions", eyebrow="Handoffs", subtitle="Canonical next move plus Trade Hub and Waivers destinations.")
    _tiles([
        {"label": "Biggest Need", "value": "Running Back", "note": "Starter and depth coverage need attention."},
        {"label": "Roster Status", "value": "Within limit", "note": "Twenty-four active players against a twenty-five player limit."},
    ])
    ui_primitives.render_section_header("Roster Core", eyebrow="Projected", subtitle="Projected core groups with canonical ranks — not live Sleeper starter locks.")
    assets = (
        football_assets.FootballPlayerAsset("fixture-qb", "Synthetic Quarterback", "QB", "MIN", "Starter", "starter", value="82", value_label="Dynasty Score", insight="OVR #12 · QB #3"),
        football_assets.FootballPlayerAsset("fixture-wr", "Synthetic Wide Receiver With A Long Name", "WR", "SEA", "Contributor", "contributor", value="67", value_label="Dynasty Score", insight="OVR #48 · WR #18"),
    )
    render_html_fragment("<div class='player-scan-grid'>" + "".join(football_assets.player_card_html(asset, density="compact", mode="action-enabled") for asset in assets) + "</div>")
    ui_primitives.render_section_header("Position Groups", eyebrow="Rooms", subtitle="Coverage outlook from existing roster-needs classifications.")
    _tiles([
        {"label": "Covered", "value": "QB · Superflex", "note": "Starter covered with backup depth."},
        {"label": "Thin", "value": "RB", "note": "Active coverage is below the current lineup requirement."},
    ])
    ui_primitives.render_section_header("Draft Capital", eyebrow="Flexibility", subtitle="Owned future picks by season.")
    _tiles([
        {"label": "2027", "value": "1st · 3rd", "note": "Owned picks for this draft year."},
        {"label": "2028", "value": "2nd", "note": "Owned picks for this draft year."},
    ])

def _waivers() -> None:
    _marker("waivers", ("Waiver Priorities", "Available Targets"))
    _workspace("Waivers", "Wire scanning and decision support for the active league.")
    players = pd.DataFrame([
        {"player_id": "fixture-qb", "name": "Garrett Nussmeier", "position": "QB", "team": "NO", "age": 23, "value_score": 4120, "position_rank": 4, "fantasy_ppg": 14.9, "opportunity_label": "Strong Opportunity", "opportunity_explanation": "Projected starter with usable weekly volume.", "opportunity_confidence": "Medium", "stale_free_agent": False},
        {"player_id": "fixture-wr", "name": "Synthetic Receiver", "position": "WR", "team": "SEA", "age": 23, "value_score": 2810, "position_rank": 9, "fantasy_ppg": 10.7, "opportunity_label": "Backup With Upside", "opportunity_explanation": "A current role creates a low-cost depth option.", "opportunity_confidence": "Medium", "stale_free_agent": False},
    ])
    @st.dialog("Player Quick View", width="large")
    def fixture_dossier(player_id: str, **_kwargs) -> None:
        row = players[players["player_id"] == player_id].iloc[0]
        st.markdown(
            "<section class='player-quick-view-shell'><div class='player-quick-view-hero'>"
            f"<div class='player-quick-view-avatar'>SQ</div><h2>{row['name']}</h2>"
            f"<p>{row['position']} · {row['team']} · Age {row['age']}</p></div></section>",
            unsafe_allow_html=True,
        )
        st.markdown(player_quick_view.snapshot_html(player_quick_view.DossierSnapshot(
            dynasty_value=f"{row['value_score']:,.0f}", rank="#48", position_rank=f"#{row['position_rank']} {row['position']}",
            fantasy_ppg=f"{row['fantasy_ppg']}", tier="Contributor", recommendation="Waiver Add", trend="Stable",
            recommendation_note=str(row['opportunity_explanation']),
        )), unsafe_allow_html=True)
    ui_primitives.render_section_header("Waiver Priorities", eyebrow="Decision Board", subtitle="Compact recommendations lead with the player and decision hook.")
    waivers_ui.render_free_agent_cards(
        players, "value_score", max_items=2,
        recommendation_reason_text=lambda value, limit: str(value)[:limit],
        player_display_name=lambda row: str(row.get("name")),
        cached_headshot_data_url=lambda _player_id: "", asset_initials=lambda _name: "SQ",
        player_status_style=lambda label: {"label": label, "tone": "neutral"},
        canonical_player_status=lambda value: str(value), tier_chip_html=lambda _value: "",
        player_support_chip_html=lambda value, _tone: f"<span class='dg-ui-badge'>{value}</span>",
        player_status_pill_html=lambda _value: "",
        render_tappable_player_html=player_cards.render_tappable_player_html,
        open_player_quick_view=fixture_dossier,
        render_recommendation_feedback=lambda **_kwargs: None,
    )
    ui_primitives.render_section_header("Available Targets", eyebrow="Waiver Snapshot", subtitle="Position leaders remain compact and open the canonical dossier.")
    waivers_ui.render_free_agent_summary_cards(
        players, "value_score", player_display_name=lambda row: str(row.get("name")),
        cached_headshot_data_url=lambda _player_id: "", asset_initials=lambda _name: "SQ",
    )


def _live_draft() -> None:
    _marker(
        "live-draft",
        ("Who should I draft next?", "Available Player Rankings", "Live Team Rankings", "Draft Board"),
    )
    _workspace("Live Draft", "Read-only recommendations for an active synthetic Sleeper room.")
    source = (
        ("Fixture Quarterback", "QB", "KC", 24, "Star", 9200, "Top remaining value and the clearest lineup need.", "Starts immediately in the open superflex spot."),
        ("Fixture Receiver", "WR", "MIN", 22, "Core Starter", 8900, "Preserves value while adding a young weekly starter.", "Adds strength without forcing positional need."),
        ("Fixture Running Back", "RB", "MIA", 25, "Starter", 8400, "Near-term production supports the active roster window.", "Improves flex depth immediately."),
        ("Fixture Tight End", "TE", "DET", 23, "Upside", 7900, "Format-adjusted upside remains inside the current tier.", "Adds a developmental option behind the starter."),
    )
    recommendations = [
        {
            "player_id": f"live-{index}", "name": name, "position": position,
            "team": team, "age": age, "tier": tier, "overall_rank": index,
            "position_rank": index, "base_value": value,
            "league_adjusted_draft_score": value + 4,
            "recommendation_role": "Recommended pick" if index == 1 else "Alternative",
            "recommendation_reason": reason,
            "position_need_impact": "Fills roster need" if index == 1 else "Best available value",
            "immediate_roster_impact": impact,
            "confidence": "High" if index == 1 else "Moderate",
            "adp_delta": 6.0 - index,
            "recommendation_label": "Best Available" if index == 1 else "Alternative",
            "movement": 0,
        }
        for index, (name, position, team, age, tier, value, reason, impact) in enumerate(source, start=1)
    ]
    state = {
        "is_my_pick": False, "picks_until_mine": 3,
        "my_upcoming_picks": [12, 17, 36], "current_pick": 9,
        "current_round": 1, "current_manager_name": "Fixture Manager",
        "current_team_name": "Fixture Football Operations",
        "positional_run": "WR 3 | RB 2", "recommendations": recommendations,
        "rankings": pd.DataFrame(recommendations), "team_rankings": pd.DataFrame(),
        "pick_rows": [],
    }
    live_draft_ui._render_on_clock(state)
    live_draft_ui._render_recommendations(state)
    live_draft_ui._render_live_rankings(state, score_label="Dynasty Score")
    live_draft_ui._render_live_team_rankings(state)
    live_draft_ui._render_pick_board(state)


def _player_dossier() -> None:
    _marker(
        "player-dossier",
        (
            "Identity",
            "Recommendation",
            "Dynasty value",
            "Why we value him this way",
            "Current fantasy evidence",
            "Recent News",
            "More details",
        ),
    )
    _workspace("Player Dossier", "Canonical front-office player intelligence.")
    current = {
        "stats_season": 2025, "games_played": 12, "fantasy_points_ppr": 205.2,
        "ppg": 17.1, "receptions": 72, "receiving_yards": 1080, "receiving_tds": 9,
        "position_finish": 5, "position": "WR",
    }
    resume = player_history.build_career_resume(
        [
            current,
            {**current, "stats_season": 2024, "games_played": 17, "fantasy_points_ppr": 318.4, "ppg": 18.7, "receiving_yards": 1540, "receiving_tds": 12, "position_finish": 2},
            {**current, "stats_season": 2023, "games_played": 16, "fantasy_points_ppr": 251.2, "ppg": 15.7, "receiving_yards": 1160, "receiving_tds": 8, "position_finish": 9},
        ],
        position="WR",
        current_season=2025,
        source_note="Synthetic verified fixture.",
        historical_cache_loaded=True,
    )
    more_open = bool(st.session_state.get("ui_dossier_more_open", False))
    stats = player_quick_view.build_stats_view(pd.Series(current))
    render_html_fragment(
        "<section class='player-quick-view-shell dg-quick-view-panel'>"
        "<div class='player-quick-view-header-band player-quick-view-hero'>"
        "<div class='player-quick-view-avatar' aria-hidden='true'>FP</div>"
        "<div class='player-quick-view-copy'><div class='player-quick-view-source'>Identity</div>"
        "<h3 class='player-quick-view-name'>Fixture Playmaker</h3>"
        "<div class='player-quick-view-meta'>WR · MIN</div>"
        "<div class='player-quick-view-age'>Age 25</div>"
        + player_quick_view.labeled_signal_badges_html(
            (("Health", "Questionable"), ("Depth-chart role", "Featured"), ("Roster impact", "Core"))
        )
        + "</div></div></section>"
    )
    render_html_fragment(player_quick_view.recommendation_context_html(
        "Verified production and stable availability support the current value.",
        "",
        action="Hold",
        confidence="High confidence",
    ))
    render_html_fragment(
        "<div class='pqv-decision-grid'>"
        "<div class='pqv-decision-primary'>"
        + player_quick_view.rank_strip_html(
            overall_display="#12",
            position_display="WR #5",
            scoring_format="PPR",
            dynasty_value="8,920",
        )
        + (player_quick_view.current_season_summary_html(stats) or "")
        + "</div>"
        "<div class='pqv-decision-secondary'>"
        + player_quick_view.why_this_recommendation_html(
            (
                ("Production", "17.1 PPR PPG"),
                ("Role", "Featured"),
                ("Health", "Questionable"),
                ("Team fit", "Core roster piece"),
            )
        )
        + "</div></div>"
    )
    st.button("Open in Trade Hub", use_container_width=True)
    st.button("Add to GM Targets", use_container_width=True)
    st.button("Share Recommendation", use_container_width=True)
    st.button("Feedback", use_container_width=True)
    player_quick_view.render_news(
            [
                player_quick_view.NewsItem(
                    headline="Fixture role remains stable.",
                    source="CBS Sports",
                    freshness="35m",
                    snippet="No new injury designation.",
                    url="https://www.cbssports.com/example",
                )
            ],
            include_shell=True,
            status="ok",
            omit_empty=True,
        )

    def _toggle_more() -> None:
        st.session_state["ui_dossier_more_open"] = not bool(
            st.session_state.get("ui_dossier_more_open", False)
        )

    st.button(
        "Hide details" if more_open else "More details",
        key="ui_dossier_more_toggle",
        use_container_width=True,
        on_click=_toggle_more,
    )
    if more_open:
        player_quick_view.render_current_season(stats)
        render_html_fragment(
            player_quick_view.career_resume_html(
                resume, expanded=True, position="RB", years_exp=6
            )
        )
        render_html_fragment(
            player_quick_view.career_timeline_html(
                resume,
                expanded=True,
                include_achievements=False,
            )
        )
        render_html_fragment(player_quick_view.executive_snapshot_html(player_quick_view.ExecutiveSnapshot(
            years_in_league="4 seasons", draft_capital="2022 / Round 1 / Pick 18",
            college="Fixture State", height="6'2\"", weight="208 lb", bye_week="6",
        )))
        st.caption("Athletic profile, college production, and methodology remain secondary.")


def _design_system() -> None:
    """Canonical geometry surface: disclosures, deep analysis, filters, footer, trade."""
    _marker(
        "design-system",
        (
            "Disclosures",
            "Deep Analysis",
            "Filters",
            "Trade",
            "Footer",
        ),
    )
    with st.container(key="mobile_gm_sheet_trigger_design_system"):
        render_html_fragment(brand_identity.gm_orb_floating_trigger_html())
        st.button(
            brand_identity.GM_ORB_ARIA_LABEL,
            help=brand_identity.GM_ORB_HELP,
            type="primary",
            key="mobile_gm_sheet_open_design_system",
        )
    _workspace("Design System", "Canonical component-family geometry validation.")
    ui_primitives.render_section_header("Disclosures", weight="secondary")
    with st.expander("League Insights", expanded=False):
        st.caption("Token-backed disclosure row.")
    with st.expander("Team Snapshot", expanded=False):
        st.caption("Same disclosure family as League Insights.")
    with st.expander("League Pulse", expanded=False):
        st.caption("Same disclosure family as Team Snapshot.")
    ui_primitives.render_section_header("Deep Analysis", weight="support")
    workspace_ui.render_home_quick_actions(
        [
            ("League Overview", "rankings"),
            ("My Team", "my_team"),
            ("Trade Hub", "trade_hub"),
            ("Draft Center", "draft_summary"),
        ],
        commit_platform_destination=lambda _route: None,
    )
    ui_primitives.render_section_header("Filters", weight="secondary")
    inject_global_styles(PLAYER_ASSET_EXPLORER_CSS)
    with st.container(key="player_asset_explorer_design_system"):
        st.text_input("Search players", key="player_asset_explorer_search_ds", placeholder="Search", autocomplete="off")
        st.pills(
            "Asset type",
            options=["Players", "Picks", "All"],
            key="player_asset_explorer_scope_ds",
        )
        st.selectbox(
            "Position",
            options=["Any", "QB", "RB", "WR", "TE"],
            key="player_asset_explorer_pos_ds",
        )
    ui_primitives.render_section_header("Trade", weight="secondary")
    idea = {
        "partner_roster_id": "fixture-partner",
        "partner_team_name": "Lakefront Franchise",
        "tag": "Get Younger + Pick",
        "my_score": 8540,
        "their_score": 9028,
        "trade_gain": 488,
        "fit_grade": "Strong",
        "market_realism_label": "Plausible",
        "trade_confidence_label": "Medium",
        "reasoning_summary": "Adds a younger weekly starter and future flexibility.",
        "_display_section": "Age Optimization",
        "send_assets": [{"asset_type": "player", "player_id": "6794", "name": "Synthetic Veteran RB"}],
        "receive_assets": [
            {"asset_type": "player", "player_id": "8155", "name": "Synthetic Young WR"},
            {"asset_type": "pick", "name": "2027 2nd"},
        ],
    }

    def detail_assets(assets: list[dict]) -> str:
        return "<div class='trade-assets'>" + "".join(
            (
                "<article class='trade-asset-row trade-asset-row-player'>"
                f"<div class='trade-asset-name'>{asset.get('name')}</div></article>"
            )
            if asset.get("asset_type") == "player"
            else (
                "<article class='trade-asset-row trade-asset-row-pick'>"
                f"<div class='trade-asset-name'>{asset.get('name')}</div></article>"
            )
            for asset in assets
        ) + "</div>"

    trade_hub_ui.render_trade_idea_card(
        idea,
        0,
        key_prefix="ci_design_system_trade",
        format_score=lambda value: f"{float(value):,.0f}",
        tidy_label=lambda value: str(value).replace("_", " ").title(),
        trade_target_reason=lambda _: "Synthetic target rationale.",
        trade_partner_reason=lambda _: "Synthetic partner rationale.",
        trade_confidence_reason=lambda _: "Synthetic confidence rationale.",
        trade_value_verdict=lambda _: "Balanced",
        trade_display_confidence_label=lambda _: "Medium",
        injury_display_context=lambda _: {"risk": False},
        glyph_chip_html=lambda *args, **kwargs: "",
        assets_html=detail_assets,
        render_tappable_player_html=player_cards.render_tappable_player_html,
        render_player_dossier=lambda *_args, **_kwargs: None,
    )
    legal_pages.render_legal_footer(current_page="", on_navigate=lambda _page: None)


def _guest_landing() -> None:
    """Logged-out landing fixture: integrated welcome + account + import.

    Deliberately omits executive_workspace_shell / command actions — guest
    landing ownership must not mount live SELECT/ALERTS/YOU controls.
    Optional ``fixture_auth`` query: guest | pending_ambiguous | pending_definite.
    """

    from modules import auth_supabase
    from modules import marketing_landing
    from modules import platform_import_ui

    fixture_auth = str(st.query_params.get("fixture_auth", "guest")).strip().lower()
    st.session_state.pop(auth_supabase.PENDING_EMAIL_CONFIRMATION_KEY, None)
    st.session_state.pop(auth_supabase.CONFIRMATION_REQUIRED_KEY, None)
    st.session_state.pop(auth_supabase.ACCOUNT_SIGNUP_CHECK_EMAIL_KEY, None)
    st.session_state["launch_auth_mode"] = "guest"

    marketing_landing.render_marketing_landing()

    config = {
        "enabled": True,
        "url": "https://example.supabase.co",
        "anon_key": "anon",
    }
    if fixture_auth == "pending_ambiguous":
        auth_supabase.enter_pending_email_confirmation(
            st.session_state,
            "existing@example.com",
            payload={
                "id": "user-fake",
                "email": "existing@example.com",
                "email_confirmed_at": None,
                "confirmation_sent_at": "2026-08-12T20:00:00Z",
                "identities": [],
            },
        )
    elif fixture_auth == "pending_definite":
        auth_supabase.enter_pending_email_confirmation(
            st.session_state,
            "fresh@example.com",
            payload={
                "id": "user-new",
                "email": "fresh@example.com",
                "email_confirmed_at": None,
                "confirmation_sent_at": "2026-08-12T20:00:00Z",
                "identities": [
                    {"id": "ident-1", "user_id": "user-new", "provider": "email"}
                ],
            },
        )

    account_ui.render_mobile_auth_entry(config=config)
    platform_import_ui.render_platform_import_panel(pd.DataFrame())
    with st.form("guest_landing_fixture_import_form", clear_on_submit=False):
        st.text_input(
            "Sleeper Username",
            key="guest_landing_fixture_username",
            placeholder="Enter your Sleeper username",
            autocomplete="username",
        )
        st.form_submit_button("Load My Leagues", use_container_width=True, type="primary")
    marketing_landing.render_marketing_landing_deferred()

    st.markdown("<div data-fgl-guest-landing='1'></div>", unsafe_allow_html=True)
    markers = (
        "Import your league",
        "Load My Leagues",
        "Save your leagues"
        if fixture_auth == "guest"
        else "Check your email",
    )
    _marker("guest-landing", markers)
    st.caption("Guest landing fixture — zero live executive command headers.")


def main() -> None:
    st.set_page_config(page_title="FantasyGM Lab deterministic UI validation", layout="wide", initial_sidebar_state="collapsed")
    # Match production inject order from app.py script start, then command header
    # (late, like render_top_league_identity_header). MOBILE_INTERACTION_OVERLAY_CSS
    # is already concatenated into APP_CSS — do not re-inject after the command owner.
    inject_global_styles(APP_CSS)
    inject_global_styles(MOBILE_VISUAL_POLISH_CSS)
    inject_global_styles(FOUNDER_BETA_UX_CSS)
    inject_global_styles(DASHBOARD_WORKFLOW_CSS)
    inject_global_styles(EXECUTIVE_COMMAND_HEADER_CSS)
    inject_global_styles(PLAYER_QUICK_VIEW_CSS)
    inject_global_styles(WAIVERS_PRESENTATION_CSS)
    surface = str(st.query_params.get("surface", "dashboard")).strip().lower()
    fixture_nav = _text(st.query_params.get("fixture_nav"))
    if fixture_nav:
        _fixture_open_destination(fixture_nav)
    if surface not in SURFACES:
        st.error(f"Unknown validation surface: {surface}")
        st.stop()
    {
        "dashboard": _dashboard,
        "league": _league,
        "trade": _trade,
        "my-team": _my_team,
        "waivers": _waivers,
        "navigation": _navigation,
        "live-draft": _live_draft,
        "player-dossier": _player_dossier,
        "header-geometry": _header_geometry,
        "design-system": _design_system,
        "guest-landing": _guest_landing,
        "trade-analyzer": _trade_analyzer,
    }[surface]()
    _render_fixture_ack_markers()
    st.caption("Synthetic fixture only — no credentials, personal identifiers, or production data.")


if __name__ == "__main__":
    main()

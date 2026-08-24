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


def _padded_sleeper_style_headshot_data_uri() -> str:
    """Synthetic transparent PNG kept as a fallback fixture only."""

    import base64
    from io import BytesIO

    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((72, 8, 168, 108), fill=(210, 168, 126, 255))
    draw.rectangle((88, 96, 152, 168), fill=(36, 64, 118, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _production_equivalent_headshot_src(sleeper_id: str) -> str:
    """Use the same Sleeper CDN path production uses, with a vendored JPEG fallback."""

    from modules.player_images import get_player_headshot_url, headshot_data_url

    fixture_png = ROOT / "tests" / "fixtures" / "sleeper_headshots" / f"{sleeper_id}.png"
    fixture_jpg = ROOT / "tests" / "fixtures" / "sleeper_headshots" / f"{sleeper_id}.jpg"
    if fixture_png.is_file():
        return headshot_data_url(fixture_png.read_bytes())
    if fixture_jpg.is_file():
        return headshot_data_url(fixture_jpg.read_bytes())
    return get_player_headshot_url(sleeper_id)

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
    player_awards,
    player_profile_ui,
    player_quick_view,
    player_tier_identity,
    trade_hub_ui,
    ui_primitives,
    waivers_ui,
    workspace_ui,
    account_ui,
    player_asset_explorer_ui,
    valuation_archetype_ui,
    valuation_archetypes,
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
from modules.trade_detail_styles import TRADE_DETAIL_CSS
from modules.decision_surface_dialog_styles import DECISION_SURFACE_DIALOG_CSS
from modules.methodology_page_styles import METHODOLOGY_PAGE_CSS
from modules.live_draft_styles import LIVE_DRAFT_CSS
from modules.trade_analyzer_styles import TRADE_ANALYZER_CSS
from modules import trade_analyzer_assembly as analyzer_assembly
from modules import trade_analyzer_builder
from modules import trade_analyzer_ui
from modules.player_asset_explorer_styles import PLAYER_ASSET_EXPLORER_CSS
from modules.ux_polish_styles import FOUNDER_BETA_UX_CSS
from modules.html_rendering import inject_global_styles, render_html_fragment
from modules import viewport_preservation


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
    "player-asset-explorer",
    "methodology",
    "viewport-preserve",
    "recaps",
    "alerts",
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
    if notify_mode == "injury":
        fixture_tiles = [
            {
                "label": "News Alert",
                "value": "Ashton Jeanty: Injury update",
                "note": "Player status has not yet been confirmed.",
                "recommendation_id": "news-event:12527:injury_chain",
                "route_key": "my_team",
                "route_player_id": "12527",
                "player_id": "12527",
                "news_player_name": "Ashton Jeanty",
                "news_event_type": "INJURY",
                "news_event_severity": "HIGH",
                "news_roster_relationship": "MY_BENCH",
                "news_corroboration": "AWAITING STATUS UPDATE",
                "news_significant_injury_event": True,
                "news_age_seconds": 1260,
                "news_age_label": "21m",
            }
        ]
    elif notify_mode != "quiet":
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
        def _fixture_route_row(label: str, page_key: str, **button_kwargs) -> None:
            with st.container(key=f"mobile_sheet_row_{page_key}"):
                st.button(
                    label,
                    key=f"mobile_sheet_nav_{page_key}_fixture",
                    use_container_width=True,
                    **button_kwargs,
                )

        st.caption("Core")
        _fixture_route_row(
            "Dashboard",
            "dashboard",
            type="primary",
        )
        _fixture_route_row("My Team", "my_team")
        _fixture_route_row("League Overview", "rankings")
        _fixture_route_row("League Recaps / History", "league_recaps")
        _fixture_route_row(
            "Trade Hub",
            "trade_hub",
            on_click=lambda: st.session_state.update(
                _fixture_gm_open=False,
                _fixture_gm_destination="trade_hub",
            ),
        )
        _fixture_route_row("Waivers", "waivers")
        _fixture_route_row("Trade Analyzer", "trade_analyzer")
        _fixture_route_row("Draft Center", "draft_summary")
        _fixture_route_row("GM Targets", "gm_targets")
        _fixture_route_row("Premium", "premium")
        st.caption("Support")
        _fixture_route_row("Players", "players")
        st.caption("Experimental · Early access")
        st.markdown(
            "<div class='mobile-gm-experimental-note'>Early access capability. Available when enabled for your account.</div>",
            unsafe_allow_html=True,
        )
        _fixture_route_row("Labs [EXPERIMENTAL]", "methodology")


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
    from modules import game_plan_package

    st.session_state.setdefault(game_plan_package.PACKAGE_KEY, {"built_at": __import__("time").time()})
    _marker(
        "dashboard",
        (
            "Today's Game Plan",
            "What Changed",
            "Explore",
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
                "route_player_id": "8155",
                "presentation": {
                    "value_edge": "+240",
                    "send": [
                        {
                            "asset_type": "player",
                            "player_id": "6794",
                            "name": "Tyrone Tracy",
                            "position": "RB",
                            "team": "NYG",
                        }
                    ],
                    "receive": [
                        {
                            "asset_type": "player",
                            "player_id": "8155",
                            "name": "Pat Bryant",
                            "position": "WR",
                            "team": "DEN",
                        },
                        {
                            "asset_type": "pick",
                            "label": "2027 Round 3",
                            "season": "2027",
                            "round": "3",
                        },
                    ],
                },
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
                "presentation": {
                    "value_edge": "+180",
                    "send": [
                        {
                            "asset_type": "player",
                            "player_id": "6794",
                            "name": "Tyrone Tracy",
                            "position": "RB",
                            "team": "NYG",
                        }
                    ],
                    "receive": [
                        {
                            "asset_type": "player",
                            "player_id": "8155",
                            "name": "Pat Bryant",
                            "position": "WR",
                            "team": "DEN",
                        },
                        {
                            "asset_type": "pick",
                            "label": "2027 Round 3",
                            "season": "2027",
                            "round": "3",
                        },
                    ],
                },
            },
            {
                "label": "Top Waiver Opportunity",
                "value": "Add reliable depth",
                "note": "Available fixture player with a current role.",
                "recommendation_id": "fixture-waiver-1",
                "route_key": "waivers",
                "presentation": {
                    "player": {
                        "asset_type": "player",
                        "player_id": "9221",
                        "name": "Brashard Smith",
                        "position": "RB",
                        "team": "KC",
                        "role": "Backup With Upside",
                    }
                },
            },
            {
                "label": "Injury Alert",
                "value": "1 injured starter",
                "note": "A projected starter is unavailable this week.",
                "presentation": {
                    "players": [
                        {
                            "asset_type": "player",
                            "player_id": "9226",
                            "name": "Cam Skattebo",
                            "position": "RB",
                            "team": "NYG",
                        }
                    ]
                },
            },
        ]
    else:
        items = [
            {"label": "Roster Pressure", "value": "2 Over", "note": "Cut or trade now to clear the Sleeper roster limit."},
            {
                "label": "Injury Alert",
                "value": "2 injured starters",
                "note": "Projected starters are unavailable this week.",
                "presentation": {
                    "players": [
                        {
                            "asset_type": "player",
                            "player_id": "9226",
                            "name": "Cam Skattebo",
                            "position": "RB",
                            "team": "NYG",
                            "roster_relevance": "starter",
                        },
                        {
                            "asset_type": "player",
                            "player_id": "9500",
                            "name": "Kenyon Sadiq",
                            "position": "TE",
                            "team": "LAR",
                            "roster_relevance": "starter",
                        },
                    ]
                },
            },
            {"label": "Biggest Team Need", "value": "Strengthen QB depth", "note": "The current starter room has the clearest upgrade path."},
            {"label": "Depth Upgrade", "value": "Optimize flex", "note": "Additional recommendation kept behind progressive disclosure."},
            {
                "label": "Top Trade Opportunity",
                "value": "Explore a balanced swap",
                "note": "A synthetic recommendation used only for layout validation.",
                "route_key": "trade_hub",
                "presentation": {
                    "value_edge": "+180",
                    "send": [
                        {
                            "asset_type": "player",
                            "player_id": "6794",
                            "name": "Tyrone Tracy",
                            "position": "RB",
                            "team": "NYG",
                        }
                    ],
                    "receive": [
                        {
                            "asset_type": "player",
                            "player_id": "8155",
                            "name": "Pat Bryant",
                            "position": "WR",
                            "team": "DEN",
                        },
                        {
                            "asset_type": "pick",
                            "label": "2027 Round 3",
                            "season": "2027",
                            "round": "3",
                        },
                    ],
                },
            },
            {
                "label": "Top Waiver Opportunity",
                "value": "Add reliable depth",
                "note": "Available fixture player with a current role.",
                "route_key": "waivers",
                "presentation": {
                    "player": {
                        "asset_type": "player",
                        "player_id": "9221",
                        "name": "Brashard Smith",
                        "position": "RB",
                        "team": "KC",
                        "role": "Backup With Upside",
                    }
                },
            },
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
    # Production Dashboard HIT reconstructs from the stored package. Render that
    # representation so layout CI fails if presentation is dropped on hydrate.
    serialized = {
        "briefing": game_plan_package.serialize_daily_briefing(game_plan),
        "entitlement": entitlement,
        "built_at": __import__("time").time(),
    }
    st.session_state[game_plan_package.PACKAGE_KEY] = serialized
    game_plan = game_plan_package.briefing_from_package(serialized)
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
        {
            "roster_id": "1",
            "team_name": "Fixture Football Operations",
            "owner_name": "Fixture Manager",
            "avatar_url": "https://sleepercdn.com/images/v2/icons/player_default.webp",
            "avg_age": 25.8,
            "starter_score": 91,
            "bench_score": 75,
            "injury_impact_score": 2,
            "franchise_score": 125310,
            "power_score": 12400,
            "draft_capital": 4200,
        },
        {
            "roster_id": "2",
            "team_name": "Young Core",
            "owner_name": "Alex",
            "avatar_url": "https://sleepercdn.com/images/v2/icons/player_default.webp",
            "avg_age": 23.9,
            "starter_score": 84,
            "bench_score": 81,
            "injury_impact_score": 0,
            "franchise_score": 133914,
            "power_score": 11800,
            "draft_capital": 5100,
        },
        {
            "roster_id": "3",
            "team_name": "Veteran Window",
            "owner_name": "Casey",
            "avatar_url": "",
            "avg_age": 28.1,
            "starter_score": 97,
            "bench_score": 68,
            "injury_impact_score": 5,
            "franchise_score": 119000,
            "power_score": 13100,
            "draft_capital": 2800,
        },
        {
            "roster_id": "4",
            "team_name": "American Njigba Warriors of the Pacific Northwest",
            "owner_name": "very-long-owner-handle-amatl7-example",
            "avatar_url": "",
            "avg_age": 26.2,
            "starter_score": 80,
            "bench_score": 70,
            "injury_impact_score": 1,
            "franchise_score": 121500,
            "power_score": 11000,
            "draft_capital": 3300,
        },
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
            {"label": "Franchise Rank", "value": "#3", "note": "Total asset-base rank", "comparison": comparisons["Franchise Rank"]},
        ],
        render_tiles=_tiles,
        render_snapshot=lambda snapshot: workspace_ui.render_summary_tiles(
            snapshot,
            compact=True,
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
        render_page_context=lambda: valuation_archetype_ui.render_workspace_archetype_affordance(
            valuation_archetypes.BALANCED_DYNASTY,
            key=f"fixture_workspace_valuation_archetype_{briefing_mode}",
            league_name=HEADER_LEAGUE_FIXTURES.get("default", "Synthetic Founder Beta League"),
            team_name="Fixture Football Operations",
            season="2026",
        ),
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
    if str(st.query_params.get("open_modal") or "").strip().lower() == "franchise":
        workspace_ui.render_canonical_summary_tile_detail_dialog(
            {
                "label": "Franchise Rank",
                "value": "#3",
                "comparison": comparisons["Franchise Rank"],
            }
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
    from modules import draft_center_ui as _draft_center_ui
    from modules import executive_table_ui as _executive_table_ui

    _executive_table_ui.render_executive_metric_tiles(
        _draft_center_ui.build_draft_summary_metric_tiles(
            owners=12,
            team_count=12,
            missing_count=0,
            missing_names="None",
            top_pick_team="Very Long Dynasty Franchise Name That Should Wrap",
            top_pick_count=9,
            firsts=24,
            seconds=24,
            thirds=12,
            ownership_note="Current-year picks excluded after completed rookie draft",
        )
    )
    workspace_ui.render_summary_tiles(
        _draft_center_ui.build_draft_summary_headline_tiles(
            draft_completed=True,
            current_draft_year=2026,
            draft_status="complete",
            top_team={
                "team_name": "patrickshea",
                "draft_capital": 29805,
                "pick_count": 8,
            },
            best_future={
                "team_name": "patrickshea",
                "future_draft_capital": 29805,
            },
            peak_capital=29805,
            peak_future=29805,
            pick_status_note="Current-year picks excluded after completed rookie draft",
        ),
        compact=True,
        key_prefix="league_draft_capital_headline",
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
    _marker("trade-analyzer", ("You receive", "You send", "Analyze Trade", "Build the trade"))
    _workspace("Trade Analyzer", "Evaluate an offer you received.")
    toa_mode = str(st.query_params.get("toa") or "builder").strip().lower()
    st.markdown(
        "<div class='toa-partner-block'>"
        "<div class='toa-stage-kicker'>Build the trade</div>"
        "<div class='toa-block-title'>Partner</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.selectbox(
        "Partner",
        ["Lakefront Franchise | Alex", "Harbor Club | Jordan"],
        key="fixture_trade_receive_partner",
        label_visibility="collapsed",
    )
    pool_receive = [
        {"asset_type": "player", "player_id": "r1", "name": "Synthetic Young WR", "position": "WR", "team": "MIA", "score": 4200, "owner_roster_id": "partner"},
        {"asset_type": "pick", "label": "2027 1st", "name": "2027 1st", "season": 2027, "round": 1, "score": 1800, "owner_roster_id": "partner"},
    ]
    pool_send = [
        {"asset_type": "player", "player_id": "s1", "name": "Synthetic Veteran RB", "position": "RB", "team": "NE", "score": 3100, "owner_roster_id": "me"},
        {"asset_type": "player", "player_id": "s2", "name": "Depth WR", "position": "WR", "team": "CHI", "score": 900, "owner_roster_id": "me"},
    ]
    if "fixture_toa_receive" not in st.session_state:
        st.session_state["fixture_toa_receive"] = list(pool_receive)
    if "fixture_toa_send" not in st.session_state:
        st.session_state["fixture_toa_send"] = [pool_send[0]]
    if toa_mode == "result":
        from modules import trade_offer_analyzer as toa

        fit = {
            "available": True,
            "value_delta": 900,
            "explanation": "Gaining the stronger dynasty asset.",
            "lineup_summary": "Starter lineup stays close to neutral.",
            "strategy_summary": "Retool-friendly.",
            "injury_summary": "Health context stays close to neutral.",
            "roster_fit_verdict": "Mixed Fit",
            "component_scores": {
                "value": 2,
                "lineup": 1,
                "needs": 1,
                "age": 0,
                "draft": 0,
                "strategy": 1,
                "injury": 0,
            },
        }
        verdict = toa.decide_offer_verdict(
            fit,
            send_assets=st.session_state["fixture_toa_send"],
            receive_assets=st.session_state["fixture_toa_receive"],
        )
        st.markdown(
            toa.build_offer_result_card_html(
                verdict,
                send_assets=st.session_state["fixture_toa_send"],
                receive_assets=st.session_state["fixture_toa_receive"],
                league_name="Synthetic Founder Beta League",
                format_label="Superflex",
                strategy_label="Retool",
                partner_name="Lakefront Franchise",
            ),
            unsafe_allow_html=True,
        )
        st.button("Share Trade Analysis", key="fixture_toa_share")
        return
    st.session_state["trade_send_assets"] = list(st.session_state["fixture_toa_send"])
    st.session_state["trade_receive_assets"] = list(st.session_state["fixture_toa_receive"])
    analyzer_assembly.ensure_catalogs(
        st.session_state,
        context_key="fixture-toa",
        my_roster_id="me",
        partner_roster_id="partner",
        players_df=pd.DataFrame(
            [
                {
                    "player_id": "r1",
                    "name": "Synthetic Young WR",
                    "position": "WR",
                    "team": "MIA",
                    "value_score": 4200,
                    "score": 4200,
                    "age": 23,
                    "status": "Active",
                    "opportunity_label": "Elite Opportunity",
                    "owner_roster_id": "partner",
                    "owner_team_name": "Lakefront Franchise",
                },
                {
                    "player_id": "s1",
                    "name": "Synthetic Veteran RB",
                    "position": "RB",
                    "team": "NE",
                    "value_score": 3100,
                    "score": 3100,
                    "age": 27,
                    "status": "Active",
                    "opportunity_label": "Locked starter",
                    "owner_roster_id": "me",
                    "owner_team_name": "Harbor Club",
                },
                {
                    "player_id": "s2",
                    "name": "Depth WR",
                    "position": "WR",
                    "team": "CHI",
                    "value_score": 900,
                    "score": 900,
                    "age": 24,
                    "status": "Active",
                    "owner_roster_id": "me",
                    "owner_team_name": "Harbor Club",
                },
            ]
        ),
        my_player_ids=["s1", "s2"],
        partner_player_ids=["r1"],
        my_picks=[],
        partner_picks=[
            {
                "label": "2027 1st",
                "season": 2027,
                "round": 1,
                "score": 1800,
                "owner_roster_id": "partner",
                "owner_team_name": "Lakefront Franchise",
            }
        ],
        player_owner_map={
            "r1": {"owner_roster_id": "partner", "owner_team_name": "Lakefront Franchise"},
            "s1": {"owner_roster_id": "me", "owner_team_name": "Harbor Club"},
            "s2": {"owner_roster_id": "me", "owner_team_name": "Harbor Club"},
        },
    )
    trade_analyzer_ui.render_trade_analyzer_assembly(
        my_roster_id="me",
        partner_roster_id="partner",
        partner_name="Lakefront Franchise",
        league_ready=True,
    )
    st.markdown(
        "<div class='toa-analyze-row' data-toa-analyze-ready='1'></div>",
        unsafe_allow_html=True,
    )
    st.button("Analyze Trade", key="fixture_toa_analyze", type="primary", use_container_width=False)


def _player_asset_explorer() -> None:
    _marker("player-asset-explorer", ("Asset type", "Available Players", "Players currently unrostered"))
    _workspace("Players", "Search the dynasty market for this league.")
    st.session_state.setdefault("player_asset_explorer_scope", "Available Players")
    frame = pd.DataFrame(
        [
            {
                "player_id": "p-rostered",
                "name": "Rostered Star WR",
                "position": "WR",
                "team": "KC",
                "age": 25,
                "status": "Active",
                "value_score": 9100,
                "opportunity_label": "Locked starter",
            },
            {
                "player_id": "p-fa",
                "name": "Unrostered Sleeper RB",
                "position": "RB",
                "team": "NE",
                "age": 23,
                "status": "Active",
                "value_score": 2400,
                "opportunity_label": "Available in this league",
            },
        ]
    )
    player_asset_explorer_ui.render_player_asset_explorer(
        df_players=frame,
        draft_picks=[],
        roster_player_map={"1": ("p-rostered",)},
        score_field="value_score",
        score_label="Dynasty Value",
        search_assets=lambda *_args, **_kwargs: pd.DataFrame(),
        render_player_scan_cards=lambda results, **_kwargs: st.write(
            results["name"].tolist()
        ),
        is_injury_status=lambda _row: False,
        current_draft_year=2026,
        ownership_known=True,
    )


def _trade() -> None:
    from modules import player_quick_view_bridge
    from modules import trade_detail_navigation
    from modules import compact_fantasy_assets as _compact_assets
    from modules import player_images as _player_images
    import app as production_app

    def _local_headshot(player_id: object) -> str:
        return _production_equivalent_headshot_src(str(player_id or ""))

    _player_images.get_player_image_url = _local_headshot
    _compact_assets.get_player_image_url = _local_headshot
    _marker("trade", ("Balance", "Review package"))
    _workspace("Trade Hub", "Negotiation workspace for team-specific trade ideas.")
    bridged_player_request = player_quick_view_bridge.consume_player_quick_view_request(
        st.session_state,
        key="fixture_trade_player_quick_view_bridge",
    )
    if bridged_player_request:
        st.session_state["ui_trade_pqv_player_id"] = bridged_player_request["player_id"]
    pending_shortcut_request = st.session_state.pop(
        trade_detail_navigation.PENDING_PQV_KEY,
        {},
    )
    if pending_shortcut_request:
        st.session_state["ui_trade_pqv_player_id"] = pending_shortcut_request["player_id"]
    trade_hub_ui.render_trade_strategy_selector(
        automatic_strategy="retool",
        automatic_strategy_label="Retool",
        automatic_archetype="Flexible contender",
        key="ci_trade_strategy",
    )
    with st.expander("Search Around a Player — secondary tool", expanded=False):
        trade_hub_ui.render_trade_hub_section_header(
            "Search Around a Player",
            eyebrow="Secondary Tool",
            subtitle="Pick a player, then run search only when you want targeted return packages.",
        )
        st.caption("Fixture search stays on-demand. No automatic secondary search.")
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
        "send_assets": [{"asset_type": "player", "player_id": "11655", "name": "Tyrone Tracy"}],
        "receive_assets": [
            {"asset_type": "player", "player_id": "12492", "name": "Pat Bryant"},
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
        roster = {
            "11655": ("Tyrone Tracy", "RB", "NYG", True),
            "12492": ("Pat Bryant", "WR", "DEN", False),
            "4199": ("Aaron Jones", "RB", "MIN", True),
            "7090": ("Darnell Mooney", "WR", "ATL", False),
            "6904": ("Jalen Hurts", "QB", "PHI", True),
        }
        name, position, team, veteran = roster.get(player_id, ("Pat Bryant", "WR", "DEN", False))
        stats = player_quick_view.build_stats_view(
            pd.Series(
                {
                    "position": position,
                    "stats_season": 2025,
                    "games_played": 16,
                    "rush_attempts": 240 if veteran else 0,
                    "rushing_yards": 980 if veteran else 0,
                    "targets": 48 if veteran else 110,
                    "receptions": 36 if veteran else 72,
                    "receiving_yards": 280 if veteran else 1080,
                    "fantasy_points_ppr": 210 if veteran else 205,
                    "ppg": 13.1 if veteran else 17.1,
                }
            )
        )
        award_rows = [
            {
                "position": position,
                "stats_season": 2024,
                "games_played": 17,
                "rushing_yards": 1200 if veteran else 0,
                "receiving_yards": 0 if veteran else 1540,
                "receiving_tds": 0 if veteran else 12,
                "fantasy_points_ppr": 280,
                "ppg": 16.4,
                "position_finish": 3 if veteran else 2,
            }
        ]
        badges = player_awards.build_player_awards(award_rows, position=position)
        st.markdown(
            "<div class='player-quick-view-shell' "
            f"data-trade-dossier-player='{player_id}'>"
            + player_quick_view.pqv_hero_html(
                avatar_html="<div class='player-quick-view-avatar' aria-hidden='true'>"
                f"{'SV' if veteran else 'SY'}</div>",
                name=name,
                position=position,
                team=team,
                age_text="26",
                source_label="Trade Hub",
                role_label="Starter",
                overall_display="#18" if veteran else "#22",
                position_display=f"{position} #8",
                dynasty_value="7,800" if veteran else "8,140",
                scoring_format="PPR",
                identity=player_tier_identity.resolve_player_tier_identity(
                    stored_tier="Star" if veteran else "Elite"
                ),
                include_tier_legend=True,
            )
            + (player_quick_view.current_season_summary_html(stats) or "")
            + player_quick_view.why_this_recommendation_html(
                player_quick_view.compose_fantasygm_read_factors(
                    why="Inspect this asset inside the active trade package.",
                    team_fit="Starter",
                    skip_values=("Starter",),
                )
            )
            + player_quick_view.accolades_html(
                player_awards.select_display_badges(badges),
                overflow=player_awards.remaining_badges(badges),
            )
            + "</div>",
            unsafe_allow_html=True,
        )

    card_kwargs = dict(
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
        render_player_dossier=dossier,
        open_player_quick_view=lambda player_id, **_kwargs: st.session_state.__setitem__(
            "ui_trade_pqv_player_id", str(player_id or "")
        ),
        render_detail_actions=lambda detail_idea, detail_key: trade_hub_ui.render_trade_idea_player_actions(
            detail_idea,
            key_prefix=detail_key,
            return_page="trade_hub",
            source_label="Trade Hub",
            render_player_detail_button_grid=production_app.render_player_detail_button_grid,
            render_recommendation_feedback=lambda **_kwargs: None,
            trade_target_reason=lambda _: "Synthetic target rationale.",
            trade_partner_reason=lambda _: "Synthetic partner rationale.",
            trade_confidence_reason=lambda _: "Synthetic confidence rationale.",
        ),
    )
    with st.container(key="trade_hub_board"):
        with st.container(key="trade_hub_headline"):
            trade_hub_ui.render_trade_idea_card(idea, 0, key_prefix="ci_trade_board", **card_kwargs)
        with st.container(key="trade_hub_more_ideas"):
            packages = (
                ("4199", "Aaron Jones", "7090", "Darnell Mooney"),
                ("6904", "Jalen Hurts", "11655", "Tyrone Tracy"),
                ("7090", "Darnell Mooney", "4199", "Aaron Jones"),
            )
            for extra_idx, package in enumerate(packages, start=1):
                extra = dict(idea)
                extra["partner_team_name"] = f"Partner {extra_idx + 1}"
                extra["tag"] = f"Secondary path {extra_idx}"
                extra["partner_roster_id"] = f"fixture-partner-{extra_idx}"
                extra["send_assets"] = [
                    {"asset_type": "player", "player_id": package[0], "name": package[1]}
                ]
                extra["receive_assets"] = [
                    {"asset_type": "player", "player_id": package[2], "name": package[3]}
                ]
                trade_hub_ui.render_trade_idea_card(
                    extra, extra_idx, key_prefix="ci_trade_board", **card_kwargs
                )
        with st.container(key="trade_hub_show_more"):
            st.button("Show 3 more", key="ci_trade_show_more", use_container_width=True)

    pqv_player_id = str(st.session_state.get("ui_trade_pqv_player_id") or "").strip()
    if pqv_player_id:
        def _clear_trade_pqv() -> None:
            st.session_state.pop("ui_trade_pqv_player_id", None)

        @st.dialog(
            "Player Quick View",
            width="large",
            dismissible=True,
            on_dismiss=_clear_trade_pqv,
        )
        def _canonical_trade_pqv() -> None:
            dossier(pqv_player_id)

        _canonical_trade_pqv()


def _my_team() -> None:
    _marker("my-team", ("Team strategy", "Roster Decisions", "How these roster grades work", "Roster Core", "Position Groups", "Draft Capital"))
    _workspace("My Team", "Roster construction, pressure points, and the next handoff.")
    st.markdown("<div class='my-team-strategy-kicker'>Team strategy</div>", unsafe_allow_html=True)
    st.markdown(
        workspace_ui.client_disclosure_html(
            "How these roster grades work",
            workspace_ui.concept_band_html(
                [
                    {
                        "label": "Strategy",
                        "title": "One ranking lens",
                        "body": "The top strategy line is the ranking lens. Archetype is supporting copy.",
                        "tone": "strategy",
                        "hide_icon": True,
                    },
                    {
                        "label": "Actions",
                        "title": "Handoffs",
                        "body": "Trade Hub and Waivers own the prescriptions.",
                        "tone": "opportunity",
                        "hide_icon": True,
                    },
                ]
            ),
        ),
        unsafe_allow_html=True,
    )
    ui_primitives.render_section_header("Roster Signals", eyebrow="Ranks", subtitle="Power and franchise ranks without repeating strategy.")
    _tiles([
        {"label": "Outlook", "value": "Balanced Contender", "note": "Strong current roster with manageable gaps."},
        {"label": "Power", "value": "#4", "note": "Starter unit #3."},
    ])
    ui_primitives.render_section_header("Strength & Pressure", eyebrow="What matters", subtitle="Existing strengths and short-term coverage needs.")
    _tiles([
        {"label": "Strength", "value": "WR foundation", "note": "Existing team metrics mark this room as a relative strength."},
        {"label": "Pressure point", "value": "RB coverage", "note": "Short-term coverage need from the existing roster-needs assessment."},
    ])
    ui_primitives.render_section_header("Roster Decisions")
    ui_primitives.render_section_header("Roster Actions", eyebrow="Handoffs", subtitle="Canonical next move plus Trade Hub and Waivers destinations.")
    _tiles([
        {"label": "Biggest Need", "value": "Running Back", "note": "Starter and depth coverage need attention."},
        {"label": "Roster Status", "value": "Within limit", "note": "Twenty-four active players against a twenty-five player limit."},
    ])
    ui_primitives.render_section_header("Roster Core", eyebrow="Projected", subtitle="Projected core groups with canonical ranks — not live Sleeper starter locks.")
    assets = (
        football_assets.FootballPlayerAsset("12527", "Ashton Jeanty", "RB", "LV", "Starter", "starter", value="82", value_label="Dynasty Score", insight="OVR #12 · RB #3", age="Age 22"),
        football_assets.FootballPlayerAsset("fixture-wr", "Synthetic Wide Receiver With A Long Name", "WR", "SEA", "Contributor", "contributor", value="67", value_label="Dynasty Score", insight="OVR #48 · WR #18", age="Age 24"),
    )
    qb_avatar = player_profile_ui.avatar_html(
        _production_equivalent_headshot_src("12527"),
        "AJ",
        "compact-player-avatar",
    )
    wr_avatar = player_profile_ui.avatar_html("", "WR", "compact-player-avatar")
    render_html_fragment(
        "<div class='my-team-roster-core player-scan-grid'>"
        + football_assets.player_card_html(
            assets[0],
            density="compact",
            mode="action-enabled",
            avatar_html=qb_avatar,
            identity=player_tier_identity.resolve_player_tier_identity(stored_tier="Starter"),
            tier_frame="full",
            tags_html=(
                "<span class='compact-player-tags'>"
                + player_cards.player_support_chip_html("Injury Alert", "risk")
                + "</span>"
            ),
        )
        + football_assets.player_card_html(
            assets[1],
            density="compact",
            mode="action-enabled",
            avatar_html=wr_avatar,
            identity=player_tier_identity.resolve_player_tier_identity(stored_tier="Contributor"),
            tier_frame="full",
        )
        + "</div>"
    )
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
            "Why",
        "Current Season",
        "Career",
        "STATS",
        "What player tiers mean",
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
    player_key = str(st.query_params.get("pqv_player") or "fixture").strip().lower()
    portraits = {
        "tracy": (
            "11655",
            "Tyrone Tracy",
            "RB",
            "NYG",
            "TT",
        ),
        "jones": ("4199", "Aaron Jones", "RB", "MIN", "AJ"),
        "wr": ("6794", "Justin Jefferson", "WR", "MIN", "JJ"),
        "qb": ("6904", "Jalen Hurts", "QB", "PHI", "JH"),
        "te": ("1466", "Travis Kelce", "TE", "KC", "TK"),
        "missing": ("", "Missing Photo", "WR", "FA", "MP"),
    }
    sleeper_id, dossier_name, dossier_pos, dossier_team, initials = portraits.get(
        player_key,
        ("", "Fixture Playmaker", "WR", "MIN", "FP"),
    )
    avatar = player_profile_ui.avatar_html(
        _production_equivalent_headshot_src(sleeper_id) if sleeper_id else "",
        initials,
        "player-detail-avatar player-quick-view-avatar",
    )
    stats = player_quick_view.build_stats_view(pd.Series(current))
    render_html_fragment("<div data-testid='stDialog'><div role='dialog'>")
    render_html_fragment(
        player_quick_view.pqv_hero_html(
            avatar_html=avatar,
            name=dossier_name,
            position=dossier_pos,
            team=dossier_team,
            age_text="25",
            source_label="Identity",
            role_label="Featured",
            overall_display="#12",
            position_display="WR #5",
            dynasty_value="8,920",
            scoring_format="",
            signal_badges=(("Health", "Questionable"),),
            identity=player_tier_identity.resolve_player_tier_identity(stored_tier="Elite"),
            include_tier_legend=True,
        )
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
        + (player_quick_view.current_season_summary_html(stats) or "")
        + "</div>"
        "<div class='pqv-decision-secondary'>"
        + player_quick_view.why_this_recommendation_html(
            player_quick_view.compose_fantasygm_read_factors(
                why="Verified production and stable availability support the current value.",
                team_fit="Core roster piece",
                risk="Questionable",
                skip_values=("Featured",),
            )
        )
        + "</div></div>"
    )
    award_rows = [
        current,
        {**current, "stats_season": 2024, "games_played": 17, "fantasy_points_ppr": 318.4, "ppg": 18.7, "receiving_yards": 1540, "receiving_tds": 12, "position_finish": 2},
        {**current, "stats_season": 2023, "games_played": 16, "fantasy_points_ppr": 251.2, "ppg": 15.7, "receiving_yards": 1160, "receiving_tds": 8, "position_finish": 9},
    ]
    award_badges = player_awards.build_player_awards(award_rows, position="WR")
    render_html_fragment(
        player_quick_view.career_dossier_html(
            badges=player_awards.select_display_badges(award_badges),
            overflow=player_awards.remaining_badges(award_badges),
            years_exp=2 if player_key == "tracy" else 4,
            position=dossier_pos,
        )
    )
    with st.container(key="pqv_actions_fixture"):
        st.markdown(
            "<div class='player-quick-view-actions-label'>Actions</div>",
            unsafe_allow_html=True,
        )
        with st.container(key="pqv_actions_strip_fixture"):
            a, b, c, d = st.columns(4, gap="small")
            with a:
                st.button("Open in Trade Hub", key="pqv_open_trade_fixture", use_container_width=True, type="primary")
            with b:
                st.button("GM Targets", use_container_width=True)
            with c:
                st.button("Untouchable", use_container_width=True)
            with d:
                st.button("Share", use_container_width=True)
    st.button("Feedback", use_container_width=True)

    detail = str(st.session_state.get("ui_dossier_detail") or "")

    def _set_detail(label: str) -> None:
        current = str(st.session_state.get("ui_dossier_detail") or "")
        st.session_state["ui_dossier_detail"] = "" if current == label else label

    nav = st.columns(3, gap="small")
    for column, label in zip(nav, ("STATS", "CAREER", "MODEL")):
        with column:
            st.button(label, key=f"ui_dossier_nav_{label}", use_container_width=True, type="secondary", on_click=_set_detail, args=(label,))
    if detail == "STATS":
        player_quick_view.render_current_season(stats)
    elif detail == "CAREER":
        render_html_fragment(
            player_quick_view.career_timeline_html(
                resume,
                expanded=True,
                include_achievements=False,
                skip_current_season=True,
            )
        )
        render_html_fragment(player_quick_view.compact_bio_html(player_quick_view.ExecutiveSnapshot(
            years_in_league="4 seasons", draft_capital="2022 / Round 1 / Pick 18",
            college="Fixture State", height="6'2\"", weight="208 lb", bye_week="6",
        )))
        player_quick_view.render_news(
            [
                player_quick_view.NewsItem(
                    headline="Fixture role remains stable.",
                    source="CBS Sports",
                    published="2h ago",
                    url="https://example.com/news",
                    snippet="The featured role is unchanged.",
                )
            ]
        )
    elif detail == "MODEL":
        render_html_fragment("<div class='pqv-model-matrix'><div class='pqv-model-cell'><span>Market</span><strong>88</strong></div></div>")
    render_html_fragment("</div></div>")


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


def _methodology() -> None:
    """How We Evaluate + legal footer without guest marketing/import hero."""

    from modules import methodology_page

    _marker(
        "methodology",
        (
            "How FantasyGM Lab Evaluates Players",
            "What FantasyGM Lab does not claim",
            "Value is league-specific",
        ),
    )
    _workspace("How We Evaluate", "Static methodology. No league import required.")
    methodology_page.render_methodology_page()
    legal_pages.render_legal_footer(
        current_page=methodology_page.PAGE_KEY,
        on_navigate=lambda _page: None,
    )
    st.caption("Methodology fixture — no marketing hero, no public-player refresh.")


def _guest_landing() -> None:
    """Logged-out landing fixture: integrated welcome + account + import.

    Deliberately omits executive_workspace_shell / command actions — guest
    landing ownership must not mount live SELECT/ALERTS/YOU controls.
    Optional ``fixture_auth`` query: guest | signin | create | pending_ambiguous |
    pending_definite | pending_resend.
    """

    from modules import auth_supabase
    from modules import marketing_landing
    from modules import platform_import_ui

    fixture_auth = str(st.query_params.get("fixture_auth", "guest")).strip().lower()
    st.session_state.pop(auth_supabase.PENDING_EMAIL_CONFIRMATION_KEY, None)
    st.session_state.pop(auth_supabase.CONFIRMATION_REQUIRED_KEY, None)
    st.session_state.pop(auth_supabase.ACCOUNT_SIGNUP_CHECK_EMAIL_KEY, None)
    st.session_state.pop(auth_supabase.CONFIRMATION_RESEND_TS_KEY, None)
    st.session_state.pop("_confirm_resend_success", None)
    st.session_state["launch_auth_mode"] = "guest"
    st.session_state.pop("launch_account_form", None)
    auth_supabase.resend_signup_confirmation = lambda _config, _email: (True, "")

    marketing_landing.render_marketing_landing()

    config = {
        "enabled": True,
        "url": "https://example.supabase.co",
        "anon_key": "anon",
    }
    if fixture_auth == "signin":
        st.session_state["launch_auth_mode"] = "account"
        st.session_state["launch_account_form"] = "signin"
    elif fixture_auth == "create":
        st.session_state["launch_auth_mode"] = "account"
        st.session_state["launch_account_form"] = "create"
    elif fixture_auth == "pending_ambiguous":
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
    elif fixture_auth in {"pending_definite", "pending_resend"}:
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
        if fixture_auth == "pending_resend":
            import time as _time

            st.session_state["_confirm_resend_success"] = True
            st.session_state[auth_supabase.CONFIRMATION_RESEND_TS_KEY] = int(_time.time())

    def _render_import() -> None:
        platform_import_ui.render_platform_import_panel(pd.DataFrame())
        with st.form("guest_landing_fixture_import_form", clear_on_submit=False):
            st.text_input(
                "Sleeper Username",
                key="guest_landing_fixture_username",
                placeholder="Enter your Sleeper username",
                autocomplete="username",
            )
            st.form_submit_button("Load my leagues", use_container_width=True, type="primary")

    def _render_account() -> None:
        account_ui.render_mobile_auth_entry(config=config)

    if account_ui.launch_account_should_precede_import(st.session_state):
        _render_account()
        _render_import()
    else:
        _render_import()
        _render_account()
    marketing_landing.render_marketing_landing_deferred()

    st.markdown("<div data-fgl-guest-landing='1'></div>", unsafe_allow_html=True)
    if fixture_auth == "guest":
        extra = "Save your leagues"
    elif fixture_auth in {"signin", "create"}:
        extra = "Sign in" if fixture_auth == "signin" else "Create account"
    else:
        extra = "Check your email"
    markers = (
        "Import your league",
        "Sign in",
        "Continue as guest",
        "Load my leagues",
        extra,
    )
    _marker("guest-landing", markers)
    legal_pages.render_legal_footer(
        current_page="welcome",
        on_navigate=lambda _page: None,
    )
    from modules import feedback_ui

    feedback_ui.render_global_feedback_button(
        context={"page": "welcome", "surface": "guest-landing"},
        build_global_feedback_report=lambda **_kwargs: {"page": "welcome"},
        append_feedback_report=lambda _report: (True, ""),
        key_prefix="guest_landing_feedback",
        placement="floating",
    )
    st.caption("Guest landing fixture — zero live executive command headers.")


def _recaps() -> None:
    from modules import compact_fantasy_assets as _compact_assets
    from modules import player_images as _player_images
    from modules import league_history as _league_history
    from modules import league_history_ui as _league_history_ui
    from modules import league_recaps
    from modules import league_recaps_ui
    from modules import league_storylines as _league_storylines
    from modules import league_storylines_ui as _league_storylines_ui
    from modules import transaction_grades
    from modules.league_history_styles import LEAGUE_HISTORY_CSS as _LEAGUE_HISTORY_CSS
    from modules.league_recaps_styles import LEAGUE_RECAPS_CSS
    from modules.league_storylines_styles import LEAGUE_STORYLINES_CSS as _LEAGUE_STORYLINES_CSS

    inject_global_styles(LEAGUE_RECAPS_CSS)
    inject_global_styles(_LEAGUE_HISTORY_CSS)
    inject_global_styles(_LEAGUE_STORYLINES_CSS)
    inject_global_styles(f"<style>{_compact_assets.COMPACT_FANTASY_ASSET_CSS}</style>")
    _player_images.get_player_image_url = lambda player_id: _production_equivalent_headshot_src(
        str(player_id or "")
    )
    _compact_assets.get_player_image_url = _player_images.get_player_image_url
    _marker(
        "recaps",
        (
            "League Recaps / History",
            "Week 7 recap",
            "League Memory",
            "This week",
            "History",
            "Storylines",
        ),
    )
    _workspace("League Recaps / History", "What mattered this week, and what happened.")
    from modules.workspace_ui import render_section_header as _recaps_header

    league_recaps_ui.render_league_recaps_page_header(_recaps_header)
    st.pills("League Memory", ["Recaps", "History", "Storylines"], default="Recaps", key="league_memory_view_fixture")
    recap = league_recaps.build_weekly_recap(
        league_id="synthetic-founder-beta-league",
        season="2025",
        week=7,
        transactions=[],
        matchups=[
            {"week": 7, "roster_id": 1, "matchup_id": 10, "points": 148.4, "team_name": "War Room"},
            {"week": 7, "roster_id": 2, "matchup_id": 10, "points": 110.2, "team_name": "Lakefront"},
        ],
        profiles={
            "1": {"team_name": "War Room"},
            "2": {"team_name": "Lakefront"},
        },
    )
    render_html_fragment(league_recaps_ui.recap_edition_html(recap))
    st.pills("Recap archive", ["This week · 7", "Week 6"], default="This week · 7", key="league_recaps_archive_fixture")
    st.pills("Season", ["2026", "2025"], default="2026", key="league_history_season_fixture")
    st.pills("Filter", ["All", "Trades", "Waivers"], default="All", key="league_history_filter_fixture")
    _history_lookup = _league_history.player_lookup_from_rows(
        [
            {"player_id": "11655", "name": "Tyrone Tracy", "position": "RB", "team": "NYG", "value_score": 4200},
            {"player_id": "12492", "name": "Pat Bryant", "position": "WR", "team": "DEN", "value_score": 3900},
            {"player_id": "6904", "name": "Jalen Hurts", "position": "QB", "team": "PHI", "value_score": 2100},
        ]
    )
    _history_profiles = {
        "1": {"team_name": "War Room Synthetic", "username": "founder", "owner_name": "Founder", "avatar_url": ""},
        "2": {"team_name": "Lakefront Franchise", "username": "partner", "owner_name": "Partner", "avatar_url": ""},
    }
    _history_payload = {
        "league_id": "fixture-league",
        "season": "2026",
        "transactions": [
            {
                "transaction_id": "fx-trade",
                "type": "trade",
                "status": "complete",
                "status_updated": 1735689600000,
                "_history_week": 6,
                "roster_ids": [1, 2],
                "adds": {"11655": 1, "12492": 2},
                "drops": {"12492": 1, "11655": 2},
                "draft_picks": [
                    {"season": "2027", "round": 1, "owner_id": 1, "previous_owner_id": 2},
                    {"season": "2027", "round": 2, "owner_id": 2, "previous_owner_id": 1},
                ],
            },
            {
                "transaction_id": "fx-waiver",
                "type": "waiver",
                "status": "complete",
                "status_updated": 1735171200000,
                "_history_week": 4,
                "roster_ids": [1],
                "adds": {"6904": 1},
                "drops": {"12492": 1},
                "settings": {"waiver_bid": 17},
            },
        ],
    }
    _history_normalized = _league_history.normalize_season_payload(
        _history_payload,
        profiles=_history_profiles,
        player_lookup=_history_lookup,
    )
    grades = {
        str(item.get("transaction_id") or ""): transaction_grades.grade_transaction(
            item,
            player_lookup=_history_lookup,
            current_week=10,
            later_events=_history_normalized,
        )
        for item in _history_normalized
    }
    render_html_fragment(
        _league_storylines_ui.storylines_panel_html(
            _league_storylines.build_league_storylines(
                _history_normalized,
                profiles=_history_profiles,
                season="2026",
            ),
            team_logo_html=lambda *_args, **_kwargs: "<div class='dg-lh-logo'>WR</div>",
            season="2026",
        )
    )
    render_html_fragment(
        _league_history_ui.history_feed_html(
            _history_normalized,
            team_logo_html=lambda *_args, **_kwargs: "<div class='dg-lh-logo'>WR</div>",
            empty_note="No completed transactions yet for this season.",
            grades={key: value for key, value in grades.items() if value},
        )
    )


def _viewport_preserve() -> None:
    """Long-page in-place actions plus footer chrome — viewport contract fixture."""

    from modules import auth_supabase
    from modules import feedback_ui

    auth_supabase.resend_signup_confirmation = lambda _config, _email: (True, "")
    _marker(
        "viewport-preserve",
        (
            "Resend confirmation email",
            "Strategy & analysis",
            "STATS",
            "Refresh",
        ),
    )
    render_html_fragment(
        "<div data-fgl-viewport-preserve='1' style='height:720px' aria-hidden='true'></div>"
    )
    auth_supabase.enter_pending_email_confirmation(
        st.session_state,
        "fresh@example.com",
        payload={
            "id": "user-new",
            "email": "fresh@example.com",
            "email_confirmed_at": None,
            "confirmation_sent_at": "2026-08-12T20:00:00Z",
            "identities": [{"id": "ident-1", "user_id": "user-new", "provider": "email"}],
        },
    )
    config = {
        "enabled": True,
        "url": "https://example.supabase.co",
        "anon_key": "anon",
    }
    account_ui.render_confirmation_required_card(
        config=config,
        email="fresh@example.com",
        key_prefix="viewport_preserve",
    )
    render_html_fragment("<div style='height:280px' aria-hidden='true'></div>")

    panel_open = bool(st.session_state.get("viewport_strategy_panel_open"))

    def _toggle_strategy() -> None:
        st.session_state["viewport_strategy_panel_open"] = not bool(
            st.session_state.get("viewport_strategy_panel_open")
        )

    st.button(
        "Hide strategy & analysis" if panel_open else "Strategy & analysis",
        key="viewport_strategy_toggle",
        on_click=_toggle_strategy,
        use_container_width=True,
    )
    if panel_open:
        st.info("Strategy panel is open. Untouchables and role edits stay in this region.")

    more_open = bool(st.session_state.get("viewport_more_open"))

    def _toggle_more() -> None:
        st.session_state["viewport_more_open"] = not bool(
            st.session_state.get("viewport_more_open")
        )

    st.button(
        "STATS",
        key="viewport_more_toggle",
        on_click=_toggle_more,
        use_container_width=True,
        type="secondary",
    )
    if more_open:
        st.write("Expanded player details stay anchored to the detail nav.")

    if st.button("Refresh", key="viewport_refresh_inplace", type="tertiary"):
        st.session_state["viewport_refreshed"] = True
    if st.session_state.get("viewport_refreshed"):
        st.caption("Recommendations refreshed in place.")

    with st.container(key="mobile_gm_sheet_trigger_viewport"):
        render_html_fragment(brand_identity.gm_orb_floating_trigger_html())
        st.button(
            brand_identity.GM_ORB_ARIA_LABEL,
            help=brand_identity.GM_ORB_HELP,
            type="primary",
            key="mobile_gm_sheet_open_viewport",
            on_click=lambda: st.session_state.update(
                _fixture_gm_open=not bool(st.session_state.get("_fixture_gm_open"))
            ),
        )
    if st.session_state.get("_fixture_gm_open"):
        render_html_fragment(
            "<div class='mobile-gm-sheet-marker'></div>"
            "<div class='mobile-gm-destination-panel'>"
            "<div class='mobile-gm-panel-header'>"
            "<div class='mobile-gm-sheet-kicker'>FantasyGM Lab</div>"
            "<div class='mobile-gm-sheet-title'>Where to go</div>"
            "</div></div>"
        )
        st.button(
            "Close",
            key="viewport_gm_sheet_close",
            on_click=lambda: st.session_state.update(_fixture_gm_open=False),
        )
    render_html_fragment("<div style='height:640px' aria-hidden='true'></div>")
    legal_pages.render_legal_footer(
        current_page="welcome",
        on_navigate=lambda _page: None,
    )
    feedback_ui.render_global_feedback_button(
        context={"page": "viewport-preserve", "surface": "viewport-preserve"},
        build_global_feedback_report=lambda **_kwargs: {"page": "viewport-preserve"},
        append_feedback_report=lambda _report: (True, ""),
        key_prefix="viewport_preserve_feedback",
        placement="floating",
    )
    st.caption("Viewport preservation fixture — footer Feedback is an unrelated control.")


def _alerts() -> None:
    from modules import alerts_activity
    from modules import alerts_activity_ui
    from modules import notification_center as nc
    from modules.alerts_activity_styles import ALERTS_ACTIVITY_CSS
    from modules import news as canonical_news

    # Browser fixtures never call providers or mutate the committed cache.
    canonical_news.schedule_news_cache_refresh = lambda **_kwargs: False

    inject_global_styles(ALERTS_ACTIVITY_CSS)
    _marker(
        "alerts",
        (
            "Alerts",
            "Important",
            "My Players",
            "News",
            "League",
            "Decisions",
            "Ashton Jeanty status changed",
        ),
    )
    _workspace("Alerts", "Priority signals and a deeper activity timeline.")
    session = {
        nc.ACTIVITY_INBOX_SNAPSHOT_KEY: {
            "league_id": "fixture-league",
            "records": [
                {
                    "id": "urgent-jeanty",
                    "category": "URGENT",
                    "title": "Ashton Jeanty injury update",
                    "body": "News reports a potentially significant injury. Structured Sleeper status has not caught up yet.",
                    "href_hint": "my_team",
                    "age_label": "21m",
                    "source_kind": "canonical",
                    "player_id": "12527",
                    "news_player_name": "Ashton Jeanty",
                    "news_event_severity": "HIGH",
                    "news_roster_relationship": "MY_BENCH",
                    "news_event_type": "INJURY",
                    "news_significant_injury_event": True,
                    "news_status_unconfirmed": True,
                },
                {
                    "id": "news-pickens",
                    "category": "NEWS",
                    "title": "George Pickens role update",
                    "body": "Corroborated by Sleeper depth data",
                    "href_hint": "alerts",
                    "age_label": "28m",
                    "source_kind": "canonical",
                    "player_id": "pickens",
                },
                {
                    "id": "decision-waiver",
                    "category": "DECISIONS",
                    "title": "New waiver opportunity",
                    "body": "Your RB room is under pressure",
                    "href_hint": "waivers",
                    "age_label": "1h",
                    "source_kind": "canonical",
                },
            ],
        }
    }
    alerts_activity.store_timeline_events(
        session,
        [
            {
                "recommendation_id": "news-only-1",
                "value": "NFL practice report roundup",
                "note": "League-wide news — not a header alert.",
                "news_event_severity": "LOW",
                "news_roster_relationship": "UNKNOWN",
                "should_alert": False,
                "category": "NEWS",
                "news_age_label": "2h",
                "source_url": "https://example.com/practice-roundup",
            }
        ],
        league_id="fixture-league",
    )
    st.session_state.update(session)
    alerts_activity_ui.render_alerts_page(
        league_id="fixture-league",
        session=st.session_state,
        entitlement="free",
        open_player_quick_view=lambda player_id, **_kwargs: st.session_state.__setitem__(
            "fixture_alert_player_id", str(player_id or "")
        ),
    )


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
    inject_global_styles(DECISION_SURFACE_DIALOG_CSS + TRADE_DETAIL_CSS)
    inject_global_styles(METHODOLOGY_PAGE_CSS)
    inject_global_styles(LIVE_DRAFT_CSS)
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
        "player-asset-explorer": _player_asset_explorer,
        "methodology": _methodology,
        "viewport-preserve": _viewport_preserve,
        "recaps": _recaps,
        "alerts": _alerts,
    }[surface]()
    _render_fixture_ack_markers()
    viewport_preservation.render_viewport_preservation()
    st.caption("Synthetic fixture only — no credentials, personal identifiers, or production data.")


if __name__ == "__main__":
    main()

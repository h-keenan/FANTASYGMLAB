"""Deterministic fixture-backed UI surfaces for CI browser validation."""

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
    comparative_metrics,
    dashboard_orientation,
    dashboard_workflow,
    football_assets,
    league_workspace_ui,
    live_draft_ui,
    player_cards,
    player_history,
    player_quick_view,
    trade_hub_ui,
    ui_primitives,
    waivers_ui,
    workspace_ui,
)
from modules.app_styles import APP_CSS
from modules.dashboard_workflow_styles import DASHBOARD_WORKFLOW_CSS
from modules.executive_command_header_styles import EXECUTIVE_COMMAND_HEADER_CSS
from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS
from modules.waivers_presentation_styles import WAIVERS_PRESENTATION_CSS
from modules.html_rendering import inject_global_styles, render_html_fragment


SURFACES = {"dashboard", "league", "trade", "my-team", "waivers", "navigation", "live-draft", "player-dossier"}


def _workspace(title: str, note: str) -> None:
    from modules import notification_center

    notifications = notification_center.list_founder_beta_notifications()
    with st.container(key="executive_workspace_shell"):
        render_html_fragment(
            application_shell.executive_workspace_shell_html(
                application_shell.ExecutiveWorkspaceShell(
                    page_title=title,
                    page_note=note,
                    league_name="Synthetic Founder Beta League",
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
                [1, 1, 1],
                gap="small",
            )
            with league_col:
                with st.popover("Switch League", key="top_league_actions_fixture"):
                    st.caption("Existing league-switch behavior fixture.")
            with alerts_col:
                notification_center.render_notification_center(
                    items=notifications,
                    key_prefix="fixture_notifications",
                )
            with profile_col:
                with st.container(key="fixture_profile_control"):
                    with st.popover("You", key="fixture_profile_popover"):
                        st.caption("Fixture Account · Premium · Founder Beta")
                        with st.expander("Send feedback", expanded=False):
                            st.caption("Founder Beta feedback fixture.")



def _marker(surface: str, sections: tuple[str, ...]) -> None:
    st.markdown(
        f"<div data-ui-surface='{surface}' data-ui-sections='{','.join(sections)}'></div>",
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
        render_html_fragment("<div class='mobile-gm-floating-trigger-marker'></div>")
        st.button(
            "GM",
            help="Open destinations",
            type="primary",
            key="mobile_gm_sheet_open_fixture",
            on_click=lambda: st.session_state.update(_fixture_gm_open=True),
        )
    if not st.session_state.get("_fixture_gm_open"):
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
        st.button(
            "Close destinations",
            key="mobile_sheet_close_fixture",
            use_container_width=True,
            on_click=lambda: st.session_state.update(_fixture_gm_open=False),
        )
        st.caption("Core")
        st.button("Dashboard", key="mobile_sheet_nav_dashboard_fixture", type="primary", use_container_width=True)
        st.button("My Team", key="mobile_sheet_nav_my_team_fixture", use_container_width=True)
        st.button("Trade Hub", key="mobile_sheet_nav_trade_fixture", use_container_width=True)
        st.button("Waivers", key="mobile_sheet_nav_waivers_fixture", use_container_width=True)
        st.caption("Support")
        st.button("League Overview", key="mobile_sheet_nav_league_fixture", use_container_width=True)
        st.button("Players", key="mobile_sheet_nav_players_fixture", use_container_width=True)
        st.caption("Experimental · Early access")
        st.markdown(
            "<div class='mobile-gm-experimental-note'>Early access capability. Available when enabled for your account.</div>",
            unsafe_allow_html=True,
        )
        st.button("Labs [EXPERIMENTAL]", key="mobile_sheet_nav_labs_fixture", use_container_width=True)


def _dashboard() -> None:
    _marker(
        "dashboard",
        (
            "Immediate Action",
            "Your Next Move",
            "Team Snapshot",
            "League Intelligence",
            "Deep Analysis",
        ),
    )
    _workspace("Dashboard", "Daily command center for the next move window.")
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
        render_quick_actions=lambda _actions: st.button(
            "Open League Overview",
            key="fixture_dashboard_deep_analysis",
            use_container_width=True,
        ),
        render_league_pulse=lambda: _tiles(
            [{"label": "Market", "value": "Balanced", "note": "No fixture manager is dominating current activity."}]
        ),
    )


def _league() -> None:
    _marker("league", ("Power Rankings", "About these metrics"))
    _workspace("League Overview", "Competitive context across the current league.")
    ui_primitives.render_section_header("Power Rankings", eyebrow="Strongest Now", subtitle="Current lineup strength appears before supporting education.")
    league_workspace_ui.render_team_rank_cards({
        "power_rank": 4, "franchise_rank": 2, "roster_value_rank": 3,
        "starter_rank": 5, "bench_rank": 2, "age_rank": 6, "draft_capital_rank": 1,
    })
    with st.expander("About these metrics", expanded=False):
        _tiles([
            {"label": "Power Rank", "value": "Current strength", "note": "Starter quality and usable depth."},
            {"label": "Franchise Rank", "value": "Total asset base", "note": "Roster value plus owned draft capital."},
            {"label": "Strategy", "value": "Balanced", "note": "Recommended operating direction."},
            {"label": "Archetype", "value": "Flexible contender", "note": "Descriptive roster shape."},
        ])


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
    _marker("my-team", ("Roster Priorities", "Position Groups"))
    _workspace("My Team", "Roster construction and position-level context.")
    ui_primitives.render_section_header("Roster Priorities", eyebrow="What to do next", subtitle="Current fixture needs and opportunities.")
    _tiles([
        {"label": "Biggest Need", "value": "Quarterback", "note": "Starter and depth coverage need attention."},
        {"label": "Roster Status", "value": "Within limit", "note": "Twenty-four active players against a twenty-five player limit."},
    ])
    ui_primitives.render_section_header("Position Groups", eyebrow="Roster", subtitle="Canonical football assets remain full width and tappable.")
    assets = (
        football_assets.FootballPlayerAsset("fixture-qb", "Synthetic Quarterback", "QB", "MIN", "Starter", "starter", value="82", value_label="Dynasty Score", insight="Projected weekly starter."),
        football_assets.FootballPlayerAsset("fixture-wr", "Synthetic Wide Receiver With A Long Name", "WR", "SEA", "Contributor", "contributor", value="67", value_label="Dynasty Score", insight="Reliable depth with a current role."),
    )
    render_html_fragment("<div class='player-scan-grid'>" + "".join(football_assets.player_card_html(asset, density="compact", mode="action-enabled") for asset in assets) + "</div>")


def _waivers() -> None:
    _marker("waivers", ("Waiver Priorities", "Available Targets"))
    _workspace("Waivers", "Wire scanning and decision support for the active league.")
    players = pd.DataFrame([
        {"player_id": "fixture-qb", "name": "Synthetic Quarterback", "position": "QB", "team": "NO", "age": 26, "value_score": 3895, "position_rank": 4, "fantasy_ppg": 14.9, "opportunity_label": "Strong Opportunity", "opportunity_explanation": "Projected starter with usable weekly volume.", "opportunity_confidence": "Medium", "stale_free_agent": False},
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
            "Current Value",
            "Current Season",
            "Career Resume",
            "Career Timeline",
            "View complete season stats",
            "Recent News",
            "Advanced Details",
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
    expanded = bool(st.session_state.get("ui_dossier_history_expanded", False))
    stats = player_quick_view.build_stats_view(pd.Series(current))
    render_html_fragment(
        "<section class='player-quick-view-shell dg-quick-view-panel'>"
        "<div class='player-quick-view-header-band player-quick-view-hero'>"
        "<div class='player-quick-view-avatar' aria-hidden='true'>FP</div>"
        "<div class='player-quick-view-copy'><div class='player-quick-view-source'>Identity</div>"
        "<h3 class='player-quick-view-name'>Fixture Playmaker</h3>"
        "<div class='player-quick-view-meta'>WR / MIN / Age 25</div>"
        "<div class='player-quick-view-primary-row'>Healthy / Active</div></div></div></section>"
    )
    render_html_fragment(player_quick_view.recommendation_context_html(
        "Verified production and stable availability support the current value.",
        "Hold as a lineup cornerstone unless the return materially improves the roster.",
        action="Hold",
    ))
    render_html_fragment(player_quick_view.snapshot_html(
        player_quick_view.DossierSnapshot(
            dynasty_value="8,920", rank="#12", position_rank="#5 WR", fantasy_ppg="17.1",
            health="Healthy", tier="Elite", recommendation="Hold", trend="Rising",
            recommendation_note="Cornerstone production supports the current roster window.",
        ),
        include_recommendation=False,
    ))
    season_summary = player_quick_view.current_season_summary_html(stats)
    if season_summary:
        render_html_fragment(season_summary)
    render_html_fragment(player_quick_view.career_resume_html(resume, expanded=expanded))
    if st.button(
        "Collapse career history" if expanded else "View full career resume",
        key="ui_dossier_history_toggle",
        use_container_width=True,
    ):
        st.session_state["ui_dossier_history_expanded"] = not expanded
        st.rerun()
    if expanded:
        render_html_fragment(
            player_quick_view.career_timeline_html(
                resume,
                expanded=expanded,
                include_achievements=False,
            )
        )
    with st.expander("View complete season stats", expanded=False):
        player_quick_view.render_current_season(stats)
    with st.expander("Recent News", expanded=False):
        player_quick_view.render_news(
            [player_quick_view.NewsItem("Fixture role remains stable.")],
            include_shell=False,
        )
    with st.expander("Advanced Details", expanded=False):
        render_html_fragment(player_quick_view.executive_snapshot_html(player_quick_view.ExecutiveSnapshot(
            years_in_league="4 seasons", draft_capital="2022 / Round 1 / Pick 18",
            college="Fixture State", height="6'2\"", weight="208 lb", bye_week="6",
        )))
        st.caption("Athletic profile, college production, and methodology remain secondary.")


def main() -> None:
    st.set_page_config(page_title="FantasyGM Lab deterministic UI validation", layout="wide", initial_sidebar_state="collapsed")
    inject_global_styles(APP_CSS)
    inject_global_styles(DASHBOARD_WORKFLOW_CSS)
    inject_global_styles(EXECUTIVE_COMMAND_HEADER_CSS)
    inject_global_styles(PLAYER_QUICK_VIEW_CSS)
    inject_global_styles(WAIVERS_PRESENTATION_CSS)
    surface = str(st.query_params.get("surface", "dashboard")).strip().lower()
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
    }[surface]()
    st.caption("Synthetic fixture only — no credentials, personal identifiers, or production data.")


if __name__ == "__main__":
    main()

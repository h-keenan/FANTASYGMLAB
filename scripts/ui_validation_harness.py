"""Deterministic fixture-backed UI surfaces for CI browser validation."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import (
    application_shell,
    comparative_metrics,
    dashboard_orientation,
    dashboard_workflow,
    football_assets,
    league_workspace_ui,
    player_cards,
    player_quick_view,
    trade_hub_ui,
    ui_primitives,
    waivers_ui,
    workspace_ui,
)
from modules.app_styles import APP_CSS
from modules.dashboard_workflow_styles import DASHBOARD_WORKFLOW_CSS
from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS
from modules.waivers_presentation_styles import WAIVERS_PRESENTATION_CSS
from modules.html_rendering import inject_global_styles, render_html_fragment


SURFACES = {"dashboard", "league", "trade", "my-team", "waivers"}


def _workspace(title: str, note: str) -> None:
    render_html_fragment(
        application_shell.workspace_header_html(
            application_shell.WorkspaceHeader(
                page_title=title,
                page_note=note,
                league_name="Synthetic Founder Beta League",
                team_name="Fixture Football Operations",
                platform="Sleeper",
                account_label="Fixture Account",
                entitlement_label="Premium",
                has_league=True,
                metrics=(
                    application_shell.WorkspaceMetric("Power Rank", "#4", "Current strength"),
                    application_shell.WorkspaceMetric("Franchise Rank", "#2", "Total asset base"),
                ),
            )
        )
    )


def _marker(surface: str, sections: tuple[str, ...]) -> None:
    st.markdown(
        f"<div data-ui-surface='{surface}' data-ui-sections='{','.join(sections)}'></div>",
        unsafe_allow_html=True,
    )


def _tiles(items: list[dict]) -> None:
    html = "".join(
        "<article class='home-command-card dg-ui-card'>"
        f"<div class='home-command-card-label'>{item['label']}</div>"
        f"<div class='home-command-card-value'>{item['value']}</div>"
        f"<p>{item['note']}</p></article>"
        for item in items
    )
    render_html_fragment("<div class='home-command-grid'>" + html + "</div>")


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
        {"label": "Highest Priority", "value": "Strengthen QB depth", "note": "The current starter room has the clearest upgrade path."},
        {"label": "Top Trade Opportunity", "value": "Explore a balanced swap", "note": "A synthetic recommendation used only for layout validation."},
        {"label": "Top Waiver Opportunity", "value": "Add reliable depth", "note": "Available fixture player with a current role."},
    ]
    briefing = dashboard_workflow.organize_dashboard_items(items)
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
    _marker("trade", ("Trade Board", "Estimated value difference"))
    _workspace("Trade Hub", "Negotiation workspace for team-specific trade ideas.")
    ui_primitives.render_section_header("Trade Board", eyebrow="Recommendations", subtitle="Scan the package, then open the existing lazy detail dialog.")
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


def main() -> None:
    st.set_page_config(page_title="DynastyGM deterministic UI validation", layout="wide", initial_sidebar_state="collapsed")
    inject_global_styles(APP_CSS)
    inject_global_styles(DASHBOARD_WORKFLOW_CSS)
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
    }[surface]()
    st.caption("Synthetic fixture only — no credentials, personal identifiers, or production data.")


if __name__ == "__main__":
    main()

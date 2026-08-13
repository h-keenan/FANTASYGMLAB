"""Data-surface polish + remaining performance contracts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from modules import component_family_styles
from modules import deferred_rendering
from modules import dense_list_primitives
from modules import dense_list_styles
from modules import game_plan_package
from modules import league_workspace_ui
from modules import waivers_ui
from modules.app_styles import APP_CSS
from modules.dense_list_styles import DENSE_LIST_CSS


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
FAMILY = component_family_styles.COMPONENT_FAMILY_CSS
BRIEFING = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
WAIVERS = (ROOT / "modules" / "waivers_ui.py").read_text(encoding="utf-8")
DRAFT = (ROOT / "modules" / "draft_center_ui.py").read_text(encoding="utf-8")


def test_compact_activity_metric_strips_redundant_suffix():
    assert league_workspace_ui.compact_activity_metric("High Activity") == "High"
    assert league_workspace_ui.compact_activity_metric("Medium") == "Medium"
    assert league_workspace_ui.compact_activity_metric("") == "—"
    html = league_workspace_ui.team_comparison_row_html(
        power_rank="#1",
        franchise_rank="#4",
        team_name="Charmmanderr",
        owner_text="charliehornsby",
        archetype="Aging Contender",
        style_philosophy="Aggressive Trader · Win-Now · Pick Seller",
        activity="High Activity",
        logo_html="<div class='dg-ranked-logo'>C</div>",
        tap_class=" team-card-tappable",
        tap_attrs=" role='button' tabindex='0'",
        is_current=True,
    )
    assert "dg-dense-dual-rank" in html
    assert "Power" in html
    assert "Franchise" in html
    assert "Charmmanderr" in html
    assert "charliehornsby" in html
    assert "Aging Contender" in html
    assert "Aggressive Trader" in html
    assert "High Activity" not in html
    assert "High" in html
    assert "Activity" in html
    assert "role='button'" in html
    assert "tabindex='0'" in html
    assert "stDataFrame" not in html


def test_team_comparison_board_sorts_without_dataframe_widget():
    frame = pd.DataFrame(
        [
            {
                "roster_id": "2",
                "team_name": "Beta",
                "owner_username": "b",
                "owner_name": "Bee",
                "avatar_url": "",
                "power_rank": 2,
                "franchise_rank": 1,
                "archetype_label": "Rebuild",
                "trading_style": "Patient",
                "roster_philosophy": "Rebuild",
                "asset_behavior": "Pick Buyer",
                "activity_level": "Low",
            },
            {
                "roster_id": "1",
                "team_name": "Alpha",
                "owner_username": "a",
                "owner_name": "Aye",
                "avatar_url": "",
                "power_rank": 1,
                "franchise_rank": 4,
                "archetype_label": "Contender",
                "trading_style": "Aggressive",
                "roster_philosophy": "Win-Now",
                "asset_behavior": "Pick Seller",
                "activity_level": "High",
            },
        ]
    )
    captured = {}

    def _capture(*, html: str, key_prefix: str):
        captured["html"] = html
        captured["key"] = key_prefix
        return None

    league_workspace_ui.render_team_comparison_board(
        frame,
        team_tap_markup=lambda _row: (" team-card-tappable", " role='button' tabindex='0'"),
        render_team_card_tap_grid=_capture,
        open_league_team_from_tap=lambda _clicked: False,
        team_logo_html=lambda *_a, **_k: "<div class='dg-ranked-logo'>T</div>",
        current_roster_id="1",
    )
    html = captured["html"]
    assert captured["key"] == "league_team_comparison"
    assert html.index("Alpha") < html.index("Beta")
    assert "dg-team-comparison-board" in html
    assert "dg-ranked-row--current" in html


def test_league_overview_uses_branded_comparison_not_raw_metrics_dataframe():
    rankings = APP[APP.index('if league_section == "Rankings":') :]
    assert "render_team_comparison_board" in rankings
    assert '"Team comparison"' in rankings
    chunk = rankings[rankings.index("Team comparison") : rankings.index("Team comparison") + 2800]
    assert "st.dataframe" not in chunk
    assert "render_deferred_section_gate" in chunk
    assert "Load scoring and health detail" in chunk


def test_expander_details_owned_by_component_family_not_new_app_css_block():
    compact = FAMILY.replace(" ", "").replace("\n", "")
    assert "[data-testid=\"stExpanderDetails\"]{max-height:none!important;overflow:visible!important" in compact
    assert FAMILY in APP_CSS
    assert APP_CSS.index(FAMILY) < APP_CSS.index(DENSE_LIST_CSS)
    dense_compact = DENSE_LIST_CSS.replace(" ", "").replace("\n", "")
    assert ".dg-team-comparison-board{max-height:none;overflow:visible}" in dense_compact
    assert "minmax(6.5rem,8rem)" in DENSE_LIST_CSS
    assert "stExpanderDetails" not in DENSE_LIST_CSS


def test_dense_dual_rank_primitive_is_compact():
    html = dense_list_primitives.dense_dual_rank_html(power="#1", franchise="#4")
    assert "dg-dense-dual-rank" in html
    assert "#1" in html
    assert "#4" in html
    assert "Power" in html
    assert "Franchise" in html


def test_waivers_detailed_table_is_deferred_and_capped():
    assert 'with st.expander("Detailed Table View", expanded=False):' in WAIVERS
    assert "deferred_rendering.render_section_gate" in WAIVERS
    assert 'button_label="Load waiver table"' in WAIVERS
    assert "WAIVERS_DETAILED_TABLE_PREVIEW_ROWS" in WAIVERS
    assert waivers_ui.WAIVERS_DETAILED_TABLE_PREVIEW_ROWS == 40
    assert "present.head(WAIVERS_DETAILED_TABLE_PREVIEW_ROWS)" in WAIVERS


def test_deep_analysis_expensive_widgets_are_deferred():
    my_team = APP[APP.index('with st.expander("Deep Analysis"') :]
    assert "Load Deep Analysis controls" in my_team
    gate = my_team.index("Load Deep Analysis controls")
    roles = my_team.index("Edit Roles")
    roster_table = my_team.index("Detailed Roster Table")
    assert gate < roles < roster_table
    assert "render_deferred_section_gate" in my_team[:gate]


def test_draft_center_detailed_table_is_deferred():
    assert 'with st.expander("Detailed Table View", expanded=False):' in DRAFT
    assert 'button_label="Load draft capital table"' in DRAFT
    assert "deferred_rendering.render_section_gate" in DRAFT


def test_deferred_section_gate_helper_is_session_isolated():
    st_module = MagicMock()
    state_a: dict = {}
    state_b: dict = {}
    assert not deferred_rendering.render_section_gate(
        st_module,
        state_a,
        "league_a",
        button_label="Load",
        note="note",
    )
    deferred_rendering.mark_deferred_section_ready(state_a, "league_a")
    assert deferred_rendering.render_section_gate(
        st_module,
        state_a,
        "league_a",
        button_label="Load",
        note="note",
    )
    assert not deferred_rendering.is_deferred_section_ready(state_b, "league_a")


def test_trade_analyzer_does_not_build_unrelated_route_surfaces():
    start = APP.index("# TRADE ANALYZER")
    end = APP.index('if current_page == "premium":')
    block = APP[start:end]
    assert "include_intelligence=False" in block
    assert "render_waiver_workspace_sections" not in block
    assert "render_startup_draft_center" not in block
    assert "render_team_comparison_board" not in block
    assert "render_todays_game_plan" not in block


def test_rankings_reuses_shared_league_intelligence_context():
    overview = APP[APP.index("league_context = get_shared_league_context(include_trust=False)") :]
    setup = overview[: overview.index('if league_section == "Rankings":')]
    rankings = overview[overview.index('if league_section == "Rankings":') :]
    assert "league_intelligence_frame" in setup
    assert "cached_league_intelligence_frame(" not in rankings[:8000]
    assert "render_team_comparison_board" in rankings
    assert "get_shared_league_context(include_intelligence=False)" not in setup


def test_gm_targets_prefers_shared_roster_map():
    gm = APP[APP.index('if current_page == "gm_targets":') : APP.index('if current_page == "players":')]
    assert "roster_player_map.get(str(my_roster_id)" in gm
    assert gm.index("mapped_ids") < gm.index("get_roster_player_ids")


def test_recommendation_refresh_invalidates_package_once():
    block = BRIEFING[
        BRIEFING.index('"Refresh recommendations"') : BRIEFING.index('"Refresh recommendations"')
        + 500
    ]
    assert "invalidate_recommendation_packages(st.session_state)" in block
    assert "st.rerun()" in block
    assert "auth_supabase" not in block
    assert "prepared_player_frame" not in block
    assert block.count("invalidate_recommendation_packages") == 1


def test_prepared_frame_and_game_plan_owners_unchanged():
    assert "prepared_player_frame.get_or_build_valued_ranked_frame" in APP
    assert game_plan_package.PACKAGE_KEY == "_game_plan_package_bundle"
    assert game_plan_package.SOFT_TTL_SECONDS == 5 * 60 * 60


def test_app_css_budget_and_ownership_order():
    assert len(APP_CSS) < 390_000
    assert APP_CSS.index(FAMILY) < APP_CSS.index(DENSE_LIST_CSS)
    assert "dg-dense-dual-rank" in APP_CSS
    assert ".dg-team-comparison-board" in APP_CSS


def test_harness_and_mobile_include_team_comparison():
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    assert "render_team_comparison_board" in harness
    assert "High Activity" in harness

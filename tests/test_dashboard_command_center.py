"""Dashboard command-center presentation regressions.

Presentation-only: no new football scoring, provider calls, or eager hydration.
"""

from __future__ import annotations

from pathlib import Path

from modules import compact_fantasy_assets as compact
from modules import daily_gm_briefing as dgb
from modules import daily_gm_briefing_ui
from modules import dashboard_workflow
from modules import deferred_rendering


ROOT = Path(__file__).resolve().parents[1]


def _tile(label: str, value: str, *, rec_id: str = "", note: str = "note", **extra):
    payload = {
        "label": label,
        "value": value,
        "note": note,
        "recommendation_id": rec_id,
    }
    payload.update(extra)
    return payload


def test_trade_top_priority_renders_give_get_portraits_and_edge():
    html = compact.game_plan_trade_visual_html(
        {
            "value_edge": "+237",
            "send": [
                {
                    "asset_type": "player",
                    "player_id": "6794",
                    "name": "Tyrone Tracy",
                    "position": "RB",
                    "team": "NYG",
                    "age": 26,
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
        }
    )
    assert "Tyrone Tracy" in html
    assert "Pat Bryant" in html
    assert "2027 Round 3" in html
    assert "You give" in html
    assert "You get" in html
    assert "dg-gp-trade-for" in html
    assert "FOR" in html.upper()
    assert "+237 VALUE EDGE" in html
    assert "dg-compact-asset-avatar" in html
    assert "dg-compact-asset--standard" in html
    assert "fetch_player_headshot_bytes" not in Path(
        "modules/compact_fantasy_assets.py"
    ).read_text(encoding="utf-8")


def test_watch_attention_uses_portraits_not_debug_pipes():
    html = compact.watch_attention_html(
        [
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
                "team": "NYJ",
                "roster_relevance": "starter",
            },
        ]
    )
    assert "Cam" in html and "Skattebo" in html
    assert "Kenyon" in html and "Sadiq" in html
    assert "Starter" in html
    assert " | " not in html
    assert "dg-gp-watch-list" in html
    assert "dg-compact-asset--standard" in html
    ui = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    assert "watch_attention_html" in ui
    assert "_should_show_reason" in ui


def test_waiver_opportunity_renders_player_identity_and_role():
    html = compact.compact_asset_html(
        {
            "asset_type": "player",
            "player_id": "8134",
            "name": "Emanuel Wilson",
            "position": "RB",
            "team": "GB",
            "role": "Handcuff",
        },
        size="compact",
        show_value=False,
    )
    assert "Emanuel Wilson" in html
    assert "RB" in html
    assert "Handcuff" in html
    assert "dg-compact-asset-avatar" in html


def test_non_trade_top_priority_does_not_force_trade_geometry():
    briefing = dashboard_workflow.organize_dashboard_items(
        [_tile("Biggest Team Need", "QB", rec_id="need-1", route_key="my_team")]
    )
    plan = dgb.compose_daily_gm_briefing(briefing)
    item = plan.items[0]
    assert item.category == dgb.CATEGORY_TOP_PRIORITY
    assert daily_gm_briefing_ui._card_visual_html(item) == ""
    assert daily_gm_briefing_ui._should_show_headline(item)


def test_quiet_day_copy_is_intentional_not_empty_boxes():
    briefing = dashboard_workflow.organize_dashboard_items([])
    plan = dgb.compose_daily_gm_briefing(briefing)
    ui = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    assert plan.quiet
    assert "No urgent roster issues right now." in ui
    assert "giant" not in ui.casefold()


def test_header_is_compact_document_flow_not_floating_badge():
    ui = (ROOT / "modules" / "valuation_archetype_ui.py").read_text(encoding="utf-8")
    styles = (ROOT / "modules" / "dashboard_workflow_styles.py").read_text(encoding="utf-8")
    assert "dg-dashboard-page-identity" not in ui
    assert "Dashboard</div>" not in ui
    assert "Valuation:" in ui
    assert "position:absolute" not in ui
    assert "position: static" not in styles.split(".st-key-dashboard_page_context", 1)[1].split(
        "@media (min-width: 1024px)", 1
    )[0]
    assert "display: flex" in styles
    assert "flex-direction: column" in styles


def test_updated_and_refresh_share_a_wrapping_utility_row():
    ui = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    assert "dg-game-plan-meta" in ui
    assert "_refresh_row" in ui
    assert "dg-game-plan-utility" in ui
    assert '"Refresh"' in ui
    assert "st.columns(" not in ui
    assert "position:absolute" not in ui
    assert ui.index("dg-game-plan-lede") < ui.index('"Refresh"')
    assert ui.index("dg-game-plan-utility") < ui.index('"Refresh"')
    header = ui[
        ui.index('with st.container(key=f"{key_prefix}_header")') : ui.index("if plan.quiet:")
    ]
    assert header.index("dg-game-plan-lede") < header.index("_refresh_row")
    assert header.index("_refresh_row") < header.index("dg-game-plan-utility")
    assert header.index("dg-game-plan-utility") < header.index('"Refresh"')
    assert "st.markdown(meta_html" in header


def test_what_changed_stays_deferred_with_lighter_affordance():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    block = app.split("def _render_what_changed()", 1)[1][:1200]
    assert "See what changed" in block
    assert "Since your last check-in" in block
    assert "use_container_width=False" in block
    assert "render_deferred_section_gate" in block
    assert "decision_change_history_ui.render_what_changed_section" in app
    source = (ROOT / "modules" / "deferred_rendering.py").read_text(encoding="utf-8")
    assert "heading: str = \"\"" in source
    assert "use_container_width: bool = True" in source


def test_explore_is_quiet_support_nav_not_sitemap_hero():
    source = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
    assert 'render_section_header(\n                "Explore"' in source
    assert '"Deep Analysis"' not in source
    assert "Deeper tools when a recommendation isn't enough." in source
    assert source.index("render_todays_game_plan()") < source.index('"Explore"')
    assert source.index("render_what_changed()") < source.index('"Explore"')


def test_game_plan_desktop_grid_does_not_force_equal_height_empty_cells():
    css = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    compact_css = css.replace(" ", "")
    assert "align-items:start" in compact_css
    assert ":not(:has([class*=\"_card_2\"]))" in css or ":not(:has([class*=\"_card_2\"]))" in compact_css
    assert "grid-row:1 / span 2" in css


def test_deferred_gates_and_no_new_provider_calls_in_dashboard_presentation():
    ui = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    workflow = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    dashboard = app.split("def render_home_dashboard(", 1)[1].split(
        "STARTUP_DRAFT_STRATEGIES", 1
    )[0]
    assert "sleeper" not in ui.casefold()
    assert "requests." not in ui
    assert "fetch_player_headshot" not in ui
    assert "compose_daily_gm_briefing(" in dashboard
    assert "render_deferred_section_gate" in dashboard
    assert "Load League Pulse" in dashboard
    assert "See what changed" in dashboard
    assert "@st.fragment" not in workflow
    assert deferred_rendering.deferred_state_key("dashboard_what_changed_x").startswith(
        "deferred_section_ready__"
    )


def test_injury_watch_presentation_reuses_existing_player_fields():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    home = app.split("def render_home_dashboard(", 1)[1].split(
        "STARTUP_DRAFT_STRATEGIES", 1
    )[0]
    assert '"roster_relevance": injury_player.get("roster_relevance")' in home
    assert '"injury_status": injury_player.get("injury_status")' in home
    assert "select_top_waiver_opportunity(" in home
    assert "cached_dashboard_trade_headline(" in home

"""Dashboard final IA + reduced-breadth Game Plan contracts."""

from pathlib import Path

from modules.executive_design_unify_styles import EXECUTIVE_DESIGN_UNIFY_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_strategy_context_is_owned_by_dashboard_header_not_a_floating_pill():
    ui = (ROOT / "modules" / "valuation_archetype_ui.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    workflow = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
    assert "dashboard_valuation_lens" in ui
    assert "Lens ·" not in ui
    assert 'key="dashboard_page_context"' in ui
    assert "dg-dashboard-page-identity" not in ui
    assert "dg-dashboard-page-kicker" not in ui
    home = app.split("def render_home_dashboard(", 1)[1].split(
        "def render_platform_topbar(", 1
    )[0]
    assert "render_page_context=" in home
    assert "render_workspace_archetype_affordance(" in home
    assert workflow.index("render_page_context()") < workflow.index(
        "render_todays_game_plan()"
    )


def test_game_plan_header_owns_refresh_and_concise_copy():
    briefing = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    assert "Today's Game Plan" in briefing
    assert "Your highest-impact moves right now." in briefing
    assert "Highest-signal actions" not in briefing
    assert '"Refresh"' in briefing
    assert "Refresh recommendations" not in briefing
    assert f"{'{key_prefix}'}_header" in briefing or "_header" in briefing
    assert "dg-game-plan-utility" in briefing
    assert "dg-game-plan-card-primary" in briefing
    assert "st.columns(" not in briefing
    assert f"{'{key_prefix}'}_refresh_row" in briefing or "_refresh_row" in briefing


def test_desktop_game_plan_uses_card_grid_not_full_width_strips():
    css = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    compact = css.replace(" ", "")
    assert "grid-template-columns:minmax(0,1.7fr)minmax(0,1fr)" in compact
    assert "@media(max-width:1023px)" in compact
    assert "@media(max-width:760px)" in compact
    assert "grid-template-columns:minmax(0,1fr)" in compact
    workflow_css = (ROOT / "modules" / "dashboard_workflow_styles.py").read_text(
        encoding="utf-8"
    )
    assert "gap: var(--space-lg) !important" in workflow_css
    assert "space-3xl" not in EXECUTIVE_DESIGN_UNIFY_CSS.split(
        "@media (min-width:1440px)", 1
    )[1][:120]


def test_dashboard_trade_headline_uses_shared_engine_with_reduced_budget():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    builder = source.split("def cached_dashboard_trade_headline(", 1)[1].split(
        "def build_trade_trust_context(", 1
    )[0]
    hub = source.split("def cached_trade_ideas(", 1)[1].split(
        "def cached_dashboard_trade_headline(", 1
    )[0]
    ideas = (ROOT / "modules" / "trade_ideas.py").read_text(encoding="utf-8")
    assert "max_ideas=1" in builder
    assert 'search_budget="dashboard"' in builder
    assert "prefetched_rosters" in builder
    assert "build_trade_ideas(" in builder
    assert 'search_budget="dashboard"' not in hub
    assert "dashboard_budget" in ideas
    assert "partner_cap" in ideas
    assert "dashboard_pool_limit" in ideas
    assert "def build_trade_ideas(" in ideas


def test_dashboard_waiver_reuses_roster_map_and_canonical_ranker():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    preview = source.split("def build_home_dashboard_free_agent_preview(", 1)[1].split(
        "def dashboard_premium_content_state(", 1
    )[0]
    home = source.split("def render_home_dashboard(", 1)[1].split(
        "STARTUP_DRAFT_STRATEGIES", 1
    )[0]
    assert "rostered_ids" in preview
    assert "injury_need_positions" in preview
    assert "select_top_waiver_opportunity(" in home
    assert "rank_priority_add_candidates" not in home.split("def _render_todays_game_plan", 1)[0]
    assert "rostered_ids={" in home

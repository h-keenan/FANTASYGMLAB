"""Daily GM Briefing composition tests — no new football scoring."""

from __future__ import annotations

from pathlib import Path

from modules import daily_gm_briefing as dgb
from modules import dashboard_workflow
from modules import recommendation_lifecycle


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


def test_compose_copies_presentation_assets():
    trade = _tile(
        "Top Trade Opportunity",
        "Acquire RB depth",
        rec_id="trade-1",
        route_key="trade_hub",
        presentation={
            "send": [{"asset_type": "player", "name": "Tyrone Tracy", "player_id": "1"}],
            "receive": [{"asset_type": "player", "name": "Pat Bryant", "player_id": "2"}],
        },
    )
    briefing = dashboard_workflow.organize_dashboard_items([trade])
    plan = dgb.compose_daily_gm_briefing(briefing)
    assert plan.items[0].presentation["send"][0]["name"] == "Tyrone Tracy"
    assert plan.items[0].presentation["receive"][0]["name"] == "Pat Bryant"


def test_compose_one_canonical_trade_as_top_priority():
    trade = _tile(
        "Top Trade Opportunity",
        "Acquire RB depth",
        rec_id="trade-1",
        route_key="trade_hub",
        route_player_id="4046",
        recommendation_narrative={"recommendation_id": "trade-1", "kind": "trade"},
    )
    briefing = dashboard_workflow.organize_dashboard_items([trade])
    plan = dgb.compose_daily_gm_briefing(briefing, league_id="L1", entitlement="premium")
    assert not plan.quiet
    assert len(plan.items) == 1
    assert plan.items[0].category == dgb.CATEGORY_TOP_PRIORITY
    assert plan.items[0].recommendation_id == "trade-1"
    assert plan.items[0].destination == "trade_hub"
    assert plan.items[0].headline == "Acquire RB depth"


def test_compose_multiple_recommendations_respects_existing_order():
    items = [
        _tile("Biggest Team Need", "QB", rec_id="need-1"),
        _tile("Top Trade Opportunity", "Trade A", rec_id="trade-1", route_key="trade_hub"),
        _tile("Top Waiver Opportunity", "Add WR", rec_id="waiver-1"),
    ]
    briefing = dashboard_workflow.organize_dashboard_items(items)
    plan = dgb.compose_daily_gm_briefing(briefing, league_id="L1")
    categories = [item.category for item in plan.items]
    assert categories[0] == dgb.CATEGORY_TOP_PRIORITY
    assert plan.items[0].headline == "QB"
    assert dgb.CATEGORY_WAIVER in categories
    assert dgb.CATEGORY_LEAGUE_MOVEMENT in categories


def test_waiver_only_opportunity():
    waiver = _tile("Top Waiver Opportunity", "Add reliable depth", rec_id="w1")
    briefing = dashboard_workflow.organize_dashboard_items([waiver])
    plan = dgb.compose_daily_gm_briefing(briefing)
    assert plan.items[0].category == dgb.CATEGORY_TOP_PRIORITY
    assert plan.items[0].destination in {"waivers", "dashboard"}


def test_roster_decision_only_watch_state():
    injury = _tile("Injury Alert", "2 injured starters", note="Starters out")
    briefing = dashboard_workflow.organize_dashboard_items(
        [injury],
        immediate_labels=frozenset({"Injury Alert"}),
    )
    plan = dgb.compose_daily_gm_briefing(briefing)
    assert plan.items[0].category == dgb.CATEGORY_WATCH
    assert plan.items[0].destination == "my_team"


def test_quiet_no_action_state():
    briefing = dashboard_workflow.organize_dashboard_items([])
    plan = dgb.compose_daily_gm_briefing(briefing)
    assert plan.quiet
    assert plan.items == ()
    assert "no urgent approved actions" in plan.quiet_reason.casefold()


def test_duplicate_recommendation_suppression():
    trade = _tile(
        "Top Trade Opportunity",
        "Acquire RB",
        rec_id="same-id",
        route_key="trade_hub",
    )
    # Same id later as intelligence should not double.
    briefing = dashboard_workflow.DashboardBriefing(
        immediate=(),
        primary=trade,
        additional=(),
        intelligence=(trade,),
    )
    plan = dgb.compose_daily_gm_briefing(briefing)
    ids = [item.recommendation_id for item in plan.items]
    assert ids.count("same-id") == 1


def test_context_mismatch_detection():
    briefing = dashboard_workflow.organize_dashboard_items(
        [_tile("Top Trade Opportunity", "X", rec_id="t1")]
    )
    plan = dgb.compose_daily_gm_briefing(
        briefing, league_id="L1", roster_id="R1", valuation_lens="dynasty_score"
    )
    assert dgb.briefing_matches_context(plan, league_id="L1", roster_id="R1")
    assert not dgb.briefing_matches_context(plan, league_id="L2")


def test_free_and_premium_use_same_compose_path():
    trade = _tile("Top Trade Opportunity", "Move", rec_id="t1", route_key="trade_hub")
    briefing = dashboard_workflow.organize_dashboard_items([trade])
    free = dgb.compose_daily_gm_briefing(briefing, entitlement="free")
    premium = dgb.compose_daily_gm_briefing(briefing, entitlement="premium")
    assert free.items[0].headline == premium.items[0].headline
    assert free.items[0].recommendation_id == premium.items[0].recommendation_id
    assert free.entitlement == "free"
    assert premium.entitlement == "premium"


def test_compose_does_not_invent_scoring_or_order_helpers():
    source = (ROOT / "modules" / "daily_gm_briefing.py").read_text(encoding="utf-8")
    assert "daily_briefing_score" not in source
    assert "sort(" not in source.split("def compose_daily_gm_briefing", 1)[1].split(
        "return DailyGmBriefing", 1
    )[0]
    assert "organize_dashboard_items" in source or "DashboardBriefing" in source


def test_app_wires_game_plan_without_new_inventory_builders():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    dashboard = app.split("def render_home_dashboard(", 1)[1].split(
        "STARTUP_DRAFT_STRATEGIES", 1
    )[0]
    assert "compose_daily_gm_briefing(" in dashboard
    assert "render_todays_game_plan=_render_todays_game_plan" in dashboard
    assert "_open_daily_gm_briefing_item" in app
    # Still uses existing inventory — no parallel trade/waiver engine.
    assert "cached_dashboard_trade_headline(" in dashboard
    assert "select_top_waiver_opportunity(" in dashboard


def test_navigation_destinations_preserve_recommendation_id():
    trade = _tile(
        "Top Trade Opportunity",
        "Acquire X",
        rec_id="nav-1",
        route_key="trade_hub",
        recommendation_narrative={"recommendation_id": "nav-1", "kind": "trade"},
    )
    plan = dgb.compose_daily_gm_briefing(
        dashboard_workflow.organize_dashboard_items([trade])
    )
    item = plan.items[0]
    assert item.recommendation_id == "nav-1"
    assert item.recommendation_narrative["recommendation_id"] == "nav-1"
    assert recommendation_lifecycle.item_recommendation_id(
        {"recommendation_id": item.recommendation_id}
    ) == "nav-1"


def test_rank_context_uses_canonical_formatter_not_new_math():
    trade = _tile(
        "Top Trade Opportunity",
        "De'Von Achane",
        rec_id="r1",
        route_key="trade_hub",
        player_row={
            "overall_rank": 14,
            "position_rank": 6,
            "position": "RB",
        },
    )
    plan = dgb.compose_daily_gm_briefing(
        dashboard_workflow.organize_dashboard_items([trade]),
        scoring_format="Half-PPR",
    )
    assert plan.items[0].player_rank_context == "RB #6 · OVR #14 · Half-PPR"


def test_contract_doc_exists():
    text = (ROOT / "docs" / "daily-gm-briefing-contract.md").read_text(encoding="utf-8")
    for heading in (
        "Architecture",
        "Canonical inputs",
        "Ordering rules",
        "Deduplication",
        "Entitlement behavior",
        "Lifecycle",
        "Navigation",
        "Performance",
        "Quiet day",
        "Known limitations",
    ):
        assert heading in text
    assert "daily_briefing_score" in text  # documented as forbidden


def test_scoring_format_and_valuation_lens_are_provenance_only():
    trade = _tile("Top Trade Opportunity", "Acquire X", rec_id="t1", route_key="trade_hub")
    briefing = dashboard_workflow.organize_dashboard_items([trade])
    half = dgb.compose_daily_gm_briefing(
        briefing, scoring_format="Half-PPR", valuation_lens="dynasty_score"
    )
    ppr = dgb.compose_daily_gm_briefing(
        briefing, scoring_format="PPR", valuation_lens="redraft_score"
    )
    assert half.items[0].headline == ppr.items[0].headline
    assert half.items[0].recommendation_id == ppr.items[0].recommendation_id
    assert half.scoring_format == "Half-PPR"
    assert ppr.valuation_lens == "redraft_score"
    assert not dgb.briefing_matches_context(
        half, valuation_lens="redraft_score"
    )
    assert not dgb.briefing_matches_context(half, scoring_format="PPR")
    assert dgb.briefing_matches_context(
        half, valuation_lens="dynasty_score", scoring_format="Half-PPR"
    )


def test_league_and_roster_switch_invalidate_context_match():
    plan = dgb.compose_daily_gm_briefing(
        dashboard_workflow.organize_dashboard_items(
            [_tile("Top Trade Opportunity", "Move", rec_id="t1")]
        ),
        league_id="L-old",
        roster_id="R-old",
    )
    assert not dgb.briefing_matches_context(plan, league_id="L-new", roster_id="R-old")
    assert not dgb.briefing_matches_context(plan, league_id="L-old", roster_id="R-new")


def test_stale_recommendation_without_headline_is_omitted():
    empty = {"label": "Top Trade Opportunity", "value": "", "note": "", "recommendation_id": "stale"}
    briefing = dashboard_workflow.DashboardBriefing(
        immediate=(),
        primary=empty,
        additional=(),
        intelligence=(),
    )
    plan = dgb.compose_daily_gm_briefing(briefing)
    assert plan.quiet
    assert plan.items == ()


def test_open_item_uses_daily_gm_briefing_handoff_source():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    opener = app.split("def _open_daily_gm_briefing_item", 1)[1].split(
        "\ndef ", 1
    )[0]
    assert 'handoff_source="daily_gm_briefing"' in opener
    assert 'origin_page="dashboard"' in opener
    assert 'origin_label="Today\'s Game Plan"' in opener
    assert "recommendation_narrative=narrative" in opener


def test_briefing_not_session_cached():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    dashboard = app.split("def render_home_dashboard(", 1)[1].split(
        "STARTUP_DRAFT_STRATEGIES", 1
    )[0]
    assert "compose_daily_gm_briefing(" in dashboard
    assert "session_state[\"daily_gm_briefing\"]" not in dashboard
    assert "session_state['daily_gm_briefing']" not in dashboard


def test_ui_module_uses_existing_executive_primitives():
    source = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    assert 'render_section_header("Today\'s Game Plan"' in source
    assert "No move needed right now" in source
    assert "dg-daily-briefing" in source

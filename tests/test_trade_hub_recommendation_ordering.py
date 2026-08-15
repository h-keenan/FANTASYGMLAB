"""Trade Hub surface ranking and presentation order contracts."""

from __future__ import annotations

from pathlib import Path

from modules import premium, trade_hub_ui, trade_ideas
from scripts.profile_trade_hub import FixtureSpec, build_fixture, run_trade_hub


ROOT = Path(__file__).resolve().parents[1]


def _ident(idea: dict) -> tuple:
    return (
        str(idea.get("partner_team_name") or ""),
        str(idea.get("tag") or ""),
        int(idea.get("trade_gain") or 0),
        tuple(str(asset.get("player_id") or "") for asset in (idea.get("send_assets") or [])),
        tuple(str(asset.get("player_id") or "") for asset in (idea.get("receive_assets") or [])),
    )


def test_trade_surface_sort_key_prefers_headline_primary_and_confidence():
    weaker = {
        "trade_headline_ready": False,
        "trade_surface_tier": "secondary",
        "trade_confidence_label": "Medium",
        "market_realism_score": 90,
        "fit_score": 90,
        "partner_fit_score": 90,
        "strategy_fit_score": 90,
        "priority": 90,
    }
    stronger = {
        "trade_headline_ready": True,
        "trade_surface_tier": "primary",
        "trade_confidence_label": "High",
        "market_realism_score": 10,
        "fit_score": 10,
        "partner_fit_score": 10,
        "strategy_fit_score": 10,
        "priority": 10,
    }
    assert trade_ideas._trade_surface_sort_key(stronger) > trade_ideas._trade_surface_sort_key(
        weaker
    )


def test_diversity_fill_restores_surface_rank_on_real_fixtures():
    specs = (
        FixtureSpec("8-team-1qb-shallow", 8, 22, "1QB"),
        FixtureSpec(
            "12-team-1qb-deep",
            12,
            28,
            "1QB",
            te_premium=True,
            strategy="rebuild",
        ),
        FixtureSpec("12-team-superflex-primary", 12, 28, "Superflex", te_premium=True),
    )
    for spec in specs:
        approved = run_trade_hub(build_fixture(spec))["approved"]
        keys = [trade_ideas._trade_surface_sort_key(idea) for idea in approved]
        assert all(
            keys[index] >= keys[index + 1] for index in range(len(keys) - 1)
        ), spec.label
        if approved:
            best = max(approved, key=trade_ideas._trade_surface_sort_key)
            assert _ident(approved[0]) == _ident(best), spec.label


def test_presentation_order_helper_and_annotate_preserve_rank_not_category():
    disordered = [
        {
            "tag": "Secondary contender",
            "partner_team_name": "Z",
            "partner_roster_id": "z",
            "trade_headline_ready": False,
            "trade_surface_tier": "secondary",
            "trade_confidence_label": "Low",
            "market_realism_score": 40,
            "fit_score": 40,
            "partner_fit_score": 40,
            "strategy_fit_score": 40,
            "priority": 1,
            "trade_gain": 9000,
            "send_assets": [{"player_id": "s1"}],
            "receive_assets": [{"player_id": "r1"}],
            "reasoning_summary": "Contender title push package",
        },
        {
            "tag": "True headline",
            "partner_team_name": "A",
            "partner_roster_id": "a",
            "trade_headline_ready": True,
            "trade_surface_tier": "primary",
            "trade_confidence_label": "High",
            "market_realism_score": 90,
            "fit_score": 80,
            "partner_fit_score": 70,
            "strategy_fit_score": 60,
            "priority": 100,
            "trade_gain": -500,
            "send_assets": [{"player_id": "s2"}],
            "receive_assets": [{"player_id": "r2"}],
            "reasoning_summary": "Fixes a thin position need",
        },
        {
            "tag": "Primary health",
            "partner_team_name": "B",
            "partner_roster_id": "b",
            "trade_headline_ready": False,
            "trade_surface_tier": "primary",
            "trade_confidence_label": "Medium",
            "market_realism_score": 80,
            "fit_score": 70,
            "partner_fit_score": 60,
            "strategy_fit_score": 50,
            "priority": 50,
            "trade_gain": 200,
            "send_assets": [{"player_id": "s3"}],
            "receive_assets": [{"player_id": "r3"}],
            "reasoning_summary": "Injury relief for an IR starter",
        },
    ]
    ordered = trade_hub_ui.order_trade_hub_visible_ideas(disordered)
    assert [idea["tag"] for idea in ordered] == [
        "True headline",
        "Primary health",
        "Secondary contender",
    ]
    assert ordered[0]["trade_gain"] == -500  # gain is not the ranking field

    presentation = trade_hub_ui.trade_hub_entitlement_presentation(
        [ordered[0], ordered[1]],
        [ordered[2]],
        entitlement=premium.PREMIUM,
    )
    feed = trade_hub_ui.annotate_trade_hub_feed_categories(
        presentation["visible_ideas"],
        headline_idea=ordered[0],
    )
    assert [idea["tag"] for idea in feed] == [
        "True headline",
        "Primary health",
        "Secondary contender",
    ]
    assert feed[0]["_display_section"] == "Headline Recommendation"
    assert feed[1]["_display_section"] == "Health Relief"

    grouped = trade_hub_ui.group_trade_hub_ideas(
        presentation["visible_ideas"],
        headline_idea=ordered[0],
    )
    flat = [idea["tag"] for _section, rows in grouped.items() for idea in rows]
    # Contender section precedes Health Relief in TRADE_HUB_SECTION_ORDER.
    assert flat == [
        "True headline",
        "Secondary contender",
        "Primary health",
    ]
    assert flat != [idea["tag"] for idea in feed]


def test_trade_hub_route_orders_visible_ideas_before_unified_feed():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    board = source[
        source.index("def render_top_trade_opportunities()") : source.index(
            "def render_search_around_player()"
        )
    ]
    assert "order_trade_hub_visible_ideas(" in board
    assert board.index("order_trade_hub_visible_ideas(") < board.index(
        "annotate_trade_hub_feed_categories("
    )
    assert "group_trade_hub_ideas(" in board
    assert "ranked_feed[:local_visible]" in board
    assert "def _trade_hub_visible_feed()" in board

"""Today's Game Plan trade cards must open Player Quick View on tap.

GM Plan's Trade Opportunities card (modules.gm_plan_ui) and Dashboard's Top
Priority / League Movement trade teasers (modules.daily_gm_briefing_ui) both
render give/get player identity through modules.compact_fantasy_assets, whose
avatar chips already carry a real `data-player-id` attribute — but neither
card was routed through the tap-grid component every other player card on
the site uses (modules.player_cards.render_tappable_player_html /
modules.trade_hub_ui.render_trade_html_with_player_taps), so a tap did
nothing (coridian_, 2026-10-14: "is that trade idea tappable?"). These tests
cover the Dashboard side of that fix; tests/test_gm_plan_ui.py covers the GM
Plan page's own Trade Opportunities card.
"""

from __future__ import annotations

from unittest.mock import Mock

from modules import dashboard_workflow
from modules import daily_gm_briefing as dgb
from modules import daily_gm_briefing_ui


def _trade_tile(**overrides):
    payload = {
        "label": "Top Trade Opportunity",
        "value": "Pat Bryant + 2027 Round 3",
        "note": "reason",
        "recommendation_id": "trade-1",
        "route_key": "trade_hub",
        "presentation": {
            "value_edge": "+237",
            "send": [
                {
                    "asset_type": "player",
                    "player_id": "my-1",
                    "name": "Tyrone Tracy",
                    "position": "RB",
                    "team": "NYG",
                }
            ],
            "receive": [
                {
                    "asset_type": "player",
                    "player_id": "their-1",
                    "name": "Pat Bryant",
                    "position": "WR",
                    "team": "DEN",
                }
            ],
        },
    }
    payload.update(overrides)
    return payload


def _top_priority_item():
    zones = dashboard_workflow.organize_dashboard_items([_trade_tile()])
    plan = dgb.compose_daily_gm_briefing(zones, league_id="L1", roster_id="1")
    return plan.items[0]


def _waiver_item():
    zones = dashboard_workflow.organize_dashboard_items(
        [
            {
                "label": "Top Waiver Opportunity",
                "value": "Emanuel Wilson",
                "note": "Handcuff",
                "recommendation_id": "waiver-1",
                "route_key": "waivers",
                "presentation": {
                    "player": {
                        "asset_type": "player",
                        "player_id": "8134",
                        "name": "Emanuel Wilson",
                    }
                },
            }
        ]
    )
    plan = dgb.compose_daily_gm_briefing(zones, league_id="L1", roster_id="1")
    return plan.items[0]


def test_trade_assets_for_item_combines_both_sides():
    item = _top_priority_item()
    assets = daily_gm_briefing_ui._trade_assets_for_item(item)
    player_ids = {asset.get("player_id") for asset in assets}
    assert player_ids == {"my-1", "their-1"}


def test_trade_assets_for_item_empty_for_non_trade_item():
    item = _waiver_item()
    assert daily_gm_briefing_ui._trade_assets_for_item(item) == []


def test_render_card_html_routes_trade_card_through_tap_grid_and_opens_quick_view():
    item = _top_priority_item()
    tap_renderer = Mock(return_value="their-1")
    open_quick_view = Mock()
    daily_gm_briefing_ui._render_card_html(
        "<div class='dg-game-plan-card'>card</div>",
        item,
        key_prefix="daily_gm_card_1",
        render_tappable_player_html=tap_renderer,
        open_player_quick_view=open_quick_view,
    )
    tap_renderer.assert_called_once()
    open_quick_view.assert_called_once()
    assert open_quick_view.call_args.args[0] == "their-1"


def test_render_card_html_ignores_unrelated_click_results():
    item = _top_priority_item()
    tap_renderer = Mock(return_value="")
    open_quick_view = Mock()
    daily_gm_briefing_ui._render_card_html(
        "<div class='dg-game-plan-card'>card</div>",
        item,
        key_prefix="daily_gm_card_1",
        render_tappable_player_html=tap_renderer,
        open_player_quick_view=open_quick_view,
    )
    tap_renderer.assert_called_once()
    open_quick_view.assert_not_called()


def test_render_card_html_falls_back_to_plain_render_without_tap_callables():
    item = _top_priority_item()
    # No callables wired (e.g. a caller that hasn't adopted tap-through yet)
    # — must render without raising and must not fabricate a click.
    daily_gm_briefing_ui._render_card_html(
        "<div class='dg-game-plan-card'>card</div>",
        item,
        key_prefix="daily_gm_card_1",
        render_tappable_player_html=None,
        open_player_quick_view=None,
    )


def test_render_card_html_plain_render_for_non_trade_card():
    item = _waiver_item()
    tap_renderer = Mock(return_value="8134")
    open_quick_view = Mock()
    daily_gm_briefing_ui._render_card_html(
        "<div class='dg-game-plan-card'>card</div>",
        item,
        key_prefix="daily_gm_card_2",
        render_tappable_player_html=tap_renderer,
        open_player_quick_view=open_quick_view,
    )
    # Waiver's own single-player chip isn't in scope for this fix (it has no
    # give/get trade assets) — the tap grid must not be invoked for it here.
    tap_renderer.assert_not_called()
    open_quick_view.assert_not_called()

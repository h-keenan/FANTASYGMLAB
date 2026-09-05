"""Dashboard Game Plan must stay rich across automatic package-hit reruns."""

from __future__ import annotations

from modules import compact_fantasy_assets as compact
from modules import daily_gm_briefing as dgb
from modules import daily_gm_briefing_ui
from modules import dashboard_workflow
from modules import game_plan_package
from modules import player_profile_ui


def _tile(label: str, value: str, *, rec_id: str, **extra):
    payload = {
        "label": label,
        "value": value,
        "note": extra.pop("note", "reason"),
        "recommendation_id": rec_id,
    }
    payload.update(extra)
    return payload


def _rich_briefing() -> dgb.DailyGmBriefing:
    trade = _tile(
        "Top Trade Opportunity",
        "Pat Bryant + 2027 Round 3",
        rec_id="trade-tracy-bryant",
        route_key="trade_hub",
        note="reason",
        presentation={
            "value_edge": "+237",
            "send": [
                {
                    "asset_type": "player",
                    "player_id": "6794",
                    "name": "Tyrone Tracy",
                    "position": "RB",
                    "team": "NYG",
                    "age": 26,
                    "role": "Committee Back",
                }
            ],
            "receive": [
                {
                    "asset_type": "player",
                    "player_id": "8155",
                    "name": "Pat Bryant",
                    "position": "WR",
                    "team": "DEN",
                    "age": 23,
                    "role": "Backup With Upside",
                },
                {
                    "asset_type": "pick",
                    "label": "2027 Round 3",
                    "season": "2027",
                    "round": "3",
                },
            ],
        },
    )
    watch = _tile(
        "Injury Alert",
        "Cam Skattebo (RB) - starter | Kenyon Sadiq (TE) - starter",
        rec_id="watch-injury",
        route_key="my_team",
        note="Cam Skattebo (RB) - starter | Kenyon Sadiq (TE) - starter",
        presentation={
            "players": [
                {
                    "asset_type": "player",
                    "player_id": "9226",
                    "name": "Cam Skattebo",
                    "position": "RB",
                    "team": "NYG",
                    "roster_relevance": "starter",
                    "injury_status": "Questionable",
                },
                {
                    "asset_type": "player",
                    "player_id": "9500",
                    "name": "Kenyon Sadiq",
                    "position": "TE",
                    "team": "NYJ",
                    "roster_relevance": "starter",
                    "injury_status": "Questionable",
                },
            ]
        },
    )
    waiver = _tile(
        "Top Waiver Opportunity",
        "Emanuel Wilson",
        rec_id="waiver-wilson",
        route_key="waivers",
        note="Handcuff",
        presentation={
            "player": {
                "asset_type": "player",
                "player_id": "8134",
                "name": "Emanuel Wilson",
                "position": "RB",
                "team": "SEA",
                "role": "Handcuff",
            }
        },
    )
    zones = dashboard_workflow.organize_dashboard_items(
        [trade, watch, waiver],
        immediate_labels=frozenset({"Injury Alert"}),
    )
    return dgb.compose_daily_gm_briefing(zones, league_id="L1", roster_id="1")


def _assert_rich(plan: dgb.DailyGmBriefing) -> None:
    by_category = {item.category: item for item in plan.items}
    trade = by_category[dgb.CATEGORY_TOP_PRIORITY]
    watch = by_category[dgb.CATEGORY_WATCH]
    waiver = by_category[dgb.CATEGORY_WAIVER]
    trade_html = daily_gm_briefing_ui._card_visual_html(trade)
    watch_html = daily_gm_briefing_ui._card_visual_html(watch)
    waiver_html = daily_gm_briefing_ui._card_visual_html(waiver)
    assert "Tyrone Tracy" in trade_html
    assert "Pat Bryant" in trade_html
    assert "You give" in trade_html
    assert "You get" in trade_html
    assert "+237 VALUE EDGE" in trade_html
    assert "dg-compact-asset-avatar" in trade_html
    assert daily_gm_briefing_ui._should_show_headline(trade) is False
    assert "Cam" in watch_html and "Skattebo" in watch_html
    assert " | " not in watch_html
    assert daily_gm_briefing_ui._should_show_reason(watch, watch_html) is False
    assert "Emanuel Wilson" in waiver_html
    assert "Handcuff" in waiver_html
    assert "dg-compact-asset-avatar" in waiver_html
    assert daily_gm_briefing_ui._should_show_headline(waiver) is False


def test_package_hit_rerun_does_not_downgrade_rich_game_plan():
    """Initial compose (miss) then session package hydrate (hit) must stay rich.

    Production iPhone: first paint is rich; a later automatic rerun (~seconds)
    used briefing_from_package and dropped presentation, collapsing cards.
    """

    dgb.clear_compose_memo()
    plan = _rich_briefing()
    _assert_rich(plan)
    state: dict = {}
    game_plan_package.store_package(
        state,
        signature="lifecycle-sig",
        package={
            "briefing": game_plan_package.serialize_daily_briefing(plan),
            "dashboard_briefing": {},
            "snapshot_items": [],
            "recommendation_ids": [item.recommendation_id for item in plan.items],
        },
    )
    cached, hit = game_plan_package.lookup_package(state, signature="lifecycle-sig")
    assert hit is True
    restored = game_plan_package.briefing_from_package(cached)
    assert restored.items[0].presentation is not None
    _assert_rich(restored)
    assert restored.items[0].presentation["send"][0]["name"] == "Tyrone Tracy"
    assert restored.items[1].presentation["players"][0]["player_id"] == "9226"
    assert restored.items[2].presentation["player"]["player_id"] == "8134"
    # A later automatic remount (second HIT) must still keep identity fields.
    cached_again, hit_again = game_plan_package.lookup_package(
        state, signature="lifecycle-sig"
    )
    assert hit_again is True
    _assert_rich(game_plan_package.briefing_from_package(cached_again))


def test_thin_payload_is_allowed_only_when_rich_presentation_never_existed():
    thin = dgb.compose_daily_gm_briefing(
        dashboard_workflow.organize_dashboard_items(
            [
                _tile(
                    "Top Trade Opportunity",
                    "Pat Bryant + 2027 Round 3",
                    rec_id="thin-trade",
                    route_key="trade_hub",
                )
            ]
        )
    )
    item = thin.items[0]
    assert daily_gm_briefing_ui._card_visual_html(item) == ""
    assert daily_gm_briefing_ui._should_show_headline(item) is True


def test_avatar_hides_fallback_when_photo_element_exists():
    loaded = player_profile_ui.avatar_html(
        "https://sleepercdn.com/content/nfl/players/8134.jpg",
        "EW",
        "dg-compact-asset-avatar",
    )
    assert "dg-player-headshot-image" in loaded
    assert ">EW<" in loaded
    assert "onerror=" not in loaded
    missing = player_profile_ui.avatar_html("", "EW", "dg-compact-asset-avatar")
    assert "<img" not in missing
    assert ">EW<" in missing
    css = compact.COMPACT_FANTASY_ASSET_CSS
    assert ":has(img.dg-player-headshot-image)" in css
    waiver = compact.compact_asset_html(
        {
            "asset_type": "player",
            "player_id": "8134",
            "name": "Emanuel Wilson",
            "position": "RB",
            "team": "SEA",
            "role": "Handcuff",
        },
        size="compact",
        show_value=False,
    )
    assert "dg-player-headshot-image" in waiver or "sleepercdn.com" in waiver
    transparent = player_profile_ui.avatar_html(
        "https://example.com/cutout.png",
        "EW",
        "dg-compact-asset-avatar",
    )
    assert "<img" in transparent
    assert ":has(img.dg-player-headshot-image)" in compact.COMPACT_FANTASY_ASSET_CSS
    broken_contract = player_profile_ui.avatar_html(
        "https://example.com/missing.png",
        "EW",
        "dg-compact-asset-avatar",
    )
    assert "onload=" not in broken_contract
    assert "onerror=" not in broken_contract
    assert "dg-player-headshot-fallback" in broken_contract

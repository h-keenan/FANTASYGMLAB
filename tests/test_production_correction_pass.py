from __future__ import annotations

from pathlib import Path

import pandas as pd

import app
from modules import canonical_recommendation_narrative as narratives
from modules import daily_gm_briefing
from modules import notification_center
from modules import trade_hub_ui
from modules import trade_visual_language
from modules import league_workspace_ui


def _trade(*, partner: str = "2") -> dict:
    return {
        "partner_roster_id": partner,
        "partner_team_name": "Tongue Punchers",
        "tag": "Get younger plus pick",
        "my_score": 3503,
        "their_score": 3740,
        "trade_gain": 237,
        "send_assets": [
            {"asset_type": "player", "player_id": "tracy", "name": "Tyrone Tracy"}
        ],
        "receive_assets": [
            {"asset_type": "player", "player_id": "bryant", "name": "Pat Bryant"},
            {"asset_type": "pick", "pick_id": "2027-r3", "label": "2027 Round 3"},
        ],
    }


def test_alert_readiness_requires_complete_canonical_inventory():
    state: dict = {}
    notification_center.publish_activity_inventory(
        state,
        [],
        league_id="L1",
        inventory_complete=False,
    )
    assert not notification_center.activity_inventory_ready(state, league_id="L1")
    assert "Checking league activity" in notification_center._inbox_header_html(
        unread=0, active=0, ready=False
    )

    notification_center.publish_activity_inventory(state, [], league_id="L1")
    assert notification_center.activity_inventory_ready(state, league_id="L1")
    assert "All caught up" in notification_center._inbox_header_html(
        unread=0, active=0, ready=True
    )


def test_product_only_item_cannot_declare_league_inventory_ready():
    state = {
        notification_center.ACTIVITY_INBOX_SNAPSHOT_KEY: {
            "league_id": "L1",
            "records": [],
            "inventory_complete": False,
        }
    }
    product = notification_center.product_update_notification()
    assert product.source_kind == "product"
    assert not notification_center.activity_inventory_ready(state, league_id="L1")


def test_actionable_hydration_becomes_ready_and_retains_identity():
    state: dict = {}
    tile = {
        "label": "Top Trade Opportunity",
        "value": "Tongue Punchers",
        "note": "Current approved package.",
        "route_key": "trade_hub",
        "recommendation_id": "trade-current",
    }
    notification_center.publish_activity_inventory(state, [tile], league_id="L1")
    assert notification_center.activity_inventory_ready(state, league_id="L1")
    items = notification_center.compose_activity_inbox(session=state, league_id="L1")
    assert any(item.recommendation_id == "trade-current" for item in items)


def test_dashboard_handoff_revalidates_exact_omitted_package():
    dashboard = _trade()
    rec_id = narratives.trade_recommendation_id(dashboard)
    other = _trade(partner="3")
    calls: list[list[dict]] = []

    def validate(candidates: list[dict]) -> list[dict]:
        calls.append(candidates)
        return candidates

    reconciled, status = trade_hub_ui.revalidate_handoff_candidate(
        [other], rec_id, dashboard, validator=validate
    )
    assert status == "focused_revalidated"
    assert trade_hub_ui.idea_recommendation_id(reconciled[0]) == rec_id
    assert calls == [[dashboard]]


def test_invalid_dashboard_handoff_fails_stale_and_triggers_no_freeze():
    dashboard = _trade()
    rec_id = narratives.trade_recommendation_id(dashboard)
    reconciled, status = trade_hub_ui.revalidate_handoff_candidate(
        [], rec_id, dashboard, validator=lambda _ideas: []
    )
    assert reconciled == []
    assert status == "stale"


def test_daily_briefing_preserves_handoff_context_through_serialization():
    idea = _trade()
    rec_id = narratives.trade_recommendation_id(idea)
    item = daily_gm_briefing.DailyBriefingItem(
        source="dashboard_inventory",
        source_id=rec_id,
        recommendation_id=rec_id,
        category="top_priority",
        headline="Trade with Tongue Punchers",
        reason="Current approved package.",
        supporting_context="Top Trade Opportunity",
        destination="trade_hub",
        league_id="L1",
        roster_id="1",
        valuation_lens="value_score",
        scoring_format="PPR",
        freshness="dashboard_frame",
        provenance="test",
        handoff_context={"idea": idea, "dashboard_trade_signature": "sig-1"},
    )
    restored = daily_gm_briefing.DailyBriefingItem.from_mapping(item.to_dict())
    assert restored is not None
    assert restored.recommendation_id == rec_id
    assert narratives.trade_recommendation_id(restored.handoff_context["idea"]) == rec_id


def test_trade_value_labels_share_one_canonical_threshold_owner():
    expected = {237: "Fair", -991: "Slight Overpay", 0: "Fair", 900: "Favorable"}
    for delta, label in expected.items():
        assert trade_visual_language.trade_value_band(delta) == label
        assert app.trade_value_verdict(delta) == label
        if delta:
            assert f"TRADE VALUE / {label.upper()}" in trade_visual_language.value_edge_html(delta)


def test_priority_add_layout_and_share_are_owned_by_one_card_container():
    ui = Path("modules/waivers_ui.py").read_text(encoding="utf-8")
    css = Path("modules/waivers_presentation_styles.py").read_text(encoding="utf-8")
    assert "waiver-card-decision-grid" in ui
    assert "waiver_recommendation_{player_id}_{index}" in ui
    assert 'button_label="Share recommendation"' in ui
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 1.35fr) auto" in css
    assert '@media (max-width: 700px)' in css


def test_most_injured_card_defaults_to_summary_and_keeps_detail():
    row = {
        "roster_id": "1",
        "team_name": "Revivalry",
        "owner_name": "Founder",
        "mode": "contender",
        "avg_age": 25,
        "starter_current_score": 100,
        "power_rank": 1,
        "starter_rank": 1,
        "rebuild_index": 1,
        "draft_capital": 10,
        "first_rounders": 1,
        "pick_count": 3,
        "trade_count": 1,
        "trade_asset_total": 2,
        "top_heavy_ratio": 1,
        "starter_share": 0.5,
        "bench_current_score": 50,
        "undervalued_gap": 1,
        "injury_value_impact": 120,
        "major_injured_starters": 2,
        "injured_starters": 3,
        "active_injured_starters": 2,
        "injury_data_quality": "available",
        "key_injuries": ["Player One (RB)", "Player Two (WR)", "Player Three (TE)"],
        "actionable_injury_summary": (
            "Player One (RB) - OUT, starter, impact 70 | "
            "Player Two (WR) - IR, starter, impact 50 | Player Three (TE) - Q"
        ),
    }
    cards = league_workspace_ui.build_league_intelligence_cards(
        pd.DataFrame([row]),
        "value_score",
        has_meaningful_team_injury_impact=lambda candidate: bool(
            candidate.get("injury_value_impact")
        ),
        team_injury_display_label=lambda _candidate: "2 affected starters",
    )
    injury = next(card for card in cards if card["label"] == "Most Injured Roster")
    assert injury["note"] == "2 affected starters · Player One (RB), Player Two (WR)"
    assert "Player Three" in injury["detail"]

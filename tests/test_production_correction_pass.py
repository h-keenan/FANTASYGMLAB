from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import canonical_recommendation_narrative as narratives
from modules import daily_gm_briefing
from modules import notification_center
from modules import trade_hub_presentation
from modules import trade_visual_language
from modules import league_display


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

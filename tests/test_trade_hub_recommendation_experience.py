"""Trade Hub recommendation continuity, identity, and card composition."""

from __future__ import annotations

from pathlib import Path

from modules import canonical_recommendation_narrative as crn
from modules import recommendation_trust_ux
from modules import trade_hub_presentation
from modules.compact_fantasy_assets import COMPACT_FANTASY_ASSET_CSS
from modules.portrait_normalization import card_focus_x


ROOT = Path(__file__).resolve().parents[1]


def _idea(*, partner: str, send: str, receive: str, gain: int = 100, **extra) -> dict:
    idea = {
        "partner_roster_id": f"roster-{partner}",
        "partner_team_name": partner,
        "my_player": send,
        "their_player": receive,
        "my_score": 4000,
        "their_score": 4000 + gain,
        "trade_gain": gain,
        "tag": f"{send} for {receive}",
        "trade_surface_tier": "primary",
        "trade_headline_ready": True,
        "trade_confidence_label": "High",
        "fit_grade": "Strong",
        "market_realism_label": "Likely",
        "send_assets": [{"asset_type": "player", "player_id": "1", "name": send}],
        "receive_assets": [{"asset_type": "player", "player_id": "2", "name": receive}],
    }
    idea.update(extra)
    return idea


def test_canonical_identity_is_package_digest_not_headline():
    first = _idea(partner="A", send="Tracy", receive="Bryant")
    clone = dict(first)
    other = _idea(partner="B", send="Tracy", receive="Wilson")
    assert crn.trade_recommendation_id(first) == crn.trade_recommendation_id(clone)
    assert crn.trade_recommendation_id(first) != crn.trade_recommendation_id(other)
    assert trade_hub_presentation.idea_recommendation_id(first) == crn.trade_recommendation_id(first)

"""PQV / Trade Hub / share-card presentation contracts (no football semantics)."""

from __future__ import annotations

from pathlib import Path

from modules import brand_identity
from modules import share_recommendation_cards as share
from modules import trade_hub_presentation


ROOT = Path(__file__).resolve().parents[1]


def test_share_labels_are_perspective_safe_with_and_without_team_names():
    named = share.build_trade_share_card(
        {
            "partner_team_name": "Tongue Punchers",
            "trade_gain": 10,
            "send_assets": [{"name": "Send", "player_id": "1"}],
            "receive_assets": [{"name": "Get", "player_id": "2"}],
            "reasoning_summary": "Need-based swap.",
        },
        my_team_name="Harbor Club",
    )
    assert named.send_side_label == "Tongue Punchers receives"
    assert named.receive_side_label == "Harbor Club receives"
    rewritten = share.rewrite_share_reason_sides(
        "You add future flexibility.",
        my_team_name="Harbor Club",
    )
    assert rewritten == "Harbor Club adds future flexibility."
    assert "You " not in rewritten
    payload = share.build_share_text_payload(named)
    assert "YOU GIVE" not in payload
    assert "YOU GET" not in payload
    assert "YOU SEND" not in payload
    assert "Tongue Punchers receives" in payload
    assert "Harbor Club receives" in payload

    unnamed = share.build_trade_share_card(
        {
            "trade_gain": 0,
            "send_assets": [{"name": "Send", "player_id": "1"}],
            "receive_assets": [{"name": "Get", "player_id": "2"}],
            "reasoning_summary": "You add future flexibility.",
        }
    )
    assert unnamed.send_side_label == "Trade partner receives"
    assert unnamed.receive_side_label == "This roster receives"
    assert "YOU GIVE" not in share.build_share_text_payload(unnamed)
    assert "Proposing roster" not in share.build_share_text_payload(unnamed)
    assert "You add" not in unnamed.reason
    assert "This roster adds future flexibility" in unnamed.reason
    assert unnamed.verdict == "Fair"
    payload = share.build_share_text_payload(unnamed)
    assert "Edge:" in payload
    assert payload.index("Fair") < payload.index("Edge:")
    assert "Balance:" not in payload

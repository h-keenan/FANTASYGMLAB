"""Growth share cards (Trade Grade, Power Rankings) — contracts and regressions.

Follows the same shape as tests/test_share_recommendation_cards.py and
tests/test_share_composition_layout.py: assert on returned PNG bytes'
format/dimensions and on the pure data-shaping functions, never on exact
pixels — no display or font-rendering environment is assumed.
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd
import pytest

from modules import premium
from modules import share_recommendation_cards as share


def _trade_card(*, send_total=3503, acquire_total=3740, partner="Partner Squad", mine="My Dynasty Team"):
    return share.build_trade_share_card(
        {
            "tag": "Get younger plus pick",
            "trade_gain": acquire_total - send_total,
            "my_score": send_total,
            "their_score": acquire_total,
            "trade_confidence_label": "Low",
            "reasoning_summary": "Move aging RB volume for a younger WR and a 2027 third.",
            "send_assets": [
                {
                    "asset_type": "player",
                    "name": "Tyrone Tracy",
                    "position": "RB",
                    "team": "NYG",
                    "player_id": "tracy",
                }
            ],
            "receive_assets": [
                {
                    "asset_type": "player",
                    "name": "Pat Bryant",
                    "position": "WR",
                    "team": "DEN",
                    "player_id": "bryant",
                },
                {"asset_type": "pick", "label": "2027 Round 3", "position": "PICK"},
            ],
            "partner_team_name": partner,
        },
        my_team_name=mine,
    )


def _rankings_frame(n: int = 10) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append(
            {
                "team_name": f"Team {i + 1}",
                "owner_name": f"Owner {i + 1}",
                "owner_username": f"owner{i + 1}" if i % 2 == 0 else "",
                "power_rank": i + 1,
                "power_score": 2000 - i * 37,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Growth feature is never gated behind entitlement.
# ---------------------------------------------------------------------------


def test_share_card_export_never_gated():
    assert premium.can_export_share_card(None) is True
    assert premium.can_export_share_card("free") is True
    assert premium.can_export_share_card("front_office") is True


# ---------------------------------------------------------------------------
# Fixed 1080x1350 PNG format.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Watermark / footer.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Trade grade data-shaping (pure logic, no rendering).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Power rankings data-shaping (pure logic, no rendering).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Analytics wiring — reuses the already-reserved share_card_* events.
# ---------------------------------------------------------------------------

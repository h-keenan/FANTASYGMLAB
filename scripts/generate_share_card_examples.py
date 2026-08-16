#!/usr/bin/env python3
"""Generate example Share Recommendation PNGs for visual QA (offline)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import share_card_renderer
from modules import share_recommendation_cards as share


OUT = ROOT / "artifacts" / "share-cards"


def main() -> int:
    share.clear_share_cache_for_tests()
    OUT.mkdir(parents=True, exist_ok=True)
    examples = {
        "1-for-1": share.build_trade_share_card(
            {
                "trade_gain": 213,
                "trade_confidence_label": "Low",
                "reasoning_summary": "Swap replaceable RB volume for a weekly WR starter.",
                "partner_team_name": "Lakefront Franchise",
                "send_assets": [
                    {"name": "Aaron Jones", "position": "RB", "team": "MIN", "player_id": "4199"},
                ],
                "receive_assets": [
                    {"name": "Darnell Mooney", "position": "WR", "team": "ATL", "player_id": "5859"},
                ],
            }
        ),
        "1-for-player-pick": share.build_trade_share_card(
            {
                "trade_gain": 213,
                "trade_confidence_label": "Low",
                "reasoning_summary": "Move aging RB volume for a younger WR and a 2027 third.",
                "partner_team_name": "The League 🏈",
                "send_assets": [
                    {"name": "Aaron Jones", "position": "RB", "team": "MIN", "player_id": "4199"},
                ],
                "receive_assets": [
                    {"name": "Darnell Mooney", "position": "WR", "team": "ATL", "player_id": "5859"},
                    {"asset_type": "pick", "label": "2027 R3"},
                ],
            }
        ),
        "2-for-1": share.build_trade_share_card(
            {
                "trade_gain": 88,
                "trade_confidence_label": "Medium",
                "reasoning_summary": "Consolidate two replaceable pieces into a weekly starter.",
                "partner_team_name": "Northside Forever and Always Dynasty Club",
                "send_assets": [
                    {"name": "Aaron Jones", "position": "RB", "team": "MIN", "player_id": "4199"},
                    {"name": "Tank Bigsby", "position": "RB", "team": "PHI", "player_id": "9225"},
                ],
                "receive_assets": [
                    {"name": "Darnell Mooney", "position": "WR", "team": "ATL", "player_id": "5859"},
                ],
            }
        ),
        "long-player-name": share.build_trade_share_card(
            {
                "trade_gain": 120,
                "trade_confidence_label": "Low",
                "reasoning_summary": "Buy the name that still has a path to snaps.",
                "send_assets": [
                    {"name": "Equanimeous St. Brown", "position": "WR", "team": "NO", "player_id": "eq1"},
                ],
                "receive_assets": [
                    {"name": "D'Andre Swift-Jones III", "position": "RB", "team": "CHI", "player_id": "ds1"},
                ],
            }
        ),
        "waiver-add": share.build_waiver_share_card(
            {
                "name": "Breakout WR",
                "position": "WR",
                "team": "ATL",
                "player_id": "505",
                "opportunity_confidence": "High",
            },
            action="Add",
            reason="Immediate depth with a clear path to snaps.",
            position_rank=28,
            overall_rank=87,
            scoring_format="PPR",
        ),
        "player-hold": share.build_player_share_card(
            display_name="Franchise RB",
            player_id="606",
            position="RB",
            team="SF",
            overall_rank=11,
            position_rank=3,
            scoring_format="PPR",
            narrative={
                "is_active_recommendation": True,
                "action": "Hold",
                "reason": "Workhorse role with durable weekly leverage.",
                "confidence_label": "High",
            },
        ),
    }
    for name, card in examples.items():
        png = share_card_renderer.render_share_card_png(card, portraits={})
        path = OUT / f"{name}.png"
        path.write_bytes(png)
        phone = share_card_renderer.phone_display_png(png, 390)
        (OUT / f"{name}-390.png").write_bytes(phone)
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

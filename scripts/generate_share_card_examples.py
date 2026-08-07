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
        "trade-player-for-player": share.build_trade_share_card(
            {
                "trade_gain": 314,
                "trade_confidence_label": "High",
                "reasoning_summary": "Acquire the ascending WR while sending replaceable depth.",
                "send_assets": [
                    {"name": "Depth WR", "position": "WR", "team": "CHI", "player_id": "101"},
                ],
                "receive_assets": [
                    {"name": "Alpha WR", "position": "WR", "team": "MIA", "player_id": "202"},
                ],
            }
        ),
        "trade-player-plus-pick": share.build_trade_share_card(
            {
                "trade_gain": 88,
                "trade_confidence_label": "Medium",
                "reasoning_summary": "Buy the QB window with a future second.",
                "send_assets": [
                    {"name": "Veteran QB", "position": "QB", "team": "LV", "player_id": "303"},
                    {"asset_type": "pick", "label": "2027 2nd"},
                ],
                "receive_assets": [
                    {"name": "Ascending QB", "position": "QB", "team": "GB", "player_id": "404"},
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
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

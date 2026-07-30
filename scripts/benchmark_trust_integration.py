"""Deterministic local/CI microbenchmark for Trust Engine boundaries.

This does not claim to measure authenticated Render routes. It isolates the
incremental player-boundary and visible-board enforcement cost without network
calls or private league data.
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.player_eligibility import annotate_player_eligibility, player_eligibility
from modules.trust_enforcement import enforce_player_record, enforce_trade_board


def _players(count: int = 1000) -> pd.DataFrame:
    now_ms = int(time.time() * 1000)
    return pd.DataFrame(
        [
            {
                "player_id": f"p{index}",
                "name": f"Player {index}",
                "position": "WR",
                "fantasy_positions": ["WR"],
                "sport": "nfl",
                "active": True,
                "status": "Active",
                "team": "A" if index % 2 == 0 else "B",
                "depth_chart_position": "WR",
                "age": 24,
                "bye_week": 8,
                "news_updated": now_ms,
            }
            for index in range(count)
        ]
    )


def _context(players: pd.DataFrame):
    records = {
        str(row["player_id"]): row.to_dict()
        for _, row in players.iterrows()
    }
    enforcement = {
        player_id: enforce_player_record(
            row,
            eligible=True,
            canonical_player_ids=frozenset(records),
        )
        for player_id, row in records.items()
    }
    return records, enforcement


def _ideas(count: int = 8):
    return [
        {
            "send_assets": [
                {
                    "asset_type": "player",
                    "player_id": f"p{index * 2}",
                    "label": f"Player {index * 2}",
                }
            ],
            "receive_assets": [
                {
                    "asset_type": "player",
                    "player_id": f"p{index * 2 + 1}",
                    "label": f"Player {index * 2 + 1}",
                }
            ],
            "partner_team_name": "Other",
            "partner_roster_id": 2,
            "trade_confidence_label": "High",
            "trade_idea_score": 100 - index,
        }
        for index in range(count)
    ]


def _median_ms(func, repeats: int = 7) -> float:
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        func()
        samples.append((time.perf_counter() - started) * 1000)
    return round(statistics.median(samples), 3)


def main() -> None:
    players = _players()
    records, enforcement = _context(players)
    ideas = _ideas()
    ownership = {
        **{f"p{index * 2}": 1 for index in range(8)},
        **{f"p{index * 2 + 1}": 2 for index in range(8)},
    }
    trade_context = {
        "canonical_players": records,
        "player_enforcement": enforcement,
        "ownership_by_player": ownership,
        "valid_roster_ids": frozenset({1, 2}),
        "my_roster_id": 1,
        "team_name_to_roster": {"other": 2},
        "league_context_valid": True,
    }

    player_baseline = _median_ms(
        lambda: [player_eligibility(row) for _, row in players.iterrows()]
    )
    player_cold = _median_ms(lambda: annotate_player_eligibility(players), repeats=1)
    annotated_players = annotate_player_eligibility(players)
    player_warm = _median_ms(
        lambda: annotate_player_eligibility(annotated_players)
    )
    trade_baseline = _median_ms(lambda: list(ideas))
    trade_warm = _median_ms(lambda: enforce_trade_board(ideas, **trade_context))

    assert len(annotate_player_eligibility(players)) == len(players)
    assert len(enforce_trade_board(ideas, **trade_context).recommendations) == len(ideas)
    print(
        {
            "scope": "local_no_network_microbenchmark",
            "players": len(players),
            "trades": len(ideas),
            "player_baseline_ms": player_baseline,
            "player_trust_cold_ms": player_cold,
            "player_trust_warm_ms": player_warm,
            "trade_baseline_ms": trade_baseline,
            "trade_trust_warm_ms": trade_warm,
        }
    )


if __name__ == "__main__":
    main()

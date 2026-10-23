"""Combined #252+#253 valuation hardening harnesses.

Locks value ownership (base vs league vs strategy), decomposable league
adjustments, redraft pick non-stacking, and A→B→A→B cross-league restoration.
"""

from __future__ import annotations

import pandas as pd

from modules import prepared_player_frame
from modules import trade_ideas
from modules import team_eval


def _base_row(player_id: str, **kwargs) -> dict:
    row = {
        "player_id": player_id,
        "name": player_id,
        "position": "WR",
        "team": "KC",
        "age": 25,
        "years_exp": 3,
        "score": 6000,
        "dynasty_score": 6000,
        "value_score": 6000,
        "market_score": 6000,
        "role_score": 7000,
        "opportunity_score": 7000,
        "scarcity_score": 2000,
        "risk_multiplier": 1.0,
        "status": "Active",
        "injury_status": "",
        "search_rank": 40,
        "targets": 80,
        "receptions": 55,
        "rush_attempts": 0,
        "passing_tds": 0,
        "passing_yards": 0,
    }
    row.update(kwargs)
    return row


def test_252_regressions_opportunity_lineup_role_field():
    # Starter At Risk no double haircut
    from modules import rankings

    major = rankings.opportunity_profile(
        "RB",
        depth_chart_position="RB",
        market_score=6000,
        depth_chart_order=1,
        years_exp=3,
        age=24,
        status="Injured Reserve",
        injury_status="Torn ACL",
    )
    assert major["opportunity_label"] == "Starter At Risk"
    assert major["opportunity_score"] == 6600

    frame = pd.DataFrame(
        [
            {"player_id": "young", "name": "Y", "position": "RB", "dynasty_score": 9000, "value_score": 1000},
            {"player_id": "old", "name": "O", "position": "RB", "dynasty_score": 2000, "value_score": 8000},
            {"player_id": "qb", "name": "Q", "position": "QB", "dynasty_score": 5000, "value_score": 5000},
        ]
    )
    dynasty_lineup = team_eval.suggest_optimal_lineup(
        frame, {"QB": 1, "RB": 1, "WR": 0, "TE": 0, "FLEX": 0, "K": 0}, score_field="dynasty_score"
    )
    assert (
        dynasty_lineup[(dynasty_lineup["position"] == "RB") & dynasty_lineup["suggested_starter"]].iloc[0][
            "player_id"
        ]
        == "young"
    )

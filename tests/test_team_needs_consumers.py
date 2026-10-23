from unittest.mock import patch

import pandas as pd

from modules.roster_needs import assess_team_needs
from modules.waivers_logic import select_top_waiver_opportunity


SETTINGS = {
    "qb_count": 1,
    "rb_count": 1,
    "wr_count": 1,
    "te_count": 1,
    "superflex_count": 0,
    "flex_count": 0,
}


def player(
    player_id: str,
    position: str,
    *,
    age: int = 25,
    years_exp: int = 3,
    value: int = 50,
    tier: str = "Starter",
    opportunity: str = "Strong Opportunity",
    status: str = "Active",
    injury_status: str = "",
) -> dict:
    return {
        "player_id": player_id,
        "name": player_id,
        "position": position,
        "age": age,
        "years_exp": years_exp,
        "value_score": value,
        "market_score": value,
        "player_tier": tier,
        "opportunity_label": opportunity,
        "status": status,
        "injury_status": injury_status,
    }


def covered_roster() -> tuple[pd.DataFrame, pd.DataFrame]:
    roster = pd.DataFrame(
        [
            player("elite-qb", "QB", age=27, years_exp=5, value=80, tier="Star"),
            player(
                "backup-qb",
                "QB",
                age=29,
                years_exp=7,
                value=28,
                tier="Contributor",
                opportunity="Backup With Upside",
            ),
            player(
                "developmental-qb",
                "QB",
                age=22,
                years_exp=1,
                value=18,
                tier="Developmental",
            ),
            player("rb", "RB", age=23, years_exp=2, value=60, tier="Core Starter"),
            player("wr", "WR", age=23, years_exp=2, value=60, tier="Core Starter"),
            player("te", "TE", age=23, years_exp=2, value=60, tier="Core Starter"),
        ]
    )
    lineup = roster.copy()
    lineup["suggested_starter"] = [True, False, False, True, True, True]
    return roster, lineup


def test_waiver_context_uses_true_needs_not_relative_weaknesses():
    roster, lineup = covered_roster()
    covered = assess_team_needs(
        roster,
        lineup,
        SETTINGS,
        relative_weaknesses=["QB"],
    )
    deficient_roster = roster[roster["position"].ne("QB")].copy()
    deficient_lineup = lineup[lineup["position"].ne("QB")].copy()
    deficient = assess_team_needs(deficient_roster, deficient_lineup, SETTINGS)
    free_agents = pd.DataFrame(
        [
            {"player_id": "qb-fa", "position": "QB", "value_score": 90},
            {"player_id": "rb-fa", "position": "RB", "value_score": 60},
        ]
    )

    covered_selected = select_top_waiver_opportunity(
        free_agents,
        roster,
        SETTINGS,
        "value_score",
        needed_positions=list(covered.true_needs),
    )
    deficient_selected = select_top_waiver_opportunity(
        free_agents,
        deficient_roster,
        SETTINGS,
        "value_score",
        needed_positions=list(deficient.true_needs),
    )

    assert covered_selected["player_id"] == "rb-fa"
    assert deficient_selected["player_id"] == "qb-fa"


def test_true_te_need_still_supplies_waiver_need_context():
    roster, lineup = covered_roster()
    deficient_roster = roster[roster["position"].ne("TE")].copy()
    deficient_lineup = lineup[lineup["position"].ne("TE")].copy()
    assessment = assess_team_needs(
        deficient_roster,
        deficient_lineup,
        SETTINGS,
    )
    free_agents = pd.DataFrame(
        [
            {"player_id": "te-fa", "position": "TE", "value_score": 90},
            {"player_id": "rb-fa", "position": "RB", "value_score": 60},
        ]
    )

    selected = select_top_waiver_opportunity(
        free_agents,
        deficient_roster,
        SETTINGS,
        "value_score",
        needed_positions=list(assessment.true_needs),
    )

    assert "TE" in assessment.true_needs
    assert selected["player_id"] == "te-fa"

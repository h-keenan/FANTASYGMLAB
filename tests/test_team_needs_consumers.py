from modules.roster_needs import assessment_from_model
from modules.waivers_logic import select_top_waiver_opportunity
import pandas as pd

from tests.need_model_fixtures import room, team_needs

SETTINGS = {
    "qb_count": 1,
    "rb_count": 1,
    "wr_count": 1,
    "te_count": 1,
    "superflex_count": 0,
    "flex_count": 0,
}


def _roster() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"player_id": "qb", "name": "qb", "position": "QB", "age": 27, "value_score": 8000},
            {"player_id": "rb", "name": "rb", "position": "RB", "age": 24, "value_score": 6000},
            {"player_id": "wr", "name": "wr", "position": "WR", "age": 24, "value_score": 6000},
            {"player_id": "te", "name": "te", "position": "TE", "age": 24, "value_score": 6000},
        ]
    )


def _free_agents() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"player_id": "qb-fa", "position": "QB", "value_score": 900},
            {"player_id": "rb-fa", "position": "RB", "value_score": 600},
        ]
    )


def test_waiver_context_uses_true_needs_not_relative_weakness():
    # QB trails the league a little (watch) but is covered: not a need, so the
    # best add is the free agent at the position the roster actually needs.
    covered = assessment_from_model(
        team_needs(room("QB", "watch", rank=7), room("RB", "secondary", slot="RB1", rank=10), room("WR", "covered"))
    )
    # With QB itself the need, the QB free agent wins.
    deficient = assessment_from_model(team_needs(room("QB", "secondary", rank=11), room("RB", "covered")))

    covered_selected = select_top_waiver_opportunity(
        _free_agents(), _roster(), SETTINGS, "value_score", needed_positions=list(covered.true_needs)
    )
    deficient_selected = select_top_waiver_opportunity(
        _free_agents(), _roster(), SETTINGS, "value_score", needed_positions=list(deficient.true_needs)
    )

    assert covered.true_needs == ("RB",)
    assert covered_selected["player_id"] == "rb-fa"
    assert deficient.true_needs == ("QB",)
    assert deficient_selected["player_id"] == "qb-fa"


def test_true_te_need_still_supplies_waiver_need_context():
    assessment = assessment_from_model(team_needs(room("TE", "secondary", slot="TE1", rank=11), room("RB", "covered")))
    free_agents = pd.DataFrame(
        [
            {"player_id": "te-fa", "position": "TE", "value_score": 900},
            {"player_id": "rb-fa", "position": "RB", "value_score": 600},
        ]
    )

    selected = select_top_waiver_opportunity(
        free_agents, _roster(), SETTINGS, "value_score", needed_positions=list(assessment.true_needs)
    )

    assert "TE" in assessment.true_needs
    assert selected["player_id"] == "te-fa"

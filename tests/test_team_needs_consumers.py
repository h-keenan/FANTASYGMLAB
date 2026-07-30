from unittest.mock import patch

import pandas as pd

import app
from modules.roster_needs import assess_team_needs
from modules.waivers_ui import select_top_waiver_opportunity


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


def test_get_needed_positions_adapts_canonical_true_needs_and_fallbacks():
    roster, lineup = covered_roster()
    assessment = assess_team_needs(
        roster,
        lineup,
        SETTINGS,
        relative_weaknesses=["QB"],
    )

    true_only = app.get_needed_positions(
        roster,
        {"weaknesses": ["QB"]},
        SETTINGS,
        include_fallback=False,
        assessment=assessment,
    )
    with_fallback = app.get_needed_positions(
        roster,
        {"weaknesses": ["QB"]},
        SETTINGS,
        include_fallback=True,
        assessment=assessment,
    )

    assert true_only == []
    assert with_fallback == ["QB"]
    assert assessment.true_needs == ()
    assert assessment.upgrade_opportunities == ("QB",)


def test_get_needed_positions_true_needs_are_deterministic_and_precede_fallbacks():
    roster, lineup = covered_roster()
    roster = roster[~roster["position"].isin(["RB", "WR"])].copy()
    lineup = lineup[lineup["player_id"].isin(roster["player_id"])].copy()
    assessment = assess_team_needs(
        roster,
        lineup,
        SETTINGS,
        relative_weaknesses=["QB"],
    )

    assert app.get_needed_positions(
        roster,
        {"weaknesses": ["QB"]},
        SETTINGS,
        include_fallback=False,
        assessment=assessment,
    ) == ["RB", "WR"]
    assert app.get_needed_positions(
        roster,
        {"weaknesses": ["QB"]},
        SETTINGS,
        include_fallback=True,
        assessment=assessment,
    ) == ["RB", "WR", "QB"]


def test_existing_lineup_is_reused_when_building_assessment():
    roster, lineup = covered_roster()

    with patch("app.suggest_optimal_lineup") as suggest:
        assessment = app.build_team_needs_assessment(
            roster,
            {"weaknesses": ["QB"]},
            SETTINGS,
            lineup_df=lineup,
        )

    suggest.assert_not_called()
    assert assessment.upgrade_opportunities == ("QB",)


def test_dashboard_need_display_distinguishes_true_need_and_upgrade():
    roster, lineup = covered_roster()
    covered = assess_team_needs(
        roster,
        lineup,
        SETTINGS,
        relative_weaknesses=["QB"],
    )
    deficient_roster = roster[roster["position"].ne("QB")].copy()
    deficient_lineup = lineup[lineup["position"].ne("QB")].copy()
    deficient = assess_team_needs(
        deficient_roster,
        deficient_lineup,
        SETTINGS,
        relative_weaknesses=["QB"],
    )

    assert app.team_need_display(covered)["label"] == "Upgrade Opportunity"
    assert app.team_need_display(covered)["value"] == "QB"
    assert app.team_need_display(deficient)["label"] == "Biggest Team Need"
    assert app.team_need_display(deficient)["value"] == "QB"


def test_my_team_advice_keeps_upgrade_separate_from_true_need():
    roster, lineup = covered_roster()
    upgrade = assess_team_needs(
        roster,
        lineup,
        SETTINGS,
        relative_weaknesses=["QB"],
    )
    upgrade_advice = app.build_my_team_advice(
        roster,
        lineup,
        {"weaknesses": ["QB"], "strategy": "contender"},
        SETTINGS,
        needed_positions=[],
        assessment=upgrade,
    )
    deficient_roster = roster[roster["position"].ne("QB")].copy()
    deficient_lineup = lineup[lineup["position"].ne("QB")].copy()
    deficient = assess_team_needs(
        deficient_roster,
        deficient_lineup,
        SETTINGS,
    )
    deficient_advice = app.build_my_team_advice(
        deficient_roster,
        deficient_lineup,
        {"weaknesses": [], "strategy": "contender"},
        SETTINGS,
        needed_positions=list(deficient.true_needs),
        assessment=deficient,
    )

    assert any(item["label"] == "Upgrade" for item in upgrade_advice)
    assert not any(item["label"] == "Need" for item in upgrade_advice)
    assert any(item["label"] == "Need" for item in deficient_advice)


def test_dashboard_need_display_distinguishes_injury_future_and_balanced():
    roster, lineup = covered_roster()
    balanced = assess_team_needs(roster, lineup, SETTINGS)
    injured = roster.copy()
    injured.loc[injured["player_id"].eq("elite-qb"), ["status", "injury_status"]] = [
        "IR",
        "out",
    ]
    injured_lineup = lineup.copy()
    injured_assessment = assess_team_needs(injured, injured_lineup, SETTINGS)
    future_roster = pd.DataFrame(
        [
            player(
                "old-rb",
                "RB",
                age=31,
                years_exp=9,
                value=45,
                tier="Starter",
            ),
            *[row for row in roster.to_dict("records") if row["position"] != "RB"],
        ]
    )
    future_lineup = future_roster.copy()
    future_lineup["suggested_starter"] = [
        row["player_id"] in {"old-rb", "elite-qb", "wr", "te"}
        for row in future_roster.to_dict("records")
    ]
    future = assess_team_needs(future_roster, future_lineup, SETTINGS)

    assert app.team_need_display(balanced)["label"] == "Balanced Roster"
    assert app.team_need_display(injured_assessment)["label"] == "Injury Pressure"
    assert app.team_need_display(future)["label"] == "Future Roster Risk"


def test_player_fit_wording_uses_canonical_categories_for_quick_and_detail():
    roster, lineup = covered_roster()
    upgrade = assess_team_needs(
        roster,
        lineup,
        SETTINGS,
        relative_weaknesses=["QB"],
    )
    deficient_roster = roster[roster["position"].ne("QB")].copy()
    deficient_lineup = lineup[lineup["position"].ne("QB")].copy()
    need = assess_team_needs(deficient_roster, deficient_lineup, SETTINGS)

    quick_upgrade = app.player_fit_context("QB", upgrade)
    detail_upgrade = app.player_fit_context("QB", upgrade)
    quick_need = app.player_fit_context("QB", need)
    detail_need = app.player_fit_context("QB", need)

    assert quick_upgrade == detail_upgrade
    assert quick_upgrade["category"] == "upgrade"
    assert "Upgrades a covered QB room" in quick_upgrade["message"]
    assert quick_need == detail_need
    assert quick_need["category"] == "true_need"
    assert "Fills a QB roster need" in quick_need["message"]


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

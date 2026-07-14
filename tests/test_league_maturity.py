import inspect

import pandas as pd

from modules import league_maturity


def _rosters(games=0, count=4, populated=True):
    rows = []
    for roster_id in range(1, count + 1):
        rows.append(
            {
                "roster_id": roster_id,
                "players": [f"p{roster_id}"] if populated else [],
                "settings": {
                    "wins": games,
                    "losses": 0,
                    "ties": 0,
                },
            }
        )
    return rows


def _analysis(trades=0, waivers=0, transactions=0, managers=4):
    return pd.DataFrame(
        [
            {
                "roster_id": roster_id,
                "trade_count": trades,
                "waiver_moves": waivers,
                "transaction_count": transactions,
            }
            for roster_id in range(1, managers + 1)
        ]
    )


def test_startup_in_progress_uses_draft_and_roster_evidence():
    evidence = league_maturity.build_league_evidence(
        startup_context={
            "startup_mode": True,
            "draft_status": "in_progress",
            "draft_completed": False,
        },
        rosters=_rosters(populated=False),
    )
    assert evidence["maturity"] == "STARTUP_IN_PROGRESS"
    assert evidence["dashboard_phase"] == "startup"


def test_brand_new_completed_startup_has_no_fabricated_history():
    evidence = league_maturity.build_league_evidence(
        startup_context={
            "draft_status": "complete",
            "draft_completed": True,
        },
        rosters=_rosters(),
        league_frame=_analysis(),
    )
    assert evidence["maturity"] == "NEW_STARTUP"
    assert evidence["completed_trades"] == 0
    assert evidence["waiver_moves"] == 0
    assert not league_maturity.insight_is_available(
        "most_active_trader", evidence
    )
    assert not league_maturity.insight_is_available(
        "likely_buyers", evidence
    )
    assert not league_maturity.insight_is_available(
        "trade_tendencies", evidence
    )


def test_zero_trade_league_gets_informative_evidence_placeholder():
    evidence = league_maturity.build_league_evidence(
        rosters=_rosters(games=5),
        league_frame=_analysis(trades=0, waivers=4, transactions=4),
    )
    status = league_maturity.evidence_status("likely_sellers", evidence)
    assert status["available"] is False
    assert "Not enough league history yet" in status["message"]
    assert "completed trades" in status["message"]


def test_many_trade_league_unlocks_trade_history_insights():
    evidence = league_maturity.build_league_evidence(
        rosters=_rosters(games=6),
        league_frame=_analysis(trades=2, transactions=5),
    )
    assert evidence["completed_trades"] == 4
    assert evidence["trade_participants"] == 4
    assert league_maturity.insight_is_available(
        "most_active_trader", evidence
    )
    assert league_maturity.insight_is_available("likely_buyers", evidence)
    assert league_maturity.insight_is_available("likely_sellers", evidence)
    assert league_maturity.insight_is_available(
        "trade_tendencies", evidence
    )


def test_many_waivers_unlock_waiver_tendencies_without_trade_claims():
    evidence = league_maturity.build_league_evidence(
        rosters=_rosters(games=3),
        league_frame=_analysis(waivers=2, transactions=2),
    )
    assert evidence["waiver_moves"] == 8
    assert league_maturity.insight_is_available(
        "waiver_tendencies", evidence
    )
    assert not league_maturity.insight_is_available(
        "most_active_trader", evidence
    )


def test_midseason_classifies_from_games_not_calendar_dates():
    evidence = league_maturity.build_league_evidence(
        league={"settings": {"playoff_week_start": 14}},
        rosters=_rosters(games=7),
        league_frame=_analysis(transactions=2),
    )
    assert evidence["maturity"] == "ACTIVE_SEASON"
    assert evidence["dashboard_phase"] == "in_season"


def test_early_season_uses_observed_activity_volume():
    evidence = league_maturity.build_league_evidence(
        rosters=_rosters(games=2),
        league_frame=_analysis(transactions=1),
    )
    assert evidence["maturity"] == "EARLY_SEASON"
    assert evidence["dashboard_phase"] == "early_season"


def test_playoff_push_uses_league_setting_and_games_played():
    evidence = league_maturity.build_league_evidence(
        league={"settings": {"playoff_week_start": 14}},
        rosters=_rosters(games=11),
        league_frame=_analysis(transactions=3),
    )
    assert evidence["playoff_push"] is True
    assert evidence["dashboard_phase"] == "playoff_push"


def test_previous_season_link_marks_mature_dynasty_without_dates():
    evidence = league_maturity.build_league_evidence(
        league={"previous_league_id": "redacted"},
        rosters=_rosters(),
        league_frame=_analysis(),
    )
    assert evidence["maturity"] == "MATURE_DYNASTY"


def _startup_frame():
    return pd.DataFrame(
        [
            {
                "roster_id": 1,
                "team_name": "Alpha",
                "strategy": "contender",
                "power_score": 900,
                "power_rank": 1,
                "franchise_score": 850,
                "avg_age": 27.8,
                "draft_capital": 200,
                "qb_score": 200,
                "rb_score": 240,
                "wr_score": 250,
                "te_score": 90,
                "bench_score": 300,
                "rebuild_index": 70,
                "top_heavy_ratio": 2.0,
                "undervalued_gap": 15,
            },
            {
                "roster_id": 2,
                "team_name": "Bravo",
                "strategy": "rebuild",
                "power_score": 780,
                "power_rank": 2,
                "franchise_score": 920,
                "avg_age": 23.5,
                "draft_capital": 500,
                "qb_score": 260,
                "rb_score": 180,
                "wr_score": 300,
                "te_score": 110,
                "bench_score": 410,
                "rebuild_index": 95,
                "top_heavy_ratio": 3.5,
                "undervalued_gap": 40,
            },
            {
                "roster_id": 3,
                "team_name": "Charlie",
                "strategy": "fringe_contender",
                "power_score": 810,
                "power_rank": 3,
                "franchise_score": 800,
                "avg_age": 25.2,
                "draft_capital": 250,
                "qb_score": 220,
                "rb_score": 260,
                "wr_score": 210,
                "te_score": 140,
                "bench_score": 280,
                "rebuild_index": 75,
                "top_heavy_ratio": 2.5,
                "undervalued_gap": 20,
            },
        ]
    )


def test_startup_specific_insights_use_current_roster_fields_only():
    frame = _startup_frame()
    before = frame.copy(deep=True)
    insights = league_maturity.build_startup_roster_insights(frame)
    by_label = {item["label"]: item for item in insights}

    assert by_label["Strongest Roster After the Draft"]["value"] == "Alpha"
    assert by_label["Youngest Contender"]["value"] == "Charlie"
    assert by_label["Oldest Contender"]["value"] == "Alpha"
    assert by_label["Highest Future Draft Capital"]["value"] == "Bravo"
    assert by_label["Best WR Room"]["value"] == "Bravo"
    assert by_label["Deepest Bench"]["value"] == "Bravo"
    assert all(
        item["evidence_basis"] == "current_roster_only"
        for item in insights
    )
    pd.testing.assert_frame_equal(frame, before)


def test_existing_ranking_order_and_scores_are_not_changed():
    frame = _startup_frame()
    original_order = frame.sort_values(
        "power_score", ascending=False
    )["roster_id"].tolist()
    original_scores = frame[
        ["roster_id", "power_score", "franchise_score"]
    ].copy()
    league_maturity.build_startup_roster_insights(frame)
    assert (
        frame.sort_values("power_score", ascending=False)["roster_id"].tolist()
        == original_order
    )
    pd.testing.assert_frame_equal(
        frame[["roster_id", "power_score", "franchise_score"]],
        original_scores,
    )


def test_trade_partner_copy_uses_current_fit_until_history_exists():
    idea = {
        "hub_partner_reason": "Team Bravo needs RB help and can move WR depth.",
        "partner_trade_implication": "Aggressive trader.",
    }
    without_history = league_maturity.trade_partner_evidence(
        idea,
        historical_evidence_available=False,
    )
    with_history = league_maturity.trade_partner_evidence(
        idea,
        historical_evidence_available=True,
    )
    assert without_history["reason"] == idea["hub_partner_reason"]
    assert without_history["basis"] == "Current roster construction and package fit"
    assert "completed transaction history" in with_history["basis"]


def test_maturity_module_has_no_network_or_sleeper_dependency():
    source = inspect.getsource(league_maturity)
    assert "requests." not in source
    assert "get_transactions(" not in source
    assert "get_matchups(" not in source
    assert "from modules.sleeper" not in source

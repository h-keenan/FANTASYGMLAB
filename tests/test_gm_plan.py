"""modules.gm_plan — season-phase detection + stance-conditioned aggregation.

GM Plan is an additive roadmap layer: it reads the user's declared Team
Situation stance (modules.team_stance) and already-computed signals
(trade ideas, league rankings) and arranges them into a season-arc plan.
It never computes new valuation math, and it must degrade honestly (never
fabricate advice) when a signal is missing.
"""

from __future__ import annotations

from modules import gm_plan
from modules import team_stance as team_stance_module


# --- derive_season_phase -----------------------------------------------------


def test_no_week_reads_as_offseason_adjacent():
    assert gm_plan.derive_season_phase(0) == gm_plan.PHASE_OFFSEASON_ADJACENT
    assert gm_plan.derive_season_phase(None) == gm_plan.PHASE_OFFSEASON_ADJACENT
    assert gm_plan.derive_season_phase("") == gm_plan.PHASE_OFFSEASON_ADJACENT
    assert gm_plan.derive_season_phase(-1) == gm_plan.PHASE_OFFSEASON_ADJACENT


def test_week_past_realistic_season_length_reads_as_offseason_adjacent():
    assert gm_plan.derive_season_phase(19) == gm_plan.PHASE_OFFSEASON_ADJACENT
    assert gm_plan.derive_season_phase(52) == gm_plan.PHASE_OFFSEASON_ADJACENT


def test_early_weeks_are_early_season():
    for week in (1, 2, 3):
        assert gm_plan.derive_season_phase(week) == gm_plan.PHASE_EARLY_SEASON


def test_mid_season_weeks_are_trade_deadline_approach_with_default_playoff_start():
    # Default playoff_week_start is 15 (matches modules.league_recaps /
    # modules.league_history's own default), so the playoff-push lookback
    # window (playoff_week_start - 3 = 12) starts at week 12.
    for week in (4, 8, 11):
        assert gm_plan.derive_season_phase(week) == gm_plan.PHASE_TRADE_DEADLINE_APPROACH


def test_weeks_within_lookback_of_playoffs_are_playoff_push():
    for week in (12, 13, 14, 15, 17):
        assert gm_plan.derive_season_phase(week) == gm_plan.PHASE_PLAYOFF_PUSH


def test_explicit_playoff_week_start_overrides_default():
    # A league with an early (week 12) playoff start pushes the "playoff
    # push" window back to start at week 9.
    assert gm_plan.derive_season_phase(9, playoff_week_start=12) == gm_plan.PHASE_PLAYOFF_PUSH
    assert gm_plan.derive_season_phase(8, playoff_week_start=12) == gm_plan.PHASE_TRADE_DEADLINE_APPROACH


def test_invalid_playoff_week_start_falls_back_to_default():
    assert gm_plan.derive_season_phase(11, playoff_week_start="not-a-number") == gm_plan.PHASE_TRADE_DEADLINE_APPROACH
    assert gm_plan.derive_season_phase(12, playoff_week_start=0) == gm_plan.PHASE_PLAYOFF_PUSH


def test_non_numeric_week_is_treated_as_no_week():
    assert gm_plan.derive_season_phase("not-a-week") == gm_plan.PHASE_OFFSEASON_ADJACENT


def test_phase_label_covers_every_phase_and_has_an_honest_fallback():
    for phase in gm_plan.SEASON_PHASES:
        assert gm_plan.phase_label(phase)
    assert gm_plan.phase_label("not-a-real-phase") == gm_plan.PHASE_LABELS[gm_plan.PHASE_OFFSEASON_ADJACENT]


# --- build_gm_plan: stance conditioning -------------------------------------


def _rankings_row(**overrides) -> dict:
    row = {
        "power_rank": 3,
        "power_rank_tied": False,
        "draft_capital_rank": 9,
        "draft_capital_rank_tied": True,
        "starter_rank": 2,
        "starter_rank_tied": False,
        "bench_rank": 11,
        "bench_rank_tied": False,
        "age_rank": 6,
        "age_rank_tied": False,
    }
    row.update(overrides)
    return row


def test_build_gm_plan_reports_normalized_stance_and_label():
    plan = gm_plan.build_gm_plan(
        team_stance="Rebuilding",
        season_phase=gm_plan.PHASE_TRADE_DEADLINE_APPROACH,
    )
    assert plan["team_stance"] == team_stance_module.STANCE_REBUILDING
    assert plan["team_stance_label"] == "Rebuilding"


def test_build_gm_plan_unknown_stance_normalizes_to_empty_and_uses_no_stance_copy():
    plan = gm_plan.build_gm_plan(team_stance="tanking", season_phase=gm_plan.PHASE_EARLY_SEASON)
    assert plan["team_stance"] == ""
    assert plan["team_stance_label"] == ""
    assert "Declare a Team Situation stance" in plan["headline"]


def test_build_gm_plan_invalid_phase_falls_back_to_offseason_adjacent():
    plan = gm_plan.build_gm_plan(team_stance="", season_phase="not-a-real-phase")
    assert plan["season_phase"] == gm_plan.PHASE_OFFSEASON_ADJACENT


def test_stance_changes_trade_focus_area_framing_text():
    rebuild_plan = gm_plan.build_gm_plan(
        team_stance="rebuilding", season_phase=gm_plan.PHASE_TRADE_DEADLINE_APPROACH
    )
    compete_plan = gm_plan.build_gm_plan(
        team_stance="competing", season_phase=gm_plan.PHASE_TRADE_DEADLINE_APPROACH
    )
    rebuild_trade = next(fa for fa in rebuild_plan["focus_areas"] if fa["key"] == gm_plan.FOCUS_TRADE)
    compete_trade = next(fa for fa in compete_plan["focus_areas"] if fa["key"] == gm_plan.FOCUS_TRADE)
    assert rebuild_trade["framing"] != compete_trade["framing"]
    assert "youth" in rebuild_trade["framing"].lower()
    assert "immediate" in compete_trade["framing"].lower()


# --- build_gm_plan: signal traceability + honest no-signal behavior --------


def test_trade_focus_area_carries_real_idea_fields_and_a_traceable_source():
    ideas = [
        {
            "partner_team_name": "Team Foo",
            "my_player": "Player A",
            "their_player": "Player B",
            "my_player_id": "my-1",
            "their_player_id": "their-1",
            "rationale": "This fits your declared rebuild.",
            "trade_confidence_label": "Strong",
            "priority": 1,
            "receive_assets": [
                {"asset_type": "player", "player_id": "their-1", "status": "Active", "injury_status": ""}
            ],
        }
    ]
    plan = gm_plan.build_gm_plan(
        team_stance="rebuilding", season_phase=gm_plan.PHASE_EARLY_SEASON, trade_ideas=ideas
    )
    trade_area = next(fa for fa in plan["focus_areas"] if fa["key"] == gm_plan.FOCUS_TRADE)
    assert trade_area["status"] == gm_plan.STATUS_SIGNAL_FOUND
    assert trade_area["watch_for"] == ""
    assert len(trade_area["items"]) == 1
    item = trade_area["items"][0]
    assert item["partner_team_name"] == "Team Foo"
    assert item["my_player"] == "Player A"
    assert item["their_player"] == "Player B"
    assert item["my_player_id"] == "my-1"
    assert item["their_player_id"] == "their-1"
    assert item["their_player_injury_display"] == ""
    assert item["rationale"] == "This fits your declared rebuild."
    assert item["trade_confidence_label"] == "Strong"
    assert "trade_ideas" in item["source"] or "trade_hub_engine" in item["source"]


def test_trade_focus_area_surfaces_receive_side_injury_display():
    """The data-contract fix: GM Plan's trade-opportunity items previously
    discarded player_id/injury data even though modules.trade_ideas already
    computes it on every idea's receive_assets — this is real signal, not an
    invented one (same modules.rankings.injury_display_label vocabulary
    modules.gm_targets already uses)."""

    ideas = [
        {
            "partner_team_name": "Team Foo",
            "my_player": "Player A",
            "their_player": "Injured Player B",
            "their_player_id": "their-2",
            "receive_assets": [
                {
                    "asset_type": "player",
                    "player_id": "their-2",
                    "status": "Injured Reserve",
                    "injury_status": "Torn ACL",
                }
            ],
        }
    ]
    plan = gm_plan.build_gm_plan(team_stance="", season_phase=gm_plan.PHASE_EARLY_SEASON, trade_ideas=ideas)
    trade_area = next(fa for fa in plan["focus_areas"] if fa["key"] == gm_plan.FOCUS_TRADE)
    item = trade_area["items"][0]
    assert item["their_player_id"] == "their-2"
    assert item["their_player_injury_display"] == "Torn ACL"


def test_trade_focus_area_respects_max_trade_ideas_cap():
    ideas = [{"partner_team_name": f"Team {i}"} for i in range(10)]
    plan = gm_plan.build_gm_plan(
        team_stance="", season_phase=gm_plan.PHASE_EARLY_SEASON, trade_ideas=ideas, max_trade_ideas=2
    )
    trade_area = next(fa for fa in plan["focus_areas"] if fa["key"] == gm_plan.FOCUS_TRADE)
    assert len(trade_area["items"]) == 2


def test_trade_focus_area_ignores_non_mapping_entries():
    ideas = ["not-a-dict", {"partner_team_name": "Team Foo"}, 42]
    plan = gm_plan.build_gm_plan(team_stance="", season_phase=gm_plan.PHASE_EARLY_SEASON, trade_ideas=ideas)
    trade_area = next(fa for fa in plan["focus_areas"] if fa["key"] == gm_plan.FOCUS_TRADE)
    assert len(trade_area["items"]) == 1


def test_no_trade_ideas_produces_honest_no_signal_status_not_fabricated_advice():
    plan = gm_plan.build_gm_plan(team_stance="competing", season_phase=gm_plan.PHASE_PLAYOFF_PUSH, trade_ideas=[])
    trade_area = next(fa for fa in plan["focus_areas"] if fa["key"] == gm_plan.FOCUS_TRADE)
    assert trade_area["status"] == gm_plan.STATUS_NO_SIGNAL
    assert trade_area["items"] == []
    assert trade_area["watch_for"] == gm_plan.TRADE_NO_SIGNAL_WATCH_FOR


def test_standing_focus_area_surfaces_power_and_draft_capital_rank_with_ties():
    plan = gm_plan.build_gm_plan(
        team_stance="balanced",
        season_phase=gm_plan.PHASE_EARLY_SEASON,
        rankings_row=_rankings_row(),
        total_teams=12,
        record={"wins": 3, "losses": 1, "ties": 0},
    )
    standing = next(fa for fa in plan["focus_areas"] if fa["key"] == gm_plan.FOCUS_STANDING)
    assert standing["status"] == gm_plan.STATUS_SIGNAL_FOUND
    labels = {item["label"] for item in standing["items"]}
    assert "Roster Power" in labels
    assert "Draft Capital Rank" in labels
    assert "Record" in labels
    power_item = next(item for item in standing["items"] if item["label"] == "Roster Power")
    assert power_item["rank"] == 3
    assert power_item["total_teams"] == 12
    assert power_item["tied"] is False
    capital_item = next(item for item in standing["items"] if item["label"] == "Draft Capital Rank")
    assert capital_item["tied"] is True


def test_standing_focus_area_with_no_rankings_row_is_honest_no_signal():
    plan = gm_plan.build_gm_plan(team_stance="", season_phase=gm_plan.PHASE_EARLY_SEASON)
    standing = next(fa for fa in plan["focus_areas"] if fa["key"] == gm_plan.FOCUS_STANDING)
    assert standing["status"] == gm_plan.STATUS_NO_SIGNAL
    assert standing["items"] == []
    assert standing["watch_for"] == gm_plan.STANDING_NO_SIGNAL_WATCH_FOR


def test_standing_focus_area_surfaces_playoff_odds_when_available():
    # modules.playoff_simulator.build_league_playoff_odds_cached's own
    # `teams` row shape for the caller's roster — already-cached, so GM
    # Plan just reads it, never recomputes it.
    plan = gm_plan.build_gm_plan(
        team_stance="balanced",
        season_phase=gm_plan.PHASE_PLAYOFF_PUSH,
        rankings_row=_rankings_row(),
        total_teams=12,
        record={"wins": 8, "losses": 4, "ties": 0},
        playoff_odds={
            "roster_id": "1",
            "playoff_probability": 67.3,
            "median_seed": 4,
            "clinched": False,
            "eliminated": False,
        },
    )
    standing = next(fa for fa in plan["focus_areas"] if fa["key"] == gm_plan.FOCUS_STANDING)
    odds_item = next(item for item in standing["items"] if item["label"] == "Playoff Odds")
    assert odds_item["playoff_probability"] == 67.3
    assert odds_item["median_seed"] == 4
    assert odds_item["clinched"] is False
    assert odds_item["eliminated"] is False
    assert odds_item["source"] == "modules.playoff_simulator.build_league_playoff_odds_cached"


def test_standing_focus_area_omits_playoff_odds_when_not_ready_or_missing():
    # No fabricated fact when the simulation isn't ready yet for this
    # league (offseason / no playoff format / no rankings data) or the
    # caller's roster didn't resolve in it — same honest-degradation
    # contract as every other fact here.
    for not_ready in (None, {}, {"roster_id": "1", "playoff_probability": None}):
        plan = gm_plan.build_gm_plan(
            team_stance="",
            season_phase=gm_plan.PHASE_EARLY_SEASON,
            rankings_row=_rankings_row(),
            total_teams=12,
            playoff_odds=not_ready,
        )
        standing = next(fa for fa in plan["focus_areas"] if fa["key"] == gm_plan.FOCUS_STANDING)
        labels = {item["label"] for item in standing["items"]}
        assert "Playoff Odds" not in labels


def test_roster_focus_area_flags_bottom_third_ranks_as_relative_weak_spots():
    plan = gm_plan.build_gm_plan(
        team_stance="",
        season_phase=gm_plan.PHASE_EARLY_SEASON,
        rankings_row=_rankings_row(bench_rank=11, starter_rank=2),
        total_teams=12,
    )
    roster = next(fa for fa in plan["focus_areas"] if fa["key"] == gm_plan.FOCUS_ROSTER)
    assert roster["status"] == gm_plan.STATUS_SIGNAL_FOUND
    bench_item = next(item for item in roster["items"] if item["label"] == "Bench Depth")
    starter_item = next(item for item in roster["items"] if item["label"] == "Starter Strength")
    assert bench_item["relative_weak_spot"] is True
    assert starter_item["relative_weak_spot"] is False


def test_roster_focus_area_without_rankings_row_is_honest_no_signal():
    plan = gm_plan.build_gm_plan(team_stance="", season_phase=gm_plan.PHASE_EARLY_SEASON)
    roster = next(fa for fa in plan["focus_areas"] if fa["key"] == gm_plan.FOCUS_ROSTER)
    assert roster["status"] == gm_plan.STATUS_NO_SIGNAL
    assert roster["items"] == []
    assert roster["watch_for"] == gm_plan.ROSTER_NO_SIGNAL_WATCH_FOR


def test_build_gm_plan_never_touches_value_score_or_similar_valuation_fields():
    # Guard against scope creep: GM Plan's output must never carry a
    # value_score/dynasty_score/rebuild_score-shaped key anywhere.
    ideas = [{"partner_team_name": "Team Foo", "value_score": 999}]
    plan = gm_plan.build_gm_plan(
        team_stance="rebuilding",
        season_phase=gm_plan.PHASE_EARLY_SEASON,
        rankings_row=_rankings_row(),
        total_teams=12,
        trade_ideas=ideas,
    )

    def _walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                assert "value_score" not in str(key)
                assert "dynasty_score" not in str(key)
                _walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                _walk(value)

    _walk(plan)

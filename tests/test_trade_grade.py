"""Shared user-side trade valuation (modules.trade_grade) and its Analyzer use."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from modules import trade_analyzer_fit, trade_grade, trade_ideas, trade_offer_analyzer

IN_SEASON = trade_grade.SeasonWindow(current_week=7, remaining_weeks=11, in_season=True, source="league")
OFFSEASON = trade_grade.SeasonWindow(current_week=0, remaining_weeks=17, in_season=False, source="league")


# --- season window -------------------------------------------------------------


@pytest.mark.parametrize(
    ("today", "week"),
    (
        (date(2026, 7, 30), 0),
        (date(2026, 9, 8), 1),
        (date(2026, 9, 14), 1),
        (date(2026, 9, 15), 2),
        (date(2026, 10, 21), 7),
        (date(2026, 12, 29), 17),
        (date(2027, 1, 5), 0),
    ),
)
def test_calendar_week_estimate(today, week):
    assert trade_grade.estimate_nfl_week(today) == week


def test_league_week_overrides_the_calendar():
    window = trade_grade.season_window({"current_week": 15}, today=date(2026, 7, 30))
    assert (window.current_week, window.remaining_weeks, window.in_season, window.source) == (15, 3, True, "league")
    offseason = trade_grade.season_window({}, today=date(2026, 7, 30))
    assert (offseason.in_season, offseason.source) == (False, "calendar")


# --- injury duration -------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "injury_status", "weeks"),
    (
        ("Active", "Questionable", 0.25),
        ("Active", "Doubtful", 1.0),
        ("Active", "Out", 2.0),
        ("Inactive", "IR", 4.0),
        ("Injured Reserve", "", 4.0),
        ("Inactive", "PUP", 4.0),
        ("Active", "Sus", 3.0),
    ),
)
def test_status_defaults(status, injury_status, weeks):
    absence = trade_grade.estimate_injury_absence(status, injury_status, window=IN_SEASON)
    assert absence is not None
    assert absence.weeks == weeks
    assert absence.basis.startswith("default for")
    assert not absence.season_ending


def test_suspension_is_priced_as_a_suspension_not_a_minor_injury():
    # #1302: Sleeper's "Sus" used to fall through to the generic minor bucket.
    absence = trade_grade.estimate_injury_absence("Active", "Sus", window=IN_SEASON)
    assert absence.status_label == "Suspended"
    assert absence.weeks == 3.0


@pytest.mark.parametrize("injury_status", ("NA", "", "n/a", None))
def test_na_and_blank_stay_healthy(injury_status):
    # #1295: "NA" is Sleeper's "no designation", not an injury.
    assert trade_grade.estimate_injury_absence("Active", injury_status, window=IN_SEASON) is None


def test_bare_inactive_status_is_not_priced_as_a_recoverable_injury():
    assert trade_grade.estimate_injury_absence("Inactive", "", window=IN_SEASON) is None
    assert trade_grade.estimate_injury_absence("Practice Squad", "", window=IN_SEASON) is None


def test_season_ending_body_part_charges_the_rest_of_the_season():
    absence = trade_grade.estimate_injury_absence("Inactive", "IR", body_part="Knee - ACL", window=IN_SEASON)
    assert absence.season_ending
    assert absence.weeks == IN_SEASON.remaining_weeks


def test_surgery_note_raises_the_estimate():
    absence = trade_grade.estimate_injury_absence("Inactive", "IR", body_part="Neck", notes="Surgery", window=IN_SEASON)
    assert absence.weeks == trade_grade.SURGERY_MIN_WEEKS
    assert not absence.season_ending


# --- injury cost -------------------------------------------------------------------


def _cost(strategy, absence, window=IN_SEASON, starts=True, value=6000):
    return trade_grade.injury_availability_cost(value, absence, strategy=strategy, window=window, starts=starts)


def test_injury_cost_depends_on_posture_duration_role_and_season():
    out = trade_grade.estimate_injury_absence("Active", "Out", window=IN_SEASON)
    ir = trade_grade.estimate_injury_absence("Inactive", "IR", window=IN_SEASON)

    contender, retool, rebuild, tank = (_cost(s, out) for s in ("contender", "retool", "rebuild", "tank"))
    assert contender > retool > rebuild > tank > 0
    # weekly value x weeks x posture: 6000 x 0.40 / 17 x 2 x 0.95
    assert contender == round(6000 * 0.40 / 17 * 2 * 0.95)
    assert _cost("contender", ir) == 2 * contender
    assert _cost("contender", out, starts=False) == round(contender * 0.25)
    assert _cost("contender", out, window=OFFSEASON) == round(contender * 0.10)


def test_injury_cost_is_capped_well_below_a_permanent_loss():
    full_season = trade_grade.SeasonWindow(1, 17, True, "league")
    season = trade_grade.estimate_injury_absence("Inactive", "IR", body_part="Achilles", window=full_season)
    cost = _cost("contender", season, window=full_season)
    assert cost == round(6000 * trade_grade.INJURY_COST_CAP_SHARE)


def test_healthy_restore_only_undoes_a_discount_the_valuation_applied():
    assert trade_grade.healthy_restore_factor({"status": "Active", "injury_status": "Out", "team": "LAC"}, "dynasty_score") == 1.0
    row = {"status": "Active", "injury_status": "Out", "team": "LAC", "search_rank": 35, "risk_multiplier": 0.8}
    # 90% of the composite carries the 0.80 Out multiplier, opportunity does not.
    assert trade_grade.healthy_restore_factor(row, "dynasty_score") == pytest.approx(0.9 * 0.8 + 0.1)
    lensed = dict(row, league_settings_multiplier=1.0)
    assert trade_grade.healthy_restore_factor(lensed, "value_score") == pytest.approx(0.72)
    healthy = dict(row, injury_status="")
    assert trade_grade.healthy_restore_factor(healthy, "dynasty_score") == 1.0


# --- consolidation -----------------------------------------------------------------


def _player(pid, score, position="WR", age=25, **extra):
    return {"asset_type": "player", "player_id": pid, "name": pid, "label": pid, "position": position, "age": age, "score": score, **extra}


def test_consolidation_credits_the_side_that_lands_the_best_asset():
    send = [_player("a", 6000), _player("b", 2500)]
    receive = [_player("star", 8000)]
    credit, note = trade_grade.user_consolidation_adjustment(send, receive)
    assert credit == trade_grade.consolidation_premium(8000, 6000 / 8000) == round(8000 * (0.08 + 0.24 * 0.25))
    assert "consolidates" in note
    debit, note = trade_grade.user_consolidation_adjustment(receive, send)
    assert debit == -credit
    assert "breaks up" in note
    assert trade_grade.user_consolidation_adjustment([_player("a", 6000)], [_player("b", 6500)]) == (0, "")


def test_hub_partner_side_premium_uses_the_same_formula():
    assert trade_ideas._cornerstone_consolidation_premium(
        target_score=9000, headliner_ratio=0.7, first_round_count=1
    ) == (trade_grade.consolidation_premium(9000, 0.7), max(0, trade_grade.consolidation_premium(9000, 0.7) - 850))


# --- Analyzer -------------------------------------------------------------------------

SETTINGS = {
    "league_format": "Dynasty",
    "qb_format": "1QB",
    "qb_count": 1,
    "rb_count": 2,
    "wr_count": 3,
    "te_count": 1,
    "k_count": 0,
    "def_count": 0,
    "flex_count": 1,
    "superflex_count": 0,
    "current_week": 7,
}


def _row(pid, position, score, age=25, **extra):
    row = {
        "player_id": pid,
        "name": pid,
        "position": position,
        "team": "T",
        "status": "Active",
        "injury_status": "",
        "age": age,
        "value_score": score,
        "dynasty_score": score,
        "score": score,
    }
    row.update(extra)
    return row


def _roster():
    return pd.DataFrame(
        [
            _row("QB1", "QB", 6000),
            _row("QB2", "QB", 2000),
            _row("RB1", "RB", 6500),
            _row("RB2", "RB", 5000),
            _row("RB3", "RB", 1500),
            _row("STUD", "WR", 9000, age=26),
            _row("WR2", "WR", 5200),
            _row("WR3", "WR", 4800),
            _row("WR4", "WR", 1400),
            _row("TE1", "TE", 4000),
            _row("TE2", "TE", 900),
        ]
    )


def _pool(*extra_rows):
    return pd.concat([_roster(), pd.DataFrame(list(extra_rows))], ignore_index=True)


def _asset(row):
    return {"asset_type": "player", **row, "label": row["name"]}


def _grade(strategy, send_rows, receive_rows, pool):
    roster = pool[pool["player_id"].isin(_roster()["player_id"])]
    send = [_asset(r) for r in send_rows]
    receive = [_asset(r) for r in receive_rows]
    fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(roster, pool, send, receive, None, strategy, SETTINGS, "dynasty_score")
    return fit, trade_offer_analyzer.decide_offer_verdict(fit, send_assets=send, receive_assets=receive)


def test_breaking_up_a_stud_for_depth_is_a_decline():
    # Trade engine v2: in season the lineup-points model (not the old
    # starter-strength weight) decides. The market says "wins on raw value"
    # but the depth pieces would not start, so the expected lineup points
    # drop. The contender, who weights real lineup points 1.5x, declines; the
    # rebuilder (1.05x) is hurt much less.
    depth = [_row("D1", "WR", 3400), _row("D2", "RB", 3300), _row("D3", "TE", 3300)]
    pool = _pool(*depth)
    stud = _roster().set_index("player_id").loc["STUD"].to_dict() | {"player_id": "STUD"}

    contender_fit, contender = _grade("contender", [stud], depth, pool)
    rebuild_fit, rebuild = _grade("rebuild", [stud], depth, pool)

    assert contender_fit["raw_value_delta"] > 0  # wins on raw value...
    assert contender_fit["lineup_delta"] < -1500  # ...but guts the starting lineup
    assert contender_fit["value_adjustments"]["consolidation"] < 0
    # Season-value starter weight and flat injury cost are replaced in season.
    assert contender_fit["value_adjustments"]["starter_strength"] == 0
    assert contender_fit["lineup_model"]["points"]["ros_delta"] < 0
    assert contender.ui_verdict == "DECLINE"
    assert rebuild.trade_score > contender.trade_score
    # Posture is a parameter of the one model: contenders weight real
    # lineup points more than rebuilders do.
    assert contender_fit["lineup_model"]["weights"]["now"] == 1.5
    assert rebuild_fit["lineup_model"]["weights"]["now"] == 1.05
    assert contender.trade_score == contender_fit["trade_score"]


def test_offseason_keeps_the_value_based_starter_strength_weight():
    # No weekly claims in the offseason: the older value-based pieces stand.
    depth = [_row("D1", "WR", 3400), _row("D2", "RB", 3300), _row("D3", "TE", 3300)]
    pool = _pool(*depth)
    roster = pool[pool["player_id"].isin(_roster()["player_id"])]
    stud = _asset(_roster().set_index("player_id").loc["STUD"].to_dict() | {"player_id": "STUD"})
    send, receive = [stud], [_asset(r) for r in depth]
    fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
        roster, pool, send, receive, None, "contender", dict(SETTINGS, current_week=0), "dynasty_score"
    )
    assert fit["lineup_model"] is None
    assert fit["value_adjustments"]["starter_strength"] == round(fit["lineup_delta"] * 0.5)
    assert fit["trade_score"] == fit["value_delta"]


def test_short_injury_is_an_availability_cost_not_a_value_wipe():
    # A better young WR who is Out this week, valued the way rankings'
    # risk model discounts him (0.9 x 0.80 + 0.1 of his healthy 6000).
    injured = _row(
        "YOUNG",
        "WR",
        round(6000 * 0.82),
        age=23,
        injury_status="Out",
        injury_body_part="Hamstring",
        risk_multiplier=0.8,
    )
    pool = _pool(injured)
    wr2 = _roster().set_index("player_id").loc["WR2"].to_dict() | {"player_id": "WR2"}

    contender_fit, contender = _grade("contender", [wr2], [injured], pool)
    rebuild_fit, rebuild = _grade("rebuild", [wr2], [injured], pool)

    for fit in (contender_fit, rebuild_fit):
        (line,) = fit["injury_lines"]
        assert line["healthy_value"] == 6000
        assert line["estimated_weeks_out"] == 2.0
        assert 0 < line["availability_cost"] < 0.25 * line["healthy_value"]
        # He keeps his lineup spot: the healthy lineup improves.
        assert fit["lineup_delta"] > 0
        assert "no return date" in fit["injury_summary"]
    contender_cost = contender_fit["injury_lines"][0]["availability_cost"]
    rebuild_cost = rebuild_fit["injury_lines"][0]["availability_cost"]
    assert contender_cost > 4 * rebuild_cost
    assert rebuild.ui_verdict in {"FAIR", "ACCEPT"}
    assert contender.ui_verdict in {"FAIR", "ACCEPT"}


def test_offseason_injury_barely_matters():
    injured = _row("YOUNG", "WR", 4920, age=23, injury_status="Out", risk_multiplier=0.8)
    pool = _pool(injured)
    roster = pool[pool["player_id"].isin(_roster()["player_id"])]
    wr2 = _asset(_roster().set_index("player_id").loc["WR2"].to_dict() | {"player_id": "WR2"})
    in_season = trade_analyzer_fit.evaluate_trade_analyzer_fit(
        roster, pool, [wr2], [_asset(injured)], None, "contender", SETTINGS, "dynasty_score"
    )
    offseason = trade_analyzer_fit.evaluate_trade_analyzer_fit(
        roster, pool, [wr2], [_asset(injured)], None, "contender", dict(SETTINGS, current_week=0), "dynasty_score"
    )
    assert offseason["injury_lines"][0]["availability_cost"] < 0.2 * in_season["injury_lines"][0]["availability_cost"]
    assert offseason["season_week"]["in_season"] is False


def test_value_words_read_the_same_score_as_the_verdict_not_the_raw_delta():
    # Audit C1b: the sentence used to read raw_value_delta (+300 -> "slight
    # edge to you") under a score that decides DECLINE.
    fit = {"value_delta": -1300, "raw_value_delta": 300, "component_scores": {}}
    verdict = trade_offer_analyzer.decide_offer_verdict(fit)
    assert verdict.value_delta == -1300
    assert verdict.value_summary == "Large value gap against you"
    assert verdict.ui_verdict == "DECLINE"

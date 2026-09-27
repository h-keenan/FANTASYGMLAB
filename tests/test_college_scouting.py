"""College football prospect scouting — data model, aggregation, and the
crowd -> draft-class-strength wiring (modules.trade_ideas._rookie_class_strength_multiplier).
"""

from __future__ import annotations

from modules import college_scouting as cs
from modules import trade_ideas


def test_placeholder_prospects_are_internally_consistent():
    """The seed catalog itself must be well-formed — every entry has the
    fields the rest of this module assumes, and ids are unique."""

    seen_ids = set()
    for prospect in cs.PLACEHOLDER_PROSPECTS:
        assert prospect["id"] not in seen_ids
        seen_ids.add(prospect["id"])
        assert prospect["name"]
        assert prospect["position"]
        assert prospect["school"]
        assert isinstance(prospect["draft_year"], int)


def test_normalize_grade_rejects_out_of_range_and_bad_input():
    assert cs.normalize_grade(3) == 3
    assert cs.normalize_grade("4") == 4
    assert cs.normalize_grade(0) is None
    assert cs.normalize_grade(6) is None
    assert cs.normalize_grade(None) is None
    assert cs.normalize_grade("not-a-number") is None


def test_normalize_round_projection_optional_and_bounded():
    assert cs.normalize_round_projection(None) is None
    assert cs.normalize_round_projection("") is None
    assert cs.normalize_round_projection(1) == 1
    assert cs.normalize_round_projection(7) == 7
    assert cs.normalize_round_projection(8) is None
    assert cs.normalize_round_projection(0) is None


def test_aggregate_prospect_scouting_pools_valid_reports_only():
    reports = [
        {"user_id": "u1", "prospect_id": "p1", "grade": 5, "round_projection": 1},
        {"user_id": "u2", "prospect_id": "p1", "grade": 3, "round_projection": 2},
        # invalid grade should be skipped, not crash or count as a neutral 3.
        {"user_id": "u3", "prospect_id": "p1", "grade": 99},
        # a different prospect with no reports at all should never appear.
        {"user_id": "u4", "prospect_id": "p2", "grade": None},
    ]
    agg = cs.aggregate_prospect_scouting(reports)
    assert set(agg.keys()) == {"p1"}
    assert agg["p1"]["scout_count"] == 2
    assert agg["p1"]["avg_grade"] == 4.0
    assert agg["p1"]["avg_round_projection"] == 1.5
    assert agg["p1"]["grade_distribution"][5] == 1
    assert agg["p1"]["grade_distribution"][3] == 1


def test_crowd_class_strength_zero_reports_is_absent_not_neutral_zero():
    """A prospect/class with zero scouting entries must not silently read as
    a strong or weak signal — it should simply not appear in the result."""

    prospects = [{"id": "p1", "draft_year": 2026}]
    assert cs.crowd_class_strength_by_year(prospects, []) == {}


def test_crowd_class_strength_small_sample_is_shrunk_toward_neutral():
    prospects = [{"id": f"p{i}", "draft_year": 2026} for i in range(10)]
    # A single, extremely bullish grade (5/5) should not swing the class
    # signal anywhere near its full theoretical +0.2 — one scout is a "low"
    # confidence read.
    reports = [{"user_id": "u1", "prospect_id": "p0", "grade": 5}]
    signal = cs.crowd_class_strength_by_year(prospects, reports)
    assert signal[2026]["confidence"] == "low"
    assert signal[2026]["scout_count"] == 1
    # Shrunk multiplier: raw would be 1.2 (5 -> +0.2), confidence_weight = 1/8.
    assert 1.0 < signal[2026]["multiplier"] < 1.05


def test_crowd_class_strength_full_sample_reaches_near_full_weight():
    prospects = [{"id": f"p{i}", "draft_year": 2026} for i in range(10)]
    reports = [{"user_id": f"u{i}", "prospect_id": "p0", "grade": 5} for i in range(8)]
    signal = cs.crowd_class_strength_by_year(prospects, reports)
    assert signal[2026]["confidence"] == "high"
    # 8 scouts hits MIN_SCOUTS_FOR_FULL_CONFIDENCE -> full weight -> clamped 1.2
    assert abs(signal[2026]["multiplier"] - 1.2) < 1e-6


def test_crowd_class_strength_below_average_grades_pull_multiplier_down():
    prospects = [{"id": f"p{i}", "draft_year": 2026} for i in range(10)]
    reports = [{"user_id": f"u{i}", "prospect_id": "p0", "grade": 1} for i in range(8)]
    signal = cs.crowd_class_strength_by_year(prospects, reports)
    assert signal[2026]["multiplier"] < 1.0


def test_build_prospect_views_marks_my_report_and_watchlist():
    prospects = [
        {"id": "p1", "name": "A", "position": "QB", "school": "X", "draft_year": 2026},
        {"id": "p2", "name": "B", "position": "RB", "school": "Y", "draft_year": 2026},
    ]
    reports = [
        {"user_id": "me", "prospect_id": "p1", "grade": 4, "round_projection": 1, "note": "sleeper"},
        {"user_id": "someone-else", "prospect_id": "p1", "grade": 2},
    ]
    rows = cs.build_prospect_views(
        prospects, reports, my_user_id="me", watchlist_prospect_ids=["p2"]
    )
    by_id = {row["id"]: row for row in rows}
    assert by_id["p1"]["aggregate"]["scout_count"] == 2
    assert by_id["p1"]["aggregate"]["avg_grade"] == 3.0
    assert by_id["p1"]["my_report"]["grade"] == 4
    assert by_id["p1"]["on_watchlist"] is False
    assert by_id["p2"]["my_report"] is None
    assert by_id["p2"]["on_watchlist"] is True


# ---------------------------------------------------------------------------
# Integration with the existing draft-class-strength calculation
# ---------------------------------------------------------------------------


def test_no_crowd_signal_leaves_existing_class_strength_behavior_unchanged():
    """Every existing caller of _rookie_class_strength_multiplier passes no
    crowd_class_strength_by_year at all — this must be byte-for-byte the
    same result as before the crowdsourced signal existed."""

    assert trade_ideas._rookie_class_strength_multiplier(2026) == 1.15
    assert trade_ideas._rookie_class_strength_multiplier(2099) == 1.0


def test_crowd_signal_from_real_reports_blends_into_class_strength():
    prospects = list(cs.PLACEHOLDER_PROSPECTS)
    reports = [{"user_id": f"u{i}", "prospect_id": "2026-qb-01", "grade": 5} for i in range(8)]
    crowd_signal = cs.crowd_class_strength_by_year(prospects, reports)

    editorial_only = trade_ideas._rookie_class_strength_multiplier(2026)
    blended = trade_ideas._rookie_class_strength_multiplier(
        2026, None, crowd_signal
    )
    assert blended != editorial_only
    assert blended == max(0.8, min(1.25, editorial_only * crowd_signal[2026]["multiplier"]))


def test_crowd_signal_for_unscouted_year_has_no_effect():
    """A draft year nobody has scouted yet must fall back to the pure
    editorial multiplier — never fabricate a strong/weak read from silence."""

    crowd_signal = cs.crowd_class_strength_by_year(list(cs.PLACEHOLDER_PROSPECTS), [])
    assert crowd_signal == {}
    blended = trade_ideas._rookie_class_strength_multiplier(2026, None, crowd_signal)
    assert blended == trade_ideas._rookie_class_strength_multiplier(2026)

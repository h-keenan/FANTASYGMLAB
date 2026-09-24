"""Regression tests for coridian_'s two Pick Detail bug reports:

1. "how can this have 100% certainty ... nothing's to say it's not gonna be
   an early or late first round" -- `_pick_range_projection`'s bucket-weight
   kernel used to hard-clamp to literal zero once a bucket center was more
   than one `spread`-width away, which at years_out=0 (spread=0.18, bucket
   centers 0.32-0.34 apart) made a false ~100%/0%/0% confidence the NORMAL
   output, not an edge case.
2. "we need to make sure that your current record ... is being taken into
   account, because I am 0 and 2" -- `_pick_team_context`'s `team_modifier`
   used to be driven purely by roster-value percentile (a talent ranking),
   never consulting real win-loss data, and was capped to a hard +/-4% band
   too narrow to register any signal.

Both fixes live in modules/trade_ideas.py; see that file's comments on
`_pick_range_projection`, `_pick_team_context`, `_record_signal_weight`, and
the TEAM_MODIFIER_*/RECORD_SIGNAL_WEIGHT_* constants for the exact formulas.
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from modules import trade_ideas


def _uniform_roster_summary(count: int = 12) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "roster_id": list(range(1, count + 1)),
            "total_score": [20000 - (roster_id * 100) for roster_id in range(1, count + 1)],
        }
    )


def test_years_out_zero_confidence_is_never_degenerate():
    """No bucket may carry literal 0% or literal 100% probability at
    years_out=0 -- that false certainty was exactly the reported bug."""

    for slot in (0.0, 0.05, 0.18, 0.36, 0.5, 0.65, 0.82, 0.95, 1.0):
        projection = trade_ideas._pick_range_projection(slot, 0, 1)
        probabilities = projection["bucket_probabilities"]
        assert len(probabilities) == 3
        for bucket, probability in probabilities.items():
            assert probability > 0.0, f"bucket {bucket!r} degenerated to 0% at slot={slot}"
            assert probability < 1.0, f"bucket {bucket!r} degenerated to 100% at slot={slot}"
        assert sum(probabilities.values()) == pytest.approx(1.0)
        assert 0.0 < projection["projection_confidence"] < 1.0


def test_years_out_zero_near_screenshot_slot_gives_realistic_split():
    """Reproduces the screenshot's own numbers: a projected slot percentile
    around 0.36 (near the mid-round bucket center, 0.50) used to clamp the
    late/early buckets to exactly zero. It should now show a dominant mid
    bucket with real, non-trivial mass on the adjacent late bucket."""

    projection = trade_ideas._pick_range_projection(0.36, 0, 1)
    probabilities = projection["bucket_probabilities"]
    assert probabilities["mid"] > probabilities["late"] > probabilities["early"]
    assert probabilities["late"] > 0.05, "adjacent bucket should carry real mass, not near-zero"
    assert projection["projection_confidence"] < 0.90, "should not present as near-certain"


def test_confidence_still_degrades_for_further_out_seasons():
    """coridian_'s literal ask -- picks further out should be harder to call,
    not easier -- must still hold under the new Gaussian-shaped kernel."""

    for slot in (0.2, 0.36, 0.5, 0.7, 0.9):
        confidences = [
            trade_ideas._pick_range_projection(slot, years_out, 1)["projection_confidence"]
            for years_out in range(0, 4)
        ]
        for nearer, further in zip(confidences, confidences[1:]):
            assert further <= nearer + 1e-9


def test_poor_record_moves_team_modifier_vs_identical_roster_with_good_record():
    """Same roster-value percentile, opposite real win-loss records ->
    meaningfully different team_modifier. This is the direct fix for
    "I am 0 and 2 ... nothing's being taken into account": a poor record
    now pushes a team's own pick toward a MORE valuable (earlier) slot, and
    a good record pushes it the other way."""

    summary = pd.DataFrame({"roster_id": [1, 2], "total_score": [8000, 8000]})
    mid_season_progress = 0.5

    poor_record_context = trade_ideas._pick_team_context(
        1,
        summary,
        roster_record={"wins": 0, "losses": 5, "ties": 0},
        season_progress=mid_season_progress,
    )
    good_record_context = trade_ideas._pick_team_context(
        1,
        summary,
        roster_record={"wins": 5, "losses": 0, "ties": 0},
        season_progress=mid_season_progress,
    )

    modifier_gap = poor_record_context["team_modifier"] - good_record_context["team_modifier"]
    # Identical rosters, so any gap at all is purely the win-loss signal.
    # Require a real, meaningfully-sized gap (not a rounding artifact) --
    # the old +/-4% band could never have produced this much movement even
    # at the extremes.
    assert modifier_gap > 0.10, f"expected a meaningful gap, got {modifier_gap}"
    assert poor_record_context["team_modifier"] > good_record_context["team_modifier"]
    assert poor_record_context["slot_percentile"] > good_record_context["slot_percentile"]


def test_zero_and_two_record_moves_modifier_off_pure_roster_value_baseline():
    """Concrete before/after for the reported scenario: a team with
    middling roster value (~slot_percentile 0.375, matching the screenshot's
    implied ~0.99 team_modifier under the OLD +/-4% band) that is actually
    0-2 should see its modifier move up meaningfully once the real record is
    blended in, versus the pure-roster-value baseline with no record data."""

    summary = _uniform_roster_summary(12)
    # roster_id=8 sits at slot_percentile ~= 7/11 = 0.636 in a straight
    # talent ranking of 12 teams by total_score.
    no_record_context = trade_ideas._pick_team_context(8, summary)
    zero_and_two_context = trade_ideas._pick_team_context(
        8,
        summary,
        roster_record={"wins": 0, "losses": 2, "ties": 0},
        season_progress=2 / 14,
    )

    assert zero_and_two_context["team_modifier"] > no_record_context["team_modifier"]
    assert zero_and_two_context["record_weight"] > 0.0
    # The struggling team's blended slot percentile should sit meaningfully
    # closer to "early" (1.0 = worst roster by wins) than the pure
    # roster-value percentile did.
    assert (
        zero_and_two_context["slot_percentile"]
        > no_record_context["roster_value_percentile"] + 0.05
    )


def test_no_games_played_falls_back_to_roster_value_only():
    """Preseason (0 games) must not divide-by-zero or invent a record
    signal -- win_percentage returns None with no games, so the blend
    should no-op back to the pure roster-value percentile."""

    summary = pd.DataFrame({"roster_id": [1, 2, 3], "total_score": [9000, 6000, 3000]})
    baseline = trade_ideas._pick_team_context(1, summary)
    with_zero_games = trade_ideas._pick_team_context(
        1,
        summary,
        roster_record={"wins": 0, "losses": 0, "ties": 0},
        season_progress=0.0,
    )
    assert with_zero_games["team_modifier"] == baseline["team_modifier"]
    assert with_zero_games["slot_percentile"] == baseline["slot_percentile"]
    assert with_zero_games["record_weight"] == 0.0


def test_record_signal_weight_grows_with_season_progress():
    """Early season, a couple of results should count for something (the
    complaint was that they counted for ~nothing) but roster value should
    still lead; late season, the real record should dominate."""

    early = trade_ideas._record_signal_weight(0.0)
    mid = trade_ideas._record_signal_weight(0.5)
    late = trade_ideas._record_signal_weight(1.0)
    assert 0.0 < early < mid < late
    assert late < 1.0, "roster talent should never lose all say, even at season's end"


def test_team_modifier_band_matches_documented_constants():
    summary = pd.DataFrame({"roster_id": [1, 2], "total_score": [9000, 1000]})
    worst_roster_context = trade_ideas._pick_team_context(2, summary)
    best_roster_context = trade_ideas._pick_team_context(1, summary)
    assert best_roster_context["team_modifier"] == trade_ideas.TEAM_MODIFIER_BASE
    assert worst_roster_context["team_modifier"] == pytest.approx(
        trade_ideas.TEAM_MODIFIER_BASE + trade_ideas.TEAM_MODIFIER_RANGE
    )


def test_real_win_loss_record_reaches_pick_assets_end_to_end():
    """Full-plumbing check: `_build_roster_pick_assets` (the entry point
    Pick Detail's data actually flows through) must read each roster's REAL
    Sleeper wins/losses and the league's current week off the payloads it
    already fetches, not just accept them if hand-fed to `_pick_team_context`
    directly. Two rosters with identical roster value but opposite records
    should end up with different `team_modifier` on their own future picks."""

    summary = pd.DataFrame(
        {
            "roster_id": [1, 2],
            "team_name": ["Struggling", "Undefeated"],
            "total_score": [8000, 8000],
        }
    )
    rosters = [
        {"roster_id": 1, "players": [], "settings": {"wins": 0, "losses": 2, "ties": 0}},
        {"roster_id": 2, "players": [], "settings": {"wins": 2, "losses": 0, "ties": 0}},
    ]
    adapter = SimpleNamespace(
        get_rosters=lambda _league: rosters,
        get_league=lambda _league: {
            "season": 2026,
            "settings": {"draft_rounds": 4, "type": 2, "leg": 2, "playoff_week_start": 15},
        },
        get_traded_picks=lambda _league: [],
        normalize_roster=lambda raw: raw,
    )
    settings = {"league_format": "Dynasty", "qb_format": "1QB", "league_size": 12}
    draft_status = {"draft_year": 2026, "current_year_picks_active": False, "draft_completed": True}

    built = trade_ideas._build_roster_pick_assets(
        "L1",
        rosters,
        summary,
        league_settings=settings,
        draft_status=draft_status,
        adapter=adapter,
    )

    def first_2027_round1(roster_id: int) -> dict:
        matches = [
            pick
            for pick in built[roster_id]
            if pick["season"] == 2027 and pick["round"] == 1
        ]
        assert matches, f"expected a 2027 round-1 pick for roster {roster_id}"
        return matches[0]

    struggling_pick = first_2027_round1(1)
    undefeated_pick = first_2027_round1(2)
    assert struggling_pick["team_modifier"] > undefeated_pick["team_modifier"]
    # And it must have moved off the pure-roster-value baseline (both
    # rosters are tied on total_score, so a modifier gap here can only come
    # from the real win-loss record now being consulted).
    assert struggling_pick["team_modifier"] != undefeated_pick["team_modifier"]

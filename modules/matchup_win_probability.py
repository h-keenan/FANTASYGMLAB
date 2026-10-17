"""Live, single-week win probability for one real matchup.

coridian_: "we need team pfp and a bar saying whos winnig/ projected to
win... we need to distinguish between projected points and real points
while having a live updating predictor" / "we need real win odds we CANNOT
have any loose ends."

Deliberately NOT modules.playoff_simulator's approach: that module's own
docstring explains why it fits a logistic curve on Roster Power instead of
summing per-player weekly projections — running a full-roster, full-season
projection pass for every team/every remaining week on every cache refresh
was judged too heavy for a single percentage-per-team output. None of that
applies here: this is one matchup, one week, computed once per page load,
and services.mobile_api_service already fetches/builds a per-starter
weekly `projection` (point_estimate/low/high/confidence, from
modules.player_projections) for the real current-week lineup — this module
just combines numbers that already exist, it does not compute any new ones.

Model: each starter's weekly score is treated as independent and Normal.
A starter whose game has already kicked off contributes his real
`actual_points` as a fixed (zero-variance) value — real data always wins
over a projection once it exists. A starter who hasn't played yet
contributes `projection.point_estimate` as the mean and
`(projection.high - projection.low) / 2` as the standard deviation — that
half-width IS already the recency-weighted sample stdev (widened for
small samples / no defense-signal), see player_projections._band_half_width,
not a re-derived number. Team totals are the independent sum (mean adds,
variance adds), and P(my_total > opponent_total) is the standard
closed-form normal-difference CDF.

Starters with no usable projection (team DEF/IDP, which
player_projections.PROJECTABLE_POSITIONS excludes, or a skill-position
player with insufficient recent-game data) contribute nothing to the
model — not a guessed mean, not an invented variance. `coverage` reports
what fraction of each side's starters that leaves modeled vs. not, so a
caller can decide whether the result is trustworthy enough to show (see
MIN_COVERAGE_TO_SHOW) rather than silently presenting a probability that's
missing a real starter's scoring.
"""

from __future__ import annotations

import math
from typing import Any

# Below this fraction of EITHER side's starters actually modeled (real
# points once the game started, or a real "ok" weekly projection
# beforehand), the result is too incomplete to show as a confident
# probability — e.g. a lineup that's mostly DEF/IDP or early-season
# rookies with no games yet. Documented threshold, not a precision claim.
MIN_COVERAGE_TO_SHOW = 0.6


def _starter_distribution(starter: dict[str, Any]) -> tuple[float, float, bool]:
    """One starter's (mean, variance, modeled) contribution to his team's
    weekly point total. `modeled` is False when neither a real score nor a
    usable projection exists — that starter contributes (0.0, 0.0, False),
    never a guessed number.
    """

    actual_points = starter.get("actual_points")
    if starter.get("game_started") is True and isinstance(actual_points, (int, float)):
        return float(actual_points), 0.0, True

    projection = starter.get("projection") or {}
    if projection.get("status") == "ok":
        point_estimate = projection.get("point_estimate")
        low = projection.get("low")
        high = projection.get("high")
        if isinstance(point_estimate, (int, float)) and isinstance(low, (int, float)) and isinstance(high, (int, float)):
            half_width = max(0.0, (float(high) - float(low)) / 2.0)
            return float(point_estimate), half_width * half_width, True

    return 0.0, 0.0, False


def _team_distribution(starters: list[dict[str, Any]]) -> tuple[float, float, float]:
    """Returns (mean, variance, coverage) for one team's full lineup."""

    mean = 0.0
    variance = 0.0
    modeled_count = 0
    for starter in starters:
        starter_mean, starter_variance, modeled = _starter_distribution(starter)
        mean += starter_mean
        variance += starter_variance
        if modeled:
            modeled_count += 1
    coverage = modeled_count / len(starters) if starters else 0.0
    return mean, variance, coverage


def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def compute_live_win_probability(
    my_starters: list[dict[str, Any]], opponent_starters: list[dict[str, Any]]
) -> dict[str, Any]:
    """`{"available": False, "reason": ...}` when there isn't enough real
    signal yet (empty lineup, or either side's modeled coverage is below
    MIN_COVERAGE_TO_SHOW); otherwise `{"available": True, "probability":
    <0-1, my side's win chance>, "my_projected_total", "opponent_projected_
    total", "coverage": {"my": ..., "opponent": ...}}`.
    """

    if not my_starters or not opponent_starters:
        return {"available": False, "reason": "no_starters"}

    my_mean, my_variance, my_coverage = _team_distribution(my_starters)
    opponent_mean, opponent_variance, opponent_coverage = _team_distribution(opponent_starters)

    if my_coverage < MIN_COVERAGE_TO_SHOW or opponent_coverage < MIN_COVERAGE_TO_SHOW:
        return {
            "available": False,
            "reason": "insufficient_coverage",
            "coverage": {"my": round(my_coverage, 2), "opponent": round(opponent_coverage, 2)},
        }

    diff_mean = my_mean - opponent_mean
    diff_stdev = math.sqrt(my_variance + opponent_variance)
    if diff_stdev <= 0:
        probability = 1.0 if diff_mean > 0 else (0.0 if diff_mean < 0 else 0.5)
    else:
        probability = _normal_cdf(diff_mean / diff_stdev)

    return {
        "available": True,
        "probability": round(probability, 4),
        "my_projected_total": round(my_mean, 1),
        "opponent_projected_total": round(opponent_mean, 1),
        "coverage": {"my": round(my_coverage, 2), "opponent": round(opponent_coverage, 2)},
    }

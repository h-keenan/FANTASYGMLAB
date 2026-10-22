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

Model: each starter's weekly score is treated as independent and Normal,
built from his real points so far plus whatever of his game is left:

    mean     = actual_points + remaining * projection.point_estimate
    variance = remaining * stdev**2

where `stdev` is `(projection.high - projection.low) / 2` (that half-width
IS already the recency-weighted sample stdev, widened for small samples /
no defense signal; see player_projections._band_half_width) and
`remaining` is the share of his own game still to be played
(`game_fraction_remaining`): 1.0 before kickoff, 0.0 once nflverse has a
final score, and the unelapsed share of `GAME_WALL_CLOCK` since the real
kickoff in between. Scoring is treated as a sum of independent increments
over the game, so the remaining variance shrinks in proportion to the time
left. Pre-game, in-progress and final all use the same formula, so there
is no jump at kickoff: one minute in, a starter is still worth almost
exactly his projection, with almost all of its spread. (Before this, a
started game contributed its partial points as if final, so two identical
lineups read 0% five minutes after kickoff and 50% five minutes before.)

Team totals are the independent sum (mean adds, variance adds), and
P(my_total > opponent_total) is the standard closed-form normal-difference
CDF.

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
from datetime import datetime, timedelta, timezone
from typing import Any

# Below this fraction of EITHER side's starters actually modeled (real
# points once the game started, or a real "ok" weekly projection
# beforehand), the result is too incomplete to show as a confident
# probability — e.g. a lineup that's mostly DEF/IDP or early-season
# rookies with no games yet. Documented threshold, not a precision claim.
MIN_COVERAGE_TO_SHOW = 0.6


# How long an NFL game runs on the wall clock, kickoff to final whistle.
# Recent regular-season games average a little over three hours. The app's
# real game state comes from nflverse's schedule (modules.nfl_schedule): a
# kickoff instant and, after the game, a final score. There is no live game
# clock, so wall-clock time since kickoff is the best real measure of how
# much of a game is left. This is an approximation: it spreads scoring
# evenly over the broadcast window, halftime included.
GAME_WALL_CLOCK = timedelta(minutes=190)


def game_fraction_remaining(starter: dict[str, Any], *, now: datetime | None = None) -> float | None:
    """How much of this starter's own NFL game is still to be played, 0-1.

    - 1.0 before kickoff, or when whether it has kicked off is unknown
      (`game_started` not True), the same "not a real score yet" reading
      the Matchup screen already uses.
    - 0.0 once nflverse has a final score (`game_final`), or once the
      game's `GAME_WALL_CLOCK` window since kickoff has fully elapsed.
    - In between, the unelapsed share of `GAME_WALL_CLOCK` since the real
      `game_kickoff_at`.
    - None for a started game with neither a final flag nor a kickoff time,
      which can't be placed on the clock.
    """

    if starter.get("game_started") is not True:
        return 1.0
    if starter.get("game_final") is True:
        return 0.0
    kickoff_at = starter.get("game_kickoff_at")
    if not kickoff_at:
        return None
    try:
        kickoff = datetime.fromisoformat(str(kickoff_at))
    except ValueError:
        return None
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)
    reference = now if now is not None else datetime.now(timezone.utc)
    elapsed = (reference - kickoff) / GAME_WALL_CLOCK
    return max(0.0, min(1.0, 1.0 - elapsed))


def _projection_moments(starter: dict[str, Any]) -> tuple[float, float] | None:
    projection = starter.get("projection") or {}
    if projection.get("status") != "ok":
        return None
    point_estimate = projection.get("point_estimate")
    low = projection.get("low")
    high = projection.get("high")
    if not (
        isinstance(point_estimate, (int, float))
        and isinstance(low, (int, float))
        and isinstance(high, (int, float))
    ):
        return None
    half_width = max(0.0, (float(high) - float(low)) / 2.0)
    return float(point_estimate), half_width * half_width


def _starter_distribution(starter: dict[str, Any], *, now: datetime | None = None) -> tuple[float, float, bool]:
    """One starter's (mean, variance, modeled) contribution to his team's
    weekly point total: real points so far plus the remaining share of his
    projection (see the module docstring). `modeled` is False when neither
    a real score nor a usable projection exists; that starter contributes
    (0.0, 0.0, False), never a guessed number.
    """

    moments = _projection_moments(starter)
    actual_points = starter.get("actual_points")
    has_actual = starter.get("game_started") is True and isinstance(actual_points, (int, float))

    if not has_actual:
        # Not kicked off (or no real score yet): the projection alone.
        if moments is None:
            return 0.0, 0.0, False
        return moments[0], moments[1], True

    remaining = game_fraction_remaining(starter, now=now)
    if remaining is None:
        # Started, but neither a kickoff time nor a final flag to place it
        # on the clock: the real points are the only real number there is.
        remaining = 0.0
    if moments is None:
        # Real points but no projection for the rest of the game (team DEF/
        # IDP, or no recent-game data): the real points so far, no guess
        # for what's left.
        return float(actual_points), 0.0, True
    projection_mean, projection_variance = moments
    return (
        float(actual_points) + remaining * projection_mean,
        remaining * projection_variance,
        True,
    )


def _team_distribution(
    starters: list[dict[str, Any]], *, now: datetime | None = None
) -> tuple[float, float, float]:
    """Returns (mean, variance, coverage) for one team's full lineup."""

    mean = 0.0
    variance = 0.0
    modeled_count = 0
    for starter in starters:
        starter_mean, starter_variance, modeled = _starter_distribution(starter, now=now)
        mean += starter_mean
        variance += starter_variance
        if modeled:
            modeled_count += 1
    coverage = modeled_count / len(starters) if starters else 0.0
    return mean, variance, coverage


def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def compute_live_win_probability(
    my_starters: list[dict[str, Any]],
    opponent_starters: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """`{"available": False, "reason": ...}` when there isn't enough real
    signal yet (empty lineup, or either side's modeled coverage is below
    MIN_COVERAGE_TO_SHOW); otherwise `{"available": True, "probability":
    <0-1, my side's win chance>, "my_projected_total", "opponent_projected_
    total", "coverage": {"my": ..., "opponent": ...}}`.

    Each starter dict carries `actual_points`, `projection`, and his own
    game's state: `game_started`, `game_final` (nflverse has a final score)
    and `game_kickoff_at` (ISO-8601 UTC). `now` is the reference instant
    for how far along an in-progress game is (defaults to the current UTC
    time).
    """

    if not my_starters or not opponent_starters:
        return {"available": False, "reason": "no_starters"}

    my_mean, my_variance, my_coverage = _team_distribution(my_starters, now=now)
    opponent_mean, opponent_variance, opponent_coverage = _team_distribution(opponent_starters, now=now)

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

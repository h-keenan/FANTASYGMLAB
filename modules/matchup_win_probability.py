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
P(my_total > opponent_total) is the closed-form normal-difference CDF with
the margin's SD widened by ``projection_calibration.WIN_PROB_SPREAD_MULTIPLIER``
(the independent-starter sum is too narrow; every stated probability beyond
40-60% was 10-20 points too extreme before it, see that module).

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

from modules import projection_calibration

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


# Live projected final (owner-approved). projected_final =
#   actual + remaining * projection_mean + pace_adjustment
# The pace adjustment moves the remaining estimate toward how the player is
# actually scoring, but is capped: its blend weight never exceeds
# PACE_MAX_BLEND of the pace gap (actual minus what the projection expected
# by now), ramps in with game progress (no reaction to an early TD), and is
# scaled by the share remaining so it vanishes as the game ends.
PACE_MAX_BLEND = 0.25
PACE_FULL_WEIGHT_AT_ELAPSED = 0.5
# Mid-game exits: an injury designation that means he is not coming back.
EXIT_INJURY_STATUSES = frozenset({"out", "ir", "inactive", "pup", "suspended"})


OUT_BEFORE_KICKOFF_STATUSES = frozenset({"out", "ir", "inactive", "pup", "suspended"})


def _has_exited(starter: dict[str, Any]) -> bool:
    if starter.get("exited_game") is True:
        return True
    return str(starter.get("injury_status") or "").strip().lower() in EXIT_INJURY_STATUSES


def projected_final(starter: dict[str, Any], *, now: datetime | None = None) -> float | None:
    raw = _projected_final_raw(starter, now=now)
    return None if raw is None else round(raw, 1)


def _projected_final_raw(starter: dict[str, Any], *, now: datetime | None = None, basis: str = "point") -> float | None:
    """Live projected final points for one starter, or None when there is no
    live in-progress game to project (not started, final, unknown clock) or
    nothing real to project from. Pure arithmetic on fields already in the
    matchup payload."""

    if starter.get("game_started") is not True or starter.get("game_final") is True:
        return None
    actual = starter.get("actual_points")
    if not isinstance(actual, (int, float)):
        return None
    remaining = game_fraction_remaining(starter, now=now)
    if remaining is None or remaining <= 0.0:
        return None
    if _has_exited(starter):
        return float(actual)
    moments = _projection_moments(starter, basis=basis)
    if moments is None:
        return None
    mean = moments[0]
    elapsed = 1.0 - remaining
    pace_gap = float(actual) - elapsed * mean
    weight = PACE_MAX_BLEND * min(1.0, elapsed / PACE_FULL_WEIGHT_AT_ELAPSED)
    remaining_estimate = max(0.0, remaining * mean + weight * pace_gap * remaining)
    return float(actual) + remaining_estimate


def _projection_moments(starter: dict[str, Any], basis: str = "point") -> tuple[float, float] | None:
    """(mean, variance) of a starter's projected week. ``basis="mean"`` reads the mean-calibrated
    ``mean_estimate`` (the right number to SUM into a team total / win probability; falls back to the point
    estimate for a projection that does not carry one), ``"point"`` the median-like ``point_estimate`` (start/sit
    and any single-player number)."""

    projection = starter.get("projection") or {}
    if projection.get("status") != "ok":
        return None
    point_estimate = projection.get("point_estimate")
    if basis == "mean" and isinstance(projection.get("mean_estimate"), (int, float)):
        point_estimate = projection.get("mean_estimate")
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


def starter_expected_points(starter: dict[str, Any], *, now: datetime | None = None, basis: str = "point") -> float | None:
    """One starter's expected weekly points under this module's model (his
    real score once his game has started, his projection's point estimate
    otherwise), or None when he isn't modeled at all.

    Public so other Matchup numbers (per-position edges, suggested-move
    gains) read the exact figure the win probability uses, and pick up any
    change to `_starter_distribution` without a second copy of its rules.
    """

    mean, _variance, modeled = _starter_distribution(starter, now=now, basis=basis)
    return mean if modeled else None


def _starter_distribution(
    starter: dict[str, Any], *, now: datetime | None = None, basis: str = "mean"
) -> tuple[float, float, bool]:
    """One starter's (mean, variance, modeled) contribution to his team's
    weekly point total: real points so far plus the remaining share of his
    projection (see the module docstring). `modeled` is False when neither
    a real score nor a usable projection exists; that starter contributes
    (0.0, 0.0, False), never a guessed number.
    """

    moments = _projection_moments(starter, basis=basis)
    actual_points = starter.get("actual_points")
    has_actual = starter.get("game_started") is True and isinstance(actual_points, (int, float))

    if not has_actual:
        # Ruled out before his game: he scores nothing this week, so he adds nothing to the team total (a known zero, not an unmodeled player).
        if str(starter.get("injury_status") or "").strip().lower() in OUT_BEFORE_KICKOFF_STATUSES:
            return 0.0, 0.0, True
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
    if _has_exited(starter) and starter.get("game_final") is not True:
        # Left the game hurt: nothing more to come, so no remaining variance.
        return float(actual_points), 0.0, True
    final = _projected_final_raw(starter, now=now, basis=basis)
    if final is None:
        final = float(actual_points) + remaining * projection_mean
    return final, remaining * projection_variance, True


# Fallback for a starter the projection layer could not model (a rookie, a
# returning player, no recent-game data). Counting him as 0 points moved a
# mirror matchup to ~37% when the truth is 50%, so he is imputed at a
# documented replacement-level week for his position with a wide spread.
# (mean, sd) in PPR points per game, not calibrated to the league's scoring: the
# result flags the uncertainty (``imputed_starters`` / ``note``) rather than
# hiding it.
#
# Without any other information the anchors are the replacement levels of
# trade_lineup_model.STATIC_ANCHORS, except QB, which the 2016-26 point-in-time
# backtest (docs/audits/2026-11-projections-backtest.md "Round 2") put at about
# 8 for a QB with no NFL history who plays (first-round QBs 7.9, later rounds
# 4.5-6.5), not the 12.0 starter-level anchor.
REPLACEMENT_WEEK: dict[str, tuple[float, float]] = {
    "QB": (8.0, 7.0),
    "RB": (4.5, 4.5),
    "WR": (5.0, 4.5),
    "TE": (3.5, 3.5),
    "K": (7.0, 3.5),
}

# When his NFL draft capital is known (``starter["draft_round"]``: 1-7, 0 = undrafted) the anchor follows it:
# realized weekly PPR of no-history players who played (2016-22 fit, 2023-26 validation: RB R1 12.8 vs
# R4+ 3.2, WR 7.9 vs 2.7, TE 7.6 vs 2.4, QB 7.9 vs 4.7). Rounds 4-7 share one row; the spread keeps the
# empirical sd. Positions / rounds not listed use ``REPLACEMENT_WEEK``.
REPLACEMENT_WEEK_BY_ROUND: dict[str, dict[int, tuple[float, float]]] = {
    "QB": {1: (8.0, 7.5), 2: (6.0, 7.5), 3: (6.0, 6.0), 4: (4.7, 6.0), 0: (4.5, 6.0)},
    "RB": {1: (11.5, 5.5), 2: (6.0, 5.5), 3: (5.0, 5.5), 4: (3.2, 4.4), 0: (2.6, 4.3)},
    "WR": {1: (8.0, 7.3), 2: (5.5, 5.2), 3: (4.5, 5.0), 4: (2.7, 4.0), 0: (2.3, 3.8)},
    "TE": {1: (8.0, 6.5), 2: (3.0, 3.1), 3: (2.8, 3.5), 4: (2.2, 3.2), 0: (1.5, 2.7)},
}


def _draft_round_bucket(starter: dict[str, Any]) -> int | None:
    """1, 2, 3, 4 (rounds 4-7) or 0 (undrafted) from ``starter["draft_round"]``; None when unknown."""

    raw = starter.get("draft_round")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw != raw or raw < 0:
        return None
    return 0 if raw == 0 else min(int(raw), 4)


def _fallback_distribution(starter: dict[str, Any]) -> tuple[float, float] | None:
    """(mean, variance) for an unmodeled starter, or None when there is no
    honest fallback (a bye week is a known zero; DEF/IDP/unknown positions
    keep the old "not modeled" treatment)."""

    if str((starter.get("projection") or {}).get("status") or "") == "bye_week":
        return None
    position = str(starter.get("position") or "").strip().upper()
    if position not in REPLACEMENT_WEEK:
        return None
    mean, sd = REPLACEMENT_WEEK[position]
    bucket = _draft_round_bucket(starter)
    if bucket is not None:
        mean, sd = (REPLACEMENT_WEEK_BY_ROUND.get(position) or {}).get(bucket, (mean, sd))
    return mean, sd * sd


def _team_distribution(
    starters: list[dict[str, Any]], *, now: datetime | None = None
) -> tuple[float, float, float, int]:
    """Returns (mean, variance, coverage, imputed_count) for one team's
    lineup. ``coverage`` counts genuinely modeled starters only; imputed
    ones are reported separately so the caller can flag the uncertainty."""

    mean = 0.0
    variance = 0.0
    modeled_count = 0
    imputed = 0
    for starter in starters:
        starter_mean, starter_variance, modeled = _starter_distribution(starter, now=now)
        if modeled:
            modeled_count += 1
        else:
            fallback = _fallback_distribution(starter)
            if fallback is not None:
                starter_mean, starter_variance = fallback
                imputed += 1
        mean += starter_mean
        variance += starter_variance
    coverage = modeled_count / len(starters) if starters else 0.0
    return mean, variance, coverage, imputed


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

    my_mean, my_variance, my_coverage, my_imputed = _team_distribution(my_starters, now=now)
    opponent_mean, opponent_variance, opponent_coverage, opponent_imputed = _team_distribution(
        opponent_starters, now=now
    )

    if my_coverage < MIN_COVERAGE_TO_SHOW or opponent_coverage < MIN_COVERAGE_TO_SHOW:
        return {
            "available": False,
            "reason": "insufficient_coverage",
            "coverage": {"my": round(my_coverage, 2), "opponent": round(opponent_coverage, 2)},
        }

    diff_mean = my_mean - opponent_mean
    diff_stdev = projection_calibration.calibrated_margin_stdev(my_variance + opponent_variance)
    if diff_stdev <= 0:
        probability = 1.0 if diff_mean > 0 else (0.0 if diff_mean < 0 else 0.5)
    else:
        probability = _normal_cdf(diff_mean / diff_stdev)

    result: dict[str, Any] = {
        "available": True,
        "probability": round(probability, 4),
        "my_projected_total": round(my_mean, 1),
        "opponent_projected_total": round(opponent_mean, 1),
        "coverage": {"my": round(my_coverage, 2), "opponent": round(opponent_coverage, 2)},
    }
    if my_imputed or opponent_imputed:
        result["imputed_starters"] = {"my": my_imputed, "opponent": opponent_imputed}
        result["note"] = imputed_note(my_imputed + opponent_imputed)
    return result


def imputed_note(total: int) -> str:
    """The reason text shown wherever the probability is shown."""

    who = "starter" if total == 1 else "starters"
    return (
        f"{total} {who} without projection data counted at a replacement-level week, "
        "so this chance is less certain."
    )

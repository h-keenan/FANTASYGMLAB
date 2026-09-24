"""Shared real-record blending logic.

Two independent auto-computed metrics in this app were both found to ignore
a team's actual win-loss record and rely on roster-talent value alone:

  1. `modules.trade_ideas._pick_team_context` -- a team's projected draft pick
     slot/value (fixed in PR #737, coridian_'s "I am 0 and 2 ... nothing's
     being taken into account" report).
  2. `modules.team_eval._classify_team_strategy` -- a team's auto-computed
     roster "posture" (contender/fringe_contender/retool/rebuild/tank), which
     feeds the user-facing archetype labels ("Juggernaut", "Full Rebuild",
     etc.) shown on the My Team screen. Same bug class: a talented 0-2 roster
     still read as a "Contender".

Both need the exact same blend: a roster-value percentile combined with a
real win-loss signal, weighted by how much of the season has actually been
played (a couple of early results are noisy, so roster value should still
lead; by season's end the record should dominate). This module is the single
place that blend lives, so the two call sites can't drift apart.
"""

from __future__ import annotations

from typing import Any, Mapping

from modules.league_recaps import league_history_window
from modules.league_standings import win_percentage

# Floor: once a team has played even one game, its real record gets at least
# this much say over the blended percentile -- a single result is noisy, but
# it is still real signal, not nothing (the exact bug coridian_ flagged).
RECORD_SIGNAL_WEIGHT_FLOOR = 0.30
# Ceiling: by the end of the regular season the record should dominate, but
# roster value still gets a small say (a season-ending injury binge, a
# scheduling-luck outlier, etc).
RECORD_SIGNAL_WEIGHT_CEILING = 0.85
RECORD_SIGNAL_WEIGHT_SEASON_SLOPE = 0.55


def clamp_float(value: Any, lower: float = 0.0, upper: float = 1.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = lower
    return max(lower, min(upper, parsed))


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def record_signal_weight(season_progress: float | None) -> float:
    """How much a real win-loss record should outweigh roster-value when a
    team has actually played games. `season_progress` is a 0.0 (preseason) -
    1.0 (regular-season finale) fraction.
    """

    progress = clamp_float(season_progress if season_progress is not None else 0.0, 0.0, 1.0)
    return clamp_float(
        RECORD_SIGNAL_WEIGHT_FLOOR + (RECORD_SIGNAL_WEIGHT_SEASON_SLOPE * progress),
        RECORD_SIGNAL_WEIGHT_FLOOR,
        RECORD_SIGNAL_WEIGHT_CEILING,
    )


def season_progress_fraction(league: Mapping[str, Any] | None) -> float:
    """Fraction of the regular season completed, reusing the exact leg /
    playoff_week_start fields `league_recaps.league_history_window` already
    reads (no new time signal invented). 0.0 when the league object is
    missing/unplayed so real-record blending safely no-ops preseason."""

    if not isinstance(league, Mapping):
        return 0.0
    try:
        current_leg, regular_season_end, _max_history_week = league_history_window(league)
    except Exception:
        return 0.0
    if regular_season_end <= 0:
        return 0.0
    return clamp_float(current_leg / regular_season_end, 0.0, 1.0)


def real_record_win_pct(roster_record: Mapping[str, Any] | None) -> float | None:
    """Win percentage from a Sleeper roster's own `settings` dict
    (`{"wins", "losses", "ties"}`), or None when no games have been played /
    no record is available."""

    if not isinstance(roster_record, Mapping):
        return None
    wins = safe_int(roster_record.get("wins"), 0)
    losses = safe_int(roster_record.get("losses"), 0)
    ties = safe_int(roster_record.get("ties"), 0)
    return win_percentage(wins, losses, ties)


def blend_percentile_with_record(
    value_percentile: float,
    roster_record: Mapping[str, Any] | None,
    season_progress: float | None,
    *,
    record_strength_is_high: bool = True,
) -> tuple[float, float]:
    """Blend a roster-value percentile with a team's REAL win-loss record.

    `value_percentile` and the returned blended percentile share one
    polarity, controlled by `record_strength_is_high`:
      - True: 1.0 = strongest team (matches `win_pct` directly) -- used by
        `team_eval`'s roster-strength percentile.
      - False: 0.0 = strongest team, so record *weakness* (`1 - win_pct`) is
        blended in instead -- used by `trade_ideas`'s pick-slot percentile
        (a weaker team by record should look like an earlier/more valuable
        pick, same as a weaker team by talent).

    Returns `(blended_percentile, record_weight_applied)`. `record_weight` is
    0.0 when no valid record is available (e.g. preseason, bye week with no
    games played), so callers safely no-op and `blended_percentile ==
    value_percentile`.
    """

    blended = clamp_float(value_percentile, 0.0, 1.0)
    weight = 0.0
    win_pct = real_record_win_pct(roster_record)
    if win_pct is not None:
        record_signal = win_pct if record_strength_is_high else clamp_float(1.0 - win_pct, 0.0, 1.0)
        weight = record_signal_weight(season_progress)
        blended = clamp_float(
            ((1.0 - weight) * blended) + (weight * record_signal),
            0.0,
            1.0,
        )
    return blended, weight

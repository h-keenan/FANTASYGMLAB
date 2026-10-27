"""League calendar facts read straight off a Sleeper league payload.

One small, pure place for the two Sleeper league settings the rest of the
app previously never read:

* ``settings.trade_deadline`` — the last week trades are allowed. Observed
  values on real leagues are ordinary week numbers (11, 12, 13, 14) and
  ``99`` for "no deadline". Sleeper's deadline falls after that week's
  final game, so trades are still allowed *during* the deadline week and
  the deadline has passed once the league's current week (``settings.leg``,
  which tracks Sleeper's ``/state/nfl`` week) is greater than it.
* ``settings.best_ball`` — ``1`` when Sleeper sets the lineup
  automatically from the best weekly scores, ``0`` otherwise.

A deadline only gates trades while the league is actually in season
(``status`` of ``in_season`` / ``post_season``). A ``complete``,
``pre_draft`` or ``drafting`` league is in the offseason, where trades are
open again regardless of last season's deadline.

No I/O and no valuation math — callers pass the league payload they
already fetched.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Week numbers at or beyond a realistic NFL season length (Sleeper uses 99)
# mean the commissioner set no trade deadline.
NO_DEADLINE_WEEK_THRESHOLD = 18

IN_SEASON_STATUSES = frozenset({"in_season", "post_season"})

TRADE_DEADLINE_PASSED_REASON = "trade_deadline_passed"
TRADE_DEADLINE_PASSED_MESSAGE = "Trade deadline has passed; trades reopen after the season."
TRADE_ANALYZER_DEADLINE_NOTE = (
    "Your league's trade deadline has passed, so this trade can't be made until the "
    "offseason. Use the analyzer to plan offseason moves."
)
BEST_BALL_LINEUP_MESSAGE = (
    "Best ball league: Sleeper sets your lineup automatically from your highest "
    "scorers each week, so there's no start/sit decision to make."
)


def _settings(league: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(league, Mapping):
        return {}
    settings = league.get("settings")
    return settings if isinstance(settings, Mapping) else {}


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def trade_deadline_week(league: Mapping[str, Any] | None) -> int | None:
    """The last week trades are allowed, or None when there's no deadline."""

    week = _int_or_none(_settings(league).get("trade_deadline"))
    if week is None or week <= 0 or week >= NO_DEADLINE_WEEK_THRESHOLD:
        return None
    return week


def current_league_week(league: Mapping[str, Any] | None) -> int | None:
    """Sleeper's current league week (``leg``, falling back to ``week``)."""

    settings = _settings(league)
    week = _int_or_none(settings.get("leg"))
    if not week:
        week = _int_or_none(settings.get("week"))
    return week if week and week > 0 else None


def is_in_season(league: Mapping[str, Any] | None) -> bool:
    if not isinstance(league, Mapping):
        return False
    return str(league.get("status") or "").strip().lower() in IN_SEASON_STATUSES


def trade_deadline_passed(league: Mapping[str, Any] | None) -> bool:
    """True only while the league is in season and past its deadline week."""

    deadline = trade_deadline_week(league)
    if deadline is None or not is_in_season(league):
        return False
    week = current_league_week(league)
    return week is not None and week > deadline


# Phases of the trade window a league can be in. ``none`` = no deadline set
# (or offseason, where trades are open regardless); ``open`` = a deadline is
# still ahead; ``final_week`` = the deadline week itself (last call);
# ``passed`` = trades closed until the offseason.
DEADLINE_PHASE_NONE = "none"
DEADLINE_PHASE_OPEN = "open"
DEADLINE_PHASE_FINAL_WEEK = "final_week"
DEADLINE_PHASE_PASSED = "passed"


def weeks_to_deadline(league: Mapping[str, Any] | None) -> int | None:
    """Whole weeks between the league's current week and its deadline week.

    0 during the deadline week itself. None when there is no deadline, the
    league is not in season, the current week is unknown, or the deadline has
    already passed (never guessed: Sleeper exposes weeks, not dates).
    """

    deadline = trade_deadline_week(league)
    if deadline is None or not is_in_season(league):
        return None
    week = current_league_week(league)
    if week is None or week > deadline:
        return None
    return deadline - week


def deadline_phase(league: Mapping[str, Any] | None) -> str:
    if trade_deadline_passed(league):
        return DEADLINE_PHASE_PASSED
    left = weeks_to_deadline(league)
    if left is None:
        return DEADLINE_PHASE_NONE
    return DEADLINE_PHASE_FINAL_WEEK if left == 0 else DEADLINE_PHASE_OPEN


def is_best_ball(league: Mapping[str, Any] | None) -> bool:
    return _int_or_none(_settings(league).get("best_ball")) == 1


def trade_window(league: Mapping[str, Any] | None) -> dict[str, Any]:
    """JSON-ready trade-window state for API responses (additive field)."""

    passed = trade_deadline_passed(league)
    return {
        "trade_deadline_week": trade_deadline_week(league),
        "current_week": current_league_week(league),
        "trade_deadline_passed": passed,
        "weeks_to_deadline": weeks_to_deadline(league),
        "deadline_phase": deadline_phase(league),
        "message": TRADE_DEADLINE_PASSED_MESSAGE if passed else "",
    }

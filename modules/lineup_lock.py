"""The one definition of "this player's lineup spot is locked".

Sleeper (and every host we read) locks a player the moment his own NFL game
kicks off: a started player in the lineup cannot be benched, and a started
player on the bench cannot be started. Any surface that recommends a bench,
swap or start move must ask this module, never re-derive it, so a starter who
went Out mid-game is shown as information ("locked, nothing to do") and never
as advice.

Unknown kickoff data means "not locked": the lock never invents itself. A
started game covers in-progress AND final games (``game_has_started`` is True
from kickoff on), and a bye-week player has no game so he is never locked.

Every "is this starter a lineup problem?" question is answered here too:
``is_actionable_issue`` (an Out/bye/IR starter whose game has NOT started, the
only kind a manager can still fix) and ``left_game`` (a locked starter who is
hurt: information only, never a hole, a swap or a red verdict). The web and
app twins live in web-next/src/lib/lineupLock.ts and mobile/src/lib/lineupLock.ts.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def is_locked(player: Mapping[str, Any] | None) -> bool:
    """True when this player's own game has started (``game_started is True``)."""

    if player is None or player.get("on_bye") or player.get("start_ineligible_reason") == "Bye":
        return False
    return player.get("game_started") is True or player.get("game_locked") is True


def any_locked(*players: Mapping[str, Any] | None) -> bool:
    """True when any player in a proposed move is locked (the move is impossible)."""

    return any(is_locked(p) for p in players)


def filter_unlocked(ids: Iterable[Any], locked_ids: Iterable[Any]) -> list[str]:
    """``ids`` minus the locked ones, as strings, order preserved."""

    locked = {str(pid) for pid in locked_ids}
    return [str(pid) for pid in ids if str(pid) not in locked]


# Reasons a starter cannot play this week for a fixable reason (the lineup builder's
# ``start_ineligible_reason``); "Game started" is a lock, not a problem.
_FIXABLE_REASONS = frozenset({"Bye", "Out", "IR", "PUP", "Suspended"})


def _is_unavailable(player: Mapping[str, Any]) -> bool:
    return bool(
        player.get("ruled_out")
        or player.get("on_bye")
        or str(player.get("start_ineligible_reason") or "") in _FIXABLE_REASONS
    )


def is_actionable_issue(player: Mapping[str, Any] | None) -> bool:
    """True only for a starter who cannot play AND can still be swapped (his game has not started)."""

    return player is not None and not is_locked(player) and _is_unavailable(player)


def left_game(player: Mapping[str, Any] | None) -> bool:
    """True for a locked starter who is injured/out: shown as information ("left game (injury)")."""

    if player is None or not is_locked(player):
        return False
    return bool(player.get("ruled_out") or str(player.get("injury_label") or "").strip())

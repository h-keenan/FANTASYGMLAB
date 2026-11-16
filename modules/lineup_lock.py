"""The one definition of "this player's lineup spot is locked".

Sleeper (and every host we read) locks a player the moment his own NFL game
kicks off: a started player in the lineup cannot be benched, and a started
player on the bench cannot be started. Any surface that recommends a bench,
swap or start move must ask this module, never re-derive it, so a starter who
went Out mid-game is shown as information ("locked, nothing to do") and never
as advice.

Unknown kickoff data means "not locked": the lock never invents itself.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def is_locked(player: Mapping[str, Any] | None) -> bool:
    """True when this player's own game has started (``game_started is True``)."""

    return player is not None and player.get("game_started") is True


def any_locked(*players: Mapping[str, Any] | None) -> bool:
    """True when any player in a proposed move is locked (the move is impossible)."""

    return any(is_locked(p) for p in players)


def filter_unlocked(ids: Iterable[Any], locked_ids: Iterable[Any]) -> list[str]:
    """``ids`` minus the locked ones, as strings, order preserved."""

    locked = {str(pid) for pid in locked_ids}
    return [str(pid) for pid in ids if str(pid) not in locked]

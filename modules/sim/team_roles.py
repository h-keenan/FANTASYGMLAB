"""Team-level role coupling for the GM game (player-model-3 and later).

Every player's projection ("mean") is a per-game number *if he plays his usual role*. A backup's number is
usually inflated by past starts (McKee started three games while the starter was out), so two backups of the
same injured starter would otherwise both carry starter-level means and, summed, double count a team's
volume. This module resolves, for one NFL team and position group in one week, WHO actually plays which
role, and returns a mean multiplier per player. It is pure (stdlib only) and deterministic: no random
draws, a function of the group's depth order and who is available that week.

Rules (see ``docs/fantasy-sim-player-model.md`` section 8):

* Depth order: ``depth_chart_order`` when present, else projection. A star who starts the season injured
  (the highest-market player of his group) keeps his place at the top: live depth charts drop an injured
  starter below his fill-in, but he starts again when he returns.
* The first ``STARTER_SLOTS[pos]`` of the order are the group's depth starters (QB 1, RB 2, WR 3, TE 1).
* Each depth starter who is out/bye that week vacates a slot. Exactly ONE next-in-line healthy non-starter
  inherits each vacated slot, in depth order. Everyone else stays at baseline.
* QB: the one who plays gets ``backup_share x own mean + ABSORB x the starter's mean`` (a single-role
  position, full uplift); every other healthy QB behind the playing QB is a bench QB at ``BACKUP_QB_SHARE``
  of his if-he-starts mean (about nothing).
* RB / WR / TE: committees. The inheritor gets his own mean plus the calibrated first-backup share
  (``ABSORB x FIRST_BACKUP_SHARE``) of the vacated starter's mean; the other backups are unchanged.
* K and team defense are exempt (multiplier 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Sequence

STARTER_SLOTS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1}
# Share of an injured starter's PPG absorbed by his backups: the calibrated ``InSeasonParams.absorb`` values
# of player-model-2/3 (a test pins equality), the first backup taking FIRST_BACKUP_SHARE of it (4 : 1 split).
ABSORB = {"QB": 0.6, "RB": 0.33, "WR": 0.23, "TE": 0.10}
FIRST_BACKUP_SHARE = 0.8
# A healthy QB behind the QB who is playing: share of his if-he-starts mean. Same prior (and value) as the real
# projection's ``player_projections.BACKUP_QB_PLAY_SHARE``, so the sim and the real app agree on what a QB2 is.
BACKUP_QB_SHARE = 0.2
MAX_MULT = 20.0
NO_ORDER = 99
ROLE_POSITIONS = tuple(STARTER_SLOTS)


@dataclass(frozen=True)
class Member:
    pid: str
    pos: str
    team: str
    mean: float            # projection, "if he plays his role"
    market: float = 0.0
    order: int = NO_ORDER  # Sleeper depth_chart_order (1 = first); NO_ORDER when unknown
    starts_out: bool = False  # injured at the start of the season


@dataclass(frozen=True)
class Role:
    kind: str              # starter | fill_in | backup | bench | out | exempt
    mult: float = 1.0      # multiplier on the player's own mean for this week
    covering: str = ""     # pid of the starter he replaces (fill_in only)


def depth_order(members: Iterable[Member]) -> tuple[Member, ...]:
    """The group's depth order (best first), deterministic."""

    ms = list(members)
    top = max((m.market for m in ms), default=0.0)
    def key(m: Member):
        returner = m.starts_out and top > 0 and m.market >= top
        return (0 if returner else 1, m.order, -m.mean, m.pid)
    return tuple(sorted(ms, key=key))


def resolve_group(ordered: Sequence[Member], available: Callable[[str], bool]) -> dict[str, Role]:
    """Roles for one (team, position) group in one week. ``available(pid)``: healthy and not on a bye."""

    if not ordered:
        return {}
    pos = ordered[0].pos
    k = STARTER_SLOTS.get(pos)
    if k is None:  # K, DEF
        return {m.pid: Role("exempt") for m in ordered}
    starters, rest = ordered[:k], ordered[k:]
    vacated = [m for m in starters if not available(m.pid)]
    candidates = [m for m in rest if available(m.pid)]
    out: dict[str, Role] = {}
    for m in starters:
        out[m.pid] = Role("starter") if available(m.pid) else Role("out")
    inheritors: dict[str, Member] = {}
    for vac, cand in zip(vacated, candidates):
        inheritors[cand.pid] = vac
    for m in rest:
        if not available(m.pid):
            out[m.pid] = Role("out")
        elif m.pid in inheritors:
            vac = inheritors[m.pid]
            share = ABSORB[pos] * (1.0 if pos == "QB" else FIRST_BACKUP_SHARE)
            base = m.mean * (BACKUP_QB_SHARE if pos == "QB" else 1.0)
            role_mean = base + share * vac.mean
            mult = min(MAX_MULT, role_mean / m.mean) if m.mean > 0 else 1.0
            out[m.pid] = Role("fill_in", round(mult, 4), vac.pid)
        elif pos == "QB":
            out[m.pid] = Role("backup", BACKUP_QB_SHARE)
        else:
            out[m.pid] = Role("bench")
    return out


class RoleBook:
    """Depth order of every (team, position) group of a player pool, built once per snapshot."""

    def __init__(self, players: Mapping[str, object]) -> None:
        groups: dict[tuple[str, str], list[Member]] = {}
        for pid, p in players.items():
            pos = getattr(p, "pos", "")
            team = str(getattr(p, "nfl_team", "") or "")
            if pos not in STARTER_SLOTS or not team:
                continue
            extra = getattr(p, "extra", {}) or {}
            try:
                order = int(float(extra.get("depth_chart_order"))) if extra.get("depth_chart_order") is not None else NO_ORDER
            except (TypeError, ValueError):
                order = NO_ORDER
            if order <= 0:
                order = NO_ORDER
            groups.setdefault((team, pos), []).append(Member(
                pid=str(pid), pos=pos, team=team, mean=float(getattr(p, "mean", 0.0) or 0.0),
                market=float(getattr(p, "market", 0.0) or 0.0), order=order,
                starts_out=int(getattr(p, "injury_weeks", 0) or 0) > 0,
            ))
        self.groups = {key: depth_order(ms) for key, ms in groups.items()}
        self.group_of = {m.pid: key for key, ms in self.groups.items() for m in ms}

    def key(self, pid: str) -> tuple[str, str] | None:
        return self.group_of.get(pid)

    def roles(self, key: tuple[str, str], available: Callable[[str], bool]) -> dict[str, Role]:
        return resolve_group(self.groups[key], available)


def week_one_roles(players: Mapping[str, object]) -> dict[str, Role]:
    """Roles in week 1 from the pool alone (signed-out browse): a player with ``injury_weeks`` > 0 is out."""

    book = RoleBook(players)
    out: dict[str, Role] = {}
    for key in book.groups:
        out.update(book.roles(key, lambda pid: int(getattr(players[pid], "injury_weeks", 0) or 0) <= 0))
    return out


__all__ = [
    "week_one_roles",
    "ABSORB", "BACKUP_QB_SHARE", "FIRST_BACKUP_SHARE", "Member", "Role", "RoleBook", "STARTER_SLOTS",
    "depth_order", "resolve_group",
]

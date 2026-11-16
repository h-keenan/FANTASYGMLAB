"""Incumbent depth charts (``incumbent_v`` 1+): a starter keeps his job each offseason unless a challenger is clearly better.

Before this a dynasty's depth chart was re-sorted every offseason purely by projected mean (then market), so a QB2 at 18 ppg could fall to a backup
the next year over a projection gap of a few percent (the projections are noisy posteriors, a coach does not bench a starter over them). Real
depth charts are sticky: the real panel (2021-25, top-12 ppg at the position, same team the next year) has the QB1 keep the job 42 times of 42, the
TE 92 percent, the RB 81 percent and the WR (top 12) 67 percent.

Mechanism (one rule, scaled; no per-position special cases beyond its parameters):

* A player who held a starting slot last year (``STARTER_SLOTS``: QB 1, RB 2, WR 3, TE 1) carries a **margin** ``MARGIN[pos] x protection x age``: his
  projection is multiplied by ``1 + margin`` when the group is sorted, so a challenger must be better by that much to pass him.
* ``protection`` in [0.15, 1] is his last season against the position's starter line (the median production of last year's starters): a strong
  season (1.15x the line or better) protects fully, a bust (0.55x or worse) barely.
* ``age`` factor: past ``AGE_OUT[pos]`` the margin fades to zero over three years (a coach moves on from an old starter).
* A rookie with draft capital (``CAPITAL[pos]``, QB and RB only, slots 1-16 of his class) carries a bonus of the same kind in the other direction: the
  team that spent the pick gives him the chance, so he needs a smaller edge.
* Everything else (retired incumbents, long-term injuries during the season) takes care of itself: a retired player is not in the pool, and an injured
  starter stays first on the chart while the role resolver (``team_roles``) fills in for him and hands the job straight back when he returns.

Every starter-slot change is returned as a record that ``game_dynasty.start_next_season`` writes into the event log as a ``depth_chart`` event (shape in
``docs/audits/2026-11-sim-desk-logic-realism-audit.md``).
"""

from __future__ import annotations

import itertools
from statistics import median
from typing import Any, Mapping

from modules.sim import team_roles as tr

STARTER_SLOTS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1}
MARGIN = {"QB": 0.45, "RB": 0.30, "WR": 0.12, "TE": 0.32}
AGE_OUT = {"QB": 39.0, "RB": 29.0, "WR": 32.0, "TE": 33.0}
AGE_FADE_YEARS = 3.0
CAPITAL = {"QB": 0.20, "RB": 0.15}
CAPITAL_SLOTS = 16.0
PROT_LO, PROT_HI, PROT_FLOOR = 0.55, 1.15, 0.15


def _age_factor(pos: str, age: float) -> float:
    over = float(age) - AGE_OUT.get(pos, 99.0)
    return 1.0 if over <= 0 else max(0.0, 1.0 - over / AGE_FADE_YEARS)


def _protection(last_ppg: float, line: float) -> float:
    if line <= 0.0:
        return 0.5
    rel = last_ppg / line
    return max(PROT_FLOOR, min(1.0, (rel - PROT_LO) / (PROT_HI - PROT_LO)))


def _season_label(prot: float) -> str:
    return "strong" if prot >= 0.75 else "solid" if prot >= 0.4 else "down"


def rookie_capital(pid: str, pos: str) -> float:
    """0..1: how high a class rookie went (his slot in the class, which ``rookie_class`` writes into the id: ``R<year>-<slot>``)."""

    if pos not in CAPITAL or not pid.startswith("R") or "-" not in pid:
        return 0.0
    try:
        slot = int(pid.rsplit("-", 1)[1])
    except ValueError:
        return 0.0
    return max(0.0, 1.0 - (slot - 1) / CAPITAL_SLOTS)


def refresh(rows: dict[str, dict[str, Any]], prev_players: Mapping[str, Any], last_ppg: Mapping[str, float]) -> list[dict[str, Any]]:
    """Set ``extra["depth_chart_order"]`` on every QB / RB / WR / TE of an NFL team (incumbents sticky) and return the starter changes.

    ``prev_players``: last season's pool (its depth order is the incumbents). ``last_ppg``: last season's production per game by player (the
    strength of the season each incumbent just had)."""

    book = tr.RoleBook(prev_players)
    old_order: dict[tuple[str, str], list[str]] = {k: [m.pid for m in ms] for k, ms in book.groups.items()}
    # the position's starter line: the median production of last year's starters
    line: dict[str, float] = {}
    for pos, n in STARTER_SLOTS.items():
        xs = [last_ppg[p] for (t, q), pids in old_order.items() if q == pos for p in pids[:n] if p in last_ppg]
        line[pos] = float(median(xs)) if xs else 0.0
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in rows.values():
        if r["pos"] in STARTER_SLOTS and r["nfl_team"] not in ("", "FA"):
            groups.setdefault((r["nfl_team"], r["pos"]), []).append(r)
    log: list[dict[str, Any]] = []
    for key in sorted(groups):
        team, pos = key
        n = STARTER_SLOTS[pos]
        was = old_order.get(key, [])
        incumbents = set(was[:n])
        mult: dict[str, float] = {}
        info: dict[str, tuple[float, str]] = {}
        for r in groups[key]:
            pid = r["pid"]
            m = 1.0
            if pid in incumbents:
                prot = _protection(float(last_ppg.get(pid, 0.0)), line[pos])
                m += MARGIN[pos] * prot * _age_factor(pos, r["age"])
                info[pid] = (prot, _season_label(prot))
            else:
                m += CAPITAL.get(pos, 0.0) * rookie_capital(pid, pos)
            mult[pid] = m
        ordered = sorted(groups[key], key=lambda r: (-float(r["mean"]) * mult[r["pid"]], -float(r["market"]), r["pid"]))
        for i, r in enumerate(ordered, 1):
            extra = dict(r.get("extra") or {})
            extra["depth_chart_order"] = float(i)
            r["extra"] = extra
        new_top = [r["pid"] for r in ordered[:n]]
        gained = [p for p in new_top if p not in was[:n]]
        lost = [p for p in was[:n] if p not in new_top]
        by_pid = {r["pid"]: r for r in groups[key]}
        for g, l in itertools.zip_longest(gained, lost):
            if g is None:
                continue  # a vacated slot filled by someone already starting: no one new took a job
            rec: dict[str, Any] = {"nfl_team": team, "pos": pos, "slot": new_top.index(g) + 1, "pid": g, "replaced_pid": l}
            gr = by_pid[g]
            if l is None:
                rec.update(reason="filled_open_slot", gap=None, needed=None)
            elif l not in by_pid:
                rec.update(reason="incumbent_retired" if l not in rows else "incumbent_left", gap=None, needed=None)
            else:
                lr = by_pid[l]
                gap = float(gr["mean"]) / max(float(lr["mean"]), 1e-9)
                needed = mult[l] / mult[g]
                if _age_factor(pos, lr["age"]) < 1.0:  # his protection was cut by age: a coach moves on from an old starter
                    reason = "incumbent_aged"
                elif g.startswith("R") and "-" in g:
                    reason = "rookie_won_job"
                else:
                    reason = "outperformed_incumbent"
                rec.update(reason=reason, gap=round(gap, 3), needed=round(needed, 3), incumbent_season=info.get(l, (0, ""))[1])
            log.append(rec)
    return log


__all__ = ["STARTER_SLOTS", "MARGIN", "refresh", "rookie_capital"]

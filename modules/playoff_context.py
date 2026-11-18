"""Playoff odds as the pick-slot and buyer / seller engine.

Handshake item 9 of docs/audits/2026-11-advice-handshakes.md. The league already
runs one rest-of-season simulation (``playoff_simulator``, one number for every
surface, docs/decisions/one-playoff-odds.md). Until now it fed only the odds
screens, so a pick's projected slot came from roster value plus the current record
and "is this team buying or selling" came from trade counts alone.

This module reads that same simulation result (no second model):

* slot      simulated expected finish (playoff odds, median final wins, median
            seed) becomes a slot percentile in the SAME orientation the pick model
            already uses (0 = strongest team = latest pick, 1 = weakest = earliest
            pick). It is blended with the roster-value / record percentile, never
            replacing it, so a team's talent and record still count.
* lean      buyer / seller / hold from several factors: simulated playoff odds,
            clinched / eliminated, the team's resolved posture, and whether its
            core is older than the league's. A lean always lists its reasons and
            needs at least two agreeing points to leave "hold".

Pick prices are untouched: the blended percentile goes through the same
``trade_ideas.pick_value_components`` (the one pick pricer). Off-season and any
missing input return nothing, so callers fall back to today's behaviour.

The odds are a Pro feature (the odds screen is Pro-only), so only Pro surfaces
hand the odds in; a Free surface never runs or reads the simulation.

Kill switch: ``DYNASTYGM_PLAYOFF_ODDS_CONTEXT_V1`` (default ON; 0/false/off
restores the previous output exactly). Sim AI GMs do not read this module."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from modules import age_profile, experimental_graduation

PLAYOFF_ODDS_CONTEXT_ENV_KEY = "DYNASTYGM_PLAYOFF_ODDS_CONTEXT_V1"
# Share of the slot percentile that comes from the simulated finish (the rest is the
# existing roster-value + record blend).
ODDS_SLOT_WEIGHT = 0.5
BUY_ODDS = 65.0
LEAN_ODDS = 50.0
SELL_ODDS = 20.0
DEEP_SELL_ODDS = 8.0
LEAN_POINTS = 2
CONTEND_KEYS = frozenset({"contender", "fringe_contender"})
REBUILD_KEYS = frozenset({"rebuild", "tank"})


def enabled() -> bool:
    return experimental_graduation.graduated_kill_switch_enabled(PLAYOFF_ODDS_CONTEXT_ENV_KEY, default=True)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if out == out else default


def _teams(odds: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not odds or not odds.get("ok") or not odds.get("teams"):
        return []
    return [t for t in odds["teams"] if isinstance(t, Mapping) and t.get("playoff_probability") is not None]


def expected_finish_ranks(odds: Mapping[str, Any] | None) -> dict[str, int]:
    """roster_id -> expected finish (1 = best) from the simulation."""

    teams = _teams(odds)
    ordered = sorted(
        teams,
        key=lambda t: (-_num(t.get("playoff_probability")), -_num(t.get("median_final_wins")), _num(t.get("median_seed"), 99)),
    )
    return {str(t.get("roster_id")): i for i, t in enumerate(ordered, start=1)}


def slot_percentiles(odds: Mapping[str, Any] | None) -> dict[int, float]:
    """roster_id -> simulated-finish slot percentile (0 strongest .. 1 weakest).

    Empty when the flag is off or the odds are not ready (off-season, no format)."""

    if not enabled():
        return {}
    ranks = expected_finish_ranks(odds)
    n = len(ranks)
    if n < 2:
        return {}
    out: dict[int, float] = {}
    for rid, rank in ranks.items():
        try:
            out[int(rid)] = (rank - 1) / (n - 1)
        except ValueError:
            continue
    return out


def blend_slot_percentile(existing: float, odds_percentile: float | None, weight: float = ODDS_SLOT_WEIGHT) -> float:
    if odds_percentile is None:
        return float(existing)
    w = max(0.0, min(1.0, weight))
    return float((1.0 - w) * existing + w * odds_percentile)


def lean(
    row: Mapping[str, Any] | None,
    *,
    posture_key: Any = "",
    core_age_delta: float | None = None,
) -> dict[str, Any]:
    """Buyer / seller / hold for one team with the reasons behind it."""

    if not row or row.get("playoff_probability") is None:
        return {"lean": "", "points": 0, "why": []}
    p = _num(row.get("playoff_probability"))
    points = 0
    why: list[str] = []
    if row.get("eliminated"):
        points -= 3
        why.append("eliminated from the playoffs")
    elif row.get("clinched"):
        points += 2
        why.append("playoff spot clinched")
    elif p >= BUY_ODDS:
        points += 2
        why.append(f"{p:.0f}% playoff odds")
    elif p >= LEAN_ODDS:
        points += 1
        why.append(f"{p:.0f}% playoff odds, on the bubble")
    elif p <= DEEP_SELL_ODDS:
        points -= 3
        why.append(f"only {p:.0f}% playoff odds")
    elif p <= SELL_ODDS:
        points -= 2
        why.append(f"{p:.0f}% playoff odds")
    else:
        why.append(f"{p:.0f}% playoff odds, " + ("a long shot" if p < 35 else "a bit below even"))
    key = str(posture_key or "").lower()
    if key in CONTEND_KEYS:
        points += 1
        why.append("roster reads as a contender")
    elif key in REBUILD_KEYS:
        points -= 1
        why.append("roster reads as a rebuild")
    if core_age_delta is not None and abs(core_age_delta) >= age_profile.TEAM_OLDER_RETOOL_DELTA_YEARS and p < 35:
        if core_age_delta > 0:
            points -= 1
            why.append(f"core runs {core_age_delta:.1f} years older than the league")
        else:
            why.append(f"core runs {abs(core_age_delta):.1f} years younger than the league")
    side = "buyer" if points >= LEAN_POINTS else "seller" if points <= -LEAN_POINTS else "hold"
    return {"lean": side, "points": points, "why": why}


def team_reads(odds: Mapping[str, Any] | None, profile: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    """roster_id -> {slot_percentile, expected_finish, lean, points, why} for every team."""

    if not enabled():
        return {}
    teams = {str(t.get("roster_id")): t for t in _teams(odds)}
    if not teams:
        return {}
    ranks = expected_finish_ranks(odds)
    pcts = slot_percentiles(odds)
    profile_teams = (profile or {}).get("teams") or {}
    cores = [t.get("age", {}).get("core_avg") for t in profile_teams.values() if (t.get("age") or {}).get("core_avg") is not None]
    league_core = sum(float(c) for c in cores) / len(cores) if cores else None
    out: dict[str, dict[str, Any]] = {}
    for rid, row in teams.items():
        prof = profile_teams.get(rid) or {}
        core = (prof.get("age") or {}).get("core_avg")
        delta = float(core) - league_core if core is not None and league_core is not None else None
        read = lean(row, posture_key=(prof.get("posture") or {}).get("key"), core_age_delta=delta)
        try:
            pct = pcts.get(int(rid))
        except ValueError:
            pct = None
        out[rid] = {"slot_percentile": pct, "expected_finish": ranks.get(rid), "team_count": len(teams), **read}
    return out

"""Is this player a sensible acquisition TARGET for this team right now? (flag DYNASTYGM_TARGET_VIABILITY_V1)

The Trade Board picked targets on market value, need and age only. A player on IR with no return date who sits RB6 on his
team's chart still scored as a top RB by market, so he was recommended with no mention of the injury or the role. This module
is the one availability + role check for acquisition targets. Nothing is modelled here that another module already owns:

* availability: ``trade_grade.estimate_injury_absence`` (the same absence estimate the Trade Analyzer prices), the season
  window (``trade_grade.season_window``), the posture's own weight on missed weeks (``trade_grade.injury_posture_weight``),
  and the fitted return curves (``injury_return_curves``) for what is lost over the next 17 games.
* role: depth-chart place against the team's own starter slots (``NFL_DEPTH_STARTERS``), softened by a snap-share
  read when the row carries one.
* posture: the same weight blends "this season" and "later": a contender lives on this season; a rebuilder discounts it.

Verdicts: ``target`` (recommend as before), ``stash`` (a cheap, young, injured or buried player a non-contender may hold
for later; framed honestly and never ahead of a healthy fit) and ``avoid`` (not recommended). No names, no per-player rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from modules import age_profile, injury_return_curves, trade_grade
from modules.coerce import float_nan_to_none
from modules.team_eval import normalize_team_strategy

ENV_KEY = "DYNASTYGM_TARGET_VIABILITY_V1"
# Starters per position on an NFL depth chart (a real team's usual offense), not a fantasy lineup.
NFL_DEPTH_STARTERS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1}
# Last chart place that still counts as usable depth (a backup who plays when a starter is out): QB2, RB4, WR5, TE3. Anything
# deeper (QB3+, RB5+, WR6+, TE4+) is buried. Sleeper lists WRs by sub-slot (LWR / RWR / SWR), each with its own order, so a
# sub-slot has one starter and a usable depth of three.
NFL_USABLE_DEPTH = {"QB": 2, "RB": 4, "WR": 5, "TE": 3}
WR_SUB_SLOTS = frozenset({"LWR", "RWR", "SWR"})
HORIZON_GAMES = 17.0
TARGET_MIN_VIABILITY = 0.6
STASH_MIN_VIABILITY = 0.2
# A posture whose missed-week weight is at or below this can hold a player for later (retool and below).
STASH_MAX_POSTURE_WEIGHT = 0.45
# What a non-contender credits a young player's role with later, whatever the chart says today.
FUTURE_ROLE_FLOOR = 0.5
SNAP_STARTER_SHARE = 0.55


def enabled() -> bool:
    from modules.experimental_graduation import graduated_kill_switch_enabled

    return graduated_kill_switch_enabled(ENV_KEY, default=False)


@dataclass(frozen=True)
class Viability:
    verdict: str  # "target" | "stash" | "avoid"
    viability: float
    availability: float
    role: float
    reasons: tuple[str, ...]
    note: str = ""

    @property
    def is_stash(self) -> bool:
        return self.verdict == "stash"


_num = float_nan_to_none


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def role_factor(row: Mapping[str, Any]) -> tuple[float, str]:
    """1.0 = starter-level role; lower the deeper he sits behind his team's starters. No chart data = no evidence = 1.0."""

    pos = _text(row.get("position")).upper()
    slots = NFL_DEPTH_STARTERS.get(pos)
    order = _num(row.get("depth_chart_order"))
    if not slots or order is None or order <= 0:
        return 1.0, ""
    usable = NFL_USABLE_DEPTH[pos]
    if pos == "WR" and _text(row.get("depth_chart_position")).upper() in WR_SUB_SLOTS:
        slots, usable = 1, 3
    factor = 1.0 if order <= slots + 1 else 0.8 if order <= usable else 0.3
    snap = _num(row.get("snap_share"))
    if snap is not None:
        snap = snap / 100.0 if snap > 1.5 else snap
        if snap >= SNAP_STARTER_SHARE:
            factor = max(factor, 0.8)
    if factor >= 1.0:
        return factor, ""
    return factor, f"{pos}{int(order)} on the depth chart"


def availability_factor(
    row: Mapping[str, Any],
    *,
    strategy: str,
    window: "trade_grade.SeasonWindow",
) -> tuple[float, str]:
    """1.0 = fully available. Blends the share of this season missed with what the return curves say is lost later, by the
    posture's own weight on missed weeks."""

    absence = trade_grade.estimate_injury_absence(
        row.get("status"), row.get("injury_status"),
        body_part=row.get("injury_body_part"), notes=row.get("injury_notes"), window=window,
    )
    if absence is None:
        return 1.0, ""
    effective = max(float(window.effective_weeks), 1.0)
    now_loss = min(1.0, float(absence.weeks) / effective)
    if not window.in_season:
        now_loss *= trade_grade.OFFSEASON_INJURY_FACTOR
    later_games = injury_return_curves.expected_games_lost(
        row.get("status"), row.get("injury_status"), position=_text(row.get("position")).upper() or None
    )
    later_loss = min(1.0, (later_games or 0.0) / HORIZON_GAMES)
    weight = trade_grade.injury_posture_weight(strategy)
    loss = weight * now_loss + (1.0 - weight) * later_loss
    body = _text(row.get("injury_body_part")).lower()
    status = _text(row.get("injury_status")) or _text(row.get("status")) or absence.status_label
    detail = f"{status}{', ' + body if body else ''}"
    if absence.season_ending:
        timing = "out for the season"
    elif absence.unconfirmed or absence.basis.startswith("default"):
        timing = "no return date"
    else:
        timing = f"out ~{int(round(absence.weeks))} wk"
    return max(0.0, 1.0 - loss), f"{detail}, {timing}"


def assess(
    row: Mapping[str, Any],
    *,
    strategy: str,
    window: "trade_grade.SeasonWindow",
    value: float,
    cheap_value: float,
) -> Viability:
    """The availability + role verdict for acquiring ``row`` as a ``strategy`` team. ``cheap_value`` is the score at or
    under which a player is cheap enough to hold as a stash (same scale as ``value``)."""

    strategy = normalize_team_strategy(strategy)
    weight = trade_grade.injury_posture_weight(strategy)
    availability, injury_text = availability_factor(row, strategy=strategy, window=window)
    role, role_text = role_factor(row)
    age = _num(row.get("age"))
    if role < 1.0 and age is not None and age_profile.at_most(age, age_profile.REBUILD_TARGET_MAX_AGE):
        role = weight * role + (1.0 - weight) * max(role, FUTURE_ROLE_FLOOR)
    viability = availability * role
    reasons = tuple(text for text in (injury_text, role_text) if text)
    if viability >= TARGET_MIN_VIABILITY:
        # Still labelled when he carries a short absence or a thin role: the Analyzer prices it, the card says it.
        note = f"Availability: {'; '.join(reasons)}." if reasons else ""
        return Viability("target", viability, availability, role, reasons, note)
    young_cap = age_profile.RETOOL_TARGET_MAX_AGE if strategy == "retool" else age_profile.REBUILD_TARGET_MAX_AGE
    stash_ok = (
        weight <= STASH_MAX_POSTURE_WEIGHT
        and age is not None
        and age_profile.at_most(age, young_cap)
        and value <= cheap_value
        and viability >= STASH_MIN_VIABILITY
    )
    why = "; ".join(reasons) or "limited availability or role"
    if stash_ok:
        kind = "Injured stash" if injury_text else "Depth stash"
        note = f"{kind}, buy-low only: {why}; cheap now, value if {'he returns and ' if injury_text else ''}the role opens."
        return Viability("stash", viability, availability, role, reasons, note)
    who = "a contending team" if weight > STASH_MAX_POSTURE_WEIGHT else "this price and age"
    return Viability("avoid", viability, availability, role, reasons, f"Not a target for {who}: {why}.")

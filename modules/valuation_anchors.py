"""League-aware role/opportunity anchors (trade-advice audit P1-1 and P1-2).

docs/audits/2026-11-trade-advice-backtest.md section 8:

* P1-1 "QB and TE inflation in 1QB": the role (0.06 x 8,500) and opportunity
  (0.10 x 8,800) anchors saturate for ANY QB1/TE1 on a depth chart, adding about
  +1,390 engine points to a player the league never starts (a QB19 in a 1QB
  league). Fix: make role/opportunity position-relative to the league's STARTING
  DEMAND. :func:`starting_demand_adjustment` fades the above-neutral part of the
  role and opportunity contributions for players ranked beyond their position's
  demand (smoothly: full credit inside the demand, none at 1.5x the demand).
* P1-2 "No-market floor of about +850": a player with no market value still
  carries neutral production (2,200 x 0.12) and opportunity (2,800 x 0.10) anchors,
  so depth pieces add value out of nothing. Fix (the audit's first option, anchor
  to 0 when there is no evidence): :func:`no_market_floor_adjustment` removes the
  anchor contribution of a no-market player whose production / opportunity score
  is still exactly the neutral anchor, i.e. carries no evidence.

Both return a NON-POSITIVE per-row point adjustment applied to the league-lens
pre-league scores in ``league_value_settings.apply_valuation_lens``. They never
touch the canonical ``base_score``. Each is behind its own flag, default ON (owner-approved 2026-11-18; set to 0 to disable):
``DYNASTYGM_ROLE_STARTING_DEMAND_V1`` and ``DYNASTYGM_NO_MARKET_FLOOR_V1``.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from modules.coerce import float_or_default
from modules.experimental_graduation import graduated_kill_switch_enabled

STARTING_DEMAND_ENV_KEY = "DYNASTYGM_ROLE_STARTING_DEMAND_V1"
NO_MARKET_FLOOR_ENV_KEY = "DYNASTYGM_NO_MARKET_FLOOR_V1"

# Same constants as rankings.COMPOSITE_WEIGHT_* / *_NEUTRAL_ANCHOR (kept local so
# this module has no import cycle with rankings; tests pin them to the originals).
ROLE_WEIGHT = 0.06
OPPORTUNITY_WEIGHT = 0.10
PRODUCTION_WEIGHT = 0.12
ROLE_NEUTRAL = 3800.0
OPPORTUNITY_NEUTRAL = 2800.0
PRODUCTION_NEUTRAL = 2200.0
# Full role/opportunity credit up to the league's demand, none at 1.5x the demand.
FADE_SPAN = 0.5
NEUTRAL_TOLERANCE = 1.0
DEMAND_POSITIONS = ("QB", "RB", "WR", "TE")


def flag_default_on(key: str) -> bool:
    """Default-ON flag: unset or any non-false value is on; only an explicit
    0/false/no/off turns it off (kill switch)."""

    return graduated_kill_switch_enabled(key, default=True)


def starting_demand_enabled() -> bool:
    return flag_default_on(STARTING_DEMAND_ENV_KEY)


def no_market_floor_enabled() -> bool:
    return flag_default_on(NO_MARKET_FLOOR_ENV_KEY)


def fingerprint_parts() -> tuple[str, ...]:
    """Cache-key parts: one per enabled flag, so flipping a flag invalidates valued-player caches."""

    parts = []
    if starting_demand_enabled():
        parts.append("role_demand=1")
    if no_market_floor_enabled():
        parts.append("no_market_floor=1")
    return tuple(parts)


def starting_demand_by_position(settings: Mapping[str, Any] | None) -> dict[str, float]:
    """League-wide count of starters per position from the detected league settings:
    dedicated slots plus each flex slot's share, times the league size."""

    s = dict(settings or {})

    def setting(key: str, default: float = 0.0) -> float:
        return float_or_default(s.get(key) if s.get(key) is not None else default, default)

    size = max(2.0, setting("league_size", 12.0))
    flex, wrrb, rec = setting("regular_flex_count"), setting("wrrb_flex_count"), setting("rec_flex_count")
    per_team = {
        "QB": setting("qb_count", 1.0) + setting("superflex_count"),
        "RB": setting("rb_count", 2.0) + 0.5 * flex + 0.5 * wrrb,
        "WR": setting("wr_count", 3.0) + 0.5 * flex + 0.5 * wrrb + 0.5 * rec,
        "TE": setting("te_count", 1.0) + 0.34 * flex + 0.5 * rec,
    }
    return {pos: max(1.0, count) * size for pos, count in per_team.items()}


def _numeric(df: pd.DataFrame, column: str, default: float) -> pd.Series:
    if column not in df.columns:
        return pd.Series(float(default), index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").fillna(float(default))


def starting_demand_adjustment(
    df: pd.DataFrame, settings: Mapping[str, Any] | None, risk: pd.Series | None = None
) -> pd.Series:
    """Points to subtract per row: the above-neutral role/opportunity credit of a
    player ranked (by market value, within position) beyond the league's demand."""

    out = pd.Series(0.0, index=df.index, dtype="float64")
    if df.empty or "position" not in df.columns:
        return out
    positions = df["position"].fillna("").astype(str).str.upper()
    market = _numeric(df, "market_score", 0.0)
    role = _numeric(df, "role_score", ROLE_NEUTRAL)
    opp = _numeric(df, "opportunity_score", OPPORTUNITY_NEUTRAL)
    credit = ROLE_WEIGHT * (role - ROLE_NEUTRAL).clip(lower=0) + OPPORTUNITY_WEIGHT * (opp - OPPORTUNITY_NEUTRAL).clip(lower=0)
    demand = starting_demand_by_position(settings)
    for pos in DEMAND_POSITIONS:
        mask = positions == pos
        if not mask.any():
            continue
        # 1 = best market value at the position.
        rank = market.where(mask).rank(ascending=False, method="first")
        need = demand[pos]
        fade = ((rank - need) / (FADE_SPAN * need)).clip(lower=0.0, upper=1.0)
        out = out.where(~mask, -(credit * fade))
    if risk is not None:
        out = out * pd.to_numeric(risk, errors="coerce").fillna(1.0).clip(lower=0.0, upper=1.0)
    return out.round(2)


def no_market_floor_adjustment(df: pd.DataFrame) -> pd.Series:
    """Points to subtract per row: the neutral production / opportunity anchor
    contribution of a player with no market value and no evidence for that factor."""

    out = pd.Series(0.0, index=df.index, dtype="float64")
    if df.empty:
        return out
    no_market = _numeric(df, "market_score", 0.0) <= 0
    prod_blank = (_numeric(df, "production_score", PRODUCTION_NEUTRAL) - PRODUCTION_NEUTRAL).abs() <= NEUTRAL_TOLERANCE
    opp_blank = (_numeric(df, "opportunity_score", OPPORTUNITY_NEUTRAL) - OPPORTUNITY_NEUTRAL).abs() <= NEUTRAL_TOLERANCE
    out = out - np.where(no_market & prod_blank, PRODUCTION_WEIGHT * PRODUCTION_NEUTRAL, 0.0)
    out = out - np.where(no_market & opp_blank, OPPORTUNITY_WEIGHT * OPPORTUNITY_NEUTRAL, 0.0)
    return pd.Series(out, index=df.index, dtype="float64")

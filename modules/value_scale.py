"""The league's value scale, so absolute-point thresholds survive a league whose values sit on a different scale.

``modules/trade_ideas.py`` classifies and filters with absolute score cutoffs (a 1800-point throw-in, a 5200-point
premium asset, a 7600-point star, a -1200..+1800 fair-value band ...). They were tuned on the production value scale
(top of the board near 10000). A league whose valuation lands on another scale (a different lens, a rescaled
import, a different market snapshot) silently changes what "star" means. This module derives ONE scale factor from the
league's own value distribution and the trade ideas engine multiplies every absolute cutoff by it.

The anchor is the median of the 36 highest RB/WR values: the elite-skill band. It is stable across dates and formats
(RB/WR are the two positions Superflex and TE premium do not move) and does not depend on league size or on how many
players the pool holds. ``REFERENCE_ANCHOR`` is that median on the production scale the cutoffs were tuned on
(5.3k-5.5k across 2022-2025 snapshots in the trade-advice backtest). Scale = league anchor / reference, so the scale
is exactly 1.0 on the production scale and moves linearly with a uniform rescale of every value.

Flag ``DYNASTYGM_SCALE_AWARE_THRESHOLDS_V1`` (default OFF, owner coridian_). OFF: ``scale()`` is always 1 and
``scaled`` returns its argument untouched (same object, same type), so behaviour is bit-identical to before.
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import Any, Iterator, Mapping

import pandas as pd

ENV_KEY = "DYNASTYGM_SCALE_AWARE_THRESHOLDS_V1"
REFERENCE_ANCHOR = 5400.0
ANCHOR_POSITIONS = ("RB", "WR")
ANCHOR_TOP_N = 36
MIN_ANCHOR_PLAYERS = 12  # fewer RB/WR values than this is not a distribution; keep scale 1
MIN_SCALE, MAX_SCALE = 0.05, 20.0

_ACTIVE: contextvars.ContextVar[float | None] = contextvars.ContextVar("dynastygm_value_scale", default=None)


def enabled(*, environ: Mapping[str, Any] | None = None) -> bool:
    from modules.app_config import config_value

    return config_value(ENV_KEY, environ=environ).strip().casefold() in {"1", "true", "yes", "on"}


def league_scale(frame: pd.DataFrame | None, score_field: str) -> float | None:
    """The league's value scale relative to the production scale, or None when it cannot be measured."""

    if frame is None or frame.empty or score_field not in frame.columns or "position" not in frame.columns:
        return None
    pos = frame["position"].astype(str).str.upper()
    values = pd.to_numeric(frame.loc[pos.isin(ANCHOR_POSITIONS), score_field], errors="coerce").dropna()
    values = values[values > 0].sort_values(ascending=False)
    if len(values) < MIN_ANCHOR_PLAYERS:
        return None
    anchor = float(values.head(ANCHOR_TOP_N).median())
    return min(MAX_SCALE, max(MIN_SCALE, anchor / REFERENCE_ANCHOR))


def scale() -> float:
    """The active scale (1.0 when the flag is off or no league scale is in scope)."""

    value = _ACTIVE.get()
    return 1.0 if value is None else value


def scaled(points: Any) -> Any:
    """An absolute point threshold expressed on the active league's scale. Untouched when no scale is active."""

    value = _ACTIVE.get()
    if value is None:
        return points
    return points * value


@contextlib.contextmanager
def scope(frame: pd.DataFrame | None, score_field: str) -> Iterator[float | None]:
    """Activate the league scale for ``frame`` while the flag is on; a no-op otherwise."""

    value = league_scale(frame, score_field) if enabled() else None
    token = _ACTIVE.set(value)
    try:
        yield value
    finally:
        _ACTIVE.reset(token)

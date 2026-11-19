"""The ONE age vocabulary: rising / prime / declining / cliff, position-aware.

Before this module each advice surface kept its own hardcoded cutoffs (24, 25,
28, 29, 31 ...), so one player was "young", "prime" or "aging" depending on
which screen looked. This module answers those questions from the real
calibrated curve (``rankings.AGE_CURVE_CONTROL_POINTS`` and its prime window,
``rankings.prime_window_for_position``) and nothing else. It adds no valuation
and changes no stored value: it only names where an age sits on the curve.

Bands (per position, from the curve):

* ``rising``    age is before the prime window opens.
* ``prime``     inside the prime window (curve within 90% of the position peak).
* ``declining`` past the prime window, curve still at or above 70% of peak.
* ``cliff``     curve below 70% of peak.
* ``unknown``   no curve for the position (DEF, IDP) or no usable age.

``young`` is wider than ``rising``: a player is young until one year into the
window (``YOUNG_RUNWAY_YEARS``), because the first prime year is still a
development-runway year in every dynasty read.

Kill switch: ``DYNASTYGM_CANONICAL_AGE_CURVE`` (default ON). When off, every
``is_*`` helper returns the legacy hardcoded answer its caller passes in, so the
old cutoffs come back bit for bit. Positions with no curve always use the legacy
cutoff.

Sim does not use this module (its own aging model is pinned by game_rules)."""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

from modules import experimental_graduation

AGE_CURVE_ENV_KEY = "DYNASTYGM_CANONICAL_AGE_CURVE"

CLIFF_SHARE_OF_PEAK = 0.70
YOUNG_RUNWAY_YEARS = 1.0
# The placeholder for "unknown birth date" (see team_eval.MAX_KNOWN_PLAYER_AGE).
MAX_KNOWN_AGE = 60.0

# Team-level (relative) age deltas. These compare a team's average age with the
# league median, so they are relative gaps rather than absolute age bands; they
# live here so every team-age rule shares one named value.
TEAM_OLDER_RETOOL_DELTA_YEARS = 1.25
TEAM_OLDER_TANK_DELTA_YEARS = 1.0
YOUNGER_RETURN_YEARS = 1.25

# Analyzer-fit team age deltas (years the roster's average age moves because of one trade). Relative, like the
# deltas above; named here so the verdict's age component and its prose read the same numbers.
FIT_REBUILD_YOUNGER_STRONG_DELTA = -0.4  # a rebuild gaining this much youth scores the full age credit
FIT_REBUILD_OLDER_STRONG_DELTA = 0.5  # ... and aging up this much takes the full penalty
FIT_CONTENDER_OK_OLDER_DELTA = 0.6  # a contender tolerates this much aging when the lineup improves
FIT_CONTENDER_BAD_OLDER_DELTA = 0.8  # ... but not this much when the lineup does not
FIT_RETOOL_YOUNGER_DELTA = -0.35
FIT_RETOOL_OLDER_DELTA = 0.75
FIT_NOTE_OLDER_DELTA = 0.4  # "pushes the roster older" wording
FIT_NEGATIVE_OLDER_DELTA = 0.6  # "ages the roster up" negative

PHASES = ("rising", "prime", "declining", "cliff")

# --- Named flat cutoffs ------------------------------------------------------------------------------------------------
# Surfaces that deliberately use ONE absolute age for every position (a market-value rule, a screen heuristic, a data
# sanity check) read it from here instead of carrying a literal. Each value is what that surface has always used;
# naming it does not change it. Position-aware reads (``is_young`` / ``phase`` ...) stay the preferred way to ask "is
# this player young"; these exist so a deliberate flat cutoff is documented, greppable and guarded
# (tests/test_no_age_literals_outside_age_profile.py) instead of scattered.
UNKNOWN_AGE_SENTINEL = 99.0  # the "no birth date" fill value some frames use

# trade_ideas market classification (asset score x age)
THROW_IN_VETERAN_MIN_AGE = 28.0  # an old, low-tier, low-score asset is a throw-in
PREMIUM_RB_MAX_AGE = 26.0  # a young RB with a strong score or tier is a premium market asset
CORNERSTONE_YOUNG_MAX_AGE = 26.0  # an elite-tier player this young is a cornerstone
CORNERSTONE_SF_QB_MAX_AGE = 28.0  # Superflex QBs keep cornerstone status longer
CORNERSTONE_ELITE_RB_MAX_AGE = 24.0  # RBs lose cornerstone status early
CORE_YOUNG_MAX_AGE = 25.0  # a young, high-score player is a core / long-term starter

# trade_ideas fit scoring (who a posture wants to buy, sell or hold)
SELL_HIGH_VETERAN_MIN_AGE = 27.0  # an older player fits a partner that wants production now
REBUILD_TARGET_MAX_AGE = 25.0  # a rebuild / tank wants targets this young
RETOOL_TARGET_MAX_AGE = 26.0
CONTENDER_TARGET_AGES = (27.0, 30.0)  # (min, max) a contender wants
AGING_CONTENDER_TARGET_AGES = (26.0, 30.0)
YOUNG_CORE_ARCHETYPE_MAX_AGE = 25.0  # young-core archetypes (Juggernaut ...) protect assets this young
REBUILD_SELL_MIN_AGE = 26.0  # a rebuild converts an older player into youth or picks
CONTENDER_WINDOW_AGES = (26.0, 30.0)  # age band that fits a win-now window (legacy path, curve switch off)
LEGACY_PRIME_AGES = (25.0, 30.0)  # the old partner-acceptance "prime" band (legacy path, curve switch off)
LEGACY_GROUP_OLD_AVG_AGE = 28.0  # group_band legacy_old for a trade package
LEGACY_GROUP_YOUNG_AVG_AGE = 25.0  # group_band legacy_young for a trade package
OLDER_RETURN_MIN_AGE = 28.5  # a single incoming player this old makes a return "older" for a rebuild

# rankings / waivers / draft heuristics
YOUNG_UPSIDE_MAX_AGE = 24.0  # a player this young still reads as upside (opportunity, stash, rookie-like draft pool)
FUTURE_ASSET_MAX_AGE = 23.0  # injury-return "future asset" profile
STALE_FA_RETIRED_MIN_AGE = 40.0  # a free agent this old is treated as retired
STALE_FA_VETERAN_MIN_AGE = 30.0  # ... or stale when also unranked and long un-updated
STALE_FA_LONG_CAREER_MIN_AGE = 35.0  # ... or a 12+ year veteran this old with no market

# Drop-candidates young-upside protection is measured from this window-opening reference (see posture_model).
YOUTH_RUNWAY_BASE_AGE = 23.0


def at_most(age: Any, cutoff: float) -> bool:
    """``0 < age <= cutoff``: a known age at or under a flat cutoff (missing / zero age never qualifies)."""

    return 0 < age <= cutoff


def at_least(age: Any, cutoff: float) -> bool:
    """``age >= cutoff`` (a missing age compares as the caller's 0 and never qualifies)."""

    return age >= cutoff


def within(age: Any, bounds: tuple[float, float]) -> bool:
    """``min <= age <= max`` for a flat (min, max) age band."""

    return bounds[0] <= age <= bounds[1]


def enabled(*, environ: Mapping[str, Any] | None = None) -> bool:
    return experimental_graduation.graduated_kill_switch_enabled(AGE_CURVE_ENV_KEY, environ=environ, default=True)


def _rankings():
    from modules import rankings  # lazy: rankings is heavy and imports half the repo

    return rankings


def _clean_age(age: Any) -> float | None:
    try:
        value = float(age)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value <= 0 or value > MAX_KNOWN_AGE:
        return None
    return value


def window(position: Any) -> tuple[float, float] | None:
    """(start, end) of the position's prime window, or None with no curve."""

    return _rankings().prime_window_for_position(str(position or "").upper())


def peak_age(position: Any) -> float | None:
    """The age the curve peaks at (centre of the prime window)."""

    win = window(position)
    if win is None:
        return None
    return round((win[0] + win[1]) / 2.0, 1)


def phase(position: Any, age: Any) -> str:
    """rising / prime / declining / cliff, or "unknown"."""

    value = _clean_age(age)
    win = window(position)
    if value is None or win is None:
        return "unknown"
    start, end = win
    if value < start:
        return "rising"
    if value <= end:
        return "prime"
    rk = _rankings()
    points = rk.AGE_CURVE_CONTROL_POINTS.get(str(position or "").upper()) or ()
    peak = max((m for _, m in points), default=1.0)
    if rk.age_multiplier(str(position).upper(), value) < CLIFF_SHARE_OF_PEAK * peak:
        return "cliff"
    return "declining"


def prime_years_left(position: Any, age: Any) -> float | None:
    """Years until the prime window closes (0 once past it); None when unknown."""

    value = _clean_age(age)
    win = window(position)
    if value is None or win is None:
        return None
    return round(max(0.0, win[1] - value), 1)


def offset(position: Any, age: Any) -> float | None:
    """Years outside the prime window: negative before it, 0 inside, positive after."""

    value = _clean_age(age)
    win = window(position)
    if value is None or win is None:
        return None
    if value < win[0]:
        return round(value - win[0], 2)
    if value > win[1]:
        return round(value - win[1], 2)
    return 0.0


def _raw_age(age: Any) -> float:
    try:
        value = float(age)
    except (TypeError, ValueError):
        return 0.0
    return value if math.isfinite(value) else 0.0


# The legacy answers take the age exactly as the old inline comparisons did
# (including their treatment of a missing age as 0), so the kill switch restores
# the old behaviour bit for bit.
def _legacy_young(age: Any, legacy_max: float) -> bool:
    value = _raw_age(age)
    return 0 < value <= legacy_max


def _legacy_aging(age: Any, legacy_min: float) -> bool:
    return _raw_age(age) >= legacy_min


def is_young(position: Any, age: Any, *, legacy_max: float, environ: Mapping[str, Any] | None = None) -> bool:
    """Young: before the window, or within ``YOUNG_RUNWAY_YEARS`` of it opening.
    ``legacy_max`` is the old hardcoded cutoff, used when the switch is off or the
    position has no curve."""

    win = window(position) if enabled(environ=environ) else None
    value = _clean_age(age)
    if win is None:
        return _legacy_young(age, legacy_max)
    return value is not None and value <= win[0] + YOUNG_RUNWAY_YEARS


def is_aging(position: Any, age: Any, *, legacy_min: float, environ: Mapping[str, Any] | None = None) -> bool:
    """Aging: past the prime window (declining or cliff)."""

    win = window(position) if enabled(environ=environ) else None
    if win is None:
        return _legacy_aging(age, legacy_min)
    return phase(position, age) in {"declining", "cliff"}


def runway_ok(
    position: Any, age: Any, *, years_past_start: float, legacy_max: float, environ: Mapping[str, Any] | None = None
) -> bool:
    """Posture-tuned youth runway: age within ``years_past_start`` of the window
    opening. Lets a rebuilder protect a longer runway than a contender without a
    separate absolute age table."""

    win = window(position) if enabled(environ=environ) else None
    value = _clean_age(age)
    if win is None:
        return _legacy_young(age, legacy_max)
    return value is not None and value <= win[0] + years_past_start


def pair_for(asset: Mapping[str, Any]) -> tuple[str, Any]:
    return str(asset.get("position") or asset.get("pos") or ""), asset.get("age")


def group_offset(pairs: Iterable[tuple[Any, Any]]) -> float | None:
    """Mean ``offset`` over (position, age) pairs with a curve; None if none."""

    offs = [o for o in (offset(p, a) for p, a in pairs) if o is not None]
    if not offs:
        return None
    return sum(offs) / len(offs)


def group_band(
    pairs: Sequence[tuple[Any, Any]],
    *,
    legacy_avg: float | None,
    legacy_old: float,
    legacy_young: float,
    environ: Mapping[str, Any] | None = None,
) -> str:
    """"young" / "prime" / "old" / "unknown" for a package of players.

    Canonical: mean years outside the prime window > 0 is
    old; mean years past the window opening <= YOUNG_RUNWAY_YEARS is young;
    otherwise prime). Legacy (switch off, or no player has a
    curve): ``legacy_avg`` against the old cutoffs (>= ``legacy_old`` old,
    <= ``legacy_young`` young)."""

    on = enabled(environ=environ)
    mean = group_offset(pairs) if on else None
    into = _group_into_window(pairs) if on else None
    if mean is None or into is None:
        if not legacy_avg:
            return "unknown"
        if legacy_avg >= legacy_old:
            return "old"
        if legacy_avg <= legacy_young:
            return "young"
        return "prime"
    if mean > 0.0:
        return "old"
    if into <= YOUNG_RUNWAY_YEARS:
        return "young"
    return "prime"


def _group_into_window(pairs: Iterable[tuple[Any, Any]]) -> float | None:
    """Mean years past the window opening (negative while still rising)."""

    vals = []
    for pos, age in pairs:
        win, value = window(pos), _clean_age(age)
        if win is not None and value is not None:
            vals.append(value - win[0])
    return sum(vals) / len(vals) if vals else None


def player_age_profile(position: Any, age: Any) -> dict[str, Any]:
    """The per-player record the team profile carries."""

    return {
        "age": _clean_age(age),
        "phase": phase(position, age),
        "prime_years_left": prime_years_left(position, age),
    }

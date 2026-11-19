"""The one posture model: how a team posture (contender .. tank) changes what a trade is worth.

Before this module the same idea, "how much does a rebuilder value now vs later", lived in per-module tables that were
tuned independently (trade_grade starter weights and injury weights, trade_posture present-adjust / window / orientation,
trade_hub_engine age curve and pick multiplier, trade_ideas pick-send terms, multi_team_trade_finder pick want,
drop_candidates youth protection). Tuning one fork broke another (the P1-5 starter floor vs ``PRESENT_ADJUST``). They now
all live here and every consumer reads them from here, so a retune is one edit and is golden-tested as one unit
(tests/test_posture_model_golden.py). No posture weight table may be defined outside this file
(tests/test_no_posture_tables_outside_model.py).

Derived values stay derived: the lineup model's now-weight comes from the starter-strength weight, and
``PRESENT_ADJUST`` comes from the net lineup-point target minus that now-weight, so raising a starter weight never
silently changes how a rebuilder prices a lineup point. The youth bonus tempering follows the same starter-floor flag.

This module imports nothing from the engine (only ``app_config`` lazily, for the flag) so every engine module can
import it without cycles.
"""

from __future__ import annotations

from typing import NamedTuple

from modules import age_profile

POSTURES: tuple[str, ...] = ("contender", "fringe_contender", "retool", "rebuild", "tank")

# --- starter strength (trade_grade): how much a real lineup point is worth beyond market, by posture -------------------

STARTER_STRENGTH_BASE: dict[str, float] = {
    "contender": 0.50,
    "fringe_contender": 0.35,
    "retool": 0.15,
    "rebuild": 0.05,
    "tank": 0.0,
}

# Trade-advice audit P1-5 (owner-approved 2026-11-18): realized two-season lineup points are ~0.55-0.6 of a market
# point at EVERY posture, so rebuild/tank weights of 0.05 / 0 under-price starting points. Default ON (0/false/no/off
# disables; read at import because the lineup model's weights and PRESENT_ADJUST derive from this table). Rebuild and
# tank are floored at 0.20 and their youth bonus is tempered (see ``tempered_youth_points``). Retool stays at 0.15.
STARTER_FLOOR_ENV_KEY = "DYNASTYGM_STARTER_WEIGHT_FLOOR_V1"
STARTER_WEIGHT_FLOOR = 0.20
STARTER_FLOOR_POSTURES = ("rebuild", "tank")
# Share of a rebuild/tank youth bonus kept while the floor is on (the floor already credits real points).
YOUTH_BONUS_TEMPER = 0.5


def starter_floor_enabled() -> bool:
    from modules.app_config import config_value

    return config_value(STARTER_FLOOR_ENV_KEY).strip().casefold() not in {"0", "false", "no", "off"}


STARTER_STRENGTH_WEIGHTS: dict[str, float] = dict(STARTER_STRENGTH_BASE)
if starter_floor_enabled():
    STARTER_STRENGTH_WEIGHTS = {
        k: (max(v, STARTER_WEIGHT_FLOOR) if k in STARTER_FLOOR_POSTURES else v) for k, v in STARTER_STRENGTH_BASE.items()
    }

# --- coherence retune (owner-approved 2026-11-19, flagged) ----------------------------------------------------------
# Three divergences that were preserved on purpose by the shared-model refactor (#2199) are coupled to the shared
# tables when this flag is ON: the injury weights follow the starter weights, the multi-team finder's pick want
# follows the tank/rebuild pick-sale distinction, and the pick-sale priority follows the posture ordering. Default
# OFF until the out-of-sample backtest clears it. Read at import because the tables below derive from it.
COHERENCE_ENV_KEY = "DYNASTYGM_POSTURE_COHERENCE_V1"


def coherence_enabled() -> bool:
    from modules.app_config import config_value

    return config_value(COHERENCE_ENV_KEY).strip().casefold() in {"1", "true", "yes", "on"}


COHERENCE_ON = coherence_enabled()

# --- injury availability (trade_grade): how much a posture cares about the weeks a player misses ---------------------

_INJURY_POSTURE_BASE: dict[str, float] = {
    "contender": 0.95,
    "fringe_contender": 0.75,
    "retool": 0.45,
    "rebuild": 0.15,
    "tank": 0.05,
}
# Coherence ON: a missed week costs a posture at least what a starter point earns it, so a floored rebuilder (starter
# weight 0.20) no longer prices a missed week (0.15) below a point. Derived from the same now-weight source.
INJURY_POSTURE_WEIGHTS: dict[str, float] = (
    {k: max(v, STARTER_STRENGTH_WEIGHTS[k]) for k, v in _INJURY_POSTURE_BASE.items()}
    if COHERENCE_ON
    else dict(_INJURY_POSTURE_BASE)
)

# --- lineup model weights (trade_lineup_model): (now, future); derived from the starter weight -------------------------
# A posture's extra weight on REAL lineup points is the starter-strength weight; future capital stays at 1.0 for every
# posture because the asset scores arriving at the lineup model are already posture-priced upstream (age curve, pick
# multiplier).
POSTURE_WEIGHTS: dict[str, tuple[float, float]] = {
    posture: (1.0 + starter_weight, 1.0) for posture, starter_weight in STARTER_STRENGTH_WEIGHTS.items()
}

# --- trade_posture: window cost, present adjust, orientation ---------------------------------------------------------
# A win-now team pays a window premium equal to the market price of the points themselves (contender 1.0), on top of the
# w_now emphasis. Retool is not a window team and stays at 0.15 (doubling it turned a sensible thin-roster 2-for-1
# upgrade from COUNTER into DECLINE). Calibration: 4 public leagues, "sell the top skill player for two R1s".
WINDOW_WIN_WEIGHT: dict[str, float] = {
    "contender": 1.0,
    "fringe_contender": 0.7,
    "retool": 0.15,
    "rebuild": 0.0,
    "tank": 0.0,
}
# The net weight on REAL lineup points a rebuilding team puts on a point of ROS lineup change (value units per point =
# the model's k), relative to the market's 1.0: rebuild ~0.65, tank ~0.40.
NET_POINT_WEIGHT_TARGET: dict[str, float] = {"rebuild": 0.65, "tank": 0.40}
# Extra weight beyond ``POSTURE_WEIGHTS``. DERIVED: the lineup model's own now-weight plus this lands on the net target.
PRESENT_ADJUST: dict[str, float] = {
    "contender": 0.0,
    "fringe_contender": 0.0,
    "retool": 0.0,
    **{posture: round(target - POSTURE_WEIGHTS[posture][0], 4) for posture, target in NET_POINT_WEIGHT_TARGET.items()},
}
# Where a posture wants its assets: +1 = present (lineup now), -1 = future (youth, picks). Retool is neutral.
ORIENTATION: dict[str, float] = {
    "contender": 1.0,
    "fringe_contender": 0.6,
    "retool": 0.0,
    "rebuild": -0.8,
    "tank": -1.0,
}

# --- trade_hub_engine: strategy age curve and pick multiplier ----------------------------------------------------------

PICK_SCORE_MULTIPLIER: dict[str, float] = {
    "contender": 0.88,
    "fringe_contender": 0.95,
    "retool": 1.02,
    "rebuild": 1.16,
    "tank": 1.25,
}


class Decline(NamedTuple):
    """Age decline for ``positions`` starting at ``start``, bottoming at ``floor`` (``smooth_decline``)."""

    positions: tuple[str, ...]
    start: float
    floor: float


class AgeCurve(NamedTuple):
    """One posture's age preference: youth-bonus knots ``(age, multiplier)`` then per-position declines (applied in order)."""

    youth: tuple[tuple[float, float], ...]
    declines: tuple[Decline, ...]
    tempered: bool = False  # youth bonus is scaled by YOUTH_BONUS_TEMPER while the starter floor is on


AGE_CURVES: dict[str, AgeCurve] = {
    "contender": AgeCurve(
        youth=((22.0, 0.98), (25.0, 1.04), (30.0, 1.04), (32.0, 1.0)),
        declines=(Decline(("RB",), 29, 0.94),),
    ),
    "fringe_contender": AgeCurve(
        youth=((22.0, 1.01), (24.0, 1.01), (25.0, 1.025), (29.0, 1.025), (31.0, 1.0)),
        declines=(Decline(("RB", "WR", "TE"), 31, 0.96),),
    ),
    "retool": AgeCurve(
        youth=((22.0, 1.04), (25.0, 1.04), (26.0, 1.01), (29.0, 1.01), (31.0, 1.0)),
        declines=(Decline(("RB",), 28, 0.91), Decline(("WR", "TE"), 31, 0.94)),
    ),
    "rebuild": AgeCurve(
        youth=((23.0, 1.10), (25.0, 1.06), (26.0, 1.02), (28.0, 1.0)),
        declines=(
            Decline(("RB",), 28, 0.82),
            Decline(("WR",), 30, 0.86),
            Decline(("TE",), 31, 0.88),
            Decline(("QB",), 34, 0.92),
        ),
        tempered=True,
    ),
    "tank": AgeCurve(
        youth=((23.0, 1.15), (25.0, 1.09), (26.0, 1.0)),
        declines=(
            Decline(("RB",), 27, 0.75),
            Decline(("WR",), 30, 0.80),
            Decline(("TE",), 31, 0.84),
            Decline(("QB",), 34, 0.88),
        ),
        tempered=True,
    ),
}


def youth_points(curve: AgeCurve) -> tuple[tuple[float, float], ...]:
    """The youth-bonus knots for ``curve``, tempered when the starter floor is on and the posture is floored."""

    if not curve.tempered or not starter_floor_enabled():
        return curve.youth
    return tuple((age, 1.0 + (mult - 1.0) * YOUTH_BONUS_TEMPER) for age, mult in curve.youth)


# --- drop_candidates: young-upside protection ---------------------------------------------------------------------------
# (max age for skill players, QB age bump, minimum healthy value as a share of the high-value threshold).
# The max age is the age_profile window-opening reference (``YOUTH_RUNWAY_BASE_AGE``) plus a posture-tuned runway in
# years: a rebuild protects a longer youth runway than a contender. ``drop_candidates`` measures the same runway from
# each position's real window start (``age_profile.runway_ok``); the absolute age is only the no-curve fallback.
YOUTH_RUNWAY_YEARS: dict[str, float] = {"tank": 3.0, "rebuild": 2.0, "retool": 1.0, "fringe_contender": 0.0, "contender": 0.0}
_BASE = age_profile.YOUTH_RUNWAY_BASE_AGE
YOUTH_PROTECTION: dict[str, tuple[float, float, float]] = {
    "tank": (_BASE + YOUTH_RUNWAY_YEARS["tank"], 1.0, 0.10),
    "rebuild": (_BASE + YOUTH_RUNWAY_YEARS["rebuild"], 2.0, 0.12),
    "retool": (_BASE + YOUTH_RUNWAY_YEARS["retool"], 2.0, 0.20),
    "fringe_contender": (_BASE + YOUTH_RUNWAY_YEARS["fringe_contender"], 2.0, 0.28),
    "contender": (_BASE + YOUTH_RUNWAY_YEARS["contender"], 2.0, 0.35),
}

# --- trade_ideas: what posture thinks of the user's own pick sales --------------------------------------------------------
# A rebuilder dislikes selling picks. (fit_priority per pick, my-side fit term). Contender-like postures get a bonus.
PICK_SALE_PRIORITY_PER_PICK: dict[str, int] = {
    "contender": 6,
    "fringe_contender": 6,
    "retool": 1,
}
PICK_SALE_PRIORITY_DEFAULT = -7  # rebuild and tank
PICK_SALE_FIT_TERM: dict[str, int] = {"tank": -16, "rebuild": -12, "retool": -2}
if COHERENCE_ON:
    # Fringe sits between contender (+6) and retool (+1), interpolated by the shared orientation (0.6 of the way).
    PICK_SALE_PRIORITY_PER_PICK["fringe_contender"] = round(
        PICK_SALE_PRIORITY_PER_PICK["retool"]
        + (PICK_SALE_PRIORITY_PER_PICK["contender"] - PICK_SALE_PRIORITY_PER_PICK["retool"])
        * (ORIENTATION["fringe_contender"] - ORIENTATION["retool"])
        / (ORIENTATION["contender"] - ORIENTATION["retool"])
    )

# --- multi_team_trade_finder: how much a posture group wants draft capital back, who sends it -------------------------
# Keyed by posture GROUP (team_eval.normalize_team_strategy collapses tank into rebuild for the finder).
PICK_WANT_BY_GROUP: dict[str, float] = {"rebuild": 2.0, "retool": 1.0, "contender": 0.0}
PICK_SENDER_GROUPS: frozenset[str] = frozenset({"contender"})


def pick_want(group: str, posture: str | None = None) -> float:
    """How much a team wants draft capital back. ``group`` is the finder's collapsed posture group; with coherence ON
    the finder also passes the full ``posture`` and tank scales the rebuild want by the pick-sale fit-term ratio
    (the same tank/rebuild distinction ``pick_sale_terms`` and the hub pick multiplier already draw)."""

    want = PICK_WANT_BY_GROUP.get(group, 0.0)
    if COHERENCE_ON and group == "rebuild" and posture in PICK_SALE_FIT_TERM:
        want *= PICK_SALE_FIT_TERM[posture] / PICK_SALE_FIT_TERM["rebuild"]
    return want


def pick_sale_terms(strategy: str, picks: int) -> tuple[int, int]:
    """(fit_priority term, my-side fit term) a posture charges for selling ``picks`` picks."""

    priority = PICK_SALE_PRIORITY_PER_PICK.get(strategy, PICK_SALE_PRIORITY_DEFAULT) * picks
    return priority, PICK_SALE_FIT_TERM.get(strategy, 0)


def lineup_weights(posture: str, default: str = "retool") -> tuple[float, float]:
    return POSTURE_WEIGHTS.get(posture, POSTURE_WEIGHTS[default])

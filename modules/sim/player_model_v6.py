"""Player outcome model for the Fantasy Sim GM game.

Pure and deterministic: every random draw comes from the ``numpy.random.Generator``
the caller passes in (derive it with :func:`profile_rng` / :func:`week_rng`, which
use ``SeedSequence`` keyed by stream, so results never depend on call order).
Imports only the stdlib and numpy.

Two public entry points (signatures are a contract with the game engine)::

    draw_season_profile(player, rng) -> SeasonProfile
    draw_week_points(player, profile, week, rng, scoring) -> WeekResult

A **season profile** is drawn once per player per game: the latent story of the
season (breakout / solid / bust / slump / injury-prone, a season-level multiplier
on the preseason projection, a volatility trait, the bye week, injury events with
their durations, mid-season role changes, a smooth hot/cold form curve) and the
17-week availability mask. **Weekly points** are then drawn from a position-aware
stat line (attempts, yards, touchdowns, receptions, ...) scored with the league's
own scoring, so fantasy points are skewed and TD-driven the way real ones are.

Every constant in the CALIBRATED section was fitted to five real NFL seasons
(2021-2025, Sleeper weekly box scores and week-1 preseason projections/ADP) by
``modules/sim/calibration`` (``fit.py`` produces them, ``backtest.py`` scores them
on held-out seasons). See ``docs/fantasy-sim-player-model.md`` for the tables and
the honest limitations. Nothing here reads a database or any real module.

The ``player`` mapping: ``player_id``, ``pos``, ``age``, ``years_exp``, ``team``,
``projection_mean_ppg`` (or ``projection_season_points``), ``projection_sd``
(weekly, optional), ``adp`` / ``value_rank`` (optional), ``is_rookie``,
``bye_week`` (optional; derived deterministically from ``team`` if absent), an
optional ``team_shock`` (a standard-normal z shared by a team's players in one
game, supplied by the engine to correlate teammates) and an optional
``season_environment`` (the game's :func:`draw_environment` multiplier, shared by
every player; default 1.0).
"""

from __future__ import annotations

import math
import zlib
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Mapping

import numpy as np

MODEL_VERSION = "player-model-6"
# player-model-6 (frozen predecessor: player_model_v5.py): the SINGLE-GAME tail. Season totals, weekly means and typical weeks are player-model-5's;
# only a stat line that no NFL game has ever produced is bounded (``STAT_CAPS``, ``cap_stats``). v5 let a WR post 9 touchdowns, 377 or 448 receiving
# yards or a 94-point game (coridian_: "62.3 points from one WR"); the real 2021-25 record is 55.6. See docs/audits/2026-11-sim-single-game-tail.md.
# player-model-5 adds only the in-season path tilt (PATH_TILT below); everything else is player-model-4.
# player-model-3 (frozen in player_model_v3.py) = player-model-2 + team-level role coupling (a multiplier on the hidden
# season mean). player-model-4 fixes the unbounded tails that composition made (a 0.6 ppg depth WR filling in for a
# star scored 72 in one game and was then "projected" 70):
#   * expected points are BOUNDED: a smooth ceiling per position on the season mean and on every weekly mean
#     (``SEASON_CEIL`` / ``WEEK_CEIL``, from the best real seasons and best 6-game stretches of 2021-25);
#   * a solid season's log-spread is capped and its normal draw truncated (the old spread grew without limit as the
#     projection fell, so a 1.2 ppg player had a 1-in-100 season of 40+ ppg);
#   * natural role changes cannot compound without limit (the cumulative multiplier is bounded to ``ROLE_CUM``);
#   * a team role is ADDITIVE points (a share of the vacated starter's points) on top of the player's own
#     (scaled) mean, never a multiplier on his hidden season story (``with_role``);
#   * the weekly game / efficiency / touchdown-luck draws are truncated at ``Z_TRUNC`` standard deviations.
TEAM_ROLES = True
ROLE_MODE = "additive"
# player-model-5 (frozen predecessor: player_model_v4.py): the in-season path. A player's expected weekly mean relative to his season
# mean used to fall from 1.00 in week 1 to about 0.92 by week 13 (role changes are biased down at the top of the pool) while the real
# panel is flat (``modules/sim/calibration/path_fit.py``). Weekly means are tilted by ``1 + PATH_TILT[tier] x (week - 8)``: centered on
# week 8, so season totals and every season-level calibration stay where they were.
PATH_TILT = {"elite": 0.005, "starter": 0.005, "flex": 0.001, "depth": 0.0}
PATH_CENTER = 8
PATH_POS_SCALE = {"QB": 0.3, "K": 0.0, "DEF": 0.0}  # quarterbacks rarely change roles (the model's own role_qb), kickers and defenses never do
SEASON_WEEKS = 17
# player-model-6: real-world per-game limits on each stat line component. Counts are hard limits (all-time NFL single-game records, rounded: 7 passing
# TDs, 6 rushing, 5 receiving; 23 catches); yardage saturates smoothly above a knee toward a cap just under the all-time record (rec 336, rush 296, pass
# 554), so normal games are untouched and the extreme of a heavy-tailed yards-per-unit draw is squeezed rather than clipped into a spike.
# Format: stat -> ("hard", limit) | ("soft", knee, cap).
STAT_CAPS: dict[str, dict[str, tuple]] = {
    "QB": {"pass_att": ("hard", 70), "pass_yd": ("soft", 420.0, 540.0), "pass_td": ("hard", 7), "pass_int": ("hard", 6),
           "rush_yd": ("soft", 110.0, 190.0), "rush_td": ("hard", 4)},
    "RB": {"rush_att": ("hard", 45), "rush_yd": ("soft", 160.0, 290.0), "rush_td": ("hard", 5),
           "rec_tgt": ("hard", 20), "rec": ("hard", 18), "rec_yd": ("soft", 130.0, 230.0), "rec_td": ("hard", 4)},
    "WR": {"rec_tgt": ("hard", 28), "rec": ("hard", 21), "rec_yd": ("soft", 190.0, 320.0), "rec_td": ("hard", 5),
           "rush_yd": ("soft", 60.0, 120.0), "rush_td": ("hard", 2)},
    "TE": {"rec_tgt": ("hard", 24), "rec": ("hard", 20), "rec_yd": ("soft", 150.0, 260.0), "rec_td": ("hard", 4)},
}
# player-model-6: smooth saturation of the PPR points of one game above a per-position knee, p' = K + C tanh((p - K) / C) (never above K + C).
# Component caps alone leave the sum of volume x yards x touchdowns about 1.4x too frequent at 40+ and 2x at 50+ against the real 2021-25 panel
# (docs/audits/2026-11-sim-single-game-tail.md); the knee sits above the 99th percentile so typical and boom weeks are untouched. The excess is
# taken out of the yardage of the line (scoring-agnostic: yards are scaled by one factor), never out of touchdown or reception counts.
TAIL_SQUEEZE = {"QB": (36.0, 22.0), "RB": (33.0, 24.0), "WR": (33.0, 24.0), "TE": (30.0, 20.0)}
_YARD_KEYS = ("pass_yd", "rush_yd", "rec_yd")
# Smooth ceilings (PPR points per game). Best real season PPG (8+ games) 2021-25: QB 26.7, RB 25.3, WR 25.8, TE 19.2, K 11.8;
# best 6-game stretch: QB 31.6, RB 30.7, WR 31.4, TE 24.1, K 16.5. A mean can approach but never pass these.
SEASON_CEIL = {"QB": 27.0, "RB": 25.5, "WR": 26.0, "TE": 19.5, "K": 12.0}
WEEK_CEIL = {"QB": 31.0, "RB": 30.0, "WR": 30.0, "TE": 23.0, "K": 15.5}
CEIL_SHARPNESS = 6.0
ROLE_CUM = (0.2, 3.5)   # bounds of the product of a player's natural role-change multipliers
SIGMA_MAX = 1.1         # cap on a solid season's log-sd
Z_SEASON = 2.3          # truncation of the solid-season normal draw
Z_TRUNC = 2.6           # truncation of the weekly game / efficiency normals
MIX_MAX = 4.0           # cap on the touchdown-luck gamma mixture
POSITIONS = ("QB", "RB", "WR", "TE", "K")
POS_INDEX = {p: i for i, p in enumerate(POSITIONS)}
ARCHETYPES = ("solid", "breakout", "bust", "slump", "injury_prone")

# --------------------------------------------------------------------------- seeding


def _key(text: Any) -> int:
    return zlib.crc32(str(text).encode("utf-8")) & 0x7FFFFFFF


def profile_rng(seed: int, player_id: Any) -> np.random.Generator:
    """Stream for a player's season profile: same (seed, player) -> same story."""

    seq = np.random.SeedSequence(entropy=int(seed), spawn_key=(0x50524F46, _key(player_id)))
    return np.random.Generator(np.random.PCG64(seq))


def week_rng(seed: int, player_id: Any, week: int) -> np.random.Generator:
    """Stream for one player-week. Independent of every other player/week."""

    seq = np.random.SeedSequence(entropy=int(seed), spawn_key=(0x57454B53, _key(player_id), int(week)))
    return np.random.Generator(np.random.PCG64(seq))


def team_week_shock(seed: int, team: Any, week: int) -> float:
    """Standard-normal game-script z shared by every player on ``team`` this week."""

    seq = np.random.SeedSequence(entropy=int(seed), spawn_key=(0x5445414D, _key(team), int(week)))
    return float(np.random.Generator(np.random.PCG64(seq)).standard_normal())


# League-wide scoring environment: some seasons run hot or cold for everybody (the median
# actual / projected PPG ratio moved 0.80 -> 0.97 across 2021-2025). One lognormal shock per
# game, shared by all players, supplied through ``player["season_environment"]``.
ENV_SD = 0.057


def draw_environment(rng: np.random.Generator, sd: float = ENV_SD) -> float:
    """Season-wide multiplier on every player's outcome (mean one). Draw once per game."""

    return float(math.exp(sd * float(rng.standard_normal()) - 0.5 * sd**2))


# --------------------------------------------------------------------------- CALIBRATED constants
# Re-fit with ``python -m modules.sim.calibration.fit`` and paste the output here.


@dataclass(frozen=True)
class SeasonParams:
    """Season-level story parameters (fitted on 2021-2023, validated on 2024-25)."""

    b_solid: float = 1.05        # solid-season mean as a share of the projection (RB/WR/TE)
    b_solid_qb: float = 0.8733     # QBs: the preseason number overshoots more
    b_solid_k: float = 0.93
    b_tier: float = 0.0784          # solid-season share moves with log-tier (stars regress differently)
    sigma0: float = 0.0708         # log-sd of a solid season at the reference tier
    sigma_tier: float = 0.6782     # extra log-sd per unit of log-tier below the reference
    qb_sig: float = 0.2314         # QB season-level spread relative to skill players
    pb0: float = -2.7566            # logit P(breakout)
    pb_rook: float = 2.6637
    pb_age: float = 0.5535         # per 4 years younger than 26
    pb_tier: float = 0.8        # per unit of log(proj / reference): deeper = more upside
    pu0: float = -1.5948            # logit P(bust)
    pu_rook: float = 1.5
    pu_age: float = 0.0158         # per 4 years older than 27
    pu_tier: float = 0.1004
    ps0: float = -2.0203            # logit P(slump); stars slump
    ps_tier: float = 1.2
    pi0: float = -2.2            # logit P(injury_prone)
    bust_mult: float = 0.7645
    bust_sd: float = 0.371
    gain_mean: float = 3.1523       # breakout: extra PPG on top of a solid season
    gain_shape: float = 2.5
    gain_tier: float = 0.2711       # breakout PPG gain scales with (projection / reference) ** gain_tier
    gain_rook: float = 1.1329
    qb_gain: float = 0.2328
    te_gain: float = 0.6098
    # --- v2 additions (fitted with the rest; role collapse, QB bust, rookie and TE spread) ---
    pc0: float = -4.1131           # logit P(role collapse): the season falls to a fraction of the projection
    pc_tier: float = 1.1977         # per unit of log(ref / proj) below the reference: deeper = likelier to wash out
    pc_rook: float = 0.076         # rookies wash out more often
    collapse_mult: float = 0.3282  # median share of the projection kept in a collapsed season
    collapse_sd: float = 0.2566
    pu_qb: float = -0.1733           # QB bust-probability logit offset
    qb_bust_mult: float = 0.7853  # QB bust depth (a bust QB is rarely a 25% drop)
    sig_rook: float = 0.0        # solid-season log-sd inflation for rookies
    te_sig: float = 1.0325          # solid-season log-sd multiplier for tight ends


@dataclass(frozen=True)
class InSeasonParams:
    """Hot/cold form, role changes, volatility traits, injuries (calibrated)."""

    form_phi: float = 0.35               # AR(1) of weekly form
    form_sd: float = 0.06                # log-sd of weekly form
    slump_len: tuple[int, int] = (3, 6)  # slump-archetype dip window, inclusive
    slump_depth: float = 0.30            # share of mean lost inside the window
    role_rate: float = 0.65              # expected role changes per season at the reference tier
    role_rate_deep: float = 0.5         # extra for deep (low-tier) players
    p_promotion: float = 0.35
    role_star: float = 1.0137               # role-change rate falls by exp(-role_star * max(0, log(proj/ref))): stars keep their jobs
    role_qb: float = 0.1                 # QBs rarely change roles mid-season (rate multiplier; 1-D fit to the real QB season SD)
    # Share of an injured starter's PPG that his same-team, same-position backups absorb (QB, RB, WR, TE, K), measured
    # on the real panel as backup uplift in weeks the starter missed over the starter's own PPG (2021-23: RB 0.36 / 0.22
    # for the first / second backup, WR 0.20 / 0.09, TE 0.08-0.13; QB has too few cases, prior only). The values are
    # scaled so the simulated panel reproduces those measured shares (``backtest.depth_cover_report``); spread 4 : 1.
    absorb: tuple[float, float, float, float, float] = (0.6, 0.33, 0.23, 0.10, 0.0)
    promo_mult: tuple[float, float] = (1.2, 1.9)
    demo_mult: tuple[float, float] = (0.45, 0.85)
    vol_sd: float = 0.12                 # log-sd of the per-player volatility trait
    rookie_ramp: float = 0.93            # rookies, weeks 1-4
    return_ramp: float = 0.91            # first game back from injury
    onset_game_mean: float = 0.72        # share of a normal game played when hurt
    hazard: float = 0.065                # injury onset hazard per available week (age/pos adjusted)
    hazard_pos: tuple[float, float, float, float, float] = (1.2, 1.05, 1.0, 0.95, 0.6)
    hazard_age: float = 0.30             # relative hazard slope per 5 years of age above 26
    prone_mult: float = 2.0
    rookie_hazard: float = 0.75          # rookies miss fewer games than vets (1.66 vs 2.55 per season in the real data)
    frailty_shape: float = 3.0           # per-player hazard multiplier ~ Gamma(shape, 1/shape): some players are just hurt more
    # P(weeks out = 1..8); the remainder is a long absence (9..17 weeks, often season-ending).
    out_pmf: tuple[float, ...] = (0.4029, 0.1638, 0.1067, 0.0924, 0.0543, 0.0352, 0.0238, 0.021)


SEASON = SeasonParams()
INSEASON = InSeasonParams()

# Reference points-per-game for "a starter" at each position (tier = log(proj / ref)).
REF_PPG = {"QB": 18.0, "RB": 11.0, "WR": 11.0, "TE": 8.0, "K": 8.0}
# Preseason projection ppg -> typical weekly coefficient of variation (position average).
BASE_CV = {"QB": 0.40, "RB": 0.56, "WR": 0.62, "TE": 0.65, "K": 0.57, "DEF": 0.55}

# Expected stat line at a PPR-points level rho: stat = max(floor, a + b * rho). Fitted by
# least squares across real player-seasons (``fit.py templates``). Sleeper stat keys.
TEMPLATE: dict[str, dict[str, tuple[float, float]]] = {
    "QB": {"pass_att": (27.177, 0.3292), "pass_cmp": (16.229, 0.3051), "pass_yd": (143.309, 5.4089), "pass_td": (-0.177, 0.0954), "pass_int": (0.764, -0.0029), "rush_att": (-1.974, 0.3462), "rush_yd": (-19.487, 2.1945), "rush_td": (-0.255, 0.0265), "fum_lost": (0.251, -0.0027)},
    "RB": {"rush_att": (0.494, 0.9102), "rush_yd": (-0.144, 4.1634), "rush_td": (-0.075, 0.0385), "rec_tgt": (0.491, 0.2176), "rec": (0.351, 0.1712), "rec_yd": (1.854, 1.3381), "rec_td": (-0.007, 0.0092), "fum_lost": (0.015, 0.0043)},
    "WR": {"rec_tgt": (0.687, 0.4908), "rec": (0.214, 0.339), "rec_yd": (0.229, 4.5758), "rec_td": (-0.041, 0.0312), "rush_att": (0.086, 0.0135), "rush_yd": (0.566, 0.0746), "rush_td": (-0.004, 0.0017), "fum_lost": (0.017, 0.0014)},
    "TE": {"rec_tgt": (0.199, 0.5332), "rec": (0.111, 0.375), "rec_yd": (-0.853, 4.3384), "rec_td": (-0.003, 0.0292), "fum_lost": (0.002, 0.0022)},
    "K": {"fgm": (0.01, 0.2138), "xpm": (1.126, 0.1303)},
}
STAT_FLOOR = 0.02

# Weekly dispersion (fitted to real within-player weekly variation).
WEEK = {
    #        game factor sd, volume NB cv, efficiency sd, yard-per-unit gamma shape, TD mixing cv
    "QB": dict(sg=0.261, vol_cv=0.053, eff=0.079, kappa=2.922, rush_kappa=0.28, td_cv=0.002, cmp_sd=0.04),
    "RB": dict(sg=0.234, vol_cv=0.009, eff=0.139, kappa=1.087, rush_kappa=0.386, td_cv=0.734, cmp_sd=0.207),
    "WR": dict(sg=0.145, vol_cv=0.087, eff=0.132, kappa=1.75, rush_kappa=0.8, td_cv=0.447, cmp_sd=0.13),
    "TE": dict(sg=0.168, vol_cv=0.032, eff=0.194, kappa=2.062, rush_kappa=0.8, td_cv=0.388, cmp_sd=0.15),
    "K": dict(sg=0.2, vol_cv=0.35, eff=0.1, kappa=1.0, rush_kappa=1.0, td_cv=0.5, cmp_sd=0.1),
}
STYLE_SD = {"QB": {"rush": 0.45, "yd": 0.06}, "RB": {"rec": 0.35, "yd": 0.07},
            "WR": {"rec": 0.15, "yd": 0.08}, "TE": {"rec": 0.15, "yd": 0.08}, "K": {}}

# Scoring.
PPR_WEIGHTS = {
    "pass_yd": 0.04, "pass_td": 4.0, "pass_int": -1.0, "rush_yd": 0.1, "rush_td": 6.0,
    "rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0, "fum_lost": -2.0,
}
_CORE_KEYS = ("rec", "rec_yd", "rec_td", "rush_yd", "rush_td", "pass_yd", "pass_td", "pass_int", "fum_lost")
_LINEAR_KEYS = ("pass_att", "pass_cmp", "rush_att", "rec_tgt")
_REC_BONUS = {"TE": "bonus_rec_te", "RB": "bonus_rec_rb", "WR": "bonus_rec_wr"}
_THRESHOLDS = (
    ("bonus_pass_yd_300", "pass_yd", 300.0), ("bonus_pass_yd_400", "pass_yd", 400.0),
    ("bonus_rush_yd_100", "rush_yd", 100.0), ("bonus_rush_yd_200", "rush_yd", 200.0),
    ("bonus_rec_yd_100", "rec_yd", 100.0), ("bonus_rec_yd_200", "rec_yd", 200.0),
)
K_FG_DEFAULT = 3.4
K_XP_DEFAULT = 1.0


# --------------------------------------------------------------------------- dataclasses


@dataclass(frozen=True)
class InjuryEvent:
    week: int            # the game in which the player gets hurt (1-17)
    weeks_out: int       # full games missed afterwards (0 = played through)
    kind: str            # "short" (1-2), "multi" (3-8) or "long" (9+, often season-ending)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RoleChange:
    week: int            # first week of the new role
    kind: str            # "promotion" | "demotion"
    multiplier: float    # applied to the weekly mean from ``week`` on
    end_week: int = 0    # last week of the role (0 = rest of the season); set for injury cover
    add: float = 0.0     # points per game added to the weekly mean (player-model-4 team roles; kind "team_role")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SeasonProfile:
    player_id: str
    pos: str
    archetype: str                       # one of ARCHETYPES
    tier: str                            # "elite" | "starter" | "flex" | "depth" (preseason projection tier)
    projection_mean_ppg: float
    season_multiplier: float             # season mean ppg / projection ppg (the hidden outcome)
    season_mean_ppg: float
    volatility: float                    # weekly dispersion multiplier (1.0 = typical for the position)
    bye_week: int
    games_available_mask: tuple[bool, ...]   # 17 entries; False = bye or out injured
    unavailable_reason: tuple[str, ...]      # "" | "bye" | "injury"
    injury_events: tuple[InjuryEvent, ...]
    role_changes: tuple[RoleChange, ...]
    form: tuple[float, ...]              # 17 weekly multiplicative form factors (hot/cold, slump window)
    slump_window: tuple[int, int] | None
    rookie: bool
    style: tuple[tuple[str, float], ...]     # persistent per-player style/efficiency factors
    model_version: str = MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["injury_events"] = [e.to_dict() for e in self.injury_events]
        d["role_changes"] = [e.to_dict() for e in self.role_changes]
        d["style"] = [list(x) for x in self.style]
        d["games_available_mask"] = list(self.games_available_mask)
        d["unavailable_reason"] = list(self.unavailable_reason)
        d["form"] = list(self.form)
        d["slump_window"] = list(self.slump_window) if self.slump_window else None
        return d

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "SeasonProfile":
        sw = raw.get("slump_window")
        return cls(
            player_id=str(raw["player_id"]), pos=str(raw["pos"]), archetype=str(raw["archetype"]),
            tier=str(raw["tier"]), projection_mean_ppg=float(raw["projection_mean_ppg"]),
            season_multiplier=float(raw["season_multiplier"]), season_mean_ppg=float(raw["season_mean_ppg"]),
            volatility=float(raw["volatility"]), bye_week=int(raw["bye_week"]),
            games_available_mask=tuple(bool(x) for x in raw["games_available_mask"]),
            unavailable_reason=tuple(str(x) for x in raw["unavailable_reason"]),
            injury_events=tuple(InjuryEvent(int(e["week"]), int(e["weeks_out"]), str(e["kind"])) for e in raw["injury_events"]),
            role_changes=tuple(RoleChange(int(e["week"]), str(e["kind"]), float(e["multiplier"]), int(e.get("end_week", 0)), float(e.get("add", 0.0))) for e in raw["role_changes"]),
            form=tuple(float(x) for x in raw["form"]), slump_window=(int(sw[0]), int(sw[1])) if sw else None,
            rookie=bool(raw["rookie"]), style=tuple((str(k), float(v)) for k, v in raw["style"]),
            model_version=str(raw.get("model_version", MODEL_VERSION)),
        )


@dataclass(frozen=True)
class WeekResult:
    points: float                        # fantasy points in the supplied scoring
    stats: dict[str, float]              # stat line (Sleeper keys); {} when inactive
    active: bool                         # played in this game
    status: str                          # "active" | "partial" | "bye" | "injured"
    injury_incurred: bool                # hurt in this game (see profile.injury_events for weeks_out)
    injury: InjuryEvent | None = None
    game_fraction: float = 1.0           # share of the game played (< 1 only when hurt mid-game)
    expected_points: float = 0.0         # the hidden true mean for this game (analysis/recaps only)
    components: dict[str, float] = field(default_factory=dict)  # per-bucket points, for box scores


# --------------------------------------------------------------------------- helpers


def soft_ceiling(m: float, ceil: float | None, k: float = CEIL_SHARPNESS) -> float:
    """Smooth saturation: ~m well below ``ceil``, 0.89 x ceil at the ceiling, never above it."""

    if ceil is None or m <= 0.0:
        return m
    return m / (1.0 + (m / ceil) ** k) ** (1.0 / k)


def _sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-x))


def _f(player: Mapping[str, Any], *keys: str, default: float | None = None) -> float | None:
    for k in keys:
        v = player.get(k)
        if v is None or isinstance(v, bool):
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(x):
            return x
    return default


def normalize_player(player: Mapping[str, Any]) -> dict[str, Any]:
    """Validated view of the input mapping. Raises ValueError on unusable input."""

    pid = player.get("player_id", player.get("pid"))
    if pid is None:
        raise ValueError("player_id is required")
    pos = str(player.get("pos", player.get("position", ""))).upper()
    if pos in ("DST", "DEF"):
        pos = "DEF"
    elif pos == "PK":
        pos = "K"
    if pos not in POSITIONS and pos != "DEF":
        raise ValueError(f"unsupported position {pos!r}")
    ppg = _f(player, "projection_mean_ppg", "mean", "ppg")
    if ppg is None:
        season = _f(player, "projection_season_points")
        if season is None:
            raise ValueError("projection_mean_ppg or projection_season_points is required")
        ppg = season / SEASON_WEEKS
    ppg = max(0.0, ppg)
    years = _f(player, "years_exp")
    rookie = player.get("is_rookie")
    rookie = bool(rookie) if rookie is not None else bool(years is not None and years <= 0)
    team = str(player.get("team") or player.get("nfl_team") or "")
    bye = int(_f(player, "bye_week", default=0) or 0)
    if "bye_week" in player and player["bye_week"] is not None and bye == 0:
        pass  # the caller says explicitly: no bye (unknown schedule); never invent one
    elif not 1 <= bye <= SEASON_WEEKS:
        bye = default_bye_week(team) if team else 0
    return dict(
        pid=str(pid), pos=pos, age=_f(player, "age", default=26.0), rookie=rookie, team=team,
        ppg=ppg, sd=_f(player, "projection_sd", "sd"), adp=_f(player, "adp", "value_rank", "rank"),
        bye=bye, shock=_f(player, "team_shock"), env=max(0.5, min(1.5, _f(player, "season_environment", default=1.0) or 1.0)),
    )


def default_bye_week(team: str) -> int:
    """Deterministic NFL-style bye (weeks 5-14) from the team code, used when the
    caller supplies no schedule. Teams hash into the same week every run."""

    return 5 + (_key(team) % 10)


def tier_label(pos: str, ppg: float) -> str:
    x = ppg / REF_PPG.get(pos, 10.0)
    if x >= 1.45:
        return "elite"
    if x >= 1.0:
        return "starter"
    if x >= 0.6:
        return "flex"
    return "depth"


def weights_for(scoring: Mapping[str, Any] | None, pos: str) -> dict[str, float]:
    """Per-stat weights. Absent keys in a real scoring blob pay 0 (Sleeper omits
    unscored stats); an empty/unknown blob means standard PPR."""

    raw: dict[str, float] = {}
    if scoring:
        for k, v in scoring.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
                continue
            raw[str(k)] = float(v)
    has_core = any(k in raw for k in _CORE_KEYS)
    w: dict[str, float] = {}
    if pos == "K":
        fg = [v for k, v in raw.items() if k.startswith("fgm_") and not k.startswith("fgmiss")]
        w["fgm"] = (sum(fg) / len(fg)) if fg else (raw.get("fgm", K_FG_DEFAULT))
        w["xpm"] = raw.get("xpm", K_XP_DEFAULT)
        return w
    base = {k: raw.get(k, 0.0) for k in _CORE_KEYS} if has_core else dict(PPR_WEIGHTS)
    w.update(base)
    for k in _LINEAR_KEYS:
        if raw.get(k):
            w[k] = raw[k]
    bonus = _REC_BONUS.get(pos)
    if bonus and raw.get(bonus):
        w["rec"] = w.get("rec", 0.0) + raw[bonus]
    return w


def score_stat_line(stats: Mapping[str, float], pos: str, scoring: Mapping[str, Any] | None = None) -> float:
    w = weights_for(scoring, pos)
    pts = sum(w.get(k, 0.0) * float(v) for k, v in stats.items())
    if scoring and pos != "K":
        for key, stat, threshold in _THRESHOLDS:
            bonus = scoring.get(key)
            if isinstance(bonus, (int, float)) and not isinstance(bonus, bool) and stats.get(stat, 0.0) >= threshold:
                pts += float(bonus)
    return pts


# --------------------------------------------------------------------------- season-level story (vectorised)


def season_level(
    pos_idx: np.ndarray, proj: np.ndarray, age: np.ndarray, rookie: np.ndarray, u: Mapping[str, np.ndarray],
    p: SeasonParams = SEASON,
) -> tuple[np.ndarray, np.ndarray]:
    """Archetype index (into ARCHETYPES) and season mean PPG for arrays of players.
    ``u`` carries pre-drawn randoms (``cat`` uniform, ``z1``/``z2`` normal, ``g`` gamma(1))
    so the same function serves a single draw and the fitter's common-random-number sweep."""

    ref = np.array([REF_PPG[q] for q in POSITIONS])[pos_idx]
    proj = np.maximum(proj, 0.3)
    tau = np.log(proj / ref)
    is_qb, is_te, is_k = pos_idx == 0, pos_idx == 3, pos_idx == 4
    young = np.clip((26.0 - age) / 4.0, -1.5, 1.5)
    old = np.clip((age - 27.0) / 4.0, -1.5, 1.5)
    rk = rookie.astype(float)
    pb = _sigmoid(p.pb0 + p.pb_rook * rk + p.pb_age * young + p.pb_tier * tau - 1.1 * is_qb)
    pu = _sigmoid(p.pu0 + p.pu_rook * rk + p.pu_age * old + p.pu_tier * tau + p.pu_qb * is_qb)
    ps = _sigmoid(p.ps0 + p.ps_tier * np.clip(tau, -1.0, 1.0)) * (1.0 - rk)
    pi = _sigmoid(np.full_like(proj, p.pi0))
    probs = np.stack([pb, pu, ps, pi])
    # Rescale if the four probabilities ever exceed 1 (never at fitted values).
    total = probs.sum(axis=0)
    probs = probs / np.maximum(total, 1.0)
    cum = np.cumsum(probs, axis=0)
    cat = u["cat"]
    # 0 solid 1 breakout 2 bust 3 slump 4 injury_prone
    arch = np.zeros(proj.shape, dtype=int)
    arch = np.where(cat < cum[3], 4, arch)
    arch = np.where(cat < cum[2], 3, arch)
    arch = np.where(cat < cum[1], 2, arch)
    arch = np.where(cat < cum[0], 1, arch)
    b = np.where(is_qb, p.b_solid_qb, np.where(is_k, p.b_solid_k, p.b_solid)) + p.b_tier * np.clip(tau, -1.0, 1.0)
    sig_mult = np.where(is_qb, p.qb_sig, np.where(is_te, p.te_sig, 1.0)) * (1.0 + p.sig_rook * rk)
    sigma = np.minimum((p.sigma0 + p.sigma_tier * np.maximum(0.0, -tau)) * sig_mult, SIGMA_MAX)
    solid = proj * b * np.exp(sigma * np.clip(u["z1"], -Z_SEASON, Z_SEASON) - 0.5 * sigma**2)
    gain_scale = np.where(is_qb, p.qb_gain, np.where(is_te, p.te_gain, 1.0)) * np.where(rookie, p.gain_rook, 1.0)
    gain = p.gain_mean * gain_scale * np.exp(p.gain_tier * np.clip(tau, -2.0, 1.0)) * u["g"] / p.gain_shape
    breakout = proj * b + gain
    bust_mult = np.where(is_qb, p.qb_bust_mult, p.bust_mult)
    bust = proj * bust_mult * np.exp(p.bust_sd * u["z2"] - 0.5 * p.bust_sd**2)
    mean = np.where(arch == 1, breakout, np.where(arch == 2, bust, solid))
    # Role collapse: a heavy left tail (a depth chart loss, a lost job) that a lognormal around the
    # projection cannot make. Only skill players with a real chance; a collapsed season is labelled a bust.
    if "c2" in u and p.pc0 > -20.0:
        pcol = _sigmoid(p.pc0 + p.pc_rook * rk + p.pc_tier * np.clip(-tau, -1.0, 2.0)) * (~is_qb) * (~is_k)
        hit = (u["c2"] < pcol) & (arch != 1)
        collapse = proj * b * p.collapse_mult * np.exp(p.collapse_sd * u["z2"] - 0.5 * p.collapse_sd**2)
        mean = np.where(hit, collapse, mean)
        arch = np.where(hit, 2, arch)
    return arch, np.maximum(mean, 0.05)


# --------------------------------------------------------------------------- season profile


def _draw_out_weeks(rng: np.random.Generator, ip: InSeasonParams) -> int:
    pmf = np.asarray(ip.out_pmf)
    r = rng.random()
    cum = np.cumsum(pmf)
    for i, c in enumerate(cum):
        if r < c:
            return i + 1
    return int(rng.integers(9, SEASON_WEEKS + 1))


def draw_season_profile(player: Mapping[str, Any], rng: np.random.Generator) -> SeasonProfile:
    return _draw_season_profile(player, rng, SEASON, INSEASON)


def _draw_season_profile(
    player: Mapping[str, Any], rng: np.random.Generator, sp: SeasonParams, ip: InSeasonParams,
) -> SeasonProfile:
    n = normalize_player(player)
    pos = n["pos"]
    gpos = pos if pos in POS_INDEX else "WR"
    proj = n["ppg"]
    pos_idx = np.array([POS_INDEX[gpos]])
    u = {"cat": rng.random(1), "z1": rng.standard_normal(1), "z2": rng.standard_normal(1),
         "g": rng.gamma(sp.gain_shape, 1.0, 1), "c2": rng.random(1)}
    arch_i, mean = season_level(pos_idx, np.array([proj]), np.array([n["age"]]), np.array([n["rookie"]]), u, sp)
    archetype = ARCHETYPES[int(arch_i[0])]
    mean_ppg = soft_ceiling(float(mean[0]) * n["env"], SEASON_CEIL.get(pos))
    if proj <= 0.0:
        mean_ppg = 0.0
    mult = mean_ppg / proj if proj > 0 else 1.0

    # Volatility trait: persistent boom/bust propensity, nudged toward the caller's projection_sd.
    vol = math.exp(ip.vol_sd * float(rng.standard_normal()) - 0.5 * ip.vol_sd**2)
    if n["sd"] and proj > 0:
        implied = (n["sd"] / proj) / BASE_CV.get(pos, 0.6)
        vol *= float(np.clip(implied, 0.7, 1.45)) ** 0.5
    vol = float(np.clip(vol, 0.6, 1.8))

    # Style: persistent efficiency / role-mix traits.
    style = []
    for key, sd in STYLE_SD.get(gpos, {}).items():
        style.append((key, math.exp(sd * float(rng.standard_normal()) - 0.5 * sd**2)))

    bye = n["bye"]
    mask = [True] * SEASON_WEEKS
    reason = [""] * SEASON_WEEKS
    if 1 <= bye <= SEASON_WEEKS:
        mask[bye - 1] = False
        reason[bye - 1] = "bye"

    # Injuries: hazard per available week, with age / position / proneness adjustments.
    hz = ip.hazard * ip.hazard_pos[POS_INDEX[gpos]] * (1.0 + ip.hazard_age * (n["age"] - 26.0) / 5.0)
    frailty = float(rng.gamma(ip.frailty_shape, 1.0 / ip.frailty_shape)) if ip.frailty_shape > 0 else 1.0
    hz = max(0.005, hz) * (ip.rookie_hazard if n["rookie"] else 1.0) * frailty * (ip.prone_mult if archetype == "injury_prone" else 1.0)
    events: list[InjuryEvent] = []
    week = 1
    while week <= SEASON_WEEKS:
        if not mask[week - 1] and reason[week - 1] == "bye":
            week += 1
            continue
        if rng.random() < hz:
            out = _draw_out_weeks(rng, ip)
            kind = "short" if out <= 2 else ("multi" if out <= 8 else "long")
            events.append(InjuryEvent(week=week, weeks_out=out, kind=kind))
            missed = 0
            w = week + 1
            while missed < out and w <= SEASON_WEEKS:
                if reason[w - 1] != "bye":
                    mask[w - 1] = False
                    reason[w - 1] = "injury"
                    missed += 1
                w += 1
            week = w
            continue
        week += 1

    # Role changes. Depth players change roles far more often and are likelier to gain
    # (a starter ahead of them gets hurt or benched); stars mostly lose touches or share them.
    tau = math.log(max(proj, 0.3) / REF_PPG[gpos])
    deep = max(0.0, min(1.0, -tau / 1.2))
    rate = (ip.role_rate + ip.role_rate_deep * deep) * math.exp(-ip.role_star * max(0.0, tau))
    if gpos == "QB":
        rate *= ip.role_qb
    changes: list[RoleChange] = []
    for _ in range(int(rng.poisson(rate))):
        wk = int(rng.integers(3, 15))
        promo = rng.random() < ip.p_promotion + 0.35 * deep
        lo, hi = ip.promo_mult if promo else ip.demo_mult
        m = float(rng.uniform(lo, hi))
        if promo:
            m = 1.0 + (m - 1.0) * (0.35 + 1.4 * deep)   # a star's bump is small, a backup's is large
        changes.append(RoleChange(week=wk, kind="promotion" if promo else "demotion", multiplier=round(m, 3)))
    changes.sort(key=lambda c: c.week)

    # Hot/cold form: smooth AR(1) in log space (mean-preserving), plus the slump dip for slump archetypes.
    z = rng.standard_normal(SEASON_WEEKS)
    form = []
    s = 0.0
    for w in range(SEASON_WEEKS):
        s = ip.form_phi * s + math.sqrt(1 - ip.form_phi**2) * float(z[w])
        form.append(math.exp(ip.form_sd * s - 0.5 * ip.form_sd**2))
    slump = None
    if archetype == "slump":
        length = int(rng.integers(ip.slump_len[0], ip.slump_len[1] + 1))
        start = int(rng.integers(3, SEASON_WEEKS - length + 2))
        slump = (start, start + length - 1)
        for w in range(slump[0], slump[1] + 1):
            form[w - 1] *= 1.0 - ip.slump_depth
    return SeasonProfile(
        player_id=n["pid"], pos=pos, archetype=archetype, tier=tier_label(gpos, proj),
        projection_mean_ppg=round(proj, 3), season_multiplier=round(mult, 4), season_mean_ppg=round(mean_ppg, 3),
        volatility=round(vol, 3), bye_week=bye, games_available_mask=tuple(mask), unavailable_reason=tuple(reason),
        injury_events=tuple(events), role_changes=tuple(changes), form=tuple(round(f, 4) for f in form),
        slump_window=slump, rookie=bool(n["rookie"]), style=tuple((k, round(v, 4)) for k, v in style),
    )


# --------------------------------------------------------------------------- depth-chart coupling


def apply_depth_coupling(
    players: Mapping[str, Mapping[str, Any]], profiles: Mapping[str, SeasonProfile],
    absorb: float | None = None, depth: int = 2, ip: InSeasonParams | None = None,
) -> dict[str, SeasonProfile]:
    """Couple starters' injuries to their same-team, same-position backups.

    The base model draws every player independently, so a starter's injury never helps his
    backup. Here, for each team and position the players are ranked by preseason projection;
    when a player misses games, the next ``depth`` players behind him absorb ``absorb`` of the
    lost points (split 4 : 1) as a temporary promotion
    (``RoleChange`` with an ``end_week``) covering exactly the games he is out. A backup's multiplier is capped at 6x. Pure and deterministic:
    it adds no random draws (the injury events it reads are already in the profiles) and returns
    new frozen profiles; profiles of players with no starter ahead of them are returned as is.
    The engine decides when to call it (it needs every rostered NFL teammate's profile).
    """

    table = (ip or INSEASON).absorb
    groups: dict[tuple[str, str], list[str]] = {}
    for pid, pl in players.items():
        if pid not in profiles:
            continue
        n = normalize_player(pl)
        if n["pos"] in ("QB", "RB", "WR", "TE") and n["team"]:
            groups.setdefault((n["team"], n["pos"]), []).append(pid)
    extra: dict[str, list[RoleChange]] = {}
    for (_team, _pos), pids in groups.items():
        a = float(table[POS_INDEX[_pos]]) if absorb is None else float(absorb)
        if a > 0.0:
            pids.sort(key=lambda q: (-profiles[q].projection_mean_ppg, str(q)))
            for i, starter in enumerate(pids):
                sp_ = profiles[starter]
                for ev in sp_.injury_events:
                    # the games he misses after the injury game (byes inside the window do not count)
                    out, w = [], ev.week + 1
                    while w <= SEASON_WEEKS and len(out) < ev.weeks_out:
                        if sp_.unavailable_reason[w - 1] == "injury":
                            out.append(w)
                        elif sp_.unavailable_reason[w - 1] != "bye":
                            break
                        w += 1
                    if not out:
                        continue
                    backups = pids[i + 1:i + 1 + depth]
                    wts = [0.25 ** k for k in range(len(backups))]
                    tot = sum(wts) or 1.0
                    for b, wgt in zip(backups, wts):
                        bp = profiles[b]
                        if bp.season_mean_ppg <= 0.0:
                            continue
                        lost = a * sp_.season_mean_ppg * (wgt / tot)
                        mult = min(6.0, 1.0 + lost / bp.season_mean_ppg)
                        if mult > 1.001:
                            extra.setdefault(b, []).append(RoleChange(week=out[0], kind="promotion", multiplier=round(mult, 3), end_week=out[-1]))
    out_profiles: dict[str, SeasonProfile] = {}
    for pid, prof in profiles.items():
        add = extra.get(pid)
        if not add:
            out_profiles[pid] = prof
            continue
        merged = tuple(sorted((*prof.role_changes, *add), key=lambda c: (c.week, c.end_week)))
        d = prof.to_dict()
        d["role_changes"] = [c.to_dict() for c in merged]
        out_profiles[pid] = SeasonProfile.from_dict(d)
    return out_profiles


# --------------------------------------------------------------------------- team-level role

ROLE_MULT_MAX = 20.0


def with_role(profile: SeasonProfile, week: int, scale: float, add: float) -> SeasonProfile:
    """The profile for one week with a team role: the player's own mean scaled by ``scale`` plus ``add`` points per
    game (a share of the starter he replaces). The additive part is NOT amplified by his hidden season story.
    Adds no random draw; ``scale == 1`` and ``add == 0`` returns the profile itself."""

    if abs(scale - 1.0) < 1e-9 and abs(add) < 1e-9:
        return profile
    rc = RoleChange(week=int(week), kind="team_role", multiplier=min(ROLE_MULT_MAX, max(0.0, float(scale))), end_week=int(week), add=max(0.0, float(add)))
    return replace(profile, role_changes=(*profile.role_changes, rc))


def with_role_multiplier(profile: SeasonProfile, week: int, mult: float) -> SeasonProfile:
    """The profile for one week with a team-role multiplier on that week's mean (a one-week ``RoleChange``).
    Adds no random draw. A multiplier of 1 returns the profile itself."""

    m = min(ROLE_MULT_MAX, max(0.0, float(mult)))
    if abs(m - 1.0) < 1e-9:
        return profile
    kind = "promotion" if m > 1.0 else "demotion"
    return replace(profile, role_changes=(*profile.role_changes, RoleChange(week=int(week), kind=kind, multiplier=m, end_week=int(week))))


# --------------------------------------------------------------------------- weekly mean


def expected_week_points(player: Mapping[str, Any], profile: SeasonProfile, week: int) -> float:
    """The true (hidden) mean for a healthy game this week: season mean x form x role x
    ramps. Reading it in the UI would leak the season's outcome; use the preseason
    projection there."""

    return _week_mean(profile, week, INSEASON)


def _week_mean(profile: SeasonProfile, week: int, ip: InSeasonParams) -> float:
    m = profile.season_mean_ppg * profile.form[week - 1]
    cum = 1.0
    team_scale, team_add = 1.0, 0.0
    for rc in profile.role_changes:
        if week >= rc.week and (not rc.end_week or week <= rc.end_week):
            if rc.kind == "team_role":
                team_scale *= rc.multiplier
                team_add += rc.add
            else:
                cum *= rc.multiplier
    # Natural role changes (promotions, demotions, injury cover) compound, but a role is a share of a team's volume:
    # bound the product smoothly in log space so six promotions cannot make a 20x player.
    lo, hi = math.log(ROLE_CUM[0]), math.log(ROLE_CUM[1])
    lc = math.log(cum)
    cum = math.exp(hi * math.tanh(lc / hi)) if lc > 0 else math.exp(lo * math.tanh(lc / lo))
    m *= cum
    m *= 1.0 + PATH_TILT.get(profile.tier, 0.0) * PATH_POS_SCALE.get(profile.pos, 1.0) * (week - PATH_CENTER)
    if profile.rookie and week <= 4:
        m *= ip.rookie_ramp
    if week >= 2:
        # first game back after missing time
        prev_mask = profile.games_available_mask[week - 2]
        if not prev_mask and profile.unavailable_reason[week - 2] == "injury" and profile.games_available_mask[week - 1]:
            m *= ip.return_ramp
    m = m * team_scale + team_add
    return soft_ceiling(m, WEEK_CEIL.get(profile.pos))


# --------------------------------------------------------------------------- stat lines


def _expected_stats(pos: str, rho: float, style: Mapping[str, float]) -> dict[str, float]:
    out = {}
    for k, (a, b) in TEMPLATE[pos].items():
        out[k] = max(STAT_FLOOR, a + b * rho)
    if pos == "QB":
        s = style.get("rush", 1.0)
        for k in ("rush_att", "rush_yd", "rush_td"):
            out[k] *= s
    elif pos == "RB":
        s = style.get("rec", 1.0)
        for k in ("rec_tgt", "rec", "rec_yd", "rec_td"):
            out[k] *= s
    y = style.get("yd", 1.0)
    for k in ("pass_yd", "rush_yd", "rec_yd"):
        if k in out:
            out[k] *= y
    return out


# Weekly SD / mean of each yardage stat, used only to price yardage bonuses in the solve.
_YD_CV = {"pass_yd": 0.30, "rush_yd": 0.65, "rec_yd": 0.75}


def _expected_bonus(e: Mapping[str, float], scoring: Mapping[str, Any] | None) -> float:
    """Expected threshold-bonus points of a stat line with mean ``e`` (normal approximation)."""

    if not scoring:
        return 0.0
    total = 0.0
    for key, stat, threshold in _THRESHOLDS:
        bonus = scoring.get(key)
        if stat in e and isinstance(bonus, (int, float)) and not isinstance(bonus, bool) and bonus:
            m = e[stat]
            sd = max(1e-6, _YD_CV[stat] * m)
            total += float(bonus) * 0.5 * math.erfc((threshold - m) / (sd * math.sqrt(2.0)))
    return total


def _solve_rho(
    pos: str, target: float, style: Mapping[str, float], w: Mapping[str, float],
    scoring: Mapping[str, Any] | None = None,
) -> float:
    """PPR-points level whose expected stat line scores ``target`` in the league's scoring
    (including the expected value of yardage bonuses)."""

    def pts(rho: float) -> float:
        e = _expected_stats(pos, rho, style)
        return sum(w.get(k, 0.0) * v for k, v in e.items()) + _expected_bonus(e, scoring)

    lo, hi = 0.0, 80.0
    if pts(lo) >= target:
        return lo
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if pts(mid) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _nb(rng: np.random.Generator, mean: float, cv: float) -> int:
    """Negative-binomial count with the given mean and extra-Poisson cv."""

    if mean <= 0:
        return 0
    lam = mean if cv <= 0 else rng.gamma(1.0 / cv**2, mean * cv**2)
    return int(rng.poisson(lam))


def _gfac(g: float, gamma: float, sg: float) -> float:
    """Mean-one power of the lognormal game factor (g = sg*z already applied)."""

    return math.exp(gamma * g - 0.5 * (gamma * sg) ** 2)


def _units_yards(rng: np.random.Generator, n: int, ypu: float, kappa: float, eff: float) -> float:
    if n <= 0 or ypu <= 0:
        return 0.0
    return float(rng.gamma(n * kappa, ypu * eff / kappa))


def _mix(rng: np.random.Generator, cv: float) -> float:
    return min(MIX_MAX, float(rng.gamma(1.0 / cv**2, cv**2))) if cv > 0 else 1.0


def _draw_stat_line(
    pos: str, rho: float, style: Mapping[str, float], vol: float, rng: np.random.Generator, z_team: float | None,
) -> dict[str, float]:
    wk = WEEK[pos]
    e = _expected_stats(pos, rho, style)
    sg = wk["sg"] * vol
    own = float(np.clip(rng.standard_normal(), -Z_TRUNC, Z_TRUNC))
    z = own if z_team is None else math.sqrt(0.85) * own + math.sqrt(0.15) * z_team
    g = sg * z
    se = wk["eff"] * vol
    eff = math.exp(se * float(np.clip(rng.standard_normal(), -Z_TRUNC, Z_TRUNC)) - 0.5 * se**2)
    cvv = wk["vol_cv"] * vol
    if pos == "QB":
        att = _nb(rng, e["pass_att"] * _gfac(g, 0.35, sg), cvv * 0.7)
        p = min(0.9, max(0.35, e["pass_cmp"] / e["pass_att"] * math.exp(wk["cmp_sd"] * float(rng.standard_normal()))))
        cmp_ = int(rng.binomial(att, p)) if att > 0 else 0
        yd = _units_yards(rng, cmp_, e["pass_yd"] / e["pass_cmp"], wk["kappa"], eff)
        ratio = att / max(e["pass_att"], 1e-9)
        td = int(rng.poisson(e["pass_td"] * ratio * eff * _mix(rng, wk["td_cv"] * vol)))
        ints = int(rng.poisson(e["pass_int"] * ratio * _mix(rng, 0.4)))
        ra = _nb(rng, e["rush_att"] * _gfac(g, -0.2, sg), cvv)
        ry = _units_yards(rng, ra, e["rush_yd"] / e["rush_att"], wk["rush_kappa"], 1.0 + (eff - 1.0) * 0.6)
        rtd = int(rng.poisson(e["rush_td"] * ra / max(e["rush_att"], 1e-9) * _mix(rng, 0.6)))
        fl = int(rng.poisson(e["fum_lost"]))
        return {"pass_att": att, "pass_cmp": cmp_, "pass_yd": round(yd), "pass_td": td, "pass_int": ints,
                "rush_att": ra, "rush_yd": round(ry), "rush_td": rtd, "fum_lost": fl}
    if pos == "K":
        fg = _nb(rng, e["fgm"] * _gfac(g, 0.3, sg), cvv)
        xp = _nb(rng, e["xpm"] * _gfac(g, 0.5, sg), cvv)
        return {"fgm": fg, "xpm": xp}
    # RB / WR / TE
    out: dict[str, float] = {}
    if "rush_att" in e:
        ra = _nb(rng, e["rush_att"] * _gfac(g, 0.6 if pos == "RB" else 0.0, sg), cvv)
        ypc = e["rush_yd"] / e["rush_att"]
        ry = _units_yards(rng, ra, ypc, wk["rush_kappa"], eff)
        rtd = int(rng.poisson(e["rush_td"] * ra / max(e["rush_att"], 1e-9) * eff * _mix(rng, wk["td_cv"] * vol)))
        out.update(rush_att=ra, rush_yd=round(ry), rush_td=rtd)
    tgt = _nb(rng, e["rec_tgt"] * _gfac(g, 0.8 if pos != "RB" else 0.3, sg), cvv)
    p = min(0.97, max(0.2, e["rec"] / e["rec_tgt"] * math.exp(wk["cmp_sd"] * float(rng.standard_normal()))))
    rec = int(rng.binomial(tgt, p)) if tgt > 0 else 0
    ry = _units_yards(rng, rec, e["rec_yd"] / e["rec"], wk["kappa"], eff)
    td = int(rng.poisson(e["rec_td"] * tgt / max(e["rec_tgt"], 1e-9) * eff * _mix(rng, wk["td_cv"] * vol)))
    fl = int(rng.poisson(e["fum_lost"]))
    out.update(rec_tgt=tgt, rec=rec, rec_yd=round(ry), rec_td=td, fum_lost=fl)
    return out


def _soft_cap(y: float, knee: float, cap: float) -> float:
    if y <= knee:
        return y
    span = cap - knee
    return knee + span * math.tanh((y - knee) / span)


def cap_stats(pos: str, stats: dict[str, float]) -> dict[str, float]:
    """Bound every component of a drawn stat line by what an NFL game can produce (``STAT_CAPS``)."""

    for k, rule in STAT_CAPS.get(pos, {}).items():
        v = stats.get(k)
        if v is None:
            continue
        if rule[0] == "hard":
            stats[k] = min(v, rule[1])
        elif v > rule[1]:
            stats[k] = round(_soft_cap(v, rule[1], rule[2]))
    return stats


def squeeze_tail(pos: str, stats: dict[str, float]) -> dict[str, float]:
    """Saturate the PPR points of a stat line above ``TAIL_SQUEEZE[pos]`` by shrinking its yardage (see the constant)."""

    kc = TAIL_SQUEEZE.get(pos)
    if kc is None:
        return stats
    knee, span = kc
    ppr = sum(PPR_WEIGHTS.get(k, 0.0) * v for k, v in stats.items())
    if ppr <= knee:
        return stats
    excess = ppr - (knee + span * math.tanh((ppr - knee) / span))
    ypts = sum(PPR_WEIGHTS.get(k, 0.0) * stats.get(k, 0.0) for k in _YARD_KEYS)
    if ypts <= 0.0 or excess <= 0.0:
        return stats
    q = max(0.0, 1.0 - excess / ypts)
    for k in _YARD_KEYS:
        if k in stats:
            stats[k] = round(stats[k] * q)
    return stats


def _components(stats: Mapping[str, float], pos: str, scoring: Mapping[str, Any] | None) -> dict[str, float]:
    w = weights_for(scoring, pos)
    comp = {"passing": 0.0, "rushing": 0.0, "receiving": 0.0, "kicking": 0.0, "turnovers": 0.0}
    for k, v in stats.items():
        pts = w.get(k, 0.0) * v
        if k.startswith("pass_") and k != "pass_int":
            comp["passing"] += pts
        elif k == "pass_int" or k == "fum_lost":
            comp["turnovers"] += pts
        elif k.startswith("rush_"):
            comp["rushing"] += pts
        elif k.startswith("rec"):
            comp["receiving"] += pts
        else:
            comp["kicking"] += pts
    return {k: round(v, 2) for k, v in comp.items() if v}


def draw_week_points(
    player: Mapping[str, Any], profile: SeasonProfile, week: int, rng: np.random.Generator,
    scoring: Mapping[str, Any],
) -> WeekResult:
    return _draw_week_points(player, profile, week, rng, scoring, INSEASON)


def _draw_week_points(
    player: Mapping[str, Any], profile: SeasonProfile, week: int, rng: np.random.Generator,
    scoring: Mapping[str, Any] | None, ip: InSeasonParams,
) -> WeekResult:
    if not 1 <= int(week) <= SEASON_WEEKS:
        raise ValueError(f"week must be 1..{SEASON_WEEKS}")
    week = int(week)
    if not profile.games_available_mask[week - 1]:
        reason = profile.unavailable_reason[week - 1]
        return WeekResult(points=0.0, stats={}, active=False, status="bye" if reason == "bye" else "injured",
                          injury_incurred=False)
    pos = profile.pos
    gpos = pos if pos in TEMPLATE else None
    event = next((e for e in profile.injury_events if e.week == week), None)
    mean = _week_mean(profile, week, ip)
    fraction = 1.0
    if event is not None:
        fraction = float(np.clip(rng.beta(3.6, 1.4) * ip.onset_game_mean / 0.72, 0.1, 1.0))
    z_team = _f(player, "team_shock")
    style = dict(profile.style)
    if gpos is None:
        # Team defenses and anything else we have no stat template for: a right-skewed points draw.
        cv = BASE_CV["DEF"] * profile.volatility
        pts = float(rng.gamma(1.0 / cv**2, mean * cv**2)) * fraction
        pts = round(pts, 2)
        return WeekResult(points=pts, stats={"pts": pts}, active=True, status="partial" if event else "active",
                          injury_incurred=event is not None, injury=event, game_fraction=fraction,
                          expected_points=round(mean, 2))
    w = weights_for(scoring, gpos)
    rho = _solve_rho(gpos, mean * fraction, style, w, scoring)
    stats = squeeze_tail(gpos, cap_stats(gpos, _draw_stat_line(gpos, rho, style, profile.volatility, rng, z_team)))
    pts = score_stat_line(stats, gpos, scoring)
    return WeekResult(
        points=round(pts, 2), stats={k: float(v) for k, v in stats.items()}, active=True,
        status="partial" if event else "active", injury_incurred=event is not None, injury=event,
        game_fraction=round(fraction, 3), expected_points=round(mean * fraction, 3),
        components=_components(stats, gpos, scoring),
    )


# --------------------------------------------------------------------------- convenience


def simulate_season(
    player: Mapping[str, Any], seed: int, scoring: Mapping[str, Any] | None = None,
) -> tuple[SeasonProfile, list[WeekResult]]:
    """Whole season for one player with the standard streams (for tools and tests)."""

    prof = draw_season_profile(player, profile_rng(seed, player.get("player_id", player.get("pid"))))
    pid = player.get("player_id", player.get("pid"))
    return prof, [draw_week_points(player, prof, w, week_rng(seed, pid, w), scoring or {}) for w in range(1, SEASON_WEEKS + 1)]


__all__ = [
    "ARCHETYPES", "ENV_SD", "InjuryEvent", "InSeasonParams", "MODEL_VERSION", "RoleChange", "SEASON_WEEKS", "SeasonParams",
    "SeasonProfile", "WeekResult", "apply_depth_coupling", "default_bye_week", "draw_season_profile", "draw_week_points",
    "draw_environment", "expected_week_points", "normalize_player", "profile_rng", "score_stat_line", "simulate_season",
    "team_week_shock", "week_rng", "weights_for", "TEAM_ROLES", "ROLE_MODE", "with_role", "with_role_multiplier", "cap_stats", "squeeze_tail", "TAIL_SQUEEZE", "STAT_CAPS", "soft_ceiling", "SEASON_CEIL", "WEEK_CEIL",
]

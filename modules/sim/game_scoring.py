"""The one door between the GM game and the per-player weekly scoring model.

The game never calls a player model directly. It asks this adapter for a
``ScoringModel`` and uses only the two functions every model provides:

    profile(player, rng)                           -> opaque season profile
    week(player, profile, week, rng, scoring)      -> PlayerWeek

``modules/sim/player_model.py`` (``draw_season_profile`` / ``draw_week_points``)
is the real model. Until that file exists, ``FallbackModel`` below runs instead:
a clearly labelled, deliberately simple projection mean/sd draw, so the game and
its tests work end to end. To swap models, change nothing but this file.

Replay safety: every game stores the ``model_id`` it was created with
(``GameSnapshot.scoring_model``) and asks for exactly that model forever, so
shipping a better model never changes an existing save's results.
"""

from __future__ import annotations

import dataclasses
import importlib
from dataclasses import dataclass, field
from typing import Any, Mapping

FALLBACK_ID = "fallback-meansd-1"
_REAL_MODULE = "modules.sim.player_model"
# Every player-model generation a saved game can name. v1 is a frozen copy (never edit it): games created
# under it keep their exact weekly points, results and grades. The newest entry is what new games use.
_MODEL_MODULES = {
    "player-model-1": "modules.sim.player_model_v1",
    "player-model-2": "modules.sim.player_model_v2",  # frozen copy: games created under it never change
    "player-model-3": "modules.sim.player_model_v3",  # frozen copy: + team-level role coupling (multiplicative)
    "player-model-4": "modules.sim.player_model_v4",  # frozen copy: bounded tails, additive team roles, robust projections
    "player-model-5": "modules.sim.player_model_v5",  # frozen copy: + flat in-season path (PATH_TILT)
    "player-model-6": "modules.sim.player_model",  # + bounded single-game tail (STAT_CAPS, TAIL_SQUEEZE)
}


@dataclass(frozen=True)
class PlayerWeek:
    """One player's week as the game consumes it."""

    points: float
    stats: Mapping[str, float] = field(default_factory=dict)
    active: bool = True  # False: inactive / did not play (scores 0)
    newly_injured: bool = False  # got hurt this week
    # Calendar weeks he is then out (bye weeks inside the window included), as decided
    # by the player model (0 = hurt but misses nothing, e.g. in the last week). None = the model
    # gives no duration (FallbackModel only).
    out_weeks: int | None = None


class ScoringModel:
    model_id = ""

    def profile(self, player: Mapping[str, Any], rng: Any) -> Any:  # pragma: no cover - interface
        raise NotImplementedError

    # True when the engine should resolve team-level roles and pass ``role_mult`` (player-model-3 and later).
    team_roles = False
    # "mult": the engine passes a float multiplier (player-model-3); "additive": a (scale, points) pair (player-model-4+).
    role_mode = "mult"

    def week(
        self, player: Mapping[str, Any], profile: Any, week: int, rng: Any, scoring: Mapping[str, float],
        role_mult: Any = None,
    ) -> PlayerWeek:  # pragma: no cover - interface
        raise NotImplementedError


# ------------------------------------------------------------------ fallback

_FALLBACK_INJURY_RATE = {"QB": 0.02, "RB": 0.06, "WR": 0.045, "TE": 0.04, "K": 0.005, "DEF": 0.0}


@dataclass(frozen=True)
class _FallbackProfile:
    talent: float  # season-long multiplier on the projection


class FallbackModel(ScoringModel):
    """FALLBACK, NOT THE REAL PLAYER MODEL. Season talent multiplier around 1,
    then weekly points ~ Normal(mean * talent, sd) floored at 0 with a flat
    per-position injury rate. No stat lines, no usage/role/matchup effects."""

    model_id = FALLBACK_ID

    def profile(self, player, rng):
        talent = 1.0 + 0.10 * float(rng.standard_normal())
        return _FallbackProfile(talent=min(1.3, max(0.75, talent)))

    def week(self, player, profile, week, rng, scoring, role_mult=None):
        mean = float(player.get("mean") or 0.0) * profile.talent
        sd = float(player.get("sd") or 0.0)
        z = float(rng.standard_normal())
        hurt = float(rng.random()) < _FALLBACK_INJURY_RATE.get(str(player.get("pos")), 0.03)
        return PlayerWeek(points=max(0.0, mean + sd * z), stats={}, active=True, newly_injured=hurt)


# ---------------------------------------------------------------- real model


def _to_stats(raw: Any) -> dict[str, float]:
    if raw is None:
        return {}
    if dataclasses.is_dataclass(raw) and not isinstance(raw, type):
        raw = dataclasses.asdict(raw)
    if isinstance(raw, Mapping):
        return {str(k): float(v) for k, v in raw.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    return {}


def _pick(result: Any, names: tuple[str, ...], default: Any) -> Any:
    for name in names:
        if isinstance(result, Mapping):
            if name in result:
                return result[name]
        elif hasattr(result, name):
            return getattr(result, name)
    return default


def calendar_weeks_out(profile: Any, week: int) -> int:
    """Calendar weeks a player hurt in ``week`` stays out, read from the model's own
    availability mask: the run of unavailable weeks after ``week`` that contains
    injury weeks (a bye inside the run counts, because the game counts calendar weeks)."""

    mask = list(profile.games_available_mask)
    reason = list(profile.unavailable_reason)
    last = 0
    w = week + 1
    while w <= len(mask) and not mask[w - 1]:
        if reason[w - 1] == "injury":
            last = w - week
        w += 1
    return last




class PlayerModelAdapter(ScoringModel):
    """Wraps ``modules.sim.player_model``. The model is the single source of truth for
    injuries: ``injury_incurred`` -> ``newly_injured`` and the duration comes from the
    profile's availability mask (``out_weeks``)."""

    def __init__(self, module: Any) -> None:
        self._m = module
        self.model_id = f"player_model-{getattr(module, 'MODEL_VERSION', '1')}"
        self.team_roles = bool(getattr(module, "TEAM_ROLES", False))
        self.role_mode = str(getattr(module, "ROLE_MODE", "mult"))

    def profile(self, player, rng):
        return self._m.draw_season_profile(player, rng)

    def week(self, player, profile, week, rng, scoring, role_mult=None):
        if role_mult is not None and self.team_roles:
            if self.role_mode == "additive":
                profile = self._m.with_role(profile, week, role_mult[0], role_mult[1])
            else:
                profile = self._m.with_role_multiplier(profile, week, role_mult)
        result = self._m.draw_week_points(player, profile, week, rng, scoring)
        hurt = bool(result.injury_incurred)
        return PlayerWeek(
            points=float(result.points), stats=_to_stats(result.stats), active=bool(result.active),
            newly_injured=hurt, out_weeks=calendar_weeks_out(profile, week) if hurt else 0,
        )


def _load_module(version: str) -> ScoringModel | None:
    name = _MODEL_MODULES.get(version)
    if name is None:
        return None
    try:
        module = importlib.import_module(name)
    except ImportError:
        return None
    if not (hasattr(module, "draw_season_profile") and hasattr(module, "draw_week_points")):
        return None
    return PlayerModelAdapter(module)


def _load_real() -> ScoringModel | None:
    """The newest player model (what new games use)."""

    return _load_module(list(_MODEL_MODULES)[-1])


_FALLBACK = FallbackModel()


def default_model() -> ScoringModel:
    """The model new games use: the real player model if it exists, else fallback."""

    return _load_real() or _FALLBACK


def resolve_model(model_id: str | None) -> tuple[ScoringModel, str | None]:
    """The model a saved game was created with, and a note when it could not be honoured.
    Known ids route to their own frozen module; the fallback id (or none) to FallbackModel;
    an unknown id falls back to the current default with a note."""

    if not model_id or model_id == FALLBACK_ID:
        return _FALLBACK, None
    prefix = "player_model-"
    if model_id.startswith(prefix):
        exact = _load_module(model_id[len(prefix):])
        if exact is not None and exact.model_id == model_id:
            return exact, None
    current = default_model()
    return current, f"scoring model {model_id!r} is unavailable; using {current.model_id!r}, results may differ"


def team_roles_enabled(model_id: str | None) -> bool:
    """Does a game created with ``model_id`` resolve team-level roles (one fill-in per vacated starter)?
    Only player-model-3 and later: older saves keep exactly their old behaviour."""

    return bool(getattr(resolve_model(model_id)[0], "team_roles", False))


def team_roles_mode(model_id: str | None) -> str:
    """"" (no team roles), "mult" (player-model-3) or "additive" (player-model-4+)."""

    m = resolve_model(model_id)[0]
    return str(getattr(m, "role_mode", "mult")) if getattr(m, "team_roles", False) else ""


def get_model(model_id: str | None) -> ScoringModel:
    """The model a saved game was created with (see ``resolve_model`` for the unknown-id note)."""

    return resolve_model(model_id)[0]


__all__ = ["resolve_model", "PlayerWeek", "ScoringModel", "FallbackModel", "PlayerModelAdapter", "default_model", "get_model", "team_roles_enabled", "team_roles_mode", "FALLBACK_ID"]

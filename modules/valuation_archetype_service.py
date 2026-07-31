"""League-scoped active valuation-archetype resolution."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Callable, Mapping, TypeVar

from modules.valuation_archetypes import (
    ARCHETYPE_REGISTRY,
    DEFAULT_VALUATION_ARCHETYPE_ID,
    ValuationArchetype,
    ValuationArchetypeRegistry,
    resolve_valuation_engine,
)


PROFILE_FIELD = "valuation_archetype_id"
SESSION_FIELD = "valuation_archetypes_by_league"
T = TypeVar("T")


def resolve_active_archetype(
    *,
    league_id: object,
    profile: MutableMapping[str, object] | None = None,
    session_state: MutableMapping[str, object] | None = None,
    registry: ValuationArchetypeRegistry = ARCHETYPE_REGISTRY,
) -> ValuationArchetype:
    """Resolve one deterministic league value, migrating missing/invalid values."""

    league_key = str(league_id or "").strip()
    profile_value = profile.get(PROFILE_FIELD) if profile is not None else None
    session_values = (
        session_state.get(SESSION_FIELD, {}) if session_state is not None else {}
    )
    session_value = (
        session_values.get(league_key)
        if league_key and isinstance(session_values, dict)
        else None
    )
    archetype = registry.resolve(profile_value or session_value)

    if profile is not None:
        profile[PROFILE_FIELD] = archetype.id
    if session_state is not None and league_key:
        updated = dict(session_values) if isinstance(session_values, dict) else {}
        updated[league_key] = archetype.id
        session_state[SESSION_FIELD] = updated
    return archetype


def set_active_archetype(
    archetype_id: object,
    *,
    league_id: object,
    profile: MutableMapping[str, object] | None = None,
    session_state: MutableMapping[str, object] | None = None,
    registry: ValuationArchetypeRegistry = ARCHETYPE_REGISTRY,
) -> ValuationArchetype:
    """Validate and store a future selection without owning persistence I/O."""

    archetype = registry.require(archetype_id)
    if not archetype.active:
        raise ValueError(f"Inactive valuation archetype: {archetype.id}")
    if profile is not None:
        profile[PROFILE_FIELD] = archetype.id
    if session_state is not None:
        league_key = str(league_id or "").strip()
        if league_key:
            values = session_state.get(SESSION_FIELD, {})
            updated = dict(values) if isinstance(values, dict) else {}
            updated[league_key] = archetype.id
            session_state[SESSION_FIELD] = updated
    return archetype


def default_profile_value() -> str:
    return DEFAULT_VALUATION_ARCHETYPE_ID


def apply_active_valuation(
    archetype: ValuationArchetype,
    *engine_args: object,
    engines: Mapping[str, Callable[..., T]],
    **engine_kwargs: object,
) -> T:
    """Delegate unchanged inputs to the engine registered for this invocation."""

    engine = resolve_valuation_engine(archetype, engines=engines)
    return engine(*engine_args, **engine_kwargs)

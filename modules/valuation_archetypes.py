"""Canonical valuation-archetype metadata and engine resolution."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Mapping, TypeVar


BALANCED_DYNASTY_ID = "balanced_dynasty"
DEFAULT_VALUATION_ARCHETYPE_ID = BALANCED_DYNASTY_ID

T = TypeVar("T")


@dataclass(frozen=True)
class ValuationArchetype:
    id: str
    display_name: str
    description: str
    philosophy: str
    intended_league_types: tuple[str, ...]
    badge: str
    maturity: str
    active: bool


BALANCED_DYNASTY = ValuationArchetype(
    id=BALANCED_DYNASTY_ID,
    display_name="Balanced Dynasty",
    description="The current DynastyGM valuation approach for long-term roster decisions.",
    philosophy=(
        "Balances present production, age, positional value, market context, and "
        "long-term dynasty utility without applying an additional strategic tilt."
    ),
    intended_league_types=("Dynasty",),
    badge="Balanced",
    maturity="stable",
    active=True,
)


class ValuationArchetypeRegistry:
    """Validated, immutable registry for production archetype metadata."""

    def __init__(self, archetypes: tuple[ValuationArchetype, ...]) -> None:
        by_id: dict[str, ValuationArchetype] = {}
        for archetype in archetypes:
            if not archetype.id or archetype.id != archetype.id.strip().casefold():
                raise ValueError("Archetype ids must be non-empty normalized strings.")
            if archetype.id in by_id:
                raise ValueError(f"Duplicate valuation archetype id: {archetype.id}")
            if archetype.maturity not in {"stable", "experimental"}:
                raise ValueError(f"Unsupported archetype maturity: {archetype.maturity}")
            by_id[archetype.id] = archetype
        if DEFAULT_VALUATION_ARCHETYPE_ID not in by_id:
            raise ValueError("The default valuation archetype must be registered.")
        self._by_id: Mapping[str, ValuationArchetype] = MappingProxyType(by_id)

    def get(self, archetype_id: object) -> ValuationArchetype | None:
        return self._by_id.get(str(archetype_id or "").strip().casefold())

    def require(self, archetype_id: object) -> ValuationArchetype:
        archetype = self.get(archetype_id)
        if archetype is None:
            raise ValueError(f"Unknown valuation archetype: {archetype_id}")
        return archetype

    def available(self) -> tuple[ValuationArchetype, ...]:
        return tuple(item for item in self._by_id.values() if item.active)

    def resolve(self, archetype_id: object = None) -> ValuationArchetype:
        requested = self.get(archetype_id)
        return requested if requested is not None and requested.active else self.require(
            DEFAULT_VALUATION_ARCHETYPE_ID
        )


ARCHETYPE_REGISTRY = ValuationArchetypeRegistry((BALANCED_DYNASTY,))


def resolve_valuation_engine(
    archetype: ValuationArchetype,
    *,
    engines: Mapping[str, Callable[..., T]],
) -> Callable[..., T]:
    """Resolve an engine explicitly; the registry never changes engine inputs."""

    try:
        return engines[archetype.id]
    except KeyError as exc:
        raise ValueError(f"No valuation engine is registered for {archetype.id}") from exc

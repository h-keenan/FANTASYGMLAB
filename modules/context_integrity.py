"""Deterministic integrity contracts for cross-surface DynastyGM context."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class SurfaceContext:
    surface: str
    league_id: str
    roster_id: str
    score_field: str
    valuation_context: str
    player_source: str
    analysis_version: str = "1"

    @property
    def analysis_fingerprint(self) -> str:
        payload = {
            key: value
            for key, value in asdict(self).items()
            if key != "surface"
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IntegrityViolation:
    code: str
    surface: str
    detail: str


@dataclass(frozen=True)
class IntegrityReport:
    canonical_fingerprint: str
    surfaces: tuple[str, ...]
    violations: tuple[IntegrityViolation, ...]

    @property
    def valid(self) -> bool:
        return not self.violations

    def to_json(self) -> str:
        return json.dumps(
            {
                "canonical_fingerprint": self.canonical_fingerprint,
                "surfaces": list(self.surfaces),
                "valid": self.valid,
                "violations": [asdict(item) for item in self.violations],
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def validate_surface_contexts(contexts: Iterable[SurfaceContext]) -> IntegrityReport:
    items = tuple(contexts)
    if not items:
        return IntegrityReport("", (), (IntegrityViolation("missing_context", "", "No surface context supplied."),))
    canonical = items[0]
    violations: list[IntegrityViolation] = []
    for item in items[1:]:
        if item.analysis_fingerprint != canonical.analysis_fingerprint:
            for field in (
                "league_id", "roster_id", "score_field", "valuation_context",
                "player_source", "analysis_version",
            ):
                if getattr(item, field) != getattr(canonical, field):
                    violations.append(
                        IntegrityViolation(
                            f"context_{field}_mismatch",
                            item.surface,
                            f"{field} differs from {canonical.surface}.",
                        )
                    )
    return IntegrityReport(
        canonical.analysis_fingerprint,
        tuple(item.surface for item in items),
        tuple(violations),
    )


def recommendation_analysis_signature(recommendations: Sequence[Mapping]) -> tuple[tuple, ...]:
    """Return entitlement-independent recommendation identity, order, and values."""
    def first_present(item: Mapping, keys: tuple[str, ...]):
        for key in keys:
            if key in item and item[key] is not None:
                return item[key]
        return None

    return tuple(
        (
            first_present(item, ("idea_id", "recommendation_id")),
            first_present(item, ("recommendation_type", "tag")),
            first_present(item, ("value", "trade_gain", "score")),
            first_present(item, ("explanation_id", "reasoning_summary")),
        )
        for item in recommendations
    )


def access_tiers_share_analysis(
    free_analysis: Sequence[Mapping], premium_analysis: Sequence[Mapping]
) -> bool:
    """Entitlement may restrict visibility, never alter the computed board."""
    free_signature = recommendation_analysis_signature(free_analysis)
    premium_signature = recommendation_analysis_signature(premium_analysis)
    return free_signature == premium_signature[: len(free_signature)]

"""Presentation-only Dashboard briefing hierarchy."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Sequence
from modules import recommendation_lifecycle

INTELLIGENCE_LABELS = frozenset(
    {"Top Trade Opportunity", "Top Waiver Opportunity"}
)


STATUS_ONLY_LABELS = frozenset(
    {
        "Roster Pressure",
        "Injury Alert",
        "Roster Quality",
        "Lineup Construction",
        "Startup Observation",
    }
)


@dataclass(frozen=True)
class DashboardBriefing:
    immediate: tuple[Mapping, ...]
    primary: Mapping | None
    additional: tuple[Mapping, ...]
    intelligence: tuple[Mapping, ...]


def organize_dashboard_items(
    items: Sequence[Mapping],
    *,
    immediate_labels: frozenset[str] = frozenset(),
) -> DashboardBriefing:
    """Assign existing recommendation items to presentation zones only."""

    normalized = tuple(items)
    immediate = tuple(
        item for item in normalized if str(item.get("label") or "") in immediate_labels
    )
    remaining = tuple(
        item
        for item in normalized
        if str(item.get("label") or "") not in immediate_labels
    )
    recommendations = tuple(
        item
        for item in remaining
        if str(item.get("label") or "") not in STATUS_ONLY_LABELS
    )
    primary = recommendations[0] if recommendations else None
    intelligence = tuple(
        item
        for item in recommendations[1:]
        if str(item.get("label") or "") in INTELLIGENCE_LABELS
    )
    intelligence = recommendation_lifecycle.suppress_duplicate_intelligence(
        primary,
        intelligence,
    )
    additional = tuple(
        item
        for item in recommendations[1:]
        if str(item.get("label") or "") not in INTELLIGENCE_LABELS
    )
    additional = recommendation_lifecycle.dedupe_executive_items(
        additional,
        seen_ids={
            recommendation_lifecycle.item_recommendation_id(primary)
        }
        if primary is not None
        else set(),
    )
    return DashboardBriefing(
        immediate=immediate,
        primary=primary,
        additional=additional,
        intelligence=intelligence,
    )

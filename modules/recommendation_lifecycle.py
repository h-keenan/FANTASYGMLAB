"""Recommendation lifecycle helpers — presentation and provenance only.

Does not generate, score, order, or Trust-filter recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping, Sequence

from modules import canonical_recommendation_narrative as crn


@dataclass(frozen=True)
class RecommendationContext:
    league_id: str
    roster_id: str
    valuation_lens: str


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


def item_recommendation_id(item: Mapping[str, Any] | None) -> str:
    if not isinstance(item, Mapping):
        return ""
    direct = _text(item.get("recommendation_id"))
    if direct:
        return direct
    payload = item.get("recommendation_narrative")
    if isinstance(payload, Mapping):
        return _text(payload.get("recommendation_id"))
    model = crn.CanonicalRecommendationNarrative.from_dict(payload)
    return _text(model.recommendation_id) if model is not None else ""


def narrative_matches_context(
    narrative: crn.CanonicalRecommendationNarrative | Mapping[str, Any] | None,
    *,
    league_id: str = "",
    roster_id: str = "",
    valuation_lens: str = "",
) -> bool:
    model = (
        narrative
        if isinstance(narrative, crn.CanonicalRecommendationNarrative)
        else crn.CanonicalRecommendationNarrative.from_dict(narrative)
    )
    if model is None:
        return False
    league_key = _text(league_id)
    roster_key = _text(roster_id)
    lens_key = _text(valuation_lens)
    if league_key and _text(model.league_id) and _text(model.league_id) != league_key:
        return False
    if roster_key and _text(model.roster_id) and _text(model.roster_id) != roster_key:
        return False
    if lens_key and _text(model.valuation_lens) and _text(model.valuation_lens) != lens_key:
        return False
    return True


def invalidate_stale_narrative(
    state: MutableMapping[str, Any],
    *,
    league_id: str = "",
    roster_id: str = "",
    valuation_lens: str = "",
) -> bool:
    """Clear bound narrative when league, roster, or lens no longer match."""

    narrative = crn.load_narrative(state)
    if narrative is None:
        return False
    if narrative_matches_context(
        narrative,
        league_id=league_id,
        roster_id=roster_id,
        valuation_lens=valuation_lens,
    ):
        return False
    crn.clear_narrative(state)
    return True


def dedupe_executive_items(
    items: Sequence[Mapping[str, Any]],
    *,
    seen_ids: set[str] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Drop later tiles that repeat the same recommendation_id."""

    seen = set(seen_ids or ())
    deduped: list[dict[str, Any]] = []
    for item in items:
        copy = dict(item)
        rec_id = item_recommendation_id(copy)
        if rec_id and rec_id in seen:
            continue
        if rec_id:
            seen.add(rec_id)
        deduped.append(copy)
    return tuple(deduped)


def suppress_duplicate_intelligence(
    primary: Mapping[str, Any] | None,
    intelligence: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """Hide intelligence tiles that restate the primary recommendation."""

    if primary is None:
        return tuple(intelligence)
    primary_id = item_recommendation_id(primary)
    if not primary_id:
        return tuple(intelligence)
    filtered = [
        item
        for item in intelligence
        if item_recommendation_id(item) != primary_id
    ]
    return tuple(filtered)

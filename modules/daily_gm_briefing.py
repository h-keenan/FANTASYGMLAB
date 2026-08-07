"""Daily GM Briefing — compose existing canonical Dashboard recommendations only.

Does not generate, score, order, or Trust-filter recommendations. Ordering and
identity come from dashboard_workflow.organize_dashboard_items and the already
approved recommendation inventory.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, Mapping, Sequence

from modules import dashboard_workflow
from modules import recommendation_lifecycle
from modules import canonical_player_ranking


CATEGORY_TOP_PRIORITY = "top_priority"
CATEGORY_WATCH = "watch"
CATEGORY_WAIVER = "waiver_opportunity"
CATEGORY_LEAGUE_MOVEMENT = "league_movement"

CATEGORY_LABELS = {
    CATEGORY_TOP_PRIORITY: "Top Priority",
    CATEGORY_WATCH: "Watch",
    CATEGORY_WAIVER: "Waiver Opportunity",
    CATEGORY_LEAGUE_MOVEMENT: "League Movement",
}

MAX_BRIEFING_ITEMS = 5

# Labels that may appear as WATCH developments (not primary trade/waiver moves).
_WATCH_LABELS = frozenset(
    {
        "Injury Alert",
        "Roster Pressure",
        "Biggest Team Need",
        "Roster Quality",
        "Lineup Construction",
        "Startup Observation",
    }
)

_WAIVER_LABELS = frozenset({"Top Waiver Opportunity"})
_LEAGUE_MOVEMENT_LABELS = frozenset(
    {"Top Trade Opportunity", "Top Waiver Opportunity"}
)


@dataclass(frozen=True)
class DailyBriefingItem:
    """One composed briefing row sourced from an existing recommendation tile."""

    source: str
    source_id: str
    recommendation_id: str
    category: str
    headline: str
    reason: str
    supporting_context: str
    destination: str
    league_id: str
    roster_id: str
    valuation_lens: str
    scoring_format: str
    freshness: str
    provenance: str
    route_player_id: str = ""
    route_focus_mode: str = ""
    recommendation_narrative: Mapping[str, Any] | None = None
    player_rank_context: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = {field.name: getattr(self, field.name) for field in fields(self)}
        narrative = payload.get("recommendation_narrative")
        if hasattr(narrative, "to_dict"):
            payload["recommendation_narrative"] = narrative.to_dict()
        return payload


@dataclass(frozen=True)
class DailyGmBriefing:
    items: tuple[DailyBriefingItem, ...]
    quiet: bool
    quiet_reason: str
    entitlement: str
    league_id: str
    roster_id: str
    valuation_lens: str
    scoring_format: str

    @property
    def item_count(self) -> int:
        return len(self.items)


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


def _tile_destination(tile: Mapping[str, Any], *, category: str) -> str:
    route = _text(tile.get("route_key"))
    if route:
        return route
    label = _text(tile.get("label"))
    if label in _WAIVER_LABELS or category == CATEGORY_WAIVER:
        return "waivers"
    if label in {"Injury Alert", "Biggest Team Need", "Roster Pressure"}:
        return "my_team"
    if label in _LEAGUE_MOVEMENT_LABELS:
        return "trade_hub"
    return "dashboard"


def _positive_int(value: object) -> int | None:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _rank_context_from_tile(
    tile: Mapping[str, Any],
    *,
    scoring_format: str,
) -> str:
    row = tile.get("player_row")
    if not isinstance(row, Mapping):
        return ""
    overall = row.get("overall_rank", row.get("canonical_overall_rank"))
    position_rank = row.get("position_rank", row.get("canonical_position_rank"))
    position = row.get("position", "")
    compact = canonical_player_ranking.format_compact_rank(
        overall,
        position_rank,
        position,
    )
    if compact == "Rank unavailable":
        return ""
    # Prefer position-first when both ranks exist (decision-facing order).
    pos = _text(position).upper()
    pos_n = _positive_int(position_rank)
    ovr_n = _positive_int(overall)
    if pos and pos_n and ovr_n:
        parts = [f"{pos} #{pos_n}", f"OVR #{ovr_n}"]
        fmt = _text(scoring_format)
        if fmt:
            parts.append(fmt)
        return " · ".join(parts)
    fmt = _text(scoring_format)
    return f"{compact} · {fmt}" if fmt else compact


def _item_from_tile(
    tile: Mapping[str, Any],
    *,
    category: str,
    league_id: str,
    roster_id: str,
    valuation_lens: str,
    scoring_format: str,
    entitlement: str,
) -> DailyBriefingItem | None:
    label = _text(tile.get("label"))
    headline = _text(tile.get("value"))
    reason = _text(tile.get("note"))
    if not headline and not reason:
        return None
    rec_id = recommendation_lifecycle.item_recommendation_id(tile)
    narrative = tile.get("recommendation_narrative")
    if hasattr(narrative, "to_dict"):
        narrative = narrative.to_dict()
    if not isinstance(narrative, Mapping):
        narrative = None
    destination = _tile_destination(tile, category=category)
    return DailyBriefingItem(
        source="dashboard_inventory",
        source_id=_text(tile.get("recommendation_id") or rec_id or label),
        recommendation_id=rec_id,
        category=category,
        headline=headline or label,
        reason=reason or label,
        supporting_context=label,
        destination=destination,
        league_id=_text(tile.get("league_id") or league_id),
        roster_id=_text(tile.get("roster_id") or roster_id),
        valuation_lens=_text(tile.get("valuation_lens") or valuation_lens),
        scoring_format=_text(scoring_format),
        freshness="dashboard_frame",
        provenance=(
            f"dashboard_workflow.organize_dashboard_items|{category}|{entitlement}"
        ),
        route_player_id=_text(tile.get("route_player_id")),
        route_focus_mode=_text(tile.get("route_focus_mode")),
        recommendation_narrative=narrative,
        player_rank_context=_rank_context_from_tile(
            tile, scoring_format=scoring_format
        ),
    )


def compose_daily_gm_briefing(
    briefing: dashboard_workflow.DashboardBriefing,
    *,
    league_id: str = "",
    roster_id: str = "",
    valuation_lens: str = "",
    scoring_format: str = "",
    entitlement: str = "free",
) -> DailyGmBriefing:
    """Compose Today's Game Plan from an already-organized Dashboard briefing.

    Order is derived strictly from existing presentation zones:
    1) primary recommendation
    2) immediate watch items (injury / roster pressure / need)
    3) waiver opportunity from intelligence or additional
    4) remaining league-movement intelligence
    Deduplicated by recommendation_id. No new football score is computed.
    """

    composed: list[DailyBriefingItem] = []
    seen_ids: set[str] = set()

    def _append(tile: Mapping[str, Any] | None, category: str) -> None:
        if tile is None or len(composed) >= MAX_BRIEFING_ITEMS:
            return
        item = _item_from_tile(
            tile,
            category=category,
            league_id=league_id,
            roster_id=roster_id,
            valuation_lens=valuation_lens,
            scoring_format=scoring_format,
            entitlement=entitlement,
        )
        if item is None:
            return
        if item.recommendation_id and item.recommendation_id in seen_ids:
            return
        # Also suppress exact headline+category duplicates without ids.
        fingerprint = (
            item.recommendation_id
            or f"{item.category}|{item.headline.casefold()}|{item.supporting_context}"
        )
        if fingerprint in seen_ids:
            return
        seen_ids.add(fingerprint)
        if item.recommendation_id:
            seen_ids.add(item.recommendation_id)
        composed.append(item)

    # 1 · TOP PRIORITY — canonical primary recommendation.
    if briefing.primary is not None:
        _append(briefing.primary, CATEGORY_TOP_PRIORITY)

    # 2 · WATCH — urgent/status developments that deserve attention.
    for tile in briefing.immediate:
        label = _text(tile.get("label"))
        if label in _WATCH_LABELS:
            _append(tile, CATEGORY_WATCH)

    # Need-style items in additional can surface as WATCH when not primary.
    for tile in briefing.additional:
        label = _text(tile.get("label"))
        if label in _WATCH_LABELS:
            _append(tile, CATEGORY_WATCH)

    # 3 · WAIVER OPPORTUNITY — first waiver tile from intelligence then additional.
    waiver_candidates = tuple(briefing.intelligence) + tuple(briefing.additional)
    for tile in waiver_candidates:
        if _text(tile.get("label")) in _WAIVER_LABELS:
            _append(tile, CATEGORY_WAIVER)
            break

    # 4 · LEAGUE MOVEMENT — remaining intelligence not already shown.
    for tile in briefing.intelligence:
        label = _text(tile.get("label"))
        if label in _LEAGUE_MOVEMENT_LABELS:
            _append(tile, CATEGORY_LEAGUE_MOVEMENT)

    quiet = not composed
    quiet_reason = (
        "Your roster has no urgent approved actions. We'll surface something "
        "here when the current league context produces a move worth your attention."
        if quiet
        else ""
    )
    return DailyGmBriefing(
        items=tuple(composed),
        quiet=quiet,
        quiet_reason=quiet_reason,
        entitlement=_text(entitlement).casefold() or "free",
        league_id=_text(league_id),
        roster_id=_text(roster_id),
        valuation_lens=_text(valuation_lens),
        scoring_format=_text(scoring_format),
    )


def briefing_matches_context(
    briefing: DailyGmBriefing | Mapping[str, Any] | None,
    *,
    league_id: str = "",
    roster_id: str = "",
    valuation_lens: str = "",
    scoring_format: str = "",
) -> bool:
    if briefing is None:
        return False
    if isinstance(briefing, Mapping):
        payload = briefing
    else:
        payload = {
            "league_id": briefing.league_id,
            "roster_id": briefing.roster_id,
            "valuation_lens": briefing.valuation_lens,
            "scoring_format": briefing.scoring_format,
        }
    if league_id and _text(payload.get("league_id")) and _text(payload.get("league_id")) != _text(league_id):
        return False
    if roster_id and _text(payload.get("roster_id")) and _text(payload.get("roster_id")) != _text(roster_id):
        return False
    if (
        valuation_lens
        and _text(payload.get("valuation_lens"))
        and _text(payload.get("valuation_lens")) != _text(valuation_lens)
    ):
        return False
    if (
        scoring_format
        and _text(payload.get("scoring_format"))
        and _text(payload.get("scoring_format")) != _text(scoring_format)
    ):
        return False
    return True

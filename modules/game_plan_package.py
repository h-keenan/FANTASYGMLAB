"""Canonical Today's Game Plan package memo — performance/ownership only.

Caches structured Game Plan results (briefing items + dashboard tiles) keyed by a
football/lifecycle fingerprint so Dashboard rerenders do not re-enter:

- get_shared_league_context / cached_league_context (large DataFrame hash)
- cached_dashboard_trade_headline / trade generation
- compose_daily_gm_briefing

Does not change recommendation generation, Trust, ordering, or entitlement rules.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping, Sequence
from copy import deepcopy
from hashlib import sha256
import json
from typing import Any

from modules import runtime_trace


PACKAGE_KEY = "_game_plan_package_bundle"
PACKAGE_SIG_KEY = "_game_plan_package_signature"
HIT_COUNTER = "game_plan_package_hits"
MISS_COUNTER = "game_plan_package_misses"

# Flags for Dashboard Game Plan context — aligned with Trade Hub critical path.
# Full League Intelligence is deferred to League Pulse / Insights, not Game Plan.
GAME_PLAN_CONTEXT_FLAGS = (
    False,  # include_intelligence
    True,  # include_roster_map
    True,  # include_trust
    True,  # include_maturity
)


def clear_game_plan_package(state: MutableMapping[str, Any]) -> None:
    """Drop Game Plan package memo (league / account hygiene)."""

    state.pop(PACKAGE_KEY, None)
    state.pop(PACKAGE_SIG_KEY, None)


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _stable_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(encoded.encode("utf-8")).hexdigest()[:32]


def build_package_signature(
    *,
    account_user_id: object = "",
    league_id: object = "",
    roster_id: object = "",
    prepared_frame_signature: object = "",
    score_field: object = "",
    league_settings_key: object = "",
    team_strategy: object = "",
    role_items: Sequence[tuple[str, str]] | None = None,
    untouchables: Sequence[str] | None = None,
    entitlement: object = "",
    lifecycle_digest: object = "",
    roster_state_version: object = "",
    startup_mode: bool = False,
    pick_score_multiplier: object = "",
) -> str:
    """Fingerprint for Game Plan package invalidation (real dependencies only)."""

    roles = tuple(sorted((str(pid), str(role)) for pid, role in (role_items or ())))
    untouchable_key = tuple(sorted(str(name) for name in (untouchables or ())))
    return _stable_digest(
        {
            "account_user_id": _text(account_user_id),
            "league_id": _text(league_id),
            "roster_id": _text(roster_id),
            "prepared_frame_signature": _text(prepared_frame_signature),
            "score_field": _text(score_field),
            "league_settings_key": _text(league_settings_key),
            "team_strategy": _text(team_strategy),
            "role_items": roles,
            "untouchables": untouchable_key,
            "entitlement": _text(entitlement, "free"),
            "lifecycle_digest": _text(lifecycle_digest),
            "roster_state_version": _text(roster_state_version),
            "startup_mode": bool(startup_mode),
            "pick_score_multiplier": str(pick_score_multiplier),
        }
    )


def lookup_package(
    state: MutableMapping[str, Any],
    *,
    signature: str,
) -> tuple[dict[str, Any] | None, bool]:
    """Return ``(package, hit)`` when signature matches session memo."""

    key = _text(signature)
    cached = state.get(PACKAGE_KEY)
    if key and state.get(PACKAGE_SIG_KEY) == key and isinstance(cached, Mapping):
        runtime_trace.count(HIT_COUNTER)
        return deepcopy(dict(cached)), True
    runtime_trace.count(MISS_COUNTER)
    return None, False


def store_package(
    state: MutableMapping[str, Any],
    *,
    signature: str,
    package: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist a structured Game Plan package for warm Dashboard reuse."""

    key = _text(signature)
    payload = deepcopy(dict(package or {}))
    payload["signature"] = key
    if key:
        state[PACKAGE_SIG_KEY] = key
        state[PACKAGE_KEY] = payload
    return deepcopy(payload)


def get_or_build_package(
    state: MutableMapping[str, Any],
    *,
    signature: str,
    builder: Callable[[], Mapping[str, Any]],
) -> tuple[dict[str, Any], bool]:
    """Reuse Game Plan package across warm Dashboard reruns."""

    cached, hit = lookup_package(state, signature=signature)
    if hit and cached is not None:
        return cached, True
    built = dict(builder() or {})
    return store_package(state, signature=signature, package=built), False


def package_recommendation_ids(package: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(package, Mapping):
        return []
    ids = package.get("recommendation_ids")
    if isinstance(ids, (list, tuple)):
        return [str(item) for item in ids if str(item).strip()]
    briefing = package.get("briefing")
    if isinstance(briefing, Mapping):
        items = briefing.get("items") or ()
        return [
            str(item.get("recommendation_id") or "")
            for item in items
            if isinstance(item, Mapping) and str(item.get("recommendation_id") or "").strip()
        ]
    return []


def briefing_from_package(package: Mapping[str, Any]):
    """Rebuild ``DailyGmBriefing`` from a stored package (lazy import)."""

    from modules import daily_gm_briefing

    raw = package.get("briefing") if isinstance(package, Mapping) else None
    if not isinstance(raw, Mapping):
        return daily_gm_briefing.DailyGmBriefing(
            items=(),
            quiet=True,
            quiet_reason="Cached Game Plan package was empty.",
            entitlement=_text(package.get("entitlement"), "free") if isinstance(package, Mapping) else "free",
            league_id="",
            roster_id="",
            valuation_lens="",
            scoring_format="PPR",
        )
    items_raw = raw.get("items") or ()
    items = []
    for row in items_raw:
        if not isinstance(row, Mapping):
            continue
        items.append(
            daily_gm_briefing.DailyBriefingItem(
                source=_text(row.get("source")),
                source_id=_text(row.get("source_id")),
                recommendation_id=_text(row.get("recommendation_id")),
                category=_text(row.get("category")),
                headline=_text(row.get("headline")),
                reason=_text(row.get("reason")),
                supporting_context=_text(row.get("supporting_context")),
                destination=_text(row.get("destination")),
                league_id=_text(row.get("league_id")),
                roster_id=_text(row.get("roster_id")),
                valuation_lens=_text(row.get("valuation_lens")),
                scoring_format=_text(row.get("scoring_format"), "PPR"),
                freshness=_text(row.get("freshness")),
                provenance=_text(row.get("provenance")),
                route_player_id=_text(row.get("route_player_id")),
                route_focus_mode=_text(row.get("route_focus_mode")),
                recommendation_narrative=(
                    row.get("recommendation_narrative")
                    if isinstance(row.get("recommendation_narrative"), Mapping)
                    else None
                ),
                player_rank_context=_text(row.get("player_rank_context")),
            )
        )
    return daily_gm_briefing.DailyGmBriefing(
        items=tuple(items),
        quiet=bool(raw.get("quiet")),
        quiet_reason=_text(raw.get("quiet_reason")),
        entitlement=_text(raw.get("entitlement"), "free"),
        league_id=_text(raw.get("league_id")),
        roster_id=_text(raw.get("roster_id")),
        valuation_lens=_text(raw.get("valuation_lens")),
        scoring_format=_text(raw.get("scoring_format"), "PPR"),
    )


def dashboard_briefing_from_package(package: Mapping[str, Any]):
    """Rebuild ``DashboardBriefing`` from stored tile zones."""

    from modules import dashboard_workflow

    zones = package.get("dashboard_briefing") if isinstance(package, Mapping) else None
    if not isinstance(zones, Mapping):
        return dashboard_workflow.DashboardBriefing(
            immediate=(),
            primary=None,
            additional=(),
            intelligence=(),
        )
    immediate = tuple(item for item in (zones.get("immediate") or ()) if isinstance(item, Mapping))
    additional = tuple(item for item in (zones.get("additional") or ()) if isinstance(item, Mapping))
    intelligence = tuple(
        item for item in (zones.get("intelligence") or ()) if isinstance(item, Mapping)
    )
    primary = zones.get("primary")
    if primary is not None and not isinstance(primary, Mapping):
        primary = None
    return dashboard_workflow.DashboardBriefing(
        immediate=immediate,
        primary=primary,
        additional=additional,
        intelligence=intelligence,
    )


def serialize_dashboard_briefing(briefing: Any) -> dict[str, Any]:
    return {
        "immediate": [dict(item) for item in (getattr(briefing, "immediate", ()) or ())],
        "primary": dict(briefing.primary) if getattr(briefing, "primary", None) else None,
        "additional": [dict(item) for item in (getattr(briefing, "additional", ()) or ())],
        "intelligence": [dict(item) for item in (getattr(briefing, "intelligence", ()) or ())],
    }


def serialize_daily_briefing(briefing: Any) -> dict[str, Any]:
    items = []
    for item in getattr(briefing, "items", ()) or ():
        if hasattr(item, "to_dict"):
            items.append(item.to_dict())
        elif isinstance(item, Mapping):
            items.append(dict(item))
    return {
        "items": items,
        "quiet": bool(getattr(briefing, "quiet", False)),
        "quiet_reason": _text(getattr(briefing, "quiet_reason", "")),
        "entitlement": _text(getattr(briefing, "entitlement", ""), "free"),
        "league_id": _text(getattr(briefing, "league_id", "")),
        "roster_id": _text(getattr(briefing, "roster_id", "")),
        "valuation_lens": _text(getattr(briefing, "valuation_lens", "")),
        "scoring_format": _text(getattr(briefing, "scoring_format", ""), "PPR"),
    }

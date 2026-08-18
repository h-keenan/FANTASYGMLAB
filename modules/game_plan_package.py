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
import time
from typing import Any

from modules import runtime_trace


PACKAGE_KEY = "_game_plan_package_bundle"
PACKAGE_SIG_KEY = "_game_plan_package_signature"
HIT_COUNTER = "game_plan_package_hits"
MISS_COUNTER = "game_plan_package_misses"
PROCESS_HIT_COUNTER = "game_plan_package_process_hits"
STALE_COUNTER = "game_plan_package_stale"
LAST_MISS_REASON_KEY = "_game_plan_package_last_miss_reason"
LAST_CACHE_STATUS_KEY = "_game_plan_package_last_cache_status"
LAST_BUILT_AT_KEY = "_game_plan_package_built_at"
# Soft wall-clock freshness for recommendation packages (Top Trade / Waiver / ideas).
# Semantic fingerprint still owns invalidation; TTL prevents multi-day process reuse.
SOFT_TTL_SECONDS = 5 * 60 * 60
# Bump when fingerprint composition changes (#222 removed ephemeral startup_mode).
PACKAGE_FINGERPRINT_VERSION = 3
# Process-scoped reuse across Streamlit sessions in the same worker.
# Fingerprint already embeds account_user_id + league/roster — never share across accounts.
_PROCESS_PACKAGE_STORE: dict[str, dict[str, Any]] = {}
_MAX_PROCESS_PACKAGES = 32

# Flags for Dashboard Game Plan context — aligned with Trade Hub critical path.
# Full League Intelligence is deferred to League Pulse / Insights, not Game Plan.
GAME_PLAN_CONTEXT_FLAGS = (
    False,  # include_intelligence
    True,  # include_roster_map
    True,  # include_trust
    True,  # include_maturity
)


def clear_process_game_plan_packages() -> None:
    """Drop process-scoped Game Plan packages (logout / tests / worker recycle)."""

    _PROCESS_PACKAGE_STORE.clear()


def clear_game_plan_package(state: MutableMapping[str, Any]) -> None:
    """Drop Game Plan package memo (league / account hygiene).

    Session memo only — process store is retained for warm A→B→A / remount reuse
    when fingerprints still match. Logout clears process via
    ``clear_process_game_plan_packages``.
    """

    state.pop(PACKAGE_KEY, None)
    state.pop(PACKAGE_SIG_KEY, None)
    state.pop(LAST_MISS_REASON_KEY, None)
    state.pop(LAST_CACHE_STATUS_KEY, None)
    state.pop(LAST_BUILT_AT_KEY, None)
    try:
        from modules import news_intelligence

        news_intelligence.clear_news_presentation_state(state)
    except Exception:
        pass


def _drop_stale_live_inputs() -> None:
    """Drop process memos + live Sleeper LRU so a rebuild cannot reuse stale FA/roster truth."""

    try:
        from modules.game_plan_process_cache import clear_process_game_plan_caches

        clear_process_game_plan_caches()
    except Exception:
        pass
    try:
        from modules.sleeper import clear_live_league_endpoint_caches

        clear_live_league_endpoint_caches()
    except Exception:
        pass


def invalidate_recommendation_packages(
    state: MutableMapping[str, Any],
    *,
    signature: str = "",
) -> None:
    """Manual refresh: drop session + matching process recommendation package only."""

    key = _text(signature) or _text(state.get(PACKAGE_SIG_KEY))
    clear_game_plan_package(state)
    if key:
        _PROCESS_PACKAGE_STORE.pop(key, None)
    _drop_stale_live_inputs()
    state[LAST_CACHE_STATUS_KEY] = "rebuild"
    state[LAST_MISS_REASON_KEY] = "manual_refresh"


def package_age_seconds(package: Mapping[str, Any] | None) -> float | None:
    if not isinstance(package, Mapping):
        return None
    built_at = package.get("built_at")
    try:
        built = float(built_at)
    except (TypeError, ValueError):
        return None
    if built <= 0:
        return None
    return max(0.0, time.time() - built)


def package_is_fresh(
    package: Mapping[str, Any] | None,
    *,
    ttl_seconds: int = SOFT_TTL_SECONDS,
) -> bool:
    age = package_age_seconds(package)
    if age is None:
        return False
    return age <= float(ttl_seconds)


def format_package_age_label(package: Mapping[str, Any] | None) -> str:
    age = package_age_seconds(package)
    if age is None:
        return ""
    minutes = int(age // 60)
    if minutes < 1:
        return "Updated just now"
    if minutes < 60:
        return f"Updated {minutes}m ago"
    hours = int(minutes // 60)
    if hours < 48:
        return f"Updated {hours}h ago"
    days = int(hours // 24)
    return f"Updated {days}d ago"


def explain_package_cache_state(
    state: MutableMapping[str, Any],
    *,
    signature: str,
) -> dict[str, Any]:
    """Diagnostic snapshot for Game Plan package lookup."""

    key = _text(signature)
    cached = state.get(PACKAGE_KEY)
    session_sig = _text(state.get(PACKAGE_SIG_KEY))
    session_hit = bool(key and session_sig == key and isinstance(cached, Mapping))
    process_hit = bool(key and key in _PROCESS_PACKAGE_STORE)
    miss_reason = ""
    if not session_hit:
        if not key:
            miss_reason = "empty_signature"
        elif not session_sig:
            miss_reason = "session_cold"
        elif session_sig != key:
            miss_reason = "signature_mismatch"
        else:
            miss_reason = "session_empty_package"
    return {
        "signature_prefix": key[:12],
        "session_hit": session_hit,
        "process_hit": process_hit,
        "miss_reason": miss_reason,
        "process_entries": len(_PROCESS_PACKAGE_STORE),
        "last_status": _text(state.get(LAST_CACHE_STATUS_KEY)),
        "last_miss_reason": _text(state.get(LAST_MISS_REASON_KEY)),
    }


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _stable_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(encoded.encode("utf-8")).hexdigest()[:32]


def _component_prefix(value: object, *, length: int = 8) -> str:
    return _stable_digest({"v": value})[:length]


def rostered_universe_digest(roster_player_map: Mapping[str, Sequence[object]] | None) -> str:
    """Stable digest of every rostered player id in a league (FA-pool proxy).

    User-roster ``roster_state_version`` does not move when another team
    adds/drops. Hashing the full rostered universe invalidates Game Plan
    when the waiver pool changes.
    """

    ids: list[str] = []
    for player_ids in (roster_player_map or {}).values():
        for player_id in player_ids or ():
            text = _text(player_id)
            if text:
                ids.append(text)
    if not ids:
        return ""
    return sha256("|".join(sorted(set(ids))).encode("utf-8")).hexdigest()[:16]


def _stable_pick_multiplier(value: object) -> str:
    try:
        return f"{float(value):.8f}"
    except (TypeError, ValueError):
        return "0.00000000"


def package_fingerprint_components(
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
    pick_score_multiplier: object = "",
    waiver_pool_digest: object = "",
) -> dict[str, str]:
    """Stable per-component prefixes for diagnostics (no PII payloads)."""

    roles = tuple(sorted((str(pid), str(role)) for pid, role in (role_items or ())))
    untouchable_key = tuple(sorted(str(name) for name in (untouchables or ())))
    components = {
        "fingerprint_version": str(PACKAGE_FINGERPRINT_VERSION),
        "account_user_id": _component_prefix(_text(account_user_id)),
        "league_id": _component_prefix(_text(league_id)),
        "roster_id": _component_prefix(_text(roster_id)),
        "prepared_frame_signature": _component_prefix(_text(prepared_frame_signature)),
        "score_field": _component_prefix(_text(score_field)),
        "league_settings_key": _component_prefix(_text(league_settings_key)),
        "team_strategy": _component_prefix(_text(team_strategy)),
        "role_items": _component_prefix(roles),
        "untouchables": _component_prefix(untouchable_key),
        "entitlement": _component_prefix(_text(entitlement, "free")),
        "lifecycle_digest": _component_prefix(_text(lifecycle_digest)),
        "roster_state_version": _component_prefix(_text(roster_state_version)),
        "pick_score_multiplier": _component_prefix(_stable_pick_multiplier(pick_score_multiplier)),
        "waiver_pool_digest": _component_prefix(_text(waiver_pool_digest)),
    }
    return components


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
    startup_mode: bool = False,  # retained for call-site compat; ignored (#222)
    pick_score_multiplier: object = "",
    waiver_pool_digest: object = "",
) -> str:
    """Fingerprint for Game Plan package invalidation (real football deps only).

    ``startup_mode`` is intentionally ignored — presentation/startup phase must
    not invalidate recommendation packages across post-usable auth remounts.
    """

    _ = startup_mode
    roles = tuple(sorted((str(pid), str(role)) for pid, role in (role_items or ())))
    untouchable_key = tuple(sorted(str(name) for name in (untouchables or ())))
    return _stable_digest(
        {
            "fingerprint_version": PACKAGE_FINGERPRINT_VERSION,
            "account_user_id": _text(account_user_id),
            "league_id": _text(league_id),
            "roster_id": _text(roster_id),
            "prepared_frame_signature": _text(prepared_frame_signature),
            "score_field": _text(score_field),
            "league_settings_key": _text(league_settings_key),
            "team_strategy": _text(team_strategy),
            "role_items": roles,
            "untouchables": untouchable_key,
            "entitlement": _text(entitlement, "free").casefold() or "free",
            "lifecycle_digest": _text(lifecycle_digest),
            "roster_state_version": _text(roster_state_version),
            "pick_score_multiplier": _stable_pick_multiplier(pick_score_multiplier),
            "waiver_pool_digest": _text(waiver_pool_digest),
        }
    )


def _store_process_package(key: str, payload: Mapping[str, Any]) -> None:
    if not key:
        return
    _PROCESS_PACKAGE_STORE[key] = deepcopy(dict(payload))
    while len(_PROCESS_PACKAGE_STORE) > _MAX_PROCESS_PACKAGES:
        oldest = next(iter(_PROCESS_PACKAGE_STORE))
        _PROCESS_PACKAGE_STORE.pop(oldest, None)


def lookup_package(
    state: MutableMapping[str, Any],
    *,
    signature: str,
    ttl_seconds: int = SOFT_TTL_SECONDS,
    expected_league_id: object = "",
) -> tuple[dict[str, Any] | None, bool]:
    """Return ``(package, hit)`` for session or process memo (builder not invoked).

    Soft TTL: signature-matching packages older than ``ttl_seconds`` count as
    STALE and force a rebuild (does not rebuild on every Streamlit rerun).
    When ``expected_league_id`` is set, a signature hit whose stored briefing
    league disagrees is treated as a miss so rapid switches cannot paint League A
    under League B's name.
    """

    key = _text(signature)
    wanted_league = _text(expected_league_id)

    def _league_matches(payload: Mapping[str, Any]) -> bool:
        if not wanted_league:
            return True
        briefing = payload.get("briefing") if isinstance(payload.get("briefing"), Mapping) else {}
        stored = _text(briefing.get("league_id")) or _text(payload.get("league_id"))
        return not stored or stored == wanted_league

    cached = state.get(PACKAGE_KEY)
    if key and state.get(PACKAGE_SIG_KEY) == key and isinstance(cached, Mapping):
        payload = deepcopy(dict(cached))
        if not _league_matches(payload):
            state[LAST_CACHE_STATUS_KEY] = "miss"
            state[LAST_MISS_REASON_KEY] = "league_mismatch"
            runtime_trace.count(MISS_COUNTER)
            runtime_trace.count(STALE_COUNTER)
            state.pop(PACKAGE_KEY, None)
            state.pop(PACKAGE_SIG_KEY, None)
            return None, False
        if package_is_fresh(payload, ttl_seconds=ttl_seconds):
            state[LAST_CACHE_STATUS_KEY] = "hit"
            state[LAST_MISS_REASON_KEY] = ""
            state[LAST_BUILT_AT_KEY] = payload.get("built_at")
            runtime_trace.count(HIT_COUNTER)
            return payload, True
        state[LAST_CACHE_STATUS_KEY] = "stale"
        state[LAST_MISS_REASON_KEY] = "soft_ttl_expired"
        runtime_trace.count(STALE_COUNTER)
        state.pop(PACKAGE_KEY, None)
        state.pop(PACKAGE_SIG_KEY, None)
        _PROCESS_PACKAGE_STORE.pop(key, None)
        _drop_stale_live_inputs()
        return None, False

    process_cached = _PROCESS_PACKAGE_STORE.get(key) if key else None
    if key and isinstance(process_cached, Mapping):
        hydrated = deepcopy(dict(process_cached))
        if not _league_matches(hydrated):
            state[LAST_CACHE_STATUS_KEY] = "miss"
            state[LAST_MISS_REASON_KEY] = "league_mismatch"
            runtime_trace.count(MISS_COUNTER)
            return None, False
        if package_is_fresh(hydrated, ttl_seconds=ttl_seconds):
            state[PACKAGE_SIG_KEY] = key
            state[PACKAGE_KEY] = hydrated
            state[LAST_CACHE_STATUS_KEY] = "process_hit"
            state[LAST_MISS_REASON_KEY] = ""
            state[LAST_BUILT_AT_KEY] = hydrated.get("built_at")
            runtime_trace.count(PROCESS_HIT_COUNTER)
            runtime_trace.count(HIT_COUNTER)
            return deepcopy(hydrated), True
        state[LAST_CACHE_STATUS_KEY] = "stale"
        state[LAST_MISS_REASON_KEY] = "soft_ttl_expired"
        runtime_trace.count(STALE_COUNTER)
        _PROCESS_PACKAGE_STORE.pop(key, None)
        _drop_stale_live_inputs()
        return None, False

    diagnosis = explain_package_cache_state(state, signature=key)
    state[LAST_CACHE_STATUS_KEY] = "miss"
    state[LAST_MISS_REASON_KEY] = str(diagnosis.get("miss_reason") or "miss")
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
    payload["built_at"] = float(time.time())
    if key:
        state[PACKAGE_SIG_KEY] = key
        state[PACKAGE_KEY] = payload
        state[LAST_BUILT_AT_KEY] = payload["built_at"]
        _store_process_package(key, payload)
        state[LAST_CACHE_STATUS_KEY] = "rebuild"
        state[LAST_MISS_REASON_KEY] = ""
    return deepcopy(payload)


def get_or_build_package(
    state: MutableMapping[str, Any],
    *,
    signature: str,
    builder: Callable[[], Mapping[str, Any]],
) -> tuple[dict[str, Any], bool]:
    """Reuse Game Plan package across warm Dashboard reruns."""

    cached, hit = lookup_package(
        state, signature=signature, expected_league_id=state.get("selected_league_id")
    )
    if hit and cached is not None:
        return cached, True
    built = dict(builder() or {})
    runtime_trace.count("game_plan_package_builds")
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
    """Rebuild ``DailyGmBriefing`` from a stored package (lazy import).

    Must restore every ``DailyBriefingItem`` field, including ``presentation``.
    Omitting presentation is the rich→thin Dashboard collapse after a package HIT.
    """

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
        item = daily_gm_briefing.DailyBriefingItem.from_mapping(row)
        if item is None:
            continue
        items.append(item)
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

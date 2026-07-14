from __future__ import annotations

from typing import Any, MutableMapping


SCROLL_RESET_COUNTER_KEY = "_navigation_scroll_reset_counter"
SCROLL_RESET_PENDING_KEY = "_navigation_scroll_reset_pending"
SCROLL_RESET_CONSUMED_KEY = "_navigation_scroll_reset_consumed"
LAST_DESTINATION_KEY = "_navigation_last_destination"


def _route(value: Any) -> str:
    return "" if value is None else str(value).strip()


def preserved_league_switch_destination(
    current_page: Any = "",
    *,
    session_page: Any = "",
    query_page: Any = "",
) -> str:
    """Return the current route without applying league-specific allowlists."""
    for value in (current_page, session_page, query_page):
        candidate = _route(value)
        if candidate:
            return candidate
    return "dashboard"


def request_scroll_reset(
    state: MutableMapping[str, Any],
    destination: Any,
    *,
    reason: str = "destination_change",
    force: bool = False,
) -> int | None:
    """Request one client-side scroll reset without causing another rerun."""

    destination_key = _route(destination)
    if not destination_key:
        return None
    pending = state.get(SCROLL_RESET_PENDING_KEY)
    if (
        not force
        and isinstance(pending, dict)
        and _route(pending.get("destination")) == destination_key
    ):
        try:
            return int(pending.get("token") or 0) or None
        except (TypeError, ValueError):
            return None

    token = int(state.get(SCROLL_RESET_COUNTER_KEY, 0) or 0) + 1
    state[SCROLL_RESET_COUNTER_KEY] = token
    state[SCROLL_RESET_PENDING_KEY] = {
        "token": token,
        "destination": destination_key,
        "reason": _route(reason) or "destination_change",
    }
    return token


def queue_destination_navigation(
    state: MutableMapping[str, Any],
    destination: Any,
    *,
    current_destination: Any = "",
    source: str = "navigation",
    force_scroll: bool = False,
) -> bool:
    """Queue a route and request scroll reset only for a real destination load."""

    destination_key = _route(destination)
    if not destination_key:
        return False
    current_key = _route(current_destination) or _route(
        state.get("platform_nav_page")
    )
    state["_pending_platform_route"] = destination_key
    should_reset = force_scroll or destination_key != current_key
    if should_reset:
        request_scroll_reset(
            state,
            destination_key,
            reason=source,
            force=force_scroll,
        )
    return should_reset


def synchronize_destination_change(
    state: MutableMapping[str, Any],
    destination: Any,
) -> bool:
    """Catch query/back/sidebar transitions and coalesce an existing request."""

    destination_key = _route(destination)
    if not destination_key:
        return False
    previous = _route(state.get(LAST_DESTINATION_KEY))
    changed = bool(previous and previous != destination_key)
    if changed:
        request_scroll_reset(
            state,
            destination_key,
            reason="canonical_destination_change",
        )
    state[LAST_DESTINATION_KEY] = destination_key
    return changed


def consume_scroll_reset(
    state: MutableMapping[str, Any],
    destination: Any,
) -> dict[str, Any] | None:
    """Consume the pending reset once the matching destination is rendered."""

    pending = state.get(SCROLL_RESET_PENDING_KEY)
    if not isinstance(pending, dict):
        return None
    destination_key = _route(destination)
    if _route(pending.get("destination")) != destination_key:
        return None
    try:
        token = int(pending.get("token") or 0)
        consumed = int(state.get(SCROLL_RESET_CONSUMED_KEY, 0) or 0)
    except (TypeError, ValueError):
        state.pop(SCROLL_RESET_PENDING_KEY, None)
        return None
    if token <= 0 or token <= consumed:
        state.pop(SCROLL_RESET_PENDING_KEY, None)
        return None
    state[SCROLL_RESET_CONSUMED_KEY] = token
    state.pop(SCROLL_RESET_PENDING_KEY, None)
    return {
        "token": token,
        "destination": destination_key,
        "reason": _route(pending.get("reason")) or "destination_change",
    }

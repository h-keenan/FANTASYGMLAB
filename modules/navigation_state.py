from __future__ import annotations

from typing import Any, MutableMapping


SCROLL_RESET_COUNTER_KEY = "_navigation_scroll_reset_counter"
SCROLL_RESET_PENDING_KEY = "_navigation_scroll_reset_pending"
SCROLL_RESET_CONSUMED_KEY = "_navigation_scroll_reset_consumed"
LAST_DESTINATION_KEY = "_navigation_last_destination"
SCROLL_STORAGE_SCOPE_KEY = "_navigation_scroll_storage_scope"
PENDING_ROUTE_SOURCE_KEY = "_pending_platform_route_source"

# League hydrate may queue dashboard; never let that clobber an in-app URL/session route.
LEAGUE_HYDRATE_ROUTE_SOURCES = frozenset({"league_selection", "auto_resume"})


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


def resolve_resume_destination(
    *,
    pending_page: Any = "",
    pending_source: Any = "",
    query_page: Any = "",
    session_page: Any = "",
    allowed: Any = (),
) -> str:
    """Choose the route for this run without a global persistence system.

    User navigation pending always wins so sidebar clicks are not overridden by
    a stale query string. League auto-hydrate pending yields to query, then
    session, so returning to Safari on Trade Hub does not fall back to Dashboard.
    """

    if isinstance(allowed, dict):
        allowed_keys = set(allowed)
    else:
        allowed_keys = {str(item) for item in (allowed or ()) if str(item).strip()}

    def _ok(page: str) -> bool:
        if not page:
            return False
        return not allowed_keys or page in allowed_keys

    pending = _route(pending_page)
    query = _route(query_page)
    session = _route(session_page)
    source = _route(pending_source)
    if source in LEAGUE_HYDRATE_ROUTE_SOURCES:
        if _ok(query):
            return query
        if _ok(session):
            return session
        if _ok(pending):
            return pending
        return ""
    if _ok(pending):
        return pending
    if _ok(query):
        return query
    return ""


def request_scroll_reset(
    state: MutableMapping[str, Any],
    destination: Any,
    *,
    reason: str = "destination_change",
    force: bool = False,
    mode: str = "reset",
) -> int | None:
    """Request one client-side scroll reset without causing another rerun."""

    destination_key = _route(destination)
    if not destination_key:
        return None
    pending = state.get(SCROLL_RESET_PENDING_KEY)
    scroll_mode = _route(mode) or "reset"
    # A semantic in-route destination is more specific than the generic reset
    # queued by the route change that follows it.
    if (
        isinstance(pending, dict)
        and _route(pending.get("destination")) == destination_key
        and _route(pending.get("mode")) == "anchor"
        and scroll_mode == "reset"
    ):
        try:
            return int(pending.get("token") or 0) or None
        except (TypeError, ValueError):
            return None
    if (
        not force
        and isinstance(pending, dict)
        and _route(pending.get("destination")) == destination_key
        and _route(pending.get("mode")) == scroll_mode
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
        "mode": scroll_mode,
    }
    return token


def request_scroll_restore(
    state: MutableMapping[str, Any],
    destination: Any,
    *,
    reason: str = "workflow_back",
) -> int | None:
    """Restore the prior scroll position for a return navigation."""

    return request_scroll_reset(
        state,
        destination,
        reason=reason,
        force=True,
        mode="restore",
    )


def request_scroll_anchor(
    state: MutableMapping[str, Any],
    destination: Any,
    *,
    anchor: str,
    reason: str = "semantic_destination",
) -> int | None:
    """Land once on a named in-route destination after navigation."""

    token = request_scroll_reset(
        state,
        destination,
        reason=reason,
        force=True,
        mode="anchor",
    )
    pending = state.get(SCROLL_RESET_PENDING_KEY)
    if token and isinstance(pending, dict):
        pending["anchor"] = _route(anchor)
    return token


def scroll_storage_scope(state: MutableMapping[str, Any], *, league_id: str = "") -> str:
    """Return a stable browser storage scope for scroll positions."""

    league_key = _route(league_id) or _route(state.get("selected_league_id")) or "none"
    scope = f"{league_key}"
    state[SCROLL_STORAGE_SCOPE_KEY] = scope
    return scope


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
    state[PENDING_ROUTE_SOURCE_KEY] = _route(source) or "navigation"
    should_reset = force_scroll or destination_key != current_key
    if should_reset:
        request_scroll_reset(
            state,
            destination_key,
            reason=source,
            force=force_scroll,
        )
    return should_reset


def commit_destination_navigation(
    state: MutableMapping[str, Any],
    destination: Any,
    *,
    current_destination: Any = "",
    source: str = "navigation",
    force_scroll: bool = False,
) -> bool:
    """Commit callback-selected route state before Streamlit's automatic rerun."""

    destination_key = _route(destination)
    if not destination_key:
        return False
    should_reset = queue_destination_navigation(
        state,
        destination_key,
        current_destination=current_destination,
        source=source,
        force_scroll=force_scroll,
    )
    state["platform_nav_page"] = destination_key
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
    consumed = {
        "token": token,
        "destination": destination_key,
        "reason": _route(pending.get("reason")) or "destination_change",
        "mode": _route(pending.get("mode")) or "reset",
    }
    anchor = _route(pending.get("anchor"))
    if anchor:
        consumed["anchor"] = anchor
    return consumed

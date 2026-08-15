"""Canonical route-body owner — prior-route widgets must not survive underneath.

Streamlit keeps unmatched previous-run elements visible (and often dimmed) until
the current script run finishes. Long Trade Hub / Dashboard work therefore left
footer/legal and the previous page readable under the new loading treatment.

All post-chrome page content (including the legal footer) must render inside one
``st.empty()`` slot. On a route change the slot is cleared *before* expensive
work so leftover Dashboard/Trade Hub trees cannot remain on screen.

No global opaque overlay. No repeating ``run_every`` fragment.
"""

from __future__ import annotations

from typing import Any, MutableMapping

from modules import runtime_trace

LAST_ROUTE_KEY = "_fgl_last_painted_route"
CHANGED_KEY = "_fgl_route_changed_this_run"
SLOT_ENTERED_KEY = "_fgl_route_body_entered"

_active_container: Any = None


def last_route(state: MutableMapping[str, Any] | None) -> str:
    return str((state or {}).get(LAST_ROUTE_KEY) or "").strip()


def route_changed_this_run(state: MutableMapping[str, Any] | None) -> bool:
    return bool((state or {}).get(CHANGED_KEY))


def enter_after_chrome(
    state: MutableMapping[str, Any],
    route: str,
    *,
    slot: Any,
) -> None:
    """Clear prior-route body immediately, then bind the canonical container."""

    global _active_container
    current = str(route or "").strip()
    previous = last_route(state)
    changed = bool(previous and current and previous != current)
    state[LAST_ROUTE_KEY] = current
    state[CHANGED_KEY] = changed
    if changed:
        try:
            slot.empty()
        except Exception:
            pass
        runtime_trace.count("route_body_clears")
        runtime_trace.mark("route_body_cleared")
    _active_container = slot.container()
    _active_container.__enter__()
    state[SLOT_ENTERED_KEY] = True
    runtime_trace.mark("route_body_entered")


def exit_route_body(state: MutableMapping[str, Any] | None = None) -> None:
    global _active_container
    container = _active_container
    _active_container = None
    if state is not None:
        state.pop(SLOT_ENTERED_KEY, None)
    if container is None:
        return
    try:
        container.__exit__(None, None, None)
    except Exception:
        pass

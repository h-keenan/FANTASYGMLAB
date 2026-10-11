"""Canonical route-body owner — prior-route widgets must not survive underneath.

Streamlit keeps unmatched previous-run elements visible (and often dimmed) until
the current script run finishes. Long Trade Hub / Dashboard work therefore left
footer/legal and the previous page readable under the new loading treatment.

All post-chrome page content (including the legal footer) must render inside one
real ``st.empty()`` replacement slot. On every rerun its child container replaces
the prior tree; on a route change it is also cleared before expensive work so
leftover Dashboard/Trade Hub trees cannot remain on screen.

No global opaque overlay. No repeating ``run_every`` fragment.
"""

from __future__ import annotations

from html import escape
from typing import Any, MutableMapping

from modules import runtime_trace
from modules.html_rendering import inject_global_styles

LAST_ROUTE_KEY = "_fgl_last_painted_route"
CHANGED_KEY = "_fgl_route_changed_this_run"
SLOT_ENTERED_KEY = "_fgl_route_body_entered"

# General fix for the "invisible marker eats a flex `gap`" bug class (#973,
# #coridian_ dead-space re-report). #973 pulled two specific zero-content
# custom components (auth storage bridge, scroll-track markers) off-canvas
# with per-component `st-key-*` selectors — but any ``st.markdown(...,
# unsafe_allow_html=True)`` call whose entire rendered body is a single,
# genuinely hidden (HTML ``hidden`` attribute) node produces the exact same
# dead-space symptom, and keeps recurring under a *different* marker each
# time (most recently this module's own route-root span and app.py's
# dashboard-root div — both built with no ``key=``, so they can't be
# targeted by an ``st-key-*`` selector at all). Target the *authoring
# pattern* instead of any one marker's identity: an element-container whose
# only Markdown content is a lone ``[hidden]`` node (optionally wrapped in
# one ``<p>``) is never visible, so pulling it out of the flex flow can
# never hide real content — this is intentionally broad so a future marker
# built the same way is covered automatically instead of needing a fifth
# patch.
HIDDEN_MARKDOWN_MARKER_CSS = """
div[data-testid="stElementContainer"]:has(
    > div[data-testid="stMarkdown"] div[data-testid="stMarkdownContainer"] > :only-child[hidden]
),
div[data-testid="stElementContainer"]:has(
    > div[data-testid="stMarkdown"] div[data-testid="stMarkdownContainer"] > p:only-child > :only-child[hidden]
) {
    clip: rect(0, 0, 1px, 1px) !important;
    height: 1px !important;
    margin: 0 !important;
    max-height: 1px !important;
    max-width: 1px !important;
    min-width: 1px !important;
    overflow: hidden !important;
    padding: 0 !important;
    pointer-events: none !important;
    position: fixed !important;
    left: -10px !important;
    top: -10px !important;
    opacity: 0 !important;
    width: 1px !important;
}
"""

def last_route(state: MutableMapping[str, Any] | None) -> str:
    return str((state or {}).get(LAST_ROUTE_KEY) or "").strip()


def route_changed_this_run(state: MutableMapping[str, Any] | None) -> bool:
    return bool((state or {}).get(CHANGED_KEY))


def enter_after_chrome(
    state: MutableMapping[str, Any],
    route: str,
    *,
    slot: Any,
) -> Any:
    """Clear prior-route body immediately, then return this run's container.

    The caller must pass the returned handle to :func:`exit_route_body` before
    any explicit ``st.stop``. The handle is intentionally not process-global or
    stored in session state.
    """

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
    active_container = slot.container()
    active_container.__enter__()
    active_container.markdown(
        f'<span data-fgl-route-root="{escape(current, quote=True)}" hidden></span>',
        unsafe_allow_html=True,
    )
    inject_global_styles(HIDDEN_MARKDOWN_MARKER_CSS)
    state[SLOT_ENTERED_KEY] = True
    runtime_trace.mark("route_body_entered")
    return active_container


def exit_route_body(
    container: Any,
    state: MutableMapping[str, Any] | None = None,
) -> None:
    """Close only the route container created by this script run/session."""

    if state is not None:
        state.pop(SLOT_ENTERED_KEY, None)
    if container is None:
        return
    try:
        container.__exit__(None, None, None)
    except Exception:
        pass

from __future__ import annotations

from typing import Any


def preserved_league_switch_destination(
    current_page: Any = "",
    *,
    session_page: Any = "",
    query_page: Any = "",
) -> str:
    """Return the current route without applying league-specific allowlists."""
    for value in (current_page, session_page, query_page):
        candidate = "" if value is None else str(value).strip()
        if candidate:
            return candidate
    return "dashboard"

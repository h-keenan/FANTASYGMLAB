"""Saved leagues — how many leagues one account may keep, by entitlement.

One authority for the cap so the web app (modules.account_ui's "Save
league" / the automatic context persist) and the mobile API
(services.mobile_api_service's POST /v1/leagues/save) cannot disagree:
a limit enforced on only one surface is not a limit at all.

Free: MAX_LEAGUES_FREE. Premium: MAX_LEAGUES_PREMIUM.

Preference storage only — this module never touches valuations, rankings,
recommendations, or any football truth. Saving a league stores a pointer to
a Sleeper league the user already owns; it never changes that league.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from modules import premium


LEAGUES_TABLE = "saved_leagues"

# Free accounts keep one league — adding a second is the Premium wall.
MAX_LEAGUES_FREE = 1
# Premium is "as many as you actually have". A finite number (rather than
# None/infinity) keeps every caller's arithmetic and the wire contract's
# `cap` field simple, and mirrors gm_targets.MAX_TARGETS_PREMIUM being a
# generous-but-finite 50. Nobody manages 100 Sleeper leagues from one
# account; this is a runaway-write guard, not a product limit.
MAX_LEAGUES_PREMIUM = 100


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def normalize_league_id(value: Any) -> str:
    return _safe_text(value)


def max_leagues_for_entitlement(entitlement: Any) -> int:
    """Cap for an already-resolved entitlement string ("free"/"premium")."""

    return (
        MAX_LEAGUES_PREMIUM
        if _safe_text(entitlement).casefold() == premium.PREMIUM
        else MAX_LEAGUES_FREE
    )


def max_leagues_for_session(session: Mapping[str, Any] | None) -> int:
    """Cap for a Streamlit session, resolved through the same entitlement
    chain every other web Premium gate uses (modules.premium)."""

    return (
        MAX_LEAGUES_PREMIUM
        if premium.is_premium_user(session_state=dict(session or {}))
        else MAX_LEAGUES_FREE
    )


def saved_league_ids(rows: Iterable[Mapping[str, Any]] | None) -> set[str]:
    return {
        normalize_league_id(row.get("league_id"))
        for row in (rows or [])
        if isinstance(row, Mapping) and normalize_league_id(row.get("league_id"))
    }


def is_at_cap(
    existing_rows: Iterable[Mapping[str, Any]] | None,
    *,
    league_id: str,
    cap: int,
) -> bool:
    """True when saving `league_id` would exceed `cap`.

    Re-saving a league the account already holds is never at cap — that path
    is an update (roster/name/default refresh), not a new league, and the
    automatic web persist runs it constantly.
    """

    existing = saved_league_ids(existing_rows)
    if normalize_league_id(league_id) in existing:
        return False
    return len(existing) >= max(int(cap), 0)


def is_cap_message(message: Any) -> bool:
    """True when a save refusal was the plan cap (so the surface can show an
    upgrade path) rather than a transient storage failure."""

    text = _safe_text(message)
    return bool(text) and text in {
        cap_message(MAX_LEAGUES_FREE),
        cap_message(MAX_LEAGUES_PREMIUM),
    }


def cap_message(cap: int) -> str:
    """Customer-safe copy for a refused save. Never blames the user."""

    if int(cap) <= MAX_LEAGUES_FREE:
        return (
            "Free accounts keep one saved league. "
            "Upgrade to Premium to manage all of your leagues here."
        )
    return (
        f"You've reached the saved-league limit ({int(cap)}). "
        "Remove a saved league before adding another."
    )

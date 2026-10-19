"""Saved leagues — how many leagues one account may keep, by entitlement.

One authority for the cap so the web app (modules.account_ui's "Save
league" / the automatic context persist) and the mobile API
(services.mobile_api_service's POST /v1/leagues/save) cannot disagree:
a limit enforced on only one surface is not a limit at all.

Three tiers now (modules.premium.FREE / PRO / FRONT_OFFICE):
  Free: MAX_LEAGUES_FREE (1).
  Pro: MAX_LEAGUES_PRO (5).
  Front Office: unlimited — max_leagues_for() returns None, callers must
  treat None as "no cap" rather than a sentinel large int.

Preference storage only — this module never touches valuations, rankings,
recommendations, or any football truth. Saving a league stores a pointer to
a Sleeper league the user already owns; it never changes that league.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from modules import premium


LEAGUES_TABLE = "saved_leagues"

# Free accounts keep one league — adding a second is the upgrade wall.
MAX_LEAGUES_FREE = 1
# GM Pro: "Up to 5 leagues" per the pricing spec.
MAX_LEAGUES_PRO = 5
# Back-compat alias — some older call sites/tests still read this name.
# Front Office is the actually-unlimited tier now; this finite number only
# describes what Pro gets.
MAX_LEAGUES_PREMIUM = MAX_LEAGUES_PRO
# Front Office is genuinely unlimited. Used only as the `cap` sentinel in
# legacy integer-returning call sites that predate `max_leagues_for`'s
# `None` — large enough that no real account will ever reach it, but this
# is a runaway-write guard, not a product limit.
MAX_LEAGUES_FRONT_OFFICE_GUARD = 100_000


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def normalize_league_id(value: Any) -> str:
    return _safe_text(value)


def max_leagues_for(entitlement: Any) -> int | None:
    """Cap for an already-resolved entitlement string. None = unlimited.

    The canonical API dependent workstreams (paywall triggers, mobile)
    should call. Front Office returns None rather than a large finite
    number — callers must check for that before doing cap arithmetic.
    """

    tier = premium.canonical_tier(entitlement)
    # coridian_, 2026-10-19: "go ahead and do that until we have enough
    # features to segregate between pro and front office" -- unlimited
    # saved leagues was the one real functional difference Front Office
    # ever had over Pro (everything else was copy, not a gate). Folding it
    # into Pro too is a temporary simplification while there's no real
    # feature split to justify two paid tiers, not a permanent merge --
    # see modules.premium's own FRONT_OFFICE tier, left intact for when
    # that changes. The single already-subscribed Front Office customer
    # is unaffected either way (still reads as FRONT_OFFICE here).
    if tier in (premium.PRO, premium.FRONT_OFFICE):
        return None
    return MAX_LEAGUES_FREE


def can_add_league(entitlement: Any, current_league_count: int) -> bool:
    """True when one more league would still be within the plan's cap."""

    cap = max_leagues_for(entitlement)
    if cap is None:
        return True
    return int(current_league_count or 0) < cap


def max_leagues_for_entitlement(entitlement: Any) -> int:
    """Back-compat integer-returning cap ("free"/"premium"/"pro"/"front_office").

    Existing callers (services.mobile_api_service's wire `cap` field,
    account_ui's pre-save check) expect a finite int, not Optional[int].
    Front Office's actual "no cap" is represented by
    MAX_LEAGUES_FRONT_OFFICE_GUARD here — large enough no real account
    hits it. New call sites should prefer `max_leagues_for`, which returns
    the real `None` for Front Office.
    """

    cap = max_leagues_for(entitlement)
    return MAX_LEAGUES_FRONT_OFFICE_GUARD if cap is None else cap


def max_leagues_for_session(session: Mapping[str, Any] | None) -> int:
    """Cap for a Streamlit session, resolved through the same entitlement
    chain every other web gate uses (modules.premium)."""

    return max_leagues_for_entitlement(
        premium.get_user_entitlement(session_state=dict(session or {}))
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

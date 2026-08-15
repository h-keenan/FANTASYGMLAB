"""Hard session isolation for account / league identity.

Prevents account-derived league/roster/workspace identity from appearing in
anonymous Streamlit sessions. Process-global caches may still hold football
frames keyed by league_id after an authorized session requests them — they must
never invent a selected league for a different session.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Mapping, MutableMapping

from modules import auth_supabase

# Provenance for selected_league when the session is unsigned.
# - explicit_import: user imported/selected a Sleeper league in THIS session
# - auth_resume: set while authenticated (cleared on logout)
# Missing/other + unsigned + league present ⇒ treat as leak and strip.
GUEST_LEAGUE_ORIGIN_KEY = "_guest_league_origin"
GUEST_LEAGUE_ORIGIN_EXPLICIT = "explicit_import"
GUEST_LEAGUE_ORIGIN_AUTH = "auth_resume"

# Safe diagnostic snapshot (founder/debug / startup milestone detail only).
ISOLATION_DIAGNOSTICS_KEY = "_session_isolation_diagnostics"


def _safe_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def digest_identity(value: object, *, prefix: str = "") -> str:
    """Return a short non-reversible digest, or NONE when empty."""

    text = _safe_text(value)
    if not text:
        return "NONE"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}{digest}" if prefix else digest


def mark_explicit_guest_league_import(state: MutableMapping[str, Any]) -> None:
    """Record that the current league was chosen in this guest/browser session."""

    state[GUEST_LEAGUE_ORIGIN_KEY] = GUEST_LEAGUE_ORIGIN_EXPLICIT


def mark_authenticated_league_resume(state: MutableMapping[str, Any]) -> None:
    """Record that the current league came from an authenticated account resume."""

    state[GUEST_LEAGUE_ORIGIN_KEY] = GUEST_LEAGUE_ORIGIN_AUTH


def clear_guest_league_origin(state: MutableMapping[str, Any]) -> None:
    state.pop(GUEST_LEAGUE_ORIGIN_KEY, None)


def _strip_league_workspace(state: MutableMapping[str, Any]) -> None:
    for key in (
        "selected_league_id",
        "selected_league_name",
        "my_roster_id",
        "selected_team_roster_id",
        "selected_team_name",
        "active_league_context",
        "account_saved_leagues_cache",
        "last_league_option_id",
        "leagues_for_user",
        "leagues_for_user_username",
        "username",
        "_identity_established",
        "_league_selection_established",
        "_persisted_account_context_fingerprint",
    ):
        state.pop(key, None)
    clear_guest_league_origin(state)
    for key in list(state.keys()):
        text = str(key)
        if text.startswith("_league_"):
            state.pop(key, None)
        if text.startswith("_supabase_auto_resume_attempted_"):
            state.pop(key, None)


def enforce_anonymous_account_league_boundary(
    state: MutableMapping[str, Any],
) -> dict[str, Any]:
    """Strip account-derived league when the session is unsigned.

    Guest leagues are allowed only when this session explicitly imported/selected
    one (GUEST_LEAGUE_ORIGIN_EXPLICIT). Auth-resume provenance is invalid once
    account identity is NONE.
    """

    user_id = auth_supabase.current_user_id(state)
    league_id = _safe_text(state.get("selected_league_id"))
    origin = _safe_text(state.get(GUEST_LEAGUE_ORIGIN_KEY))
    result: dict[str, Any] = {
        "authenticated": bool(user_id),
        "had_league": bool(league_id),
        "origin": origin or "NONE",
        "stripped": False,
        "prior_league_digest": digest_identity(league_id),
    }
    if user_id:
        # Authenticated sessions own their league via auto-resume / explicit select.
        if league_id and origin != GUEST_LEAGUE_ORIGIN_AUTH:
            # Keep explicit guest import marker only until first auth resume/select.
            if origin != GUEST_LEAGUE_ORIGIN_EXPLICIT:
                mark_authenticated_league_resume(state)
                result["origin"] = GUEST_LEAGUE_ORIGIN_AUTH
        return result

    # Unsigned: account-derived or unexplained league must not survive.
    if league_id and origin != GUEST_LEAGUE_ORIGIN_EXPLICIT:
        _strip_league_workspace(state)
        result["stripped"] = True
        result["origin"] = "NONE"
        return result

    # Unsigned with no selected league: drop stale identity sentinels that could
    # re-open legacy disk restore paths. Keep them when this session already has
    # an in-progress guest lookup (username + league list, picker not yet chosen).
    if not league_id:
        has_guest_lookup = bool(_safe_text(state.get("username"))) and bool(
            state.get("leagues_for_user")
        )
        if not has_guest_lookup:
            state.pop("_identity_established", None)
            state.pop("_league_selection_established", None)
        if origin == GUEST_LEAGUE_ORIGIN_AUTH:
            clear_guest_league_origin(state)
            result["origin"] = "NONE"
    return result


def build_isolation_diagnostics(
    state: Mapping[str, Any],
    *,
    restore_phase: str = "",
    league_source: str = "",
) -> dict[str, Any]:
    """Diagnostics-only snapshot — never includes email/token/league name."""

    user_id = auth_supabase.current_user_id(state)
    league_id = _safe_text(state.get("selected_league_id"))
    roster_id = _safe_text(state.get("my_roster_id"))
    startup_session_id = _safe_text(state.get("_startup_session_id"))
    streamlit_session = ""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        ctx = get_script_run_ctx()
        streamlit_session = _safe_text(getattr(ctx, "session_id", "") if ctx else "")
    except Exception:
        streamlit_session = ""

    return {
        "streamlit_session_digest": digest_identity(streamlit_session),
        "startup_session_id": startup_session_id or "NONE",
        "account_digest": digest_identity(user_id) if user_id else "NONE",
        "auth_restore_phase": _safe_text(restore_phase) or _safe_text(
            state.get("_auth_restore_phase")
        )
        or "NONE",
        "selected_league_digest": digest_identity(league_id),
        "roster_digest": digest_identity(roster_id),
        "league_source": _safe_text(league_source) or _safe_text(
            state.get(GUEST_LEAGUE_ORIGIN_KEY)
        )
        or ("session" if league_id else "NONE"),
        "guest_league_origin": _safe_text(state.get(GUEST_LEAGUE_ORIGIN_KEY)) or "NONE",
        "process_id": os.getpid(),
        "identity_established": bool(state.get("_identity_established")),
        "league_selection_established": bool(state.get("_league_selection_established")),
    }


def record_isolation_diagnostics(
    state: MutableMapping[str, Any],
    *,
    restore_phase: str = "",
    league_source: str = "",
) -> dict[str, Any]:
    snapshot = build_isolation_diagnostics(
        state,
        restore_phase=restore_phase,
        league_source=league_source,
    )
    state[ISOLATION_DIAGNOSTICS_KEY] = snapshot
    return snapshot


def anonymous_must_not_carry_account_league(state: Mapping[str, Any]) -> bool:
    """Invariant helper for tests: unsigned ⇒ no league unless explicit guest import."""

    if auth_supabase.current_user_id(state):
        return True
    league_id = _safe_text(state.get("selected_league_id"))
    if not league_id:
        return True
    return _safe_text(state.get(GUEST_LEAGUE_ORIGIN_KEY)) == GUEST_LEAGUE_ORIGIN_EXPLICIT

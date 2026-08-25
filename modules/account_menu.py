"""Authenticated You-menu identity. Live session only — never leftover profile."""

from __future__ import annotations

from typing import Any, Mapping

from modules import auth_supabase
from modules import founder_labs
from modules import founder_ops


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def live_signed_in_email(session_state: Mapping[str, Any] | None) -> str:
    """Email from the live signed-in session. Empty when not signed in."""

    state = session_state if isinstance(session_state, Mapping) else {}
    if not auth_supabase.session_is_signed_in(state):
        return ""
    email = _safe_text(state.get(auth_supabase.AUTH_EMAIL_KEY))
    if email:
        return email
    user = state.get(auth_supabase.AUTH_USER_KEY)
    if isinstance(user, Mapping):
        return _safe_text(user.get("email"))
    return ""


def account_identity(
    session_state: Mapping[str, Any] | None,
    *,
    entitlement_label: str = "",
    environ: Mapping[str, Any] | None = None,
    secrets: Any = None,
) -> dict[str, Any]:
    state = session_state if isinstance(session_state, Mapping) else {}
    signed_in = auth_supabase.session_is_signed_in(state)
    labs = bool(
        signed_in
        and founder_labs.founder_labs_authorized(
            state, environ=environ, secrets=secrets
        )
    )
    ops = bool(
        signed_in
        and founder_ops.founder_ops_authorized(
            state, environ=environ, secrets=secrets
        )
    )
    entitlement = _safe_text(entitlement_label, "Free") or "Free"
    if not signed_in:
        return {
            "signed_in": False,
            "display_identity": "",
            "entitlement_label": entitlement,
            "founder_labs": False,
            "founder_ops": False,
            "internal_badge": False,
        }
    return {
        "signed_in": True,
        "display_identity": live_signed_in_email(state) or "Signed-in account",
        "entitlement_label": entitlement,
        "founder_labs": labs,
        "founder_ops": ops,
        "internal_badge": labs or ops,
    }

"""Integration: enumeration-safe auth (#279) + welcome hierarchy (#280)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules import auth_supabase


ROOT = Path(__file__).resolve().parents[1]
AUTH = (ROOT / "modules" / "auth_supabase.py").read_text(encoding="utf-8")


def _new_unconfirmed_payload() -> dict:
    return {
        "id": "user-new",
        "email": "fresh@example.com",
        "email_confirmed_at": None,
        "confirmation_sent_at": "2026-08-12T20:00:00Z",
        "identities": [
            {
                "id": "ident-1",
                "user_id": "user-new",
                "provider": "email",
            }
        ],
    }


def _obfuscated_existing_confirmed_payload() -> dict:
    return {
        "id": "user-fake",
        "email": "existing@example.com",
        "email_confirmed_at": None,
        "confirmation_sent_at": "2026-08-12T20:00:00Z",
        "identities": [],
    }


def test_b_genuinely_new_signup_definite_pending_copy():
    """B. New signup → pending + definite copy when evidence permits."""

    payload = _new_unconfirmed_payload()
    assert (
        auth_supabase.classify_signup_confirmation_evidence(payload)
        == "definite_new_unconfirmed"
    )
    state: dict = {}
    pending = auth_supabase.enter_pending_email_confirmation(
        state, "fresh@example.com", payload=payload
    )
    assert pending["confirmation_sent"] is True
    assert pending["confirmation_evidence"] == "definite_new_unconfirmed"
    assert not auth_supabase.current_user_id(state)
    copy = auth_supabase.pending_confirmation_copy(
        evidence="definite_new_unconfirmed", email_masked="f***@example.com"
    )
    assert "We sent a confirmation link" in copy["body_html"]
    assert copy["title"] == "Check your email"


def test_diagnostics_do_not_encode_existence():
    state: dict = {}
    with patch.object(auth_supabase, "log_auth_operation_diagnostic") as diag:
        auth_supabase.enter_pending_email_confirmation(
            state, "existing@example.com", payload=_obfuscated_existing_confirmed_payload()
        )
        auth_supabase.enter_pending_email_confirmation(
            state, "fresh@example.com", payload=_new_unconfirmed_payload()
        )
    codes = [c.kwargs.get("error_code") for c in diag.call_args_list]
    assert codes == ["pending_confirmation", "pending_confirmation"]
    assert [c.kwargs.get("auth_user_created") for c in diag.call_args_list] == [
        False,
        False,
    ]

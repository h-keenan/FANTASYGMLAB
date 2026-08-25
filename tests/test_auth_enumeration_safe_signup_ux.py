"""Enumeration-safe signup confirmation UX — no false “email sent” claims."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from modules import account_ui
from modules import auth_supabase
from modules import session_isolation


def _new_unconfirmed_payload(*, with_identities: bool = True) -> dict:
    user = {
        "id": "user-new",
        "email": "fresh@example.com",
        "email_confirmed_at": None,
        "confirmation_sent_at": "2026-08-12T20:00:00Z",
        "aud": "authenticated",
        "role": "authenticated",
    }
    if with_identities:
        user["identities"] = [
            {
                "id": "ident-1",
                "user_id": "user-new",
                "identity_data": {"email": "fresh@example.com"},
                "provider": "email",
            }
        ]
    return user


def _obfuscated_existing_confirmed_payload() -> dict:
    """Supabase anti-enumeration shape for an email that already has a confirmed account."""

    return {
        "id": "user-fake",
        "email": "existing@example.com",
        "email_confirmed_at": None,
        "confirmation_sent_at": "2026-08-12T20:00:00Z",
        "aud": "authenticated",
        "role": "authenticated",
        "identities": [],
    }


def _existing_unconfirmed_payload() -> dict:
    return {
        "id": "user-unconf",
        "email": "pending@example.com",
        "email_confirmed_at": None,
        "confirmation_sent_at": "2026-08-12T20:05:00Z",
        "identities": [
            {
                "id": "ident-2",
                "user_id": "user-unconf",
                "provider": "email",
            }
        ],
    }


def test_classify_definite_new_unconfirmed_with_identities():
    payload = _new_unconfirmed_payload(with_identities=True)
    assert auth_supabase.classify_signup_confirmation_evidence(payload) == (
        "definite_new_unconfirmed"
    )
    assert auth_supabase.signup_requires_email_confirmation(payload) is True


def test_classify_definite_bare_user_without_identities_field():
    payload = _new_unconfirmed_payload(with_identities=False)
    assert "identities" not in payload
    assert auth_supabase.classify_signup_confirmation_evidence(payload) == (
        "definite_new_unconfirmed"
    )


def test_classify_obfuscated_existing_confirmed_is_ambiguous():
    payload = _obfuscated_existing_confirmed_payload()
    assert auth_supabase.classify_signup_confirmation_evidence(payload) == "ambiguous"
    assert auth_supabase.signup_requires_email_confirmation(payload) is True
    assert auth_supabase.session_is_authenticated_for_app(payload) is False


def test_classify_existing_unconfirmed_has_dispatch_evidence():
    payload = _existing_unconfirmed_payload()
    assert auth_supabase.classify_signup_confirmation_evidence(payload) == (
        "definite_new_unconfirmed"
    )


def test_pending_copy_ambiguous_never_claims_sent():
    copy = auth_supabase.pending_confirmation_copy(
        evidence="ambiguous", email_masked="e***@example.com"
    )
    assert copy["title"] == "Check your email"
    assert "If an account can be created" in copy["body_html"]
    assert "sign in instead" in copy["body_html"].casefold()
    assert "We sent a confirmation" not in copy["body_html"]
    assert copy["sent_claimed"] == "false"
    assert "If a confirmation can be sent" in copy["resend_success"]


def test_pending_copy_definite_may_claim_sent():
    copy = auth_supabase.pending_confirmation_copy(
        evidence="definite_new_unconfirmed", email_masked="f***@example.com"
    )
    assert "We sent a confirmation link" in copy["body_html"]
    assert copy["sent_claimed"] == "true"


def test_enter_pending_obfuscated_does_not_set_confirmation_sent():
    state: dict = {}
    pending = auth_supabase.enter_pending_email_confirmation(
        state,
        "existing@example.com",
        payload=_obfuscated_existing_confirmed_payload(),
    )
    assert pending["confirmation_sent"] is False
    assert pending["confirmation_evidence"] == "ambiguous"
    assert pending["auth_user_created"] is False
    assert auth_supabase.current_user_id(state) == ""
    assert state.get(auth_supabase.ACCOUNT_MODE_KEY) == "guest"


def test_enter_pending_new_user_sets_confirmation_sent():
    state: dict = {}
    pending = auth_supabase.enter_pending_email_confirmation(
        state,
        "fresh@example.com",
        payload=_new_unconfirmed_payload(),
    )
    assert pending["confirmation_sent"] is True
    assert pending["confirmation_evidence"] == "definite_new_unconfirmed"


def test_ui_obfuscated_signup_uses_safe_copy_and_sign_in_cta():
    config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
    state: dict = {}
    auth_supabase.enter_pending_email_confirmation(
        state,
        "existing@example.com",
        payload=_obfuscated_existing_confirmed_payload(),
    )
    button_labels: list[str] = []

    def _button(label, **_kwargs):
        button_labels.append(str(label))
        return False

    with patch.object(account_ui.st, "session_state", state), patch.object(
        account_ui.st, "markdown"
    ) as markdown, patch.object(account_ui.st, "button", side_effect=_button), patch.object(
        account_ui.st, "caption"
    ), patch.object(account_ui.st, "success"), patch.object(account_ui.st, "warning"), patch.object(
        account_ui.st, "info"
    ):
        actions = account_ui.render_mobile_auth_entry(config=config)
    html = " ".join(str(c.args[0]) for c in markdown.call_args_list if c.args)
    assert "Check your email" in html
    assert "If an account can be created" in html
    assert "We sent a confirmation" not in html
    assert "Already have an account? Sign in" in button_labels
    assert "Use a different email" in button_labels
    assert "Continue without an account" in button_labels
    assert actions["logged_in"] is False


def test_ui_new_signup_may_claim_sent():
    config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
    state: dict = {}
    auth_supabase.enter_pending_email_confirmation(
        state,
        "fresh@example.com",
        payload=_new_unconfirmed_payload(),
    )
    with patch.object(account_ui.st, "session_state", state), patch.object(
        account_ui.st, "markdown"
    ) as markdown, patch.object(account_ui.st, "button", return_value=False), patch.object(
        account_ui.st, "caption"
    ), patch.object(account_ui.st, "info"):
        account_ui.render_mobile_auth_entry(config=config)
    html = " ".join(str(c.args[0]) for c in markdown.call_args_list if c.args)
    assert "We sent a confirmation link" in html


def test_resend_success_uses_safe_language():
    config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
    state: dict = {}
    auth_supabase.enter_pending_email_confirmation(
        state,
        "existing@example.com",
        payload=_obfuscated_existing_confirmed_payload(),
    )
    state["_confirm_resend_success"] = True
    with patch.object(account_ui.st, "session_state", state), patch.object(
        account_ui.st, "markdown"
    ) as markdown, patch.object(account_ui.st, "button", return_value=False), patch.object(
        account_ui.st, "caption"
    ), patch.object(account_ui.st, "info"):
        account_ui.render_confirmation_required_card(
            config=config, email="existing@example.com", key_prefix="enum"
        )
    html = " ".join(str(c.args[0]) for c in markdown.call_args_list if c.args)
    assert "Confirmation email sent" not in html
    assert "If a confirmation can be sent" in html


def test_malformed_email_and_weak_password_do_not_enter_pending():
    config = {"enabled": True, "url": "https://proj.supabase.co", "anon_key": "sb_publishable_x"}

    bad_email = MagicMock()
    bad_email.status_code = 400
    bad_email.text = '{"error_code":"validation_failed","msg":"Unable to validate email address: invalid format"}'
    bad_email.json.return_value = {
        "error_code": "validation_failed",
        "msg": "Unable to validate email address: invalid format",
    }

    weak = MagicMock()
    weak.status_code = 422
    weak.text = '{"error_code":"weak_password","msg":"Password should be at least 6 characters."}'
    weak.json.return_value = {
        "error_code": "weak_password",
        "msg": "Password should be at least 6 characters.",
    }

    with patch("modules.auth_supabase.requests.post", return_value=bad_email), patch(
        "modules.auth_supabase.email_redirect_to",
        return_value="https://app.fantasygmlab.com",
    ):
        payload, error = auth_supabase.sign_up(config, "not-an-email", "StrongPass1!")
    assert payload is None
    assert error
    assert auth_supabase.signup_requires_email_confirmation(payload) is False

    with patch("modules.auth_supabase.requests.post", return_value=weak), patch(
        "modules.auth_supabase.email_redirect_to",
        return_value="https://app.fantasygmlab.com",
    ):
        payload, error = auth_supabase.sign_up(config, "ok@example.com", "123")
    assert payload is None
    assert error
    assert "password" in auth_supabase.signup_user_message(error).casefold() or error


def test_provider_error_does_not_claim_email_sent():
    config = {"enabled": True, "url": "https://proj.supabase.co", "anon_key": "sb_publishable_x"}
    boom = MagicMock()
    boom.status_code = 500
    boom.text = '{"msg":"unexpected_failure"}'
    boom.json.return_value = {"msg": "unexpected_failure"}
    with patch("modules.auth_supabase.requests.post", return_value=boom), patch(
        "modules.auth_supabase.email_redirect_to",
        return_value="https://app.fantasygmlab.com",
    ):
        payload, error = auth_supabase.sign_up(config, "ok@example.com", "StrongPass1!")
    assert payload is None
    assert error
    state: dict = {}
    # Errors must not flip into pending “we sent” UX.
    assert not auth_supabase.is_pending_email_confirmation(state)


def test_diagnostics_do_not_encode_user_existence():
    state: dict = {}
    with patch.object(auth_supabase, "log_auth_operation_diagnostic") as diag:
        auth_supabase.enter_pending_email_confirmation(
            state,
            "existing@example.com",
            payload=_obfuscated_existing_confirmed_payload(),
        )
        auth_supabase.enter_pending_email_confirmation(
            state,
            "fresh@example.com",
            payload=_new_unconfirmed_payload(),
        )
    codes = [c.kwargs.get("error_code") for c in diag.call_args_list]
    assert codes == ["pending_confirmation", "pending_confirmation"]
    created = [c.kwargs.get("auth_user_created") for c in diag.call_args_list]
    assert created == [False, False]


def test_anonymous_isolation_preserved_for_ambiguous_pending():
    state = {
        "selected_league_id": "league-a",
        "selected_league_name": "League A",
    }
    auth_supabase.enter_pending_email_confirmation(
        state,
        "existing@example.com",
        payload=_obfuscated_existing_confirmed_payload(),
    )
    result = session_isolation.enforce_anonymous_account_league_boundary(state)
    assert result["stripped"] is True
    assert not auth_supabase.current_user_id(state)


def test_signup_http_obfuscated_existing_enters_ambiguous_pending():
    config = {"enabled": True, "url": "https://proj.supabase.co", "anon_key": "sb_publishable_x"}
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = _obfuscated_existing_confirmed_payload()
    with patch("modules.auth_supabase.requests.post", return_value=mock_response), patch(
        "modules.auth_supabase.email_redirect_to",
        return_value="https://app.fantasygmlab.com",
    ):
        payload, error = auth_supabase.sign_up(
            config, "existing@example.com", "StrongPass1!"
        )
    assert error == ""
    state: dict = {}
    auth_supabase.enter_pending_email_confirmation(
        state, "existing@example.com", payload=payload
    )
    pending = state[auth_supabase.PENDING_EMAIL_CONFIRMATION_KEY]
    assert pending["confirmation_evidence"] == "ambiguous"
    assert pending["confirmation_sent"] is False

"""Integration: enumeration-safe auth (#279) + welcome hierarchy (#280)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules import account_ui
from modules import app_styles
from modules import auth_supabase
from modules import marketing_landing
from modules import session_isolation


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
ACCOUNT = (ROOT / "modules" / "account_ui.py").read_text(encoding="utf-8")
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


def test_a_cold_guest_landing_funnel_and_no_live_header():
    """A. Cold guest landing → welcome funnel clean, no live executive header."""

    landing = (ROOT / "modules" / "marketing_landing.py").read_text(encoding="utf-8")
    cold = landing.split("def render_marketing_landing(", 1)[1].split(
        "def render_marketing_landing_deferred(", 1
    )[0]
    assert "landing_primary_cta" in cold
    assert "landing_secondary_cta" in cold
    assert "landing_pricing_cta" not in cold
    assert marketing_landing.PRIMARY_CTA_LABEL == "Import your league"
    assert "render_marketing_landing_deferred()" in APP
    # Guest no-league skips live executive topbar.
    assert "_guest_landing_without_workspace" in APP
    gate_idx = APP.index("if not _guest_landing_without_workspace:")
    assert "render_platform_topbar(" in APP[gate_idx : gate_idx + 240]
    assert "PRIMARY_CTA_LABEL" in cold or "Import your league" in marketing_landing.PRIMARY_CTA_LABEL


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


def test_c_existing_confirmed_signup_enumeration_safe():
    """C. Existing confirmed email → ambiguous pending + Sign in CTA."""

    payload = _obfuscated_existing_confirmed_payload()
    assert auth_supabase.classify_signup_confirmation_evidence(payload) == "ambiguous"
    state: dict = {}
    pending = auth_supabase.enter_pending_email_confirmation(
        state, "existing@example.com", payload=payload
    )
    assert pending["confirmation_sent"] is False
    assert pending["confirmation_evidence"] == "ambiguous"
    copy = auth_supabase.pending_confirmation_copy(
        evidence="ambiguous", email_masked="e***@example.com"
    )
    assert "If an account can be created" in copy["body_html"]
    assert "We sent a confirmation" not in copy["body_html"]
    assert "Already have an account? Sign in" in ACCOUNT

    button_labels: list[str] = []

    def _button(label, **_kwargs):
        button_labels.append(str(label))
        return False

    with patch.object(account_ui.st, "session_state", state), patch.object(
        account_ui.st, "markdown"
    ) as markdown, patch.object(account_ui.st, "button", side_effect=_button), patch.object(
        account_ui.st, "caption"
    ), patch.object(account_ui.st, "info"), patch.object(account_ui.st, "success"), patch.object(
        account_ui.st, "warning"
    ):
        account_ui.render_mobile_auth_entry(
            config={"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        )
    html = " ".join(str(c.args[0]) for c in markdown.call_args_list if c.args)
    assert "If an account can be created" in html
    assert "We sent a confirmation" not in html
    assert "Already have an account? Sign in" in button_labels


def test_d_pending_confirmation_owns_account_slot_import_reachable():
    """D. Pending + welcome layout → confirmation owns slot; no duplicate account card."""

    state: dict = {}
    auth_supabase.enter_pending_email_confirmation(
        state,
        "existing@example.com",
        payload=_obfuscated_existing_confirmed_payload(),
    )
    markdown_html: list[str] = []

    def _markdown(body, **_kwargs):
        markdown_html.append(str(body))

    with patch.object(account_ui.st, "session_state", state), patch.object(
        account_ui.st, "markdown", side_effect=_markdown
    ), patch.object(account_ui.st, "button", return_value=False), patch.object(
        account_ui.st, "caption"
    ), patch.object(account_ui.st, "info"), patch.object(account_ui.st, "success"), patch.object(
        account_ui.st, "warning"
    ):
        actions = account_ui.render_mobile_auth_entry(
            config={"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        )
    joined = " ".join(markdown_html)
    assert "account-confirm-card" in joined or "Check your email" in joined
    assert "Guest · import next" not in joined
    assert "Save your leagues" not in joined
    assert "Save leagues later" not in joined
    assert joined.count("launch-account-intro") == 0
    assert actions["logged_in"] is False
    # Import panel remains wired after account entry in launch screen.
    launch = APP.split("def render_home_launch_screen", 1)[1].split("\ndef ", 1)[0]
    assert "render_platform_import_panel" in launch
    assert "fgl-import-league" in (
        ROOT / "modules" / "platform_import_ui.py"
    ).read_text(encoding="utf-8")


def test_e_continue_as_guest_from_confirmation_stays_unsigned():
    """E. Continue as guest from confirmation → unsigned, no league restore."""

    state = {
        "selected_league_id": "league-a",
        "selected_league_name": "League A",
        "account_saved_leagues_cache": [{"league_id": "league-a"}],
    }
    auth_supabase.enter_pending_email_confirmation(
        state,
        "existing@example.com",
        payload=_obfuscated_existing_confirmed_payload(),
    )

    def _button(label, **_kwargs):
        return str(label) == "Continue as guest"

    with patch.object(account_ui.st, "session_state", state), patch.object(
        account_ui.st, "markdown"
    ), patch.object(account_ui.st, "button", side_effect=_button), patch.object(
        account_ui.st, "caption"
    ), patch.object(account_ui.st, "info"), patch.object(account_ui.st, "success"), patch.object(
        account_ui.st, "warning"
    ), patch.object(account_ui.st, "rerun"):
        actions = account_ui.render_mobile_auth_entry(
            config={"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        )
    assert actions["continue_guest"] is True
    assert not auth_supabase.current_user_id(state)
    assert auth_supabase.is_pending_email_confirmation(state) is False
    # Anonymous isolation still strips league context for unsigned.
    state["selected_league_id"] = "league-a"
    result = session_isolation.enforce_anonymous_account_league_boundary(state)
    assert result["stripped"] is True
    assert actions.get("resume_league") in (None, False, {})


def test_f_confirmed_callback_clears_pending_and_authenticates():
    """F. Confirmed callback → pending clears, authenticated, single header contract."""

    state: dict = {}
    auth_supabase.enter_pending_email_confirmation(
        state, "a@b.c", payload=_new_unconfirmed_payload()
    )
    payload = {
        "access_token": "tok",
        "refresh_token": "ref",
        "user": {
            "id": "u1",
            "email": "a@b.c",
            "email_confirmed_at": "2026-08-12T22:00:00Z",
        },
    }
    auth_supabase.apply_auth_payload(state, payload)
    assert auth_supabase.current_user_id(state) == "u1"
    assert auth_supabase.is_pending_email_confirmation(state) is False
    # Authenticated users are not on guest-no-league landing → topbar mounts once.
    assert APP.count("render_platform_topbar(") >= 1
    assert '_executive_command_header_mounted"] = True' in APP
    assert "fgl-landing" not in app_styles.APP_CSS  # landing CSS stays out of APP_CSS


def test_copy_ownership_is_canonical():
    """Confirmation / ambiguous / resend / CTA labels have one owner."""

    assert "def pending_confirmation_copy" in AUTH
    assert ACCOUNT.count("We sent a confirmation link") == 0
    assert "pending_confirmation_copy" in ACCOUNT
    assert marketing_landing.PRIMARY_CTA_LABEL == "Import your league"
    assert marketing_landing.SECONDARY_CTA_LABEL == "See how it works"
    assert "Save your leagues" in ACCOUNT
    assert "Guest · import next" not in ACCOUNT
    assert "If a confirmation can be sent" in AUTH


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

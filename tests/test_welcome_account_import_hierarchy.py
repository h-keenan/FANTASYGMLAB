"""Welcome / account / import hierarchy — final launch IA pass."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules import account_ui
from modules import app_styles
from modules import auth_supabase
from modules import marketing_landing
from modules import marketing_landing_styles


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
ACCOUNT = (ROOT / "modules" / "account_ui.py").read_text(encoding="utf-8")
LANDING = (ROOT / "modules" / "marketing_landing.py").read_text(encoding="utf-8")
IMPORT_UI = (ROOT / "modules" / "platform_import_ui.py").read_text(encoding="utf-8")
GUEST = (ROOT / "modules" / "guest_conversion.py").read_text(encoding="utf-8")
STATIC = (ROOT / "static" / "landing" / "index.html").read_text(encoding="utf-8")


def test_launch_section_order_is_hero_import_account_deferred():
    launch = APP.split("def render_home_launch_screen", 1)[1].split("\ndef ", 1)[0]
    assert "render_marketing_landing()" in launch
    assert "render_platform_import_panel" in launch
    assert "render_mobile_auth_entry" in launch
    assert "render_marketing_landing_deferred()" in launch
    assert launch.index("render_platform_import_panel") < launch.index(
        "render_mobile_auth_entry"
    )
    assert launch.index("render_mobile_auth_entry") < launch.index(
        "render_marketing_landing_deferred()"
    )


def test_early_guest_path_paints_hero_only_before_import():
    early = APP.split("_guest_landing_without_workspace", 1)[1].split(
        "st.session_state[\"_guest_landing_without_workspace\"]", 1
    )[0]
    assert "render_marketing_landing()" in early
    assert "render_mobile_auth_entry" not in early


def test_no_duplicate_next_guidance():
    cold = LANDING.split("def render_marketing_landing(", 1)[1].split(
        "def render_marketing_landing_deferred(", 1
    )[0]
    assert "Next —" not in cold
    assert "fgl-landing__focus-note" not in cold
    assert "Next step" not in IMPORT_UI
    assert "Next —" not in STATIC


def test_cold_account_is_collapsed_create_and_sign_in():
    state: dict = {"launch_auth_mode": "guest"}
    labels: list[str] = []

    def _button(label, **_kwargs):
        labels.append(str(label))
        return False

    cols = [MagicMock(), MagicMock()]
    for col in cols:
        col.__enter__ = MagicMock(return_value=col)
        col.__exit__ = MagicMock(return_value=False)

    with patch.object(account_ui.st, "session_state", state), patch.object(
        account_ui.st, "markdown"
    ), patch.object(account_ui.st, "button", side_effect=_button), patch.object(
        account_ui.st, "columns", return_value=cols
    ), patch.object(account_ui.st, "caption"), patch.object(
        account_ui.st, "info"
    ), patch.object(account_ui.st, "success"), patch.object(account_ui.st, "warning"):
        actions = account_ui.render_mobile_auth_entry(
            config={"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        )
    assert actions["continue_guest"] is True
    assert "Create account" in labels
    assert "Sign in" in labels
    assert "Continue as guest" not in labels
    assert "Continue as guest instead" not in labels
    assert "Create account / Sign in" not in labels


def test_create_account_form_expands_with_confirmation_copy():
    state: dict = {"launch_auth_mode": "account", "launch_account_form": "create"}
    markdown: list[str] = []
    labels: list[str] = []

    def _button(label, **_kwargs):
        labels.append(str(label))
        return False

    with patch.object(account_ui.st, "session_state", state), patch.object(
        account_ui.st, "markdown", side_effect=lambda body, **_k: markdown.append(str(body))
    ), patch.object(account_ui.st, "button", side_effect=_button), patch.object(
        account_ui.st, "text_input", return_value=""
    ), patch.object(account_ui.st, "caption"), patch.object(
        account_ui.st, "info"
    ), patch.object(account_ui.st, "success"), patch.object(account_ui.st, "warning"):
        account_ui.render_mobile_auth_entry(
            config={"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        )
    joined = " ".join(markdown)
    assert "We'll email you a confirmation link." in joined
    assert "inactive until you confirm" not in joined
    assert "Create account" in labels
    assert "Continue as guest" in labels
    assert "Continue as guest instead" not in labels


def test_pending_owns_account_slot_alone():
    state: dict = {}
    auth_supabase.enter_pending_email_confirmation(state, "user@example.com")
    markdown: list[str] = []

    with patch.object(account_ui.st, "session_state", state), patch.object(
        account_ui.st, "markdown", side_effect=lambda body, **_k: markdown.append(str(body))
    ), patch.object(account_ui.st, "button", return_value=False), patch.object(
        account_ui.st, "caption"
    ), patch.object(account_ui.st, "info"), patch.object(
        account_ui.st, "success"
    ), patch.object(account_ui.st, "warning"):
        account_ui.render_mobile_auth_entry(
            config={"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        )
    joined = " ".join(markdown)
    assert "Check your email" in joined or "account-confirm-card" in joined
    assert "Save your leagues" not in joined
    assert "data-fgl-optional-account" not in joined


def test_canonical_create_account_wording_no_sign_up_cta():
    assert "Create free account" not in ACCOUNT
    assert "Create free account" not in GUEST
    assert '"Sign up"' not in ACCOUNT
    assert "Sign up" not in STATIC
    assert marketing_landing.PRIMARY_CTA_LABEL == "Import your league"
    assert "Create account" in ACCOUNT
    assert "Sign in" in ACCOUNT


def test_import_copy_and_espn_demotion():
    assert "Enter your Sleeper username to load your leagues." in IMPORT_UI
    assert "ESPN experimental" in IMPORT_UI
    assert 'st.radio(' not in IMPORT_UI or "League platform" not in IMPORT_UI
    assert "Use ESPN experimental import" in IMPORT_UI
    assert "Next step" not in IMPORT_UI


def test_app_css_unchanged_landing_styles_local():
    assert len(app_styles.APP_CSS) < 400_000
    assert "fgl-landing__hero" not in app_styles.APP_CSS
    assert "launch-account-intro" in marketing_landing_styles.MARKETING_LANDING_CSS

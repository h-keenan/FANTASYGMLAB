"""Signed-out welcome IA: progressive import, CTA hierarchy, no eager providers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules import account_ui
from modules import marketing_landing
from modules import auth_supabase


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
LANDING = (ROOT / "modules" / "marketing_landing.py").read_text(encoding="utf-8")
IMPORT_UI = (ROOT / "modules" / "platform_import_ui.py").read_text(encoding="utf-8")
ACCOUNT = (ROOT / "modules" / "account_ui.py").read_text(encoding="utf-8")


def test_initial_signed_out_hides_import_until_chosen():
    assert not marketing_landing.welcome_import_open({})
    assert not marketing_landing.welcome_import_open({"launch_auth_mode": "guest"})
    assert marketing_landing.welcome_import_open({"landing_focus": "get_started"})
    assert marketing_landing.welcome_import_open({"landing_focus": "guest_import"})
    assert marketing_landing.welcome_import_open(
        {"leagues_for_user": [{"league_id": "1"}]}
    )
    signed = {
        auth_supabase.AUTH_USER_KEY: {"id": "u1", "email": "a@b.c"},
        auth_supabase.AUTH_SESSION_KEY: {
            "user_id": "u1",
            "access_token": "tok",
            "expires_at": 9999999999,
        },
    }
    assert marketing_landing.welcome_import_open(signed)
    launch = APP.split("def render_home_launch_screen", 1)[1].split("\ndef ", 1)[0]
    assert "signed_out_flow == \"import\"" in launch
    assert "elif show_import:" in launch


def test_import_cta_opens_sleeper_step():
    state: dict = {}
    col = MagicMock()
    col.__enter__ = MagicMock(return_value=col)
    col.__exit__ = MagicMock(return_value=False)

    def _button(label, **kwargs):
        return str(label) == marketing_landing.APP_PRIMARY_CTA_LABEL

    with patch.object(marketing_landing.st, "session_state", state), patch.object(
        marketing_landing.st, "markdown"
    ), patch.object(marketing_landing.st, "button", side_effect=_button), patch.object(
        marketing_landing.st, "columns", return_value=[col, col]
    ), patch.object(marketing_landing, "_track"), patch.object(marketing_landing.st, "rerun"), patch.object(
        marketing_landing.st, "caption"
    ):
        actions = marketing_landing.render_marketing_landing()
    assert actions["primary"] is True
    assert state.get("signed_out_entry") == "import"
    assert marketing_landing.welcome_import_open(state)


def test_sign_in_opens_account_panel_not_import():
    state: dict = {}
    col = MagicMock()
    col.__enter__ = MagicMock(return_value=col)
    col.__exit__ = MagicMock(return_value=False)

    def _button(label, **kwargs):
        return str(label) == marketing_landing.SECONDARY_CTA_LABEL

    with patch.object(marketing_landing.st, "session_state", state), patch.object(
        marketing_landing.st, "markdown"
    ), patch.object(marketing_landing.st, "button", side_effect=_button), patch.object(
        marketing_landing.st, "columns", return_value=[col, col]
    ), patch.object(marketing_landing, "_track"), patch.object(marketing_landing.st, "rerun"), patch.object(
        marketing_landing.st, "caption"
    ):
        actions = marketing_landing.render_marketing_landing()
    assert actions["secondary"] is True
    assert state.get("launch_account_form") == "signin"
    assert not marketing_landing.welcome_import_open(state)


def test_guest_cta_removed_from_welcome():
    assert "landing_guest_cta" not in LANDING.split("def render_marketing_landing(", 1)[1].split(
        "def auth_pending_owns_entry", 1
    )[0]


def test_hero_hides_duplicate_account_chooser():
    state: dict = {
        "launch_auth_mode": "guest",
        "_welcome_hero_signin_rendered": True,
    }
    labels: list[str] = []

    def _button(label, **_kwargs):
        labels.append(str(label))
        return False

    with patch.object(account_ui.st, "session_state", state), patch.object(
        account_ui.st, "markdown"
    ), patch.object(account_ui.st, "button", side_effect=_button), patch.object(
        account_ui.st, "columns", return_value=[]
    ), patch.object(account_ui.st, "caption"):
        account_ui.render_mobile_auth_entry(
            config={"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        )
    assert "Create account" not in labels
    assert "Sign in" not in labels


def test_create_and_sign_in_are_toggles_of_one_flow():
    assert "New here? Create account" in ACCOUNT
    assert "Already have an account? Sign in" in ACCOUNT


def test_espn_is_secondary_disclosure():
    assert "Other import options" in IMPORT_UI
    sleeper = IMPORT_UI.split("if platform != \"ESPN experimental\":", 1)[1].split(
        "actions[\"platform\"] = \"espn\"", 1
    )[0]
    assert "st.expander" in sleeper
    assert "ESPN — Experimental" in sleeper
    assert "Use ESPN experimental import" in sleeper


def test_cold_welcome_has_no_provider_or_sleeper_fetch():
    cold = LANDING.split("def render_marketing_landing(", 1)[1].split(
        "def render_marketing_landing_deferred(", 1
    )[0]
    assert "load_leagues_for_username" not in cold
    assert "requests." not in cold
    assert "get_espn_adapter" not in cold
    launch = APP.split("def render_home_launch_screen", 1)[1].split("\ndef ", 1)[0]
    assert "load_leagues_for_username" in launch
    assert "if submitted:" in launch
    assert launch.index("if submitted:") < launch.index("load_leagues_for_username")


def test_authenticated_users_still_see_import_when_unsigned_onboarding_would_hide_it():
    state = {
        auth_supabase.AUTH_USER_KEY: {"id": "u1"},
        auth_supabase.AUTH_SESSION_KEY: {
            "user_id": "u1",
            "access_token": "tok",
            "expires_at": 9999999999,
        },
    }
    assert marketing_landing.welcome_import_open(state)
    assert "welcome_import_open" in APP

"""Signed-out flow correction: focused states, guest import, no eager providers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules import account_menu
from modules import auth_supabase
from modules import founder_labs
from modules import marketing_landing
from modules import session_isolation


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
LANDING = (ROOT / "modules" / "marketing_landing.py").read_text(encoding="utf-8")
LANDING_CSS = (ROOT / "modules" / "marketing_landing_styles.py").read_text(encoding="utf-8")
IMPORT_UI = (ROOT / "modules" / "platform_import_ui.py").read_text(encoding="utf-8")
ACCOUNT = (ROOT / "modules" / "account_ui.py").read_text(encoding="utf-8")


def _click(label: str):
    def _button(text, **_kwargs):
        return str(text) == label

    return _button


def _render(state: dict, label: str = ""):
    col = MagicMock()
    col.__enter__ = MagicMock(return_value=col)
    col.__exit__ = MagicMock(return_value=False)
    markdown: list[str] = []
    with patch.object(marketing_landing.st, "session_state", state), patch.object(
        marketing_landing.st, "markdown", side_effect=lambda body, **_k: markdown.append(str(body))
    ), patch.object(
        marketing_landing.st, "button", side_effect=_click(label) if label else MagicMock(return_value=False)
    ), patch.object(marketing_landing.st, "columns", return_value=[col, col]), patch.object(
        marketing_landing, "_track"
    ), patch.object(marketing_landing.st, "rerun"):
        actions = marketing_landing.render_marketing_landing()
    return actions, "\n".join(markdown)


def test_welcome_flow_states_are_exclusive():
    assert marketing_landing.welcome_flow_state({}) == "welcome"
    assert marketing_landing.welcome_flow_state({"landing_focus": "sign_in"}) == "sign_in"
    assert marketing_landing.welcome_flow_state(
        {"launch_account_form": "create"}
    ) == "create_account"
    assert marketing_landing.welcome_flow_state(
        {"landing_focus": "guest_import"}
    ) == "guest_import"
    assert marketing_landing.welcome_flow_state(
        {"landing_focus": "get_started"}
    ) == "import"
    signed = {
        auth_supabase.AUTH_USER_KEY: {"id": "u1"},
        auth_supabase.AUTH_SESSION_KEY: {
            "user_id": "u1",
            "access_token": "tok",
            "expires_at": 9999999999,
        },
    }
    assert marketing_landing.welcome_flow_state(signed) == "authenticated"


def test_sign_in_composes_compact_header_not_marketing_stack():
    state = {"launch_account_form": "signin", "landing_focus": "sign_in"}
    _actions, html = _render(state)
    assert "data-fgl-welcome-flow='sign_in'" in html
    assert "After you import" not in html
    assert marketing_landing.APP_HERO_STATEMENT in html
    assert "Roster decisions" not in html


def test_create_account_is_its_own_viewport_state():
    assert marketing_landing.welcome_flow_state(
        {"launch_account_form": "create"}
    ) == "create_account"
    assert "New here? Create account" in ACCOUNT
    assert "landing_back_cta" in LANDING


def test_guest_flow_opens_import_without_auth_session():
    state: dict = {}
    actions, html = _render(state, marketing_landing.GUEST_CTA_LABEL)
    assert actions["guest"] is True
    assert state.get("landing_focus") == "guest_import"
    assert marketing_landing.welcome_flow_state(state) == "guest_import"
    assert marketing_landing.welcome_import_open(state)
    assert not auth_supabase.current_user_id(state)
    assert not auth_supabase.session_is_signed_in(state)
    assert "does not save leagues" in html.casefold() or "does not save" in marketing_landing.GUEST_PATH_NOTE


def test_guest_never_receives_internal_privileges():
    guest = {"launch_auth_mode": "guest", "landing_focus": "guest_import"}
    identity = account_menu.account_identity(guest, entitlement_label="Free")
    assert identity["signed_in"] is False
    assert identity["founder_labs"] is False
    assert identity["founder_ops"] is False
    assert founder_labs.labs_review_keys(guest) == ()


def test_guest_explicit_import_is_not_stripped_by_auth_gate():
    session = {
        "selected_league_id": "lg-1",
        "selected_league_name": "League",
        session_isolation.GUEST_LEAGUE_ORIGIN_KEY: session_isolation.GUEST_LEAGUE_ORIGIN_EXPLICIT,
        "_identity_established": True,
        "_league_selection_established": True,
    }
    result = session_isolation.enforce_anonymous_account_league_boundary(session)
    assert result.get("stripped") is False
    assert session.get("selected_league_id") == "lg-1"
    assert not auth_supabase.current_user_id(session)


def test_early_paint_mounts_selected_workflow_before_deferred_marketing():
    early = APP.split("with st.container(key=\"early_launch_account_decision\")", 1)[1].split(
        "startup_coordinator.log_startup_milestone(", 1
    )[0]
    assert "welcome_flow_state" in early
    assert "render_home_launch_screen(" in early
    assert "_signed_out_workflow_mounted" in early
    launch = APP.split("def render_home_launch_screen", 1)[1].split("\ndef ", 1)[0]
    assert "_signed_out_workflow_mounted" in launch
    assert launch.index("_signed_out_workflow_mounted") < launch.index(
        "render_marketing_landing_deferred"
    )


def test_espn_is_discoverable_under_other_import_options():
    sleeper = IMPORT_UI.split("if platform != \"ESPN experimental\":", 1)[1].split(
        "actions[\"platform\"] = \"espn\"", 1
    )[0]
    assert "Other import options" in sleeper
    assert "ESPN — Experimental" in sleeper
    assert "Use ESPN experimental import" in sleeper
    espn_open = IMPORT_UI.split("def render_platform_import_panel", 1)[1].split(
        "adapter_factory", 1
    )[0]
    assert "get_espn_adapter" not in espn_open.split("if platform !=", 1)[0]


def test_floating_feedback_is_suppressed_on_signed_out_landing():
    assert "_guest_landing_without_workspace" in APP.split(
        "def render_global_feedback_entry", 1
    )[1].split("def ", 1)[0]
    assert "body:has(.fgl-landing)" in LANDING_CSS


def test_headline_does_not_split_words_on_mobile():
    assert "recommendations using" not in marketing_landing.APP_HERO_STATEMENT
    assert "overflow-wrap:break-word" in LANDING_CSS.replace(" ", "")
    assert "word-break:normal" in LANDING_CSS.replace(" ", "")
    assert "hyphens:none" in LANDING_CSS.replace(" ", "")
    assert "clamp(" in LANDING_CSS
    compact = "".join(LANDING_CSS.split())
    assert "font-size:clamp(1.02rem,5.2vw,1.28rem)" in compact


def test_cold_states_have_zero_provider_calls():
    cold = LANDING.split("def render_marketing_landing(", 1)[1].split(
        "def render_marketing_landing_deferred(", 1
    )[0]
    for needle in (
        "load_leagues_for_username",
        "requests.",
        "get_espn_adapter",
        "lookup_user_leagues",
    ):
        assert needle not in cold
    assert "st.columns" not in cold

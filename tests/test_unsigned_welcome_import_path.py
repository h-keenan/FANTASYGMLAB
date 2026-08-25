"""Unsigned welcome → import → league select must enter the product without auth."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from modules import auth_supabase
from modules import founder_labs
from modules import marketing_landing
from modules import session_isolation
from modules.sleeper_leagues import LeagueLookupResult


class _Session(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def _click(label: str):
    def _button(text, **_kwargs):
        return str(text) == label

    return _button


def test_welcome_import_click_replaces_welcome_with_import_state():
    state: dict = {}
    col = MagicMock()
    col.__enter__ = MagicMock(return_value=col)
    col.__exit__ = MagicMock(return_value=False)
    with patch.object(marketing_landing.st, "session_state", state), patch.object(
        marketing_landing.st, "markdown"
    ), patch.object(
        marketing_landing.st,
        "button",
        side_effect=_click(marketing_landing.APP_PRIMARY_CTA_LABEL),
    ), patch.object(marketing_landing.st, "rerun") as rerun, patch.object(
        marketing_landing, "_track"
    ), patch.object(marketing_landing.st, "columns", return_value=[col, col]), patch.object(
        marketing_landing.st, "caption"
    ):
        actions = marketing_landing.render_marketing_landing()
    assert actions["primary"] is True
    assert marketing_landing.welcome_flow_state(state) == "import"
    assert state.get(marketing_landing.SIGNED_OUT_ENTRY_KEY) == "import"
    assert not auth_supabase.current_user_id(state)
    rerun.assert_called()


def test_welcome_has_no_continue_as_guest_cta():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "modules" / "marketing_landing.py").read_text(
        encoding="utf-8"
    )
    cold = text.split("def render_marketing_landing(", 1)[1].split(
        "def auth_pending_owns_entry", 1
    )[0]
    assert "landing_guest_cta" not in cold
    assert "GUEST_CTA_LABEL" not in cold
    assert "Continue as guest" not in cold


def test_state_transitions_back_and_auth_switch():
    state: dict = {}
    marketing_landing.set_signed_out_entry(state, "import")
    assert marketing_landing.welcome_flow_state(state) == "import"
    marketing_landing.reset_welcome_flow(state)
    assert marketing_landing.welcome_flow_state(state) == "welcome"
    marketing_landing.set_signed_out_entry(state, "sign_in")
    assert marketing_landing.welcome_flow_state(state) == "sign_in"
    marketing_landing.reset_welcome_flow(state)
    assert marketing_landing.welcome_flow_state(state) == "welcome"
    marketing_landing.set_signed_out_entry(state, "sign_in")
    marketing_landing.set_signed_out_entry(state, "create_account")
    assert marketing_landing.welcome_flow_state(state) == "create_account"
    marketing_landing.set_signed_out_entry(state, "sign_in")
    assert marketing_landing.welcome_flow_state(state) == "sign_in"


def test_unsigned_import_path_loads_selects_and_stays_signed_out():
    session = _Session()
    marketing_landing.set_signed_out_entry(session, "import")
    with patch("streamlit.session_state", session), patch(
        "app.lookup_user_leagues",
        return_value=LeagueLookupResult(
            [{"league_id": "lg-1", "name": "Dynasty Club", "season": "2026"}],
            "ok",
        ),
    ), patch("app.get_current_account", return_value={}), patch(
        "app.get_user_roster_id", return_value=None
    ), patch("app._persist_active_account_context"), patch(
        "app._persist_supabase_account_context"
    ), patch("app._queue_platform_route"):
        import app

        assert marketing_landing.welcome_import_open(session)
        leagues = app.load_leagues_for_username("sleeper_user")
        assert [row["league_id"] for row in leagues] == ["lg-1"]
        assert not auth_supabase.current_user_id(session)
        session_isolation.enforce_anonymous_account_league_boundary(session)
        app.set_selected_league("lg-1", "Dynasty Club", route_to_dashboard=True)
        session_isolation.enforce_anonymous_account_league_boundary(session)
        assert session.get("selected_league_id") == "lg-1"
        assert (
            session.get(session_isolation.GUEST_LEAGUE_ORIGIN_KEY)
            == session_isolation.GUEST_LEAGUE_ORIGIN_EXPLICIT
        )
        assert not auth_supabase.session_is_signed_in(session)
        assert founder_labs.labs_review_keys(session) == ()
        session_isolation.enforce_anonymous_account_league_boundary(session)
        assert session.get("selected_league_id") == "lg-1"


def test_reload_signed_out_does_not_invent_auth():
    state = {"signed_out_entry": "welcome"}
    assert marketing_landing.welcome_flow_state(state) == "welcome"
    assert not auth_supabase.current_user_id(state)
    assert not auth_supabase.session_is_signed_in(state)


def test_authenticated_flow_is_derived_from_session_truth():
    signed = {
        auth_supabase.AUTH_USER_KEY: {"id": "u1"},
        auth_supabase.AUTH_SESSION_KEY: {
            "user_id": "u1",
            "access_token": "tok",
            "expires_at": 9999999999,
        },
        "signed_out_entry": "welcome",
    }
    assert marketing_landing.welcome_flow_state(signed) == "authenticated"

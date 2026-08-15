"""Guest Sleeper import must work unsigned and stay isolated from account state."""

from __future__ import annotations

from unittest.mock import patch

from modules import auth_supabase
from modules import session_isolation
from modules.sleeper_leagues import LeagueLookupResult, log_league_import_diagnostic


class _Session(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def test_unsigned_import_select_reaches_dashboard_contract():
    session = _Session()
    with patch("streamlit.session_state", session), patch(
        "app.lookup_user_leagues",
        return_value=LeagueLookupResult(
            [
                {"league_id": "lg-a", "name": "League A", "season": "2026"},
                {"league_id": "lg-b", "name": "League B", "season": "2025"},
            ],
            "ok",
        ),
    ), patch("app.get_current_account", return_value={}), patch(
        "app.get_user_roster_id", return_value=None
    ), patch("app._persist_active_account_context"), patch(
        "app._persist_supabase_account_context"
    ), patch("app._queue_platform_route"):
        import app

        leagues = app.load_leagues_for_username("guest_user")
        session_isolation.enforce_anonymous_account_league_boundary(session)
        assert auth_supabase.current_user_id(session) in ("", None)
        assert session.get("_identity_established") is True
        assert session.get("selected_league_id") in (None, "")
        assert len(leagues) == 2

        app.set_selected_league("lg-b", "League B", route_to_dashboard=True)
        session_isolation.enforce_anonymous_account_league_boundary(session)
        assert session.get("selected_league_id") == "lg-b"
        assert session.get("_league_selection_established") is True
        assert (
            session.get(session_isolation.GUEST_LEAGUE_ORIGIN_KEY)
            == session_isolation.GUEST_LEAGUE_ORIGIN_EXPLICIT
        )
        assert session_isolation.anonymous_must_not_carry_account_league(session)


def test_unsigned_never_restores_account_league_username():
    guest = _Session(
        {
            "selected_league_id": "account-league",
            "username": "Harryhard",
            "_identity_established": True,
            "_league_selection_established": True,
        }
    )
    session_isolation.enforce_anonymous_account_league_boundary(guest)
    assert guest.get("selected_league_id") in (None, "")
    assert guest.get("username") in (None, "")


def test_guest_select_does_not_fetch_roster_for_supabase_persist():
    session = _Session({"username": "guest_user", "leagues_for_user": []})
    with patch("streamlit.session_state", session), patch(
        "app.get_user_roster_id"
    ) as roster, patch("app._persist_active_account_context"), patch(
        "app._persist_supabase_account_context"
    ), patch("app._queue_platform_route"):
        import app

        app.set_selected_league("lg-1", "League", route_to_dashboard=True)
    roster.assert_not_called()


def test_league_import_diagnostic_omits_username(capsys):
    log_league_import_diagnostic(
        stage="username_lookup",
        status="ok",
        league_count=2,
        seasons_scanned=2,
    )
    logged = capsys.readouterr().out
    assert "DYNASTYGM_LEAGUE_IMPORT" in logged
    assert "guest_league_import" in logged
    assert "password" not in logged.casefold()
    assert "@" not in logged

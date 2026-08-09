"""Guest → free-account conversion contracts (#224)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from modules import guest_conversion
from modules import launch_analytics


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_free_benefits_exclude_premium_features():
    text = " ".join(guest_conversion.FREE_ACCOUNT_BENEFITS).casefold()
    assert "premium" not in text
    assert "decision memory" not in text
    assert "gm targets" not in text
    assert "saved leagues" in text or "remember" in text


def test_soft_prompt_requires_guest_and_league():
    state = {"selected_league_id": "lg-1"}
    assert guest_conversion.should_show_soft_prompt("dashboard", session_state=state)
    guest_conversion.dismiss_soft_prompt("dashboard", session_state=state)
    assert not guest_conversion.should_show_soft_prompt("dashboard", session_state=state)

    auth_state = {"selected_league_id": "lg-1", "auth_session": {"user_id": "u1"}}
    with patch.object(guest_conversion.auth_supabase, "current_user_id", return_value="u1"):
        assert not guest_conversion.should_show_soft_prompt(
            "dashboard", session_state=auth_state
        )


def test_capture_and_restore_guest_resume_preserves_league_route():
    state = {
        "username": "sleeper_user",
        "selected_league_id": "lg-1",
        "selected_league_name": "Dynasty",
        "my_roster_id": 7,
        "active_platform": "sleeper",
        "platform_nav_page": "trade_hub",
        "player_quick_view_player_id": "",
    }
    with patch.object(guest_conversion.auth_supabase, "current_user_id", return_value=""):
        payload = guest_conversion.capture_guest_resume(
            state, prompt_surface="trade_hub"
        )
    assert payload["selected_league_id"] == "lg-1"
    assert payload["route"] == "trade_hub"
    assert state[guest_conversion.GUEST_AUTH_RESUME_KEY]["prompt_surface"] == "trade_hub"

    wiped = {"auth_session": {"user_id": "u1", "access_token": "tok", "email": "a@b.c"}}
    guest_conversion._apply_resume_workspace(wiped, payload)
    assert wiped["selected_league_id"] == "lg-1"
    assert wiped["username"] == "sleeper_user"
    assert wiped["_pending_platform_route"] == "trade_hub"


def test_finish_auth_existing_account_default_wins():
    state = {
        guest_conversion.GUEST_AUTH_RESUME_KEY: {
            "username": "guest_user",
            "selected_league_id": "guest-lg",
            "selected_league_name": "Guest League",
            "route": "my_team",
            "platform": "sleeper",
            "my_roster_id": 3,
            "prompt_surface": "dashboard",
        }
    }
    saved = [
        {
            "league_id": "saved-lg",
            "league_name": "Saved",
            "is_default": True,
            "sleeper_username": "acct",
        }
    ]

    class _State(dict):
        pass

    session = _State(state)
    with (
        patch.object(guest_conversion, "st") as st_mod,
        patch.object(
            guest_conversion.auth_supabase,
            "current_auth_session",
            return_value={"access_token": "tok", "user_id": "u1", "email": "a@b.c"},
        ),
        patch(
            "modules.account_store.fetch_saved_leagues",
            return_value=(saved, ""),
        ),
        patch(
            "modules.account_store.default_saved_league",
            return_value=saved[0],
        ),
        patch("modules.startup_coordinator.reset_startup_coordinator"),
    ):
        st_mod.session_state = session
        guest_conversion.finish_auth_from_guest(
            config={}, mode="signin", surface="dashboard"
        )
    assert "selected_league_id" not in session
    assert "saved" in str(session.get("account_resume_notice", "")).casefold()
    assert guest_conversion.GUEST_AUTH_RESUME_KEY not in session


def test_guest_events_are_tracked_and_block_username_pii():
    assert "guest_signup_prompt_seen" in launch_analytics.TRACKED_EVENTS
    assert "guest_league_selected" in launch_analytics.TRACKED_EVENTS
    assert "prompt_surface" in launch_analytics.ALLOWED_PROP_KEYS
    assert "username" in launch_analytics.BLOCKED_PROP_KEYS
    assert "email" in launch_analytics.BLOCKED_PROP_KEYS


def test_wiring_uses_guest_conversion_module():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "from modules import guest_conversion" in app
    assert 'surface="dashboard"' in app
    assert 'surface="my_team"' in app
    assert 'surface="trade_hub"' in app
    assert 'surface="waivers"' in app
    assert "render_guest_auth_dialog" in app
    assert "Browsing as guest" in (ROOT / "modules" / "guest_conversion.py").read_text(
        encoding="utf-8"
    )


def test_docs_guest_funnel_exists():
    doc = ROOT / "docs" / "guest-free-account-conversion.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "Save your front office" in text
    assert "FREE ACCOUNT BENEFITS" in text or "Free account benefits" in text

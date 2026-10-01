"""Welcome/signup audit Fix 1 (web) + Fix 2: modules.welcome_orientation.

A new, separate first-run modal (value prop + Team Situation declaration),
distinct from modules.dashboard_orientation's confirmed-working nav-tour
card. Covers the one-shot pending/seen visibility contract, the Team
Situation write-path reuse, and the guest-vs-authenticated content split.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from modules import welcome_orientation


ROOT = Path(__file__).resolve().parents[1]


def test_mark_pending_arms_the_one_shot_flag():
    state: dict = {}
    welcome_orientation.mark_pending(state)
    assert state[welcome_orientation.PENDING_KEY] is True


def test_should_show_requires_pending():
    assert welcome_orientation.should_show({}) is False
    assert welcome_orientation.should_show({welcome_orientation.PENDING_KEY: True}) is True


def test_should_show_false_once_shown_this_session():
    state = {
        welcome_orientation.PENDING_KEY: True,
        welcome_orientation.SHOWN_THIS_SESSION_KEY: True,
    }
    assert welcome_orientation.should_show(state) is False


def test_should_show_false_when_account_settings_already_seen():
    state = {welcome_orientation.PENDING_KEY: True}
    settings = {"settings": {welcome_orientation.ACCOUNT_SETTINGS_SEEN_KEY: True}}
    assert welcome_orientation.should_show(state, user_settings=settings) is False


def test_dismissal_key_is_distinct_from_dashboard_orientation():
    from modules import user_preferences

    assert welcome_orientation.ACCOUNT_SETTINGS_SEEN_KEY != user_preferences.ONBOARDING_DISMISSED_KEY


def test_modal_content_reuses_marketing_hero_copy_not_new_copy():
    from modules import marketing_landing

    content = welcome_orientation.welcome_modal_content()
    assert content.title == marketing_landing.APP_HERO_STATEMENT
    assert content.summary == marketing_landing.APP_HERO_SUPPORT


def test_stance_picker_writes_through_team_stance_set_stance_directly():
    from modules import team_stance

    writes: list[tuple[str, str]] = []
    with (
        patch.object(team_stance, "can_access_stance", return_value=True),
        patch.object(team_stance, "fetch_stance_for_league", return_value=""),
        patch.object(
            team_stance,
            "set_stance",
            side_effect=lambda sess, *, league_id, stance: writes.append((league_id, stance)),
        ),
        patch.object(welcome_orientation.st, "divider"),
        patch.object(welcome_orientation.st, "markdown"),
        patch.object(welcome_orientation.st, "caption"),
        patch.object(
            welcome_orientation.st,
            "radio",
            return_value=team_stance.STANCE_LABELS[team_stance.STANCE_COMPETING],
        ),
    ):
        welcome_orientation._render_stance_picker(session_state={}, league_id="league-1")

    assert writes == [("league-1", team_stance.STANCE_COMPETING)]


def test_stance_picker_is_silently_absent_for_guests():
    from modules import team_stance

    with patch.object(team_stance, "can_access_stance", return_value=False), patch.object(
        welcome_orientation.st, "radio"
    ) as radio:
        welcome_orientation._render_stance_picker(session_state={}, league_id="league-1")

    radio.assert_not_called()


def test_applicable_renderer_requires_a_league_id():
    with patch.object(welcome_orientation.ui_modal, "render_modal") as render_modal:
        shown = welcome_orientation.render_welcome_orientation_if_applicable(
            session_state={welcome_orientation.PENDING_KEY: True},
            config={},
            league_id="",
        )
    assert shown is False
    render_modal.assert_not_called()


def test_applicable_renderer_marks_seen_and_opens_modal_when_pending():
    state = {welcome_orientation.PENDING_KEY: True}
    with patch.object(welcome_orientation.ui_modal, "render_modal") as render_modal:
        shown = welcome_orientation.render_welcome_orientation_if_applicable(
            session_state=state,
            config={},
            league_id="league-1",
        )
    assert shown is True
    assert state[welcome_orientation.SHOWN_THIS_SESSION_KEY] is True
    assert state[welcome_orientation.PENDING_KEY] is False
    render_modal.assert_called_once()
    _content, kwargs = render_modal.call_args
    assert kwargs["surface"] == welcome_orientation.SURFACE
    assert callable(kwargs["extra_body"])


def test_applicable_renderer_does_not_mount_when_not_pending():
    with patch.object(welcome_orientation.ui_modal, "render_modal") as render_modal:
        shown = welcome_orientation.render_welcome_orientation_if_applicable(
            session_state={},
            config={},
            league_id="league-1",
        )
    assert shown is False
    render_modal.assert_not_called()


def test_mark_seen_persists_durably_for_an_authenticated_account():
    from modules import account_store, auth_supabase

    state = {
        auth_supabase.AUTH_SESSION_KEY: {"access_token": "token", "user_id": "user-1"},
        auth_supabase.AUTH_USER_KEY: {"id": "user-1"},
        # Already cached this session (the common case once app.py's
        # preload — see test_app_preloads_preferences_before_the_welcome_
        # orientation_gate_check below — has run): no extra fetch needed.
        "account_user_settings": {"user_id": "user-1", "settings": {}},
    }
    with (
        patch.object(account_store, "upsert_user_settings", return_value=(True, "")) as save,
        patch.object(account_store, "fetch_user_settings") as fetch,
    ):
        welcome_orientation._mark_seen(state, config={"enabled": True})

    assert state[welcome_orientation.SHOWN_THIS_SESSION_KEY] is True
    assert state["account_user_settings"]["settings"][welcome_orientation.ACCOUNT_SETTINGS_SEEN_KEY] is True
    save.assert_called_once()
    fetch.assert_not_called()


def test_mark_seen_is_session_only_for_a_guest():
    state: dict = {}
    welcome_orientation._mark_seen(state, config={})
    assert state[welcome_orientation.SHOWN_THIS_SESSION_KEY] is True
    assert "account_user_settings" not in state


def test_mark_seen_fetches_existing_settings_before_writing_when_not_yet_cached():
    """Regression guard: account_store.upsert_user_settings replaces the
    WHOLE settings JSON column. If `_mark_seen` fires before
    modules.user_preferences.refresh_authenticated_preferences has cached
    `account_user_settings` this session (a real race — see app.py's call
    site comment), it must fetch the durable row first so a returning
    user's OTHER preferences (League Orientation dismissal, FAAB budgets,
    theme/density) are never silently wiped by this write.
    """

    from modules import account_store, auth_supabase

    state = {
        auth_supabase.AUTH_SESSION_KEY: {"access_token": "token", "user_id": "user-1"},
        auth_supabase.AUTH_USER_KEY: {"id": "user-1"},
        # Deliberately NOT populating "account_user_settings" — simulates
        # the race.
    }
    existing_row = {
        "user_id": "user-1",
        "settings": {"dashboard_orientation_dismissed": True, "theme": "dark"},
    }
    writes: list[dict] = []
    with (
        patch.object(account_store, "fetch_user_settings", return_value=(existing_row, "")) as fetch,
        patch.object(
            account_store,
            "upsert_user_settings",
            side_effect=lambda cfg, token, payload: (writes.append(payload), (True, ""))[1],
        ),
    ):
        welcome_orientation._mark_seen(state, config={"enabled": True})

    fetch.assert_called_once()
    assert len(writes) == 1
    assert writes[0]["settings"] == {
        "dashboard_orientation_dismissed": True,
        "theme": "dark",
        welcome_orientation.ACCOUNT_SETTINGS_SEEN_KEY: True,
    }


def test_mark_seen_skips_the_write_when_the_fetch_fails_rather_than_clobbering():
    from modules import account_store, auth_supabase

    state = {
        auth_supabase.AUTH_SESSION_KEY: {"access_token": "token", "user_id": "user-1"},
        auth_supabase.AUTH_USER_KEY: {"id": "user-1"},
    }
    with (
        patch.object(account_store, "fetch_user_settings", return_value=({}, "offline")),
        patch.object(account_store, "upsert_user_settings") as upsert,
    ):
        welcome_orientation._mark_seen(state, config={"enabled": True})

    upsert.assert_not_called()
    # Session-local flag is still set — never re-prompt within this session
    # even though the durable mark could not be confirmed.
    assert state[welcome_orientation.SHOWN_THIS_SESSION_KEY] is True


def test_app_preloads_preferences_before_the_welcome_orientation_gate_check():
    # Fixes the same race the two tests above guard at the unit level:
    # without this, a returning user's auto-resumed league could reach the
    # gate check before account_user_settings is cached this session.
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    dashboard = source.split("def render_home_dashboard(", 1)[1]
    preload = dashboard.index("user_preferences.refresh_authenticated_preferences(")
    gate_check = dashboard.index("welcome_orientation.render_welcome_orientation_if_applicable(")
    assert preload < gate_check


def test_dashboard_workflow_untouched_integration_point():
    # This module intentionally does NOT hook into
    # modules.dashboard_workflow.render_dashboard_workflow at all — it is
    # triggered directly from app.py's set_selected_league() / top of
    # render_home_dashboard, independent of the Dashboard briefing pipeline
    # dashboard_orientation (the confirmed-working nav-tour card) uses.
    source = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
    assert "welcome_orientation" not in source


def test_app_wires_mark_pending_on_first_league_selection():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "welcome_orientation.mark_pending(st.session_state)" in source
    assert "welcome_orientation.render_welcome_orientation_if_applicable(" in source


def test_ui_modal_render_modal_supports_extra_interactive_body():
    from modules import ui_modal

    content = ui_modal.ModalContent(title="T", summary="S")
    extra = Mock()
    with patch.object(ui_modal.st, "dialog", lambda *a, **k: (lambda fn: fn)), patch.object(
        ui_modal, "render_html_fragment"
    ):
        ui_modal.render_modal(content, surface="test", extra_body=extra)
    extra.assert_called_once_with()

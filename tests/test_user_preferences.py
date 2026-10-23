from pathlib import Path
from unittest.mock import Mock, patch

from modules import account_store, auth_supabase, user_preferences


ROOT = Path(__file__).resolve().parents[1]


def test_existing_user_without_preference_sees_onboarding():
    assert not user_preferences.onboarding_is_dismissed(None)
    assert not user_preferences.onboarding_is_dismissed({"settings": {}})


def test_dismissal_is_account_wide_and_strictly_boolean():
    assert user_preferences.onboarding_is_dismissed(
        {"settings": {user_preferences.ONBOARDING_DISMISSED_KEY: True}}
    )
    assert not user_preferences.onboarding_is_dismissed(
        {"settings": {user_preferences.ONBOARDING_DISMISSED_KEY: "true"}}
    )


def test_preference_merge_preserves_unrelated_settings_and_does_not_mutate_input():
    original = {"user_id": "user-1", "settings": {"theme": "dark"}}
    updated = user_preferences.with_onboarding_dismissal(original, dismissed=True)

    assert original == {"user_id": "user-1", "settings": {"theme": "dark"}}
    assert updated["settings"] == {
        "theme": "dark",
        user_preferences.ONBOARDING_DISMISSED_KEY: True,
    }


def test_reset_removes_only_onboarding_preference():
    current = {
        "settings": {
            "theme": "dark",
            user_preferences.ONBOARDING_DISMISSED_KEY: True,
        }
    }
    assert user_preferences.with_onboarding_dismissal(
        current, dismissed=False
    )["settings"] == {"theme": "dark"}


def test_persistence_uses_existing_user_settings_boundary():
    with patch.object(account_store, "upsert_user_settings", return_value=(True, "")) as save:
        updated, error = user_preferences.persist_onboarding_preference(
            config={"enabled": True},
            access_token="token",
            user_id="user-1",
            current_settings={"settings": {"theme": "dark"}},
            dismissed=True,
        )

    assert not error
    assert updated["settings"]["theme"] == "dark"
    assert updated["settings"][user_preferences.ONBOARDING_DISMISSED_KEY] is True
    save.assert_called_once()


def test_failed_persistence_does_not_create_false_local_dismissal():
    current = {"settings": {"theme": "dark"}}
    with patch.object(account_store, "upsert_user_settings", return_value=(False, "offline")):
        updated, error = user_preferences.persist_onboarding_preference(
            config={"enabled": True},
            access_token="token",
            user_id="user-1",
            current_settings=current,
            dismissed=True,
        )

    assert error == "offline"
    assert updated == current
    assert not user_preferences.onboarding_is_dismissed(updated)


def test_authenticated_refresh_restores_dismissal_in_a_new_session():
    state = {
        auth_supabase.AUTH_SESSION_KEY: {"access_token": "token", "user_id": "user-1"},
        auth_supabase.AUTH_USER_KEY: {"id": "user-1"},
    }
    persisted = {
        "user_id": "user-1",
        "settings": {user_preferences.ONBOARDING_DISMISSED_KEY: True},
    }
    with patch.object(auth_supabase, "is_configured", return_value=True), patch.object(
        account_store, "fetch_user_settings", return_value=(persisted, "")
    ) as fetch:
        error = user_preferences.refresh_authenticated_preferences(
            config={"enabled": True}, session_state=state
        )

    assert not error
    assert user_preferences.onboarding_is_dismissed(state["account_user_settings"])
    fetch.assert_called_once()


def test_authenticated_dismissal_updates_session_only_after_remote_success():
    state = {
        auth_supabase.AUTH_SESSION_KEY: {"access_token": "token", "user_id": "user-1"},
        auth_supabase.AUTH_USER_KEY: {"id": "user-1"},
        "account_user_settings": {"settings": {"theme": "dark"}},
    }
    with patch.object(
        user_preferences,
        "persist_onboarding_preference",
        return_value=(
            {"settings": {"theme": "dark", user_preferences.ONBOARDING_DISMISSED_KEY: True}},
            "",
        ),
    ):
        error = user_preferences.persist_authenticated_onboarding(
            config={"enabled": True}, session_state=state, dismissed=True
        )

    assert not error
    assert user_preferences.onboarding_is_dismissed(state["account_user_settings"])


def test_reset_lazily_fetches_existing_preferences_before_merging():
    state = {
        auth_supabase.AUTH_SESSION_KEY: {"access_token": "token", "user_id": "user-1"},
        auth_supabase.AUTH_USER_KEY: {"id": "user-1"},
    }
    existing = {
        "user_id": "user-1",
        "settings": {
            "theme": "dark",
            user_preferences.ONBOARDING_DISMISSED_KEY: True,
        },
    }
    with patch.object(
        account_store, "fetch_user_settings", return_value=(existing, "")
    ) as fetch, patch.object(
        account_store, "upsert_user_settings", return_value=(True, "")
    ) as save:
        error = user_preferences.persist_authenticated_onboarding(
            config={"enabled": True}, session_state=state, dismissed=False
        )

    assert not error
    assert state["account_user_settings"]["settings"] == {"theme": "dark"}
    fetch.assert_called_once()
    save.assert_called_once()

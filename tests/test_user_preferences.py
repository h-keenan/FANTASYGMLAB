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


def test_app_loads_preferences_during_authenticated_startup_and_wires_dismissal():
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "user_preferences.refresh_authenticated_preferences(" in source
    assert "user_preferences.onboarding_is_dismissed(" in source
    assert "on_dont_show_again=_persist_onboarding_dismissal" in source
    assert "account_user_settings" in source
    account_ui = (ROOT / "modules" / "account_ui.py").read_text(encoding="utf-8")
    assert '"Profile preferences"' in account_ui
    assert '"Reset onboarding"' in account_ui


def test_founder_beta_geometry_uses_canonical_tokens():
    polish = (ROOT / "modules" / "ux_polish_styles.py").read_text(encoding="utf-8")
    consistency = (
        ROOT / "modules" / "founder_beta_consistency_styles.py"
    ).read_text(encoding="utf-8")

    assert "--dg-ux-radius: var(--radius-panel)" in polish
    assert "--dg-ux-card-pad: var(--space-md)" in polish
    assert "border-radius: 14px" not in polish
    assert "border-radius: 999px" not in polish
    assert ".st-key-dashboard_orientation_panel" in consistency
    assert "padding: var(--space-md)" in consistency

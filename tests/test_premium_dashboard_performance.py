from pathlib import Path

from modules import premium


ROOT = Path(__file__).resolve().parents[1]


def test_effective_entitlement_uses_supabase_profile():
    state = {
        "auth_session": {"user_id": "user-1"},
        "account_profile": {"user_id": "user-1", "entitlement": "premium"},
    }
    assert premium.effective_entitlement(session_state=state, environ={}, secrets={}) == premium.PREMIUM


def test_effective_entitlement_defaults_free_without_supabase_profile():
    state = {
        "auth_session": {"user_id": "user-1"},
        "auth_user": {"id": "user-1", "entitlement": "premium"},
    }
    assert premium.effective_entitlement(session_state=state, environ={}, secrets={}) == premium.FREE


def test_development_override_has_highest_priority():
    state = {
        "auth_session": {"user_id": "user-1"},
        "account_profile": {"user_id": "user-1", "entitlement": "free"},
    }
    assert (
        premium.effective_entitlement(
            session_state=state,
            environ={"DYNASTYGM_PREMIUM_OVERRIDE": "true"},
            secrets={},
        )
        == premium.PREMIUM
    )

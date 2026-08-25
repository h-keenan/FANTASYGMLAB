"""Founder Labs authorization, inventory, and route isolation."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from unittest.mock import patch

from modules import auth_supabase
from modules import founder_labs
from modules import session_integrity
from modules.ui_architecture import (
    current_platform_destinations,
    mobile_primary_destinations,
    routable_platform_destinations,
)


ROOT = Path(__file__).resolve().parents[1]
FUTURE = int(time.time()) + 3600
PAST = int(time.time()) - 3600
FOUNDER_USER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _unsigned_jwt(claims: dict) -> str:
    def b64(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(claims)}.sig"


def _gotrue_restore_payload(*, include_app_metadata_alias: bool = False) -> dict:
    """Realistic GoTrue/localStorage restore: Postgres raw_app_meta_data + JWT."""

    raw_meta = {
        "provider": "email",
        "providers": ["email"],
        "founder_ops": True,
        "dev_review": True,
    }
    user = {
        "id": FOUNDER_USER_ID,
        "aud": "authenticated",
        "role": "authenticated",
        "email": "founder@example.com",
        "email_confirmed_at": "2026-01-01T00:00:00.000000Z",
        "confirmed_at": "2026-01-01T00:00:00.000000Z",
        "phone": "",
        "last_sign_in_at": "2026-08-25T00:00:00.000000Z",
        "raw_app_meta_data": dict(raw_meta),
        "user_metadata": {"email_verified": True},
        "identities": [{"identity_id": "id-1", "id": FOUNDER_USER_ID, "provider": "email"}],
    }
    if include_app_metadata_alias:
        user["app_metadata"] = dict(raw_meta)
    token = _unsigned_jwt(
        {
            "sub": FOUNDER_USER_ID,
            "email": "founder@example.com",
            "role": "authenticated",
            "exp": FUTURE,
            "app_metadata": dict(raw_meta),
        }
    )
    return {
        "access_token": token,
        "refresh_token": "refresh-token-example",
        "expires_at": FUTURE,
        "expires_in": 3600,
        "token_type": "bearer",
        "user": user,
    }


def _session(*, metadata: dict | None, expired: bool = False, signed_in: bool = True):
    if not signed_in:
        return {}
    return {
        "auth_user": {"id": "user-1", "app_metadata": dict(metadata or {})},
        "auth_session": {
            "user_id": "user-1",
            "access_token": "token",
            "expires_at": PAST if expired else FUTURE,
        },
    }


def test_labs_hidden_from_customer_nav():
    keys = {page.key for page in current_platform_destinations(False)}
    assert "founder_labs" not in keys
    assert "weekly_report" not in keys
    primary = {page.key for page in mobile_primary_destinations(False)}
    assert "founder_labs" not in primary


def test_labs_nav_requires_flag_without_archived_customer_items():
    shown = {
        page.key
        for page in current_platform_destinations(False, show_founder_labs=True)
    }
    hidden = {
        page.key
        for page in current_platform_destinations(False, show_founder_labs=False)
    }
    assert "founder_labs" in shown
    assert "founder_labs" not in hidden
    assert "weekly_report" not in shown
    assert "news" not in shown


def test_labs_review_routes_are_routable_but_not_in_nav():
    nav = {page.key for page in current_platform_destinations(False, show_founder_labs=True)}
    routable = {
        page.key
        for page in routable_platform_destinations(
            False,
            show_founder_labs=True,
            labs_review_keys=founder_labs.REVIEWABLE_ROUTE_KEYS,
        )
    }
    assert "founder_labs" in nav
    assert "weekly_report" not in nav
    assert "weekly_report" in routable
    assert "gm_targets" in routable


def test_authorization_matrix():
    env_on = {"DYNASTYGM_DEV_REVIEW": "1"}
    signed = _session(metadata={"founder_ops": True})
    assert founder_labs.founder_labs_authorized(signed, environ=env_on)
    assert founder_labs.founder_labs_authorized(
        _session(metadata={"dev_review": True}),
        environ=env_on,
    )
    assert not founder_labs.founder_labs_authorized(
        _session(metadata={}),
        environ=env_on,
    )
    assert not founder_labs.founder_labs_authorized(
        signed,
        environ={},
    )
    assert not founder_labs.founder_labs_authorized(
        _session(metadata={"founder_ops": True}, expired=True),
        environ=env_on,
    )
    assert not founder_labs.founder_labs_authorized({}, environ=env_on)
    assert not founder_labs.founder_labs_authorized(
        {
            "auth_user": {"user_metadata": {"dev_review": True}, "id": "user-1"},
            "auth_session": {
                "user_id": "user-1",
                "access_token": "token",
                "expires_at": FUTURE,
            },
        },
        environ=env_on,
    )
    assert not founder_labs.founder_labs_authorized(
        {
            "account_profile": {"dev_review": True},
            "auth_user": {"id": "user-1", "app_metadata": {}},
            "auth_session": {
                "user_id": "user-1",
                "access_token": "token",
                "expires_at": FUTURE,
            },
        },
        environ=env_on,
    )
    assert not founder_labs.founder_labs_authorized(
        signed,
        environ={"DYNASTYGM_SHOW_EXPERIMENTAL": "1"},
    )


def test_token_refresh_updates_claim():
    env_on = {"DYNASTYGM_DEV_REVIEW": "1"}
    state = _session(metadata={})
    assert not founder_labs.founder_labs_authorized(state, environ=env_on)
    state["auth_user"] = {"id": "user-1", "app_metadata": {"dev_review": True}}
    assert founder_labs.founder_labs_authorized(state, environ=env_on)
    state["auth_user"] = {"id": "user-1", "app_metadata": {}}
    assert not founder_labs.founder_labs_authorized(state, environ=env_on)


def test_account_switch_drops_labs_privilege():
    env_on = {"DYNASTYGM_DEV_REVIEW": "1"}
    state = _session(metadata={"founder_ops": True})
    state["platform_nav_page"] = "founder_labs"
    assert founder_labs.founder_labs_authorized(state, environ=env_on)
    session_integrity.clear_account_bound_transient_state(state)
    state["auth_user"] = {"id": "user-2", "app_metadata": {}}
    state["auth_session"] = {
        "user_id": "user-2",
        "access_token": "other",
        "expires_at": FUTURE,
    }
    assert not founder_labs.founder_labs_authorized(state, environ=env_on)


def test_inventory_is_static_and_redacted():
    rows = founder_labs.build_labs_inventory()
    keys = {row.key for row in rows}
    assert "weekly_report" in keys
    assert "espn_import" in keys
    assert "decision_memory" in keys
    blob = str([row.as_dict() for row in rows]).casefold()
    assert "sk_live" not in blob
    assert "service_role" not in blob
    assert "whsec_" not in blob
    archived = [row for row in rows if row.status == "ARCHIVED"]
    assert archived
    assert all(row.warning for row in archived)


def test_app_wires_labs():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "founder_labs.founder_labs_authorized" in source
    assert "render_founder_labs(" in source
    assert "routable_platform_destinations(" in source
    flags = source.split("def _destination_visibility_flags", 1)[1].split(
        "return flags", 1
    )[0]
    assert "show_founder_labs" in flags
    assert "emit_authorization_diagnostic" in flags
    assert "DYNASTYGM_SHOW_EXPERIMENTAL" in flags


def test_docs_and_env_contract():
    contract = (ROOT / "docs" / "runtime-environment-contract.md").read_text(
        encoding="utf-8"
    )
    setup = (ROOT / "docs" / "founder-dev-labs.md").read_text(encoding="utf-8")
    assert "DYNASTYGM_DEV_REVIEW" in contract
    assert "app_metadata.dev_review" in setup
    assert "app_metadata.founder_ops" in setup
    assert "Admin" in setup
    assert "raw_app_meta_data" in setup
    assert "account_profile" in setup.casefold()


def test_restored_gotrue_session_preserves_raw_app_meta_data_claims():
    env_on = {"DYNASTYGM_DEV_REVIEW": "1"}
    payload = _gotrue_restore_payload()
    extracted = auth_supabase.extract_auth_user(payload)
    assert extracted["app_metadata"]["founder_ops"] is True
    assert extracted["app_metadata"]["dev_review"] is True
    assert extracted["app_metadata"]["provider"] == "email"

    session_state = {}
    with patch.object(auth_supabase.requests, "get") as get_user:
        applied = auth_supabase.apply_auth_payload(session_state, payload)
        get_user.assert_not_called()
    assert applied
    restored_user = session_state[auth_supabase.AUTH_USER_KEY]
    assert restored_user["app_metadata"]["founder_ops"] is True
    assert restored_user["app_metadata"]["dev_review"] is True
    assert founder_labs.founder_labs_authorized(session_state, environ=env_on)
    snapshot = founder_labs.authorization_snapshot(session_state, environ=env_on)
    assert snapshot == {
        "env_enabled": True,
        "session_signed_in": True,
        "has_founder_ops_claim": True,
        "has_dev_review_claim": True,
        "authorized": True,
        "destination_visible": True,
    }
    dests = {
        page.key
        for page in current_platform_destinations(
            False,
            show_founder_labs=snapshot["authorized"],
        )
    }
    assert "founder_labs" in dests


def test_restored_session_without_app_metadata_alias_still_authorizes():
    env_on = {"DYNASTYGM_DEV_REVIEW": "1"}
    payload = _gotrue_restore_payload(include_app_metadata_alias=False)
    assert "app_metadata" not in payload["user"]
    session_state = {}
    auth_supabase.apply_auth_payload(session_state, payload)
    assert founder_labs.founder_labs_authorized(session_state, environ=env_on)


def test_jwt_only_restore_does_not_drop_claims():
    env_on = {"DYNASTYGM_DEV_REVIEW": "1"}
    token = _unsigned_jwt(
        {
            "sub": FOUNDER_USER_ID,
            "email": "founder@example.com",
            "exp": FUTURE,
            "app_metadata": {"founder_ops": True, "dev_review": True, "provider": "email"},
        }
    )
    payload = {
        "access_token": token,
        "refresh_token": "refresh-token-example",
        "expires_at": FUTURE,
        "token_type": "bearer",
    }
    session_state = {}
    auth_supabase.apply_auth_payload(session_state, payload)
    user = session_state[auth_supabase.AUTH_USER_KEY]
    assert user["id"] == FOUNDER_USER_ID
    assert user["app_metadata"]["founder_ops"] is True
    assert founder_labs.founder_labs_authorized(session_state, environ=env_on)


def test_unauthorized_direct_founder_labs_route_is_not_routable():
    visible = {
        page.key
        for page in routable_platform_destinations(False, show_founder_labs=False)
    }
    hidden_nav = {
        page.key for page in current_platform_destinations(False, show_founder_labs=False)
    }
    assert "founder_labs" not in visible
    assert "founder_labs" not in hidden_nav
    allowed = {
        page.key
        for page in routable_platform_destinations(False, show_founder_labs=True)
    }
    assert "founder_labs" in allowed


def test_you_menu_exposes_labs_only_when_authorized():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    profile = source[
        source.index("def render_executive_profile_control(") : source.index(
            "def render_platform_topbar("
        )
    ]
    assert "Founder Labs" in profile
    assert "founder_labs.founder_labs_authorized" in profile
    assert 'args=("founder_labs",)' in profile
    assert '("FOUNDER_LABS", "Internal")' in source
    assert "st.caption(" not in profile or "Account, Premium, and Feedback." in profile

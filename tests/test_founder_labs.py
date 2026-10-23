"""Founder Labs authorization, inventory, and route isolation."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from unittest.mock import patch

from modules import auth_supabase
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

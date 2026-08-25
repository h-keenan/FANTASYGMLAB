"""Founder Labs authorization, inventory, and route isolation."""

from __future__ import annotations

import time
from pathlib import Path

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
    assert "account_profile" in setup.casefold()

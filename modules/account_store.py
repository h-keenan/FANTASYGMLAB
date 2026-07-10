from __future__ import annotations

from typing import Any

import requests

from modules import auth_supabase

USER_MANAGED_SETTINGS_BLOCKLIST = {
    "entitlement",
    "plan",
    "tier",
    "subscription_tier",
    "is_premium",
    "premium",
    "premium_enabled",
    "has_premium",
    "customer_id",
    "subscription_id",
    "stripe_customer_id",
    "stripe_subscription_id",
    "stripe_subscription_status",
    "stripe_price_id",
    "premium_updated_at",
    "payment_status",
}


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _rest_url(config: dict, table: str, query: str = "") -> str:
    base = f"{config['url']}/rest/v1/{table}"
    return base + (f"?{query}" if query else "")


def _safe_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = {}
    message = _safe_text(
        payload.get("message") or payload.get("msg") or payload.get("hint") or payload.get("details")
    )
    lower_message = message.casefold()
    if (
        response.status_code == 404
        or "schema cache" in lower_message
        or "could not find the table" in lower_message
        or "relation" in lower_message and "does not exist" in lower_message
    ):
        return "Supabase tables are not set up yet. Run docs/supabase_accounts.sql in your Supabase SQL editor."
    return message or "Supabase table request failed."


def build_profile_payload(
    *,
    user_id: str,
    email: str = "",
    display_name: str = "",
    sleeper_username: str = "",
) -> dict:
    return {
        "user_id": _safe_text(user_id),
        "email": _safe_text(email),
        "display_name": _safe_text(display_name),
        "sleeper_username": _safe_text(sleeper_username),
    }


def build_saved_league_payload(
    *,
    user_id: str,
    sleeper_username: str = "",
    league_id: str = "",
    league_name: str = "",
    roster_id=None,
    team_id=None,
    owner_id: str = "",
    is_default: bool = True,
) -> dict:
    roster_value = roster_id if roster_id not in ("", None) else team_id
    return {
        "user_id": _safe_text(user_id),
        "sleeper_username": _safe_text(sleeper_username),
        "league_id": _safe_text(league_id),
        "league_name": _safe_text(league_name),
        "roster_id": _safe_text(roster_value),
        "team_id": _safe_text(team_id if team_id not in ("", None) else roster_value),
        "owner_id": _safe_text(owner_id),
        "is_default": bool(is_default),
    }


def build_user_settings_payload(*, user_id: str, settings: dict | None = None) -> dict:
    clean_settings = {
        key: value
        for key, value in (settings if isinstance(settings, dict) else {}).items()
        if _safe_text(key).casefold() not in USER_MANAGED_SETTINGS_BLOCKLIST
    }
    return {
        "user_id": _safe_text(user_id),
        "settings": clean_settings,
    }


def upsert_row(
    config: dict,
    access_token: str,
    table: str,
    payload: dict,
    *,
    on_conflict: str,
) -> tuple[bool, str]:
    if not auth_supabase.is_configured(config):
        return False, "Accounts are not configured."
    clean_payload = {key: value for key, value in payload.items() if value not in (None,)}
    try:
        response = requests.post(
            _rest_url(config, table, f"on_conflict={on_conflict}"),
            headers={
                **auth_supabase.auth_headers(config, access_token),
                "Prefer": "resolution=merge-duplicates,return=representation",
            },
            json=clean_payload,
            timeout=15,
        )
    except Exception:
        return False, "Could not reach Supabase table storage."
    if response.status_code >= 400:
        return False, _safe_error(response)
    return True, ""


def clear_default_saved_leagues(
    config: dict,
    access_token: str,
    *,
    user_id: str,
) -> tuple[bool, str]:
    if not auth_supabase.is_configured(config):
        return False, "Accounts are not configured."
    try:
        response = requests.patch(
            _rest_url(config, "saved_leagues", f"user_id=eq.{_safe_text(user_id)}"),
            headers={
                **auth_supabase.auth_headers(config, access_token),
                "Prefer": "return=minimal",
            },
            json={"is_default": False},
            timeout=15,
        )
    except Exception:
        return False, "Could not reach Supabase table storage."
    if response.status_code >= 400:
        return False, _safe_error(response)
    return True, ""


def upsert_profile(config: dict, access_token: str, payload: dict) -> tuple[bool, str]:
    return upsert_row(config, access_token, "profiles", payload, on_conflict="user_id")


def upsert_saved_league(config: dict, access_token: str, payload: dict) -> tuple[bool, str]:
    if payload.get("is_default"):
        cleared, error = clear_default_saved_leagues(
            config,
            access_token,
            user_id=_safe_text(payload.get("user_id")),
        )
        if not cleared:
            return False, error
    return upsert_row(config, access_token, "saved_leagues", payload, on_conflict="user_id,league_id")


def upsert_user_settings(config: dict, access_token: str, payload: dict) -> tuple[bool, str]:
    return upsert_row(config, access_token, "user_settings", payload, on_conflict="user_id")


def fetch_rows(
    config: dict,
    access_token: str,
    table: str,
    *,
    user_id: str,
    extra_query: str = "",
) -> tuple[list[dict], str]:
    if not auth_supabase.is_configured(config):
        return [], "Accounts are not configured."
    query = f"user_id=eq.{_safe_text(user_id)}"
    if extra_query:
        query += f"&{extra_query}"
    try:
        response = requests.get(
            _rest_url(config, table, query),
            headers=auth_supabase.auth_headers(config, access_token),
            timeout=15,
        )
    except Exception:
        return [], "Could not reach Supabase table storage."
    if response.status_code >= 400:
        return [], _safe_error(response)
    try:
        payload = response.json()
    except Exception:
        payload = []
    if isinstance(payload, list):
        return payload, ""
    if isinstance(payload, dict):
        return [payload], ""
    return [], ""


def fetch_saved_leagues(config: dict, access_token: str, *, user_id: str) -> tuple[list[dict], str]:
    return fetch_rows(
        config,
        access_token,
        "saved_leagues",
        user_id=user_id,
        extra_query="order=is_default.desc,league_name.asc",
    )


def fetch_profile(config: dict, access_token: str, *, user_id: str) -> tuple[dict, str]:
    base_select = "select=user_id,email,display_name,sleeper_username,entitlement&limit=1"
    billing_select = (
        "select=user_id,email,display_name,sleeper_username,entitlement,"
        "stripe_customer_id,stripe_subscription_id,stripe_subscription_status,stripe_price_id,premium_updated_at&limit=1"
    )
    rows, error = fetch_rows(config, access_token, "profiles", user_id=user_id, extra_query=billing_select)
    lower_error = error.casefold()
    if error and "stripe_" in lower_error and ("column" in lower_error or "schema cache" in lower_error):
        rows, error = fetch_rows(config, access_token, "profiles", user_id=user_id, extra_query=base_select)
    if error:
        return {}, error
    return dict(rows[0]) if rows else {}, ""


def default_saved_league(rows: list[dict], *, require_default: bool = False) -> dict:
    if not rows:
        return {}
    default_rows = [row for row in rows if row.get("is_default")]
    if require_default and not default_rows:
        return {}
    return dict((default_rows or rows)[0])

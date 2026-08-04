"""Durable Founder Beta feedback persistence.

Production destination is Supabase `feedback_reports` (RLS-protected).
Local JSONL remains a development fallback when Supabase is unavailable.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from modules import app_config
from modules import auth_supabase
from modules import build_identity
from modules import performance


# Resolve against the repository root so local writes land even if CWD drifts.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_FEEDBACK_PATH = _REPO_ROOT / "data" / "feedback_reports.jsonl"
FEEDBACK_PATH = str(
    Path(os.environ.get("DYNASTYGM_FEEDBACK_PATH", str(_DEFAULT_FEEDBACK_PATH))).expanduser()
)
APP_BUILD_MARKER = build_identity.resolve_build_identity().revision or os.environ.get(
    "DYNASTYGM_BUILD", "local-beta"
)
GLOBAL_FEEDBACK_CATEGORIES = (
    "Bug or broken page",
    "Confusing page",
    "Bad recommendation",
    "Feature request",
    "Billing or Premium",
    "Wrong player/team/league data",
    "Other feedback",
)
FEEDBACK_CONTEXT_BLOCKLIST = {
    "access_token",
    "refresh_token",
    "token",
    "auth_token",
    "authorization",
    "supabase_anon_key",
    "anon_key",
    "espn_s2",
    "swid",
    "cookie",
    "cookies",
    "secret",
    "api_key",
    "password",
    "email",
}
_FEEDBACK_LOCK = threading.Lock()
FEEDBACK_TABLE = "feedback_reports"


def _clean_list(values) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, (list, tuple, set)):
        values = [values]
    cleaned = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def _json_safe(value: Any):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    try:
        if value != value:
            return None
    except Exception:
        pass
    return str(value)


def _safe_context(value: Any):
    safe = _json_safe(value)
    if not isinstance(safe, dict):
        return {}
    return {
        str(key): item
        for key, item in safe.items()
        if str(key).strip().casefold() not in FEEDBACK_CONTEXT_BLOCKLIST
    }


def viewport_category(width: int | None = None) -> str:
    try:
        value = int(width) if width is not None else 0
    except (TypeError, ValueError):
        value = 0
    if value <= 0:
        return "unknown"
    if value < 600:
        return "mobile"
    if value < 1024:
        return "tablet"
    return "desktop"


def build_feedback_report(
    *,
    page: str,
    surface: str,
    recommendation_type: str,
    username: str = "",
    league_id: str = "",
    league_name: str = "",
    team_id: str = "",
    roster_id: str = "",
    player_ids=None,
    player_names=None,
    recommendation_title: str = "",
    recommendation_summary: str = "",
    score_fields: dict | None = None,
    confidence_fields: dict | None = None,
    reason_fields: dict | None = None,
    issue_category: str = "",
    user_comment: str = "",
    app_build: str = APP_BUILD_MARKER,
) -> dict:
    return {
        "report_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "new",
        "page": str(page or "").strip(),
        "surface": str(surface or "").strip(),
        "recommendation_type": str(recommendation_type or "").strip(),
        "username": str(username or "").strip(),
        "league_id": str(league_id or "").strip(),
        "league_name": str(league_name or "").strip(),
        "team_id": str(team_id or "").strip(),
        "roster_id": str(roster_id or "").strip(),
        "player_ids": _clean_list(player_ids),
        "player_names": _clean_list(player_names),
        "recommendation_title": str(recommendation_title or "").strip(),
        "recommendation_summary": str(recommendation_summary or "").strip(),
        "score_fields": _json_safe(score_fields or {}),
        "confidence_fields": _json_safe(confidence_fields or {}),
        "reason_fields": _json_safe(reason_fields or {}),
        "issue_category": str(issue_category or "").strip(),
        "user_comment": str(user_comment or "").strip(),
        "app_build": str(app_build or APP_BUILD_MARKER).strip(),
    }


def build_global_feedback_report(
    *,
    category: str,
    message: str,
    context: dict | None = None,
    email: str = "",
    can_contact: bool = False,
    app_build: str = APP_BUILD_MARKER,
) -> dict:
    safe_context = _safe_context(context if isinstance(context, dict) else {})
    return {
        "report_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "new",
        "feedback_type": "global",
        "category": str(category or "").strip(),
        "message": str(message or "").strip(),
        "email": str(email or "").strip() if can_contact else "",
        "can_contact": bool(can_contact),
        "context": safe_context,
        "app_build": str(app_build or APP_BUILD_MARKER).strip(),
    }


def feedback_context_payload(
    *,
    current_page: str = "",
    platform: str = "",
    league_id: str = "",
    league_name: str = "",
    team_id: str = "",
    roster_id: str = "",
    user_id: str = "",
    email: str = "",
    entitlement: str = "",
    viewport_width: int | None = None,
    auth_state: str = "",
) -> dict:
    signed_in = bool(str(user_id or "").strip())
    return {
        "page": str(current_page or "").strip(),
        "platform": str(platform or "").strip(),
        "league_id": str(league_id or "").strip(),
        "roster_id": str(roster_id or "").strip(),
        "auth_state": str(auth_state or ("signed_in" if signed_in else "guest")).strip(),
        "entitlement": str(entitlement or "").strip(),
        "viewport_category": viewport_category(viewport_width),
        # Intentionally omit email and raw league names from automatic context.
    }


def submission_fingerprint(report: dict) -> str:
    payload = "|".join(
        [
            str(report.get("feedback_type") or report.get("recommendation_type") or ""),
            str(report.get("category") or report.get("issue_category") or ""),
            str(report.get("message") or report.get("user_comment") or ""),
            str((report.get("context") or {}).get("page") or report.get("page") or ""),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _supabase_row(report: dict) -> dict:
    context = report.get("context") if isinstance(report.get("context"), dict) else {}
    user_id = str(context.get("user_id") or report.get("user_id") or "").strip() or None
    # Prefer explicit top-level fields for global reports.
    return {
        "report_id": str(report.get("report_id") or uuid.uuid4()),
        "user_id": user_id,
        "feedback_type": str(report.get("feedback_type") or "global").strip() or "global",
        "category": str(
            report.get("category") or report.get("issue_category") or ""
        ).strip(),
        "message": str(
            report.get("message") or report.get("user_comment") or ""
        ).strip(),
        "email": str(report.get("email") or "").strip() if report.get("can_contact") else "",
        "can_contact": bool(report.get("can_contact")),
        "status": str(report.get("status") or "new").strip() or "new",
        "app_build": str(report.get("app_build") or APP_BUILD_MARKER).strip(),
        "context": _safe_context(context if context else report),
    }


def append_feedback_report_jsonl(report: dict, path: str = FEEDBACK_PATH) -> tuple[bool, str]:
    """Local / development fallback writer."""

    try:
        target = Path(path).expanduser()
        if not target.is_absolute():
            target = (_REPO_ROOT / target).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(_json_safe(report), ensure_ascii=True, separators=(",", ":"))
        with _FEEDBACK_LOCK:
            with target.open("a", encoding="utf-8") as handle:
                handle.write(payload + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        return True, ""
    except Exception as exc:
        return False, str(exc)


def append_feedback_report_supabase(
    report: dict,
    *,
    config: dict | None = None,
    access_token: str = "",
) -> tuple[bool, str]:
    """Persist one feedback report to the Supabase feedback_reports table."""

    resolved = config if isinstance(config, dict) else {}
    if not auth_supabase.is_configured(resolved):
        return False, "Accounts are not configured."
    row = _supabase_row(report)
    # Authenticated inserts must own the row; guests must keep user_id null.
    token = str(access_token or "").strip()
    if token:
        user_id = str(row.get("user_id") or "").strip()
        if not user_id:
            return False, "Signed-in feedback requires a user id."
    else:
        row["user_id"] = None
        # Use the anon key as bearer for guest inserts under the anon policy.
        token = str(resolved.get("anon_key") or "").strip()
        if not token:
            return False, "Guest feedback requires the public anon key."
    try:
        with performance.time_block("supabase_feedback_insert", category="supabase"):
            response = requests.post(
                f"{str(resolved.get('url') or '').rstrip('/')}/rest/v1/{FEEDBACK_TABLE}",
                headers={
                    **auth_supabase.auth_headers(resolved, token),
                    "Prefer": "return=minimal",
                },
                json=row,
                timeout=15,
            )
    except Exception:
        return False, "Could not reach Supabase feedback storage."
    if response.status_code >= 400:
        try:
            payload = response.json()
        except Exception:
            payload = {}
        message = str(
            (payload or {}).get("message")
            or (payload or {}).get("hint")
            or getattr(response, "text", "")
            or "Supabase feedback insert failed."
        ).strip()
        lowered = message.casefold()
        if (
            response.status_code == 404
            or "schema cache" in lowered
            or "could not find the table" in lowered
        ):
            return False, (
                "Supabase feedback_reports table is missing. "
                "Run docs/supabase_feedback.sql before relying on durable feedback."
            )
        return False, message or "Supabase feedback insert failed."
    return True, ""


def append_feedback_report(
    report: dict,
    path: str = FEEDBACK_PATH,
    *,
    config: dict | None = None,
    access_token: str = "",
    prefer_supabase: bool | None = None,
) -> tuple[bool, str]:
    """Append one feedback report to the Founder Beta destination.

    Production prefers Supabase. JSONL is retained as a local fallback so
    developer environments and temporary outages still capture reports.
    """

    use_supabase = prefer_supabase
    if use_supabase is None:
        use_supabase = bool(config) and auth_supabase.is_configured(config or {})

    if use_supabase:
        saved, error = append_feedback_report_supabase(
            report,
            config=config,
            access_token=access_token,
        )
        if saved:
            return True, ""
        # Fall back to local JSONL so the user still gets a success path in
        # local/dev environments when the table is not yet provisioned.
        fallback_ok, fallback_error = append_feedback_report_jsonl(report, path=path)
        if fallback_ok:
            return True, ""
        return False, error or fallback_error

    return append_feedback_report_jsonl(report, path=path)

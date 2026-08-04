import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Resolve against the repository root so production writes land in the
# intended Founder Beta feedback log even if process CWD drifts.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_FEEDBACK_PATH = _REPO_ROOT / "data" / "feedback_reports.jsonl"
FEEDBACK_PATH = str(
    Path(os.environ.get("DYNASTYGM_FEEDBACK_PATH", str(_DEFAULT_FEEDBACK_PATH))).expanduser()
)
APP_BUILD_MARKER = os.environ.get("DYNASTYGM_BUILD", "local-beta")
GLOBAL_FEEDBACK_CATEGORIES = (
    "Bad recommendation",
    "Confusing page",
    "Wrong player/team/league data",
    "Bug or broken page",
    "Premium/paywall issue",
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
}
_FEEDBACK_LOCK = threading.Lock()


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
        "email": str(email or "").strip(),
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
) -> dict:
    return {
        "page": str(current_page or "").strip(),
        "platform": str(platform or "").strip(),
        "league_id": str(league_id or "").strip(),
        "league_name": str(league_name or "").strip(),
        "team_id": str(team_id or "").strip(),
        "roster_id": str(roster_id or "").strip(),
        "user_id": str(user_id or "").strip(),
        "email": str(email or "").strip(),
        "entitlement": str(entitlement or "").strip(),
    }


def append_feedback_report(report: dict, path: str = FEEDBACK_PATH) -> tuple[bool, str]:
    """Append one feedback report to the Founder Beta feedback destination."""

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

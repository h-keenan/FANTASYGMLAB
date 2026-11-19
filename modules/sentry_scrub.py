"""PII / secret scrubbing for backend Sentry events.

Sentry's default scrubber matches a short denylist (password, secret, token, auth...). It does NOT know this app's
credential field names (`espn_s2`, `swid`) and keeps request bodies for JSON payloads, so a 500 raised while saving
ESPN cookies would have shipped them to a third party. `before_send` here is the belt to `max_request_body_size="never"`
braces: it drops request bodies/cookies/query strings and redacts any key or value that looks like a credential, email
address or bearer/JWT token, anywhere in the event (extra, contexts, breadcrumbs, exception messages, frames).

Pure functions, no sentry_sdk import, so they are unit-testable without the SDK.
"""

from __future__ import annotations

import re
from typing import Any

FILTERED = "[Filtered]"

_SENSITIVE_KEY = re.compile(
    r"(authori[sz]ation|cookie|token|secret|password|passwd|apikey|api_key|api-key|bearer|jwt|credential|"
    r"espn_s2|swid|email|session|signature|service_role|private_key)",
    re.IGNORECASE,
)
_JWT = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL_SECRET_PARAM = re.compile(r"(?i)([?&](?:access_token|refresh_token|token|apikey|api_key|key|code)=)[^&\s]+")

# Request members that can carry user content: never forwarded.
_DROPPED_REQUEST_KEYS = ("data", "cookies", "query_string", "env")

_MAX_DEPTH = 12


def scrub_text(text: str) -> str:
    """Redact JWTs, bearer tokens, email addresses and secret-bearing URL params inside a free-text string."""

    text = _JWT.sub(FILTERED, text)
    text = _BEARER.sub("Bearer " + FILTERED, text)
    text = _URL_SECRET_PARAM.sub(lambda m: m.group(1) + FILTERED, text)
    return _EMAIL.sub(FILTERED, text)


def _scrub(value: Any, depth: int = 0) -> Any:
    if depth > _MAX_DEPTH:
        return FILTERED
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and _SENSITIVE_KEY.search(key):
                out[key] = FILTERED
            else:
                out[key] = _scrub(item, depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [_scrub(item, depth + 1) for item in value]
    return value


def scrub_event(event: dict[str, Any], hint: dict[str, Any] | None = None) -> dict[str, Any]:
    """Sentry `before_send`-compatible scrubber. Always returns the event (never drops it)."""

    try:
        request = event.get("request")
        if isinstance(request, dict):
            for key in _DROPPED_REQUEST_KEYS:
                request.pop(key, None)
            headers = request.get("headers")
            if isinstance(headers, dict):
                request["headers"] = {
                    k: (
                        FILTERED
                        if _SENSITIVE_KEY.search(str(k)) or str(k).lower() in {"x-forwarded-for", "x-real-ip"}
                        else v
                    )
                    for k, v in headers.items()
                }
            if isinstance(request.get("url"), str):
                request["url"] = scrub_text(request["url"])
        user = event.get("user")
        if isinstance(user, dict):
            # Keep the opaque id for attribution; drop everything identifying.
            event["user"] = {"id": user["id"]} if user.get("id") else {}
        for key in ("extra", "contexts", "breadcrumbs", "exception", "message", "logentry", "tags", "transaction"):
            if key in event:
                event[key] = _scrub(event[key])
    except Exception:  # noqa: BLE001 - scrubbing must never lose an error report
        pass
    return event


def scrub_breadcrumb(crumb: dict[str, Any], hint: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        return _scrub(crumb)
    except Exception:  # noqa: BLE001
        return crumb


def sentry_init_options() -> dict[str, Any]:
    """Privacy-safe options to merge into `sentry_sdk.init(...)`."""

    return {
        "send_default_pii": False,
        "max_request_body_size": "never",
        "before_send": scrub_event,
        "before_breadcrumb": scrub_breadcrumb,
    }

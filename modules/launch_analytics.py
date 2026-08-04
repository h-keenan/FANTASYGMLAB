"""Minimal privacy-conscious Founder Beta launch analytics.

Records coarse product milestones without PII. Disabled unless
DYNASTYGM_LAUNCH_ANALYTICS=1. Safe to leave off for launch.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from modules import build_identity


_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_PATH = _REPO_ROOT / "data" / "launch_analytics.jsonl"
ANALYTICS_PATH = str(
    Path(os.environ.get("DYNASTYGM_LAUNCH_ANALYTICS_PATH", str(_DEFAULT_PATH))).expanduser()
)
ENABLED = str(os.environ.get("DYNASTYGM_LAUNCH_ANALYTICS", "")).strip().casefold() in {
    "1",
    "true",
    "yes",
    "on",
}

# Coarse product milestones only — no tokens, emails, or roster payloads.
TRACKED_EVENTS = {
    "landing_visit",
    "account_created",
    "league_imported",
    "dashboard_reached",
    "trade_hub_opened",
    "player_quick_view_opened",
    "premium_checkout_started",
    "premium_checkout_completed",
    "feedback_submitted",
}

_LOCK = threading.Lock()
_SESSION_EMITTED: set[str] = set()


def _safe_props(props: dict | None) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in (props or {}).items():
        name = str(key or "").strip().casefold()
        if not name or name in {"email", "token", "access_token", "password", "cookie"}:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            clean[str(key)] = value
        else:
            clean[str(key)] = str(value)[:120]
    return clean


def track_event(event: str, *, props: dict | None = None, once_key: str = "") -> bool:
    """Append one analytics event when launch analytics is enabled."""

    name = str(event or "").strip()
    if not ENABLED or name not in TRACKED_EVENTS:
        return False
    if once_key:
        marker = f"{name}:{once_key}"
        if marker in _SESSION_EMITTED:
            return False
        _SESSION_EMITTED.add(marker)
    payload = {
        "event": name,
        "ts": time.time(),
        "build": build_identity.resolve_build_identity().revision,
        "props": _safe_props(props),
    }
    try:
        target = Path(ANALYTICS_PATH)
        if not target.is_absolute():
            target = (_REPO_ROOT / target).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        with _LOCK:
            with target.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return True
    except Exception:
        return False

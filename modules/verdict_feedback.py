"""'Report a bad verdict': a small, privacy-safe feedback record.

Reuses the existing ``feedback_reports`` table (docs/supabase_feedback.sql,
the Founder Beta feedback destination reviewed in the Supabase dashboard)
instead of adding a new store. Privacy rules, enforced here and not left to
callers:

* the row is inserted as an anonymous report (``user_id`` null, the table's
  guest-insert policy), so no auth uid is stored; the only account reference
  is a one-way ``account_hash`` inside ``context`` (HMAC-SHA256, 16 hex chars)
  that lets a reviewer see "three reports from one account" without being able
  to recover who it is;
* no free text, email or contact flag: the reporter picks one of a fixed set
  of reasons;
* ``context`` holds only what is needed to reproduce the question: league id
  (a public Sleeper identifier), player/pick ids (public), the verdict label,
  confidence and value delta that were shown, and the assumptions line.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from collections.abc import Mapping
from typing import Any

FEEDBACK_TABLE = "feedback_reports"
FEEDBACK_TYPE = "bad_verdict"
# Reason key -> label shown to the reporter (kept here so the API, web and app
# agree on one list; clients send the key).
REASONS: dict[str, str] = {
    "lineup_wrong": "Wrong about my lineup",
    "injury_wrong": "Injury or availability is off",
    "values_off": "Player values look off",
    "partner_wouldnt": "The other manager would never do this",
    "other": "Something else",
}
SURFACES = frozenset({"trade_analyzer", "trade_hub", "trade_finder"})
PLATFORMS = frozenset({"web", "ios", "android"})
MAX_IDS = 10
MAX_ID_LEN = 64
HASH_SALT_ENV = "FEEDBACK_ACCOUNT_HASH_SALT"
_DEFAULT_SALT = "fantasydesk-verdict-feedback-v1"


def account_hash(user_id: str, *, environ: Mapping[str, str] | None = None) -> str:
    """One-way, stable reference to an account (16 hex chars)."""

    env = environ if environ is not None else os.environ
    salt = (env.get(HASH_SALT_ENV) or _DEFAULT_SALT).encode("utf-8")
    return hmac.new(salt, str(user_id).encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def _ids(values: Any) -> list[str]:
    out: list[str] = []
    for value in values or []:
        text = str(value or "").strip()[:MAX_ID_LEN]
        if text and text not in out:
            out.append(text)
        if len(out) >= MAX_IDS:
            break
    return out


def _short(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def build_feedback_row(
    *,
    user_id: str,
    reason: str,
    surface: str,
    platform: str,
    league_id: str,
    lens: str,
    strategy: str,
    send_ids: Any,
    receive_ids: Any,
    verdict_label: str,
    confidence: str,
    value_delta: Any,
    assumptions_line: str,
    app_build: str = "",
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    """The ``feedback_reports`` row, or None when reason/surface is not recognised."""

    if reason not in REASONS or surface not in SURFACES:
        return None
    try:
        delta: float | None = round(float(value_delta), 1)
    except (TypeError, ValueError):
        delta = None
    return {
        "report_id": str(uuid.uuid4()),
        "user_id": None,
        "feedback_type": FEEDBACK_TYPE,
        "category": reason,
        "message": "",
        "email": "",
        "can_contact": False,
        "app_build": _short(app_build, 40),
        "context": {
            "surface": surface,
            "platform": platform if platform in PLATFORMS else "unknown",
            "account_hash": account_hash(user_id, environ=environ),
            "league_id": _short(league_id, MAX_ID_LEN),
            "lens": _short(lens, 20),
            "strategy": _short(strategy, 20),
            "send_ids": _ids(send_ids),
            "receive_ids": _ids(receive_ids),
            "verdict": _short(verdict_label, 20),
            "confidence": _short(confidence, 40),
            "value_delta": delta,
            "assumptions": _short(assumptions_line, 600),
        },
    }

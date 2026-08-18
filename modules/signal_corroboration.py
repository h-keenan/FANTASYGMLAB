"""Deterministic news ↔ structured Sleeper status corroboration.

Articles never rewrite Sleeper status. Labels stay conservative.
"""

from __future__ import annotations

from typing import Any, Mapping

from modules import news_signal

LABEL_CORROBORATED = "CORROBORATED"
LABEL_AWAITING = "AWAITING STATUS UPDATE"
LABEL_CONFLICT = "POTENTIAL CONFLICT"
LABEL_NEWS_ONLY = "NEWS ONLY"

STATUS_HEALTHY = "HEALTHY"
STATUS_Q = "Q"
STATUS_D = "D"
STATUS_OUT = "OUT"
STATUS_IR = "IR"
STATUS_PUP = "PUP"
STATUS_OTHER = "OTHER"

FT_INJURY = "INJURY"
FT_INJURY_SEVERITY_UPDATE = "INJURY_SEVERITY_UPDATE"
FT_IR_PUP_NFI = "IR_PUP_NFI"
FT_RETURN_TO_PRACTICE = "RETURN_TO_PRACTICE"
FT_RETURN_TO_PLAY = "RETURN_TO_PLAY"
FT_INACTIVE = "INACTIVE"
FT_ACTIVE = "ACTIVE"

_SEVERE = frozenset({STATUS_OUT, STATUS_IR, STATUS_PUP})


def normalize_sleeper_status(status: str = "", injury_status: str = "") -> str:
    blob = f"{status} {injury_status}".strip().lower()
    if not blob or blob in {"none", "healthy", "active"}:
        return STATUS_HEALTHY
    if "pup" in blob or "physically unable" in blob:
        return STATUS_PUP
    if "nfi" in blob or "non-football" in blob:
        return STATUS_IR
    if (
        "injured reserve" in blob
        or blob == "ir"
        or " ir" in f" {blob}"
        or blob.startswith("ir ")
        or blob.endswith(" ir")
    ):
        return STATUS_IR
    if "out" in blob or "inactive" in blob:
        return STATUS_OUT
    if "doubtful" in blob:
        return STATUS_D
    if "questionable" in blob or "probable" in blob or "limited" in blob:
        return STATUS_Q
    return STATUS_OTHER


def _event_payload(event: Mapping[str, Any] | object | None) -> dict[str, Any]:
    if event is None:
        return {}
    if hasattr(event, "as_dict"):
        return dict(event.as_dict())
    if isinstance(event, Mapping):
        return dict(event)
    return {}


def implied_news_status(event: Mapping[str, Any] | object | None) -> str:
    """Best-effort implied status from classified news. Empty → unknown."""

    payload = _event_payload(event)
    event_type = str(payload.get("event_type") or "")
    text = " ".join(
        (
            str(payload.get("article_title") or ""),
            str(payload.get("explanation") or ""),
            " ".join(str(x) for x in (payload.get("matched_evidence") or ())),
        )
    ).lower()
    if event_type in {FT_RETURN_TO_PRACTICE, FT_RETURN_TO_PLAY, FT_ACTIVE}:
        return STATUS_HEALTHY
    if event_type == FT_IR_PUP_NFI:
        if "pup" in text:
            return STATUS_PUP
        return STATUS_IR
    if event_type == FT_INACTIVE:
        return STATUS_OUT
    if "ruled out" in text or "will not play" in text or "out for sunday" in text:
        return STATUS_OUT
    if "multiple weeks" in text or "several weeks" in text or "out for the season" in text:
        return STATUS_IR
    if "doubtful" in text:
        return STATUS_D
    if "questionable" in text or "limited" in text:
        return STATUS_Q
    if event_type in {FT_INJURY, FT_INJURY_SEVERITY_UPDATE}:
        return STATUS_Q
    return ""


def corroborate_news_with_status(
    event: Mapping[str, Any] | object | None,
    *,
    sleeper_status: str = "",
    injury_status: str = "",
    player_id: str = "",
) -> dict[str, Any]:
    """Return public corroboration label + conservative confidence note."""

    payload = _event_payload(event)
    pid = str(player_id or payload.get("player_id") or "").strip()
    implied = implied_news_status(payload)
    structured = normalize_sleeper_status(sleeper_status, injury_status)

    if not implied:
        return {
            "label": LABEL_NEWS_ONLY,
            "implied_status": "",
            "sleeper_status": structured,
            "note": "News only — structured status not compared.",
            "confidence": news_signal.CONFIDENCE_SPECULATION,
        }
    if not pid:
        return {
            "label": LABEL_NEWS_ONLY,
            "implied_status": implied,
            "sleeper_status": structured,
            "note": "Player mapping unavailable — news is not joined to Sleeper status.",
            "confidence": news_signal.CONFIDENCE_SPECULATION,
        }

    if implied == structured:
        return {
            "label": LABEL_CORROBORATED,
            "implied_status": implied,
            "sleeper_status": structured,
            "note": "News and Sleeper status agree.",
            "confidence": news_signal.CONFIDENCE_STRONG,
        }

    if implied in _SEVERE and structured in _SEVERE:
        return {
            "label": LABEL_CORROBORATED,
            "implied_status": implied,
            "sleeper_status": structured,
            "note": "News and Sleeper both show a severe availability hit.",
            "confidence": news_signal.CONFIDENCE_STRONG,
        }

    if implied in {STATUS_Q, STATUS_D} and structured in {STATUS_Q, STATUS_D}:
        return {
            "label": LABEL_CORROBORATED,
            "implied_status": implied,
            "sleeper_status": structured,
            "note": "News and Sleeper both show a game-status designation.",
            "confidence": news_signal.CONFIDENCE_OBSERVATION,
        }

    if implied in _SEVERE and structured in {STATUS_Q, STATUS_D, STATUS_HEALTHY, STATUS_OTHER}:
        return {
            "label": LABEL_AWAITING,
            "implied_status": implied,
            "sleeper_status": structured,
            "note": "News is ahead of structured Sleeper status.",
            "confidence": news_signal.CONFIDENCE_OBSERVATION,
        }

    if implied == STATUS_HEALTHY and structured in _SEVERE:
        return {
            "label": LABEL_CONFLICT,
            "implied_status": implied,
            "sleeper_status": structured,
            "note": "News conflicts with current Sleeper status — Sleeper is not rewritten.",
            "confidence": news_signal.CONFIDENCE_OBSERVATION,
        }

    if implied in {STATUS_Q, STATUS_D} and structured == STATUS_HEALTHY:
        return {
            "label": LABEL_AWAITING,
            "implied_status": implied,
            "sleeper_status": structured,
            "note": "News reports a designation Sleeper has not synced yet.",
            "confidence": news_signal.CONFIDENCE_OBSERVATION,
        }

    if implied == STATUS_HEALTHY and structured in {STATUS_Q, STATUS_D}:
        return {
            "label": LABEL_AWAITING,
            "implied_status": implied,
            "sleeper_status": structured,
            "note": "News suggests improvement; Sleeper designation has not cleared.",
            "confidence": news_signal.CONFIDENCE_OBSERVATION,
        }

    return {
        "label": LABEL_NEWS_ONLY,
        "implied_status": implied,
        "sleeper_status": structured,
        "note": "Not enough agreement to corroborate structured status.",
        "confidence": news_signal.CONFIDENCE_SPECULATION,
    }


def public_status_line(sleeper_status: str, injury_status: str = "") -> str:
    code = normalize_sleeper_status(sleeper_status, injury_status)
    if code == STATUS_HEALTHY:
        return ""
    labels = {
        STATUS_Q: "QUESTIONABLE",
        STATUS_D: "DOUBTFUL",
        STATUS_OUT: "OUT",
        STATUS_IR: "IR",
        STATUS_PUP: "PUP",
    }
    pretty = labels.get(code, code)
    return f"STATUS: {pretty}"

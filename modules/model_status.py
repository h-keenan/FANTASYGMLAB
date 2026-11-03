"""Explicit "this answer came from a degraded path" markers.

The trade engine has several places where an input can legitimately be missing
(offseason, no weekly history, a brand-new league) and several where a lookup
can FAIL (a database blip, a malformed row). Those are different situations.
A legitimately missing input is a named mode the engine already labels (for
example the lineup model's ``basis``). A failure used to be swallowed by a
bare ``except Exception`` and answered from a fallback that looked identical
to the real thing, so two identical requests could be decided by different
procedures with nothing in the payload saying so.

This module is the single vocabulary for the second case:

* ``DATA_ERRORS`` / ``LOOKUP_ERRORS``: the exception types that mean "this
  input was unusable / unavailable". Anything else is a programming error and
  must propagate (and reach the unhandled-exception logger) instead of being
  papered over by a fallback.
* ``status`` / ``add`` / ``merge``: a small JSON-ready ``model_status`` payload
  (``{"degraded": bool, "reasons": [{"code", "message"}]}``) that every
  surface can show as a "limited data" note.

It never changes a number or a verdict; it only reports which path ran.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Iterable, Mapping

# The input the model was handed was the wrong shape / missing a column / out
# of range. Expected at the data boundary; never a reason to hide a bug.
DATA_ERRORS: tuple[type[BaseException], ...] = (
    KeyError,
    ValueError,
    TypeError,
    IndexError,
    ArithmeticError,
)

# A lookup against storage or the network failed (``requests`` errors are
# ``OSError`` subclasses; so are timeouts).
LOOKUP_ERRORS: tuple[type[BaseException], ...] = DATA_ERRORS + (OSError, sqlite3.Error)

# code -> short user-facing sentence. One place, so web and mobile can show the
# same words and tests can assert a code rather than a string.
MESSAGES: dict[str, str] = {
    "lineup_model_failed": (
        "The lineup model could not run for this trade, so it was graded on market value only."
    ),
    "posture_lookup_failed": (
        "Your team's standing could not be loaded, so this uses a default team posture."
    ),
    "declared_stance_failed": (
        "Your saved Team Situation could not be loaded, so this may not reflect the stance you set."
    ),
    "projection_baselines_failed": (
        "Weekly projections could not be loaded, so lineup impact uses a value-based estimate."
    ),
    "keeper_settings_failed": (
        "Your keeper settings could not be loaded, so keeper values were not applied."
    ),
    "teams_skipped": "Some teams could not be graded and are missing from this board.",
    "need_model_failed": (
        "Your roster's needs could not be fully modeled, so this uses a simpler coverage check."
    ),
    "untouchable_lookup_failed": (
        "Your untouchable players could not be loaded, so no drops are suggested."
    ),
    "drop_model_failed": "Suggested drops could not be computed for this roster.",
    "usage_trends_unavailable": (
        "Recent usage trends could not be loaded, so hot-streak protection is not applied."
    ),
}


class KeeperPricingUnavailable(Exception):
    """A keeper league's stored round penalty could not be read.

    Pricing the league with no penalty (and caching that as if it were right)
    would silently misprice every player and pick, so callers must handle it.
    """


def ok() -> dict[str, Any]:
    return {"degraded": False, "reasons": []}


def add(status: dict[str, Any], code: str, message: str = "") -> dict[str, Any]:
    """Append ``code`` to ``status`` (once) and mark it degraded."""

    reasons = status.setdefault("reasons", [])
    if not any(r.get("code") == code for r in reasons):
        reasons.append({"code": code, "message": message or MESSAGES.get(code, code)})
    status["degraded"] = True
    return status


def from_codes(codes: Iterable[str]) -> dict[str, Any]:
    status = ok()
    for code in codes:
        add(status, code)
    return status


def merge(*statuses: Mapping[str, Any] | None) -> dict[str, Any]:
    out = ok()
    for status in statuses:
        for reason in (status or {}).get("reasons") or ():
            add(out, str(reason.get("code") or ""), str(reason.get("message") or ""))
    return out


def merge_into(status: dict[str, Any], other: Mapping[str, Any] | None) -> dict[str, Any]:
    for reason in (other or {}).get("reasons") or ():
        add(status, str(reason.get("code") or ""), str(reason.get("message") or ""))
    return status


def codes(status: Mapping[str, Any] | None) -> list[str]:
    return [str(r.get("code")) for r in (status or {}).get("reasons") or ()]


# Frames carry the codes of any degraded input they were built from in
# ``DataFrame.attrs`` so the model that later receives the frame can report it.
FRAME_ATTR = "degraded_reasons"


def mark_frame(frame: Any, code: str) -> Any:
    if frame is not None and hasattr(frame, "attrs"):
        existing = list(frame.attrs.get(FRAME_ATTR) or [])
        if code not in existing:
            existing.append(code)
        frame.attrs[FRAME_ATTR] = existing
    return frame


def frame_codes(frame: Any) -> list[str]:
    return list(getattr(frame, "attrs", {}).get(FRAME_ATTR) or []) if frame is not None else []

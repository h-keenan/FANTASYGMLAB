"""Reusable dense-list presentation helpers (HTML only; no ranking math).

Canonical anatomy:
  lead → identity → primary metric → status → supporting meta → exception

Owners: this module for HTML slots; modules/dense_list_styles.py for layout CSS.
"""

from __future__ import annotations

from html import escape
from typing import Literal

DensityTier = Literal["compact", "standard", "rich"]

# Presentation-only metric label compressions (does not change underlying scores).
_METRIC_LABEL_ALIASES = {
    "starter-weighted score": "Starter score",
    "franchise value": "Franchise",
    "franchise score": "Franchise",
    "draft capital": "Draft capital",
    "draft capital score": "Draft capital",
    "roster value + draft capital": "Roster + draft",
    "power score": "Power",
}


def compact_metric_label(label: str) -> str:
    text = " ".join(str(label or "").split())
    if not text:
        return "Score"
    return _METRIC_LABEL_ALIASES.get(text.casefold(), text)


def normalize_status_pair(category: str, subtype: str) -> tuple[str, str]:
    """Return structured category/subtype without duplicate presentation."""

    cat = " ".join(str(category or "").split())
    sub = " ".join(str(subtype or "").split())
    if not cat:
        return sub, ""
    if not sub:
        return cat, ""
    if cat.casefold() == sub.casefold():
        return cat, ""
    prefix = cat.casefold() + " "
    if sub.casefold().startswith(prefix):
        remainder = sub[len(cat) :].strip(" ·-")
        return cat, remainder
    return cat, sub


def dense_metric_html(value: str, label: str, *, compact_label: bool = True) -> str:
    readable_value = escape(str(value or "—"))
    readable_label = escape(
        compact_metric_label(label) if compact_label else (" ".join(str(label or "").split()) or "Score")
    )
    return (
        "<div class='dg-dense-metric'>"
        f"<span class='dg-dense-metric__value'>{readable_value}</span>"
        f"<span class='dg-dense-metric__label'>{readable_label}</span>"
        "</div>"
    )


def dense_status_html(category: str, subtype: str = "") -> str:
    primary, secondary = normalize_status_pair(category, subtype)
    if not primary and not secondary:
        return ""
    parts = [
        f"<span class='dg-dense-status__primary'>{escape(primary)}</span>"
    ]
    if secondary:
        parts.append(
            f"<span class='dg-dense-status__secondary'>{escape(secondary)}</span>"
        )
    return f"<div class='dg-dense-status'>{''.join(parts)}</div>"


def dense_meta_html(*parts: str) -> str:
    cleaned = [escape(" ".join(str(part).split())) for part in parts if str(part or "").strip()]
    if not cleaned:
        return ""
    joined = "<span class='dg-dense-meta__sep' aria-hidden='true'>·</span>".join(
        f"<span class='dg-dense-meta__item'>{item}</span>" for item in cleaned
    )
    return f"<div class='dg-dense-meta'>{joined}</div>"


def dense_exception_html(text: str, *, label: str = "Concern") -> str:
    """Exception-only attention. Empty/zero concerns must not call this."""

    body = " ".join(str(text or "").split())
    if not body:
        return ""
    return (
        "<div class='dg-dense-exception' role='status'>"
        f"<span class='dg-dense-exception__label'>{escape(label)}</span>"
        f"<span class='dg-dense-exception__value'>{escape(body)}</span>"
        "</div>"
    )


def dense_identity_html(
    *,
    primary: str,
    secondary: str = "",
    leading_html: str = "",
) -> str:
    secondary_html = (
        f"<div class='dg-dense-identity__secondary'>{escape(secondary)}</div>"
        if secondary
        else ""
    )
    return (
        "<div class='dg-dense-identity'>"
        + (leading_html or "")
        + "<div class='dg-dense-identity__copy'>"
        f"<div class='dg-dense-identity__primary'>{escape(primary)}</div>"
        + secondary_html
        + "</div></div>"
    )

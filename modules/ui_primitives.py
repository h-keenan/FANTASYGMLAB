"""Small, token-backed presentation primitives for DynastyGM.

All string inputs are escaped. Actions are ordinary links restricted to relative
application destinations or http(s) URLs. Native Streamlit buttons remain owned
by callers; ``action_row`` only coordinates their layout.
"""

from __future__ import annotations

from html import escape
from typing import Callable, Literal
from urllib.parse import urlparse

import streamlit as st

from modules.html_rendering import render_html_fragment

BadgeVariant = Literal[
    "neutral",
    "information",
    "opportunity",
    "success",
    "caution",
    "danger",
    "premium",
    "experimental",
]
CardVariant = Literal[
    "default",
    "elevated",
    "interactive",
    "premium",
    "experimental",
    "warning",
]
EmptyStateKind = Literal["no-data", "filtered-empty", "unavailable", "error"]

BADGE_VARIANTS = frozenset(
    {"neutral", "information", "opportunity", "success", "caution", "danger", "premium", "experimental"}
)
CARD_VARIANTS = frozenset({"default", "elevated", "interactive", "premium", "experimental", "warning"})
EMPTY_STATE_KINDS = frozenset({"no-data", "filtered-empty", "unavailable", "error"})


def _text(value: object) -> str:
    return escape(str(value or "").strip())


def _variant(value: str, allowed: frozenset[str], default: str) -> str:
    normalized = str(value or "").strip().casefold()
    return normalized if normalized in allowed else default


def _safe_href(value: object) -> str:
    href = str(value or "").strip()
    parsed = urlparse(href)
    if not href or parsed.scheme not in {"", "http", "https"} or href.startswith("//"):
        raise ValueError("Primitive actions require a relative or http(s) destination.")
    return escape(href, quote=True)


def _action_html(label: object, href: object, *, class_name: str = "dg-ui-inline-action") -> str:
    return (
        f'<a class="{class_name}" href="{_safe_href(href)}">'
        f"{_text(label)}</a>"
    )


def section_header_html(
    title: object,
    *,
    subtitle: object = "",
    eyebrow: object = "",
    trailing_action: tuple[object, object] | None = None,
    heading_level: int = 2,
    weight: str = "context",
) -> str:
    """Build a section heading. Heading levels are constrained to h2-h4."""

    level = heading_level if heading_level in {2, 3, 4} else 2
    role = str(weight or "context").strip().casefold()
    if role not in {"primary", "secondary", "context", "support"}:
        role = "context"
    eyebrow_html = f'<div class="dg-ui-eyebrow">{_text(eyebrow)}</div>' if _text(eyebrow) else ""
    subtitle_html = (
        f'<p class="dg-ui-section-subtitle">{_text(subtitle)}</p>'
        if _text(subtitle)
        else ""
    )
    action_html = (
        _action_html(*trailing_action, class_name="dg-ui-section-action")
        if trailing_action
        else ""
    )
    return (
        f'<header class="dg-ui-section-header dg-ui-section-header--{role}">'
        '<div class="dg-ui-section-header-copy">'
        f"{eyebrow_html}<h{level} class=\"dg-ui-section-title\">{_text(title)}</h{level}>"
        f"{subtitle_html}</div>{action_html}</header>"
    )


def content_card_html(
    body: object,
    *,
    variant: CardVariant = "default",
    title: object = "",
    items: tuple[object, ...] = (),
    metadata: object = "",
    footer: object = "",
    action: tuple[object, object] | None = None,
) -> str:
    """Build a text-content card; arbitrary/trusted child HTML is not accepted."""

    tone = _variant(variant, CARD_VARIANTS, "default")
    if tone == "interactive" and action is None:
        raise ValueError("Interactive cards require a labeled destination.")
    title_html = f'<h3 class="dg-ui-card-title">{_text(title)}</h3>' if _text(title) else ""
    body_html = f'<div class="dg-ui-card-body">{_text(body)}</div>' if _text(body) else ""
    items_html = (
        '<ol class="dg-ui-card-list">'
        + "".join(
            f'<li class="dg-ui-card-list-item">{_text(item)}</li>'
            for item in items
            if _text(item)
        )
        + "</ol>"
        if any(_text(item) for item in items)
        else ""
    )
    metadata_html = (
        f'<div class="dg-ui-card-metadata">{_text(metadata)}</div>'
        if _text(metadata)
        else ""
    )
    footer_html = f'<div class="dg-ui-card-footer">{_text(footer)}</div>' if _text(footer) else ""
    card = (
        f'<article class="dg-ui-card dg-ui-card--{tone}">'
        f"{title_html}{body_html}{items_html}{metadata_html}{footer_html}</article>"
    )
    if action is None:
        return card
    label, href = action
    return (
        f'<a class="dg-ui-card-link" href="{_safe_href(href)}" '
        f'aria-label="{_text(label)}">{card}</a>'
    )


def status_badge_html(label: object, *, variant: BadgeVariant = "neutral") -> str:
    """Build a concise, non-interactive status badge with visible state text."""

    tone = _variant(variant, BADGE_VARIANTS, "neutral")
    return (
        f'<span class="dg-ui-badge dg-ui-badge--{tone}" '
        f'aria-label="{escape(tone.title())} status: {_text(label)}">{_text(label)}</span>'
    )


def empty_state_panel_html(
    title: object,
    explanation: object,
    *,
    kind: EmptyStateKind,
    primary_action: tuple[object, object] | None = None,
    secondary_action: tuple[object, object] | None = None,
    recovery_guidance: object = "",
) -> str:
    """Build an explicitly classified empty state with up to two safe links."""

    resolved_kind = _variant(kind, EMPTY_STATE_KINDS, "no-data")
    actions = ""
    if primary_action:
        actions += _action_html(
            *primary_action,
            class_name="dg-ui-inline-action dg-ui-inline-action--primary",
        )
    if secondary_action:
        actions += _action_html(
            *secondary_action,
            class_name="dg-ui-inline-action dg-ui-inline-action--secondary",
        )
    actions_html = f'<div class="dg-ui-empty-state-actions">{actions}</div>' if actions else ""
    recovery_html = (
        f'<div class="dg-ui-empty-state-recovery">{_text(recovery_guidance)}</div>'
        if _text(recovery_guidance)
        else ""
    )
    return (
        f'<section class="dg-ui-empty-state" data-empty-kind="{resolved_kind}" '
        f'aria-label="{_text(title)}">'
        f'<h3 class="dg-ui-empty-state-title">{_text(title)}</h3>'
        f'<div class="dg-ui-empty-state-body">{_text(explanation)}</div>'
        f"{recovery_html}{actions_html}</section>"
    )


def render_section_header(*args, **kwargs) -> None:
    render_html_fragment(section_header_html(*args, **kwargs))


def render_content_card(*args, **kwargs) -> None:
    render_html_fragment(content_card_html(*args, **kwargs))


def render_status_badge(*args, **kwargs) -> None:
    render_html_fragment(status_badge_html(*args, **kwargs))


def render_empty_state_panel(*args, **kwargs) -> None:
    render_html_fragment(empty_state_panel_html(*args, **kwargs))


def render_action_row(
    primary_action: Callable[[], None],
    *,
    key: str,
    secondary_action: Callable[[], None] | None = None,
    destructive_action: Callable[[], None] | None = None,
    tertiary_action: Callable[[], None] | None = None,
    primary_first: bool = False,
    horizontal_alignment: Literal["left", "center", "right", "distribute"] = "right",
) -> None:
    """Lay out caller-owned native actions without changing button behavior."""

    normalized_key = str(key or "").strip()
    if not normalized_key:
        raise ValueError("Action rows require a unique non-empty key.")
    if destructive_action is not None and tertiary_action is not None:
        raise ValueError("Action rows accept either a destructive or tertiary action, not both.")

    trailing_action = destructive_action or tertiary_action
    with st.container(
        key=f"dg_ui_action_row_{normalized_key}",
        horizontal=True,
        horizontal_alignment=horizontal_alignment,
        vertical_alignment="center",
        gap="small",
    ):
        if primary_first:
            primary_action()
        if secondary_action is not None:
            secondary_action()
        if trailing_action is not None:
            trailing_action()
        if not primary_first:
            primary_action()


AUTO_STRATEGY_HELP_TITLE = "What is Auto?"
AUTO_STRATEGY_HELP_BODY = (
    "Auto follows your team's evaluated direction. "
    "Changing the lens re-ranks otherwise valid recommendations without skipping fairness checks."
)


def render_auto_strategy_help(*, key: str, body: str = "") -> None:
    """Visible explanation control — never a bare Streamlit help= tooltip dot."""

    normalized_key = str(key or "").strip()
    if not normalized_key:
        raise ValueError("Auto strategy help requires a unique non-empty key.")
    copy = str(body or "").strip() or AUTO_STRATEGY_HELP_BODY
    with st.popover(AUTO_STRATEGY_HELP_TITLE, key=normalized_key):
        st.write(copy)

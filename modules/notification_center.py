"""Founder Beta Notification Center shell.

Presentation and workflow only — no football, entitlement, billing, or auth logic.
Provides deterministic demo notifications and a durable event shape for future delivery.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Callable, Sequence

import streamlit as st

from modules import brand_identity
from modules.html_rendering import render_html_fragment


NOTIFICATION_CATEGORIES: tuple[str, ...] = (
    "Trades",
    "Waivers",
    "League",
    "Injuries",
    "Live Draft",
    "Product updates",
)


@dataclass(frozen=True)
class NotificationItem:
    """Stable notification shape for Founder Beta demos and future delivery."""

    id: str
    category: str
    title: str
    body: str
    unread: bool = True
    href_hint: str = ""
    age_label: str = "Just now"


FOUNDER_BETA_DEMO_NOTIFICATIONS: tuple[NotificationItem, ...] = (
    NotificationItem(
        id="demo-trade-1",
        category="Trades",
        title="Trade board updated",
        body="A high-fit package is ready in Trade Hub.",
        unread=True,
        href_hint="trade_hub",
        age_label="12m",
    ),
    NotificationItem(
        id="demo-waiver-1",
        category="Waivers",
        title="Waiver priority shifted",
        body="A depth target entered your top shortlist.",
        unread=True,
        href_hint="waivers",
        age_label="34m",
    ),
    NotificationItem(
        id="demo-injury-1",
        category="Injuries",
        title="Starter availability watch",
        body="An injury note affects a projected starter.",
        unread=True,
        href_hint="my_team",
        age_label="1h",
    ),
    NotificationItem(
        id="demo-league-1",
        category="League",
        title="League context refreshed",
        body="War Room identity and roster context are current.",
        unread=False,
        href_hint="dashboard",
        age_label="Today",
    ),
    NotificationItem(
        id="demo-draft-1",
        category="Live Draft",
        title="Live Draft early access",
        body="Open Live Draft from the GM Orb when a room is active.",
        unread=False,
        href_hint="live_draft",
        age_label="Beta",
    ),
    NotificationItem(
        id="demo-product-1",
        category="Product updates",
        title=f"{brand_identity.FOUNDER_BETA_LABEL} command header",
        body="Alerts, league, Premium, and Feedback share one executive bar.",
        unread=False,
        href_hint="",
        age_label="Product",
    ),
)


def unread_count(items: Sequence[NotificationItem]) -> int:
    return sum(1 for item in items if item.unread)


def list_founder_beta_notifications(
    *,
    session: dict | None = None,
) -> tuple[NotificationItem, ...]:
    """Return deterministic Founder Beta notifications.

    Session is accepted for future real delivery hooks without changing callers.
    """

    _ = session
    return FOUNDER_BETA_DEMO_NOTIFICATIONS


def notification_item_html(item: NotificationItem) -> str:
    state = "is-unread" if item.unread else "is-read"
    hint = escape(item.href_hint) if item.href_hint else ""
    return (
        f"<article class='dg-notification-item {state}' data-notification-id='{escape(item.id)}'"
        f"{f' data-href-hint={chr(34)}{hint}{chr(34)}' if hint else ''}>"
        f"<div class='dg-notification-item__meta'>"
        f"<span class='dg-notification-item__category'>{escape(item.category)}</span>"
        f"<span class='dg-notification-item__age'>{escape(item.age_label)}</span>"
        "</div>"
        f"<div class='dg-notification-item__title'>{escape(item.title)}</div>"
        f"<p class='dg-notification-item__body'>{escape(item.body)}</p>"
        "</article>"
    )


def render_notification_center(
    *,
    items: Sequence[NotificationItem] | None = None,
    on_open_destination: Callable[[str], None] | None = None,
    key_prefix: str = "executive_notifications",
) -> None:
    """Render the Notification Center shell as a compact popover control."""

    resolved = tuple(items if items is not None else list_founder_beta_notifications(session=st.session_state))
    count = unread_count(resolved)
    label = f"Alerts ({count})" if count else "Alerts"
    help_text = f"{brand_identity.PRODUCT_NAME} notification center"

    with st.container(key=f"{key_prefix}_control"):
        render_html_fragment("<span class='dg-notification-marker' aria-hidden='true'></span>")
        with st.popover(label, help=help_text):
            render_html_fragment(
                "<div class='dg-notification-panel'>"
                "<div class='dg-notification-panel__header'>"
                f"<div class='dg-notification-panel__kicker'>{escape(brand_identity.FOUNDER_BETA_LABEL)}</div>"
                "<div class='dg-notification-panel__title'>Notification Center</div>"
                "<div class='dg-notification-panel__note'>"
                "Lightweight inbox shell. Demo events for Founder Beta — "
                "architecture supports future live delivery."
                "</div></div>"
                "<div class='dg-notification-panel__categories'>"
                + "".join(
                    f"<span class='dg-notification-chip'>{escape(category)}</span>"
                    for category in NOTIFICATION_CATEGORIES
                )
                + "</div></div>"
            )
            if not resolved:
                st.caption("No notifications yet.")
                return
            for item in resolved:
                render_html_fragment(notification_item_html(item))
            if on_open_destination:
                st.caption("Use the GM Orb for full navigation. Alerts stay informational in Founder Beta.")

"""Founder Beta Notification Center shell.

Presentation and workflow only — no football, entitlement, billing, or auth logic.
Provides deterministic demo notifications and a stable event shape for later wiring.
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

PRIORITY_ACTION = frozenset({"Trades", "Waivers", "Injuries"})
PRIORITY_PRODUCT = frozenset({"Product updates"})

DESTINATION_LABELS: dict[str, str] = {
    "trade_hub": "Open Trade Hub",
    "waivers": "Open Waivers",
    "my_team": "Open My Team",
    "dashboard": "Open Dashboard",
    "live_draft": "Open Live Draft",
    "league_overview": "Open League Overview",
}


@dataclass(frozen=True)
class NotificationItem:
    """Stable notification shape for Founder Beta demos and later live events."""

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
        body="High-fit package ready.",
        unread=True,
        href_hint="trade_hub",
        age_label="12m",
    ),
    NotificationItem(
        id="demo-waiver-1",
        category="Waivers",
        title="Waiver priority shifted",
        body="A depth target entered your shortlist.",
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
        body="Your league and team are up to date.",
        unread=False,
        href_hint="dashboard",
        age_label="Today",
    ),
    NotificationItem(
        id="demo-draft-1",
        category="Live Draft",
        title="Live Draft available",
        body="Join when your league is drafting.",
        unread=False,
        href_hint="live_draft",
        age_label="Beta",
    ),
    NotificationItem(
        id="demo-product-1",
        category="Product updates",
        title=f"What's new in {brand_identity.PRODUCT_NAME}",
        body="Alerts, league, and account now share one top bar.",
        unread=False,
        href_hint="",
        age_label="Product",
    ),
)


def unread_count(items: Sequence[NotificationItem]) -> int:
    return sum(1 for item in items if item.unread)


def notification_priority_band(item: NotificationItem) -> str:
    """Return presentation band: action | routine | product."""

    category = str(item.category or "")
    if category in PRIORITY_PRODUCT:
        return "product"
    if category in PRIORITY_ACTION:
        return "action"
    return "routine"


def ranked_notifications(items: Sequence[NotificationItem]) -> tuple[NotificationItem, ...]:
    """Order for the executive inbox: unread action first, product last.

    Equal-priority items keep their relative source order.
    """

    band_rank = {"action": 0, "routine": 1, "product": 2}
    indexed = list(enumerate(items))

    def sort_key(pair: tuple[int, NotificationItem]) -> tuple[int, int, int]:
        index, item = pair
        return (
            0 if item.unread else 1,
            band_rank.get(notification_priority_band(item), 1),
            index,
        )

    return tuple(item for _, item in sorted(indexed, key=sort_key))


def list_founder_beta_notifications(
    *,
    session: dict | None = None,
) -> tuple[NotificationItem, ...]:
    """Return deterministic Founder Beta notifications.

    Session is accepted for later live-delivery hooks without changing callers.
    """

    _ = session
    return ranked_notifications(FOUNDER_BETA_DEMO_NOTIFICATIONS)


def destination_label(href_hint: str) -> str:
    hint = str(href_hint or "").strip()
    if not hint:
        return ""
    return DESTINATION_LABELS.get(hint, "Open")


def notification_item_html(item: NotificationItem) -> str:
    state = "is-unread" if item.unread else "is-read"
    band = notification_priority_band(item)
    hint = escape(item.href_hint) if item.href_hint else ""
    cta = destination_label(item.href_hint)
    cta_html = (
        f"<div class='dg-notification-item__cta'>{escape(cta)} →</div>" if cta else ""
    )
    return (
        f"<article class='dg-notification-item {state} dg-notification-item--{band}' "
        f"data-notification-id='{escape(item.id)}'"
        f"{f' data-href-hint={chr(34)}{hint}{chr(34)}' if hint else ''}>"
        f"<div class='dg-notification-item__meta'>"
        f"<span class='dg-notification-item__category'>{escape(item.category)}</span>"
        f"<span class='dg-notification-item__age'>{escape(item.age_label)}</span>"
        "</div>"
        f"<div class='dg-notification-item__title'>{escape(item.title)}</div>"
        f"<p class='dg-notification-item__body'>{escape(item.body)}</p>"
        f"{cta_html}"
        "</article>"
    )


def render_notification_center(
    *,
    items: Sequence[NotificationItem] | None = None,
    on_open_destination: Callable[[str], None] | None = None,
    key_prefix: str = "executive_notifications",
) -> None:
    """Render the Notification Center as a floating executive inbox panel."""

    resolved = (
        list_founder_beta_notifications(session=st.session_state)
        if items is None
        else ranked_notifications(tuple(items))
    )
    count = unread_count(resolved)
    label = f"Alerts ({count})" if count else "Alerts"
    help_text = "League alerts and updates"
    _ = on_open_destination  # Reserved for tappable destinations in a later pass.

    with st.container(key=f"{key_prefix}_control"):
        with st.popover(label, help=help_text):
            render_html_fragment(
                "<div class='dg-notification-panel' role='region' "
                "aria-label='Notification inbox'>"
                "<div class='dg-notification-panel__header'>"
                f"<div class='dg-notification-panel__kicker'>{escape(brand_identity.FOUNDER_BETA_LABEL)}</div>"
                "<div class='dg-notification-panel__title'>Inbox</div>"
                "<div class='dg-notification-panel__note'>"
                "Stay ahead of your league. "
                "Trades, waivers, injuries, roster updates, and product news appear here."
                "</div></div>"
                "<div class='dg-notification-panel__list'>"
                + (
                    "".join(notification_item_html(item) for item in resolved)
                    if resolved
                    else "<p class='dg-notification-panel__empty'>You're all caught up.</p>"
                )
                + "</div></div>"
            )

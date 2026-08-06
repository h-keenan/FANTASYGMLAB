"""Customer-facing FantasyGM Lab brand constants and markup helpers.

Presentation only — no football, entitlement, billing, or auth logic.
"""

from __future__ import annotations

from html import escape


PRODUCT_NAME = "FantasyGM Lab"
PRODUCT_MARK = "FGL"
PRODUCT_TAGLINE = "Franchise decisions with clear leverage."
FOUNDER_BETA_LABEL = "Founder Beta"
FOUNDER_BETA_NOTE = "Exclusive early access"
EXPERIMENTAL_LABEL = "[EXPERIMENTAL]"
EXPERIMENTAL_NOTE = "Early access capability"
GM_ORB_LABEL = "Menu"
GM_ORB_HELP = f"Open Trade Hub, Waivers, My Team, and more in {PRODUCT_NAME}"


def founder_beta_badge_html(*, compact: bool = False) -> str:
    """Subtle exclusive Founder Beta badge for shells and loading."""

    size_class = " dg-founder-badge--compact" if compact else ""
    return (
        f"<span class='dg-founder-badge{size_class}' "
        f"title='{escape(FOUNDER_BETA_NOTE)}'>"
        f"<span class='dg-founder-badge__mark' aria-hidden='true'>{escape(PRODUCT_MARK)}</span>"
        f"<span class='dg-founder-badge__copy'>"
        f"<strong>{escape(PRODUCT_NAME)}</strong>"
        f"<em>{escape(FOUNDER_BETA_LABEL)}</em>"
        f"</span></span>"
    )


def product_mark_html(*, size: str = "md", aria_label: str | None = None) -> str:
    """Branded mark used on loading, shell, and screenshot-ready surfaces."""

    label = escape(aria_label or PRODUCT_NAME)
    return (
        f"<div class='dg-brand-mark dg-brand-mark--{escape(size)}' "
        f"aria-label='{label}'>"
        f"<span aria-hidden='true'>{escape(PRODUCT_MARK)}</span>"
        "</div>"
    )


def trade_screenshot_brand_html(*, css_class: str = "trade-summary-brand") -> str:
    """Tasteful footer brand for trade summaries that screenshot cleanly."""

    root = escape(css_class or "trade-summary-brand")
    return (
        f"<footer class='{root}' aria-label='FantasyGM Lab'>"
        f"<span class='{root}__mark' aria-hidden='true'>{escape(PRODUCT_MARK)}</span>"
        f"<span class='{root}__name'>{escape(PRODUCT_NAME)}</span>"
        f"<span class='{root}__badge'>{escape(FOUNDER_BETA_LABEL)}</span>"
        "</footer>"
    )


def experimental_caption(heading: str = "Experimental") -> str:
    return f"{heading} · Early access"

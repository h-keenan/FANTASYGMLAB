"""Canonical executive workspace shell for authenticated FantasyGM Lab routes."""

from dataclasses import dataclass
from html import escape

from modules import brand_identity


@dataclass(frozen=True)
class WorkspaceMetric:
    """Legacy input retained for callers; metrics never render in the global shell."""

    label: str
    value: str
    note: str


@dataclass(frozen=True)
class ExecutiveWorkspaceShell:
    page_title: str
    page_note: str
    league_name: str
    team_name: str
    platform: str
    account_label: str
    entitlement_label: str
    has_league: bool
    avatar_url: str = ""
    sync_status: str = "Refresh on demand"
    metrics: tuple[WorkspaceMetric, ...] = ()
    authenticated: bool = True
    notification_unread: int = 0


# Compatibility alias for focused consumers while the executive name becomes canonical.
WorkspaceHeader = ExecutiveWorkspaceShell


def _text(value: object, fallback: str = "") -> str:
    text = "" if value is None else str(value).strip()
    return text or fallback


def executive_workspace_shell_html(shell: ExecutiveWorkspaceShell) -> str:
    """Return one compact executive command landmark without owning actions."""

    page_title = _text(shell.page_title, brand_identity.PRODUCT_NAME)
    league_name = _text(
        shell.league_name if shell.has_league else "",
        "No league selected",
    )
    account = _text(shell.account_label, "Signed in" if shell.authenticated else "Browsing as guest")
    entitlement = _text(shell.entitlement_label) if shell.authenticated else ""
    platform = _text(shell.platform) if shell.has_league else ""
    unread = max(0, int(shell.notification_unread or 0))
    status_bits = [account]
    if entitlement:
        status_bits.append(entitlement)
    if platform:
        status_bits.append(platform)
    # Entitlement lives in status text; Alerts owns unread count. Avoid chip
    # duplicates that compete with League / Alerts / You action controls.
    _ = unread
    status_html = "<span aria-hidden='true'>&bull;</span>".join(
        f"<span>{escape(item)}</span>" for item in status_bits if item
    )
    return (
        f"<header class='dg-executive-shell' aria-label='{escape(brand_identity.PRODUCT_NAME)} executive command header'>"
        f"<div class='dg-executive-shell__brand' aria-label='{escape(brand_identity.PRODUCT_NAME)}'>"
        f"{brand_identity.mark_img_html(size_px=28, css_class='dg-executive-shell__mark')}</div>"
        "<div class='dg-executive-shell__brief'>"
        "<div class='dg-executive-shell__title-row'>"
        f"<div class='dg-executive-shell__title' role='heading' aria-level='1'>{escape(page_title)}</div>"
        f"{brand_identity.founder_beta_badge_html(compact=True)}"
        "</div>"
        "<div class='dg-executive-shell__context'>"
        "<span class='dg-executive-shell__room'>War Room</span>"
        f"<span class='dg-executive-shell__league'>{escape(league_name)}</span>"
        "</div>"
        f"<div class='dg-executive-shell__status'>{status_html}</div>"
        "</div>"
        "</header>"
    )


def workspace_header_html(header: WorkspaceHeader) -> str:
    """Backward-compatible entry point for the canonical executive shell."""

    return executive_workspace_shell_html(header)


def shell_ack_html(*, label: str, message: str) -> str:
    """Compact routine acknowledgement for the executive shell (not a banner)."""

    return (
        "<div class='dg-shell-ack' role='status' aria-live='polite'>"
        f"<span class='dg-shell-ack__label'>{escape(_text(label, 'Ready'))}</span>"
        f"<span>{escape(_text(message))}</span>"
        "</div>"
    )

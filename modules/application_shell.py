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


# Compatibility alias for focused consumers while the executive name becomes canonical.
WorkspaceHeader = ExecutiveWorkspaceShell


def _text(value: object, fallback: str = "") -> str:
    text = "" if value is None else str(value).strip()
    return text or fallback


def executive_workspace_shell_html(shell: ExecutiveWorkspaceShell) -> str:
    """Return one compact page, league, and account landmark without owning actions."""

    page_title = _text(shell.page_title, brand_identity.PRODUCT_NAME)
    league_name = _text(
        shell.league_name if shell.has_league else "",
        "No league selected",
    )
    account = _text(shell.account_label, "Signed in" if shell.authenticated else "Guest")
    entitlement = _text(shell.entitlement_label) if shell.authenticated else ""
    platform = _text(shell.platform) if shell.has_league else ""
    status_bits = [account]
    if entitlement:
        status_bits.append(entitlement)
    if platform:
        status_bits.append(platform)
    status_html = "<span aria-hidden='true'>&bull;</span>".join(
        f"<span>{escape(item)}</span>" for item in status_bits if item
    )
    return (
        f"<header class='dg-executive-shell' aria-label='{escape(brand_identity.PRODUCT_NAME)} executive workspace'>"
        f"<div class='dg-executive-shell__brand' aria-label='{escape(brand_identity.PRODUCT_NAME)}'>"
        f"{escape(brand_identity.PRODUCT_MARK)}</div>"
        "<div class='dg-executive-shell__brief'>"
        f"<div class='dg-executive-shell__title' role='heading' aria-level='1'>{escape(page_title)}</div>"
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

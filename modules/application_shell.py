"""Canonical application-shell presentation for authenticated workspaces."""

from dataclasses import dataclass
from html import escape
from urllib.parse import urlparse


@dataclass(frozen=True)
class WorkspaceMetric:
    label: str
    value: str
    note: str


@dataclass(frozen=True)
class WorkspaceHeader:
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


def _text(value: object, fallback: str = "") -> str:
    text = "" if value is None else str(value).strip()
    return text or fallback


def _initials(label: str) -> str:
    words = [part for part in _text(label, "DG").replace("/", " ").split() if part]
    if len(words) < 2:
        return words[0][:2].upper() if words else "DG"
    return (words[0][0] + words[1][0]).upper()


def _safe_image_url(value: object) -> str:
    candidate = _text(value)
    try:
        parsed = urlparse(candidate)
    except Exception:
        return ""
    return candidate if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def workspace_header_html(header: WorkspaceHeader) -> str:
    """Render one page-and-league landmark without owning any application actions."""

    page_title = _text(header.page_title, "DynastyGM")
    page_note = _text(header.page_note)
    platform = _text(header.platform, "Sleeper")
    account = _text(header.account_label, "Guest")
    entitlement = _text(header.entitlement_label, "Free")
    league_name = _text(
        header.league_name,
        "No league selected" if not header.has_league else "Selected league",
    )
    team_name = _text(
        header.team_name,
        "Import a league to begin" if not header.has_league else "Current team",
    )
    avatar_label = team_name if header.has_league else "DynastyGM"
    avatar_url = _safe_image_url(header.avatar_url)
    avatar = (
        "<div class='dg-workspace-avatar'>"
        f"<img src='{escape(avatar_url, quote=True)}' alt='{escape(avatar_label)} avatar'>"
        "</div>"
        if avatar_url
        else (
            "<div class='dg-workspace-avatar dg-workspace-avatar--fallback' aria-hidden='true'>"
            f"{escape(_initials(avatar_label))}</div>"
        )
    )
    context_bits = " · ".join(
        escape(item)
        for item in (team_name, platform, account, entitlement)
        if item
    )
    metrics = "".join(
        "<div class='dg-workspace-metric'>"
        f"<div class='dg-workspace-metric-label'>{escape(_text(metric.label))}</div>"
        f"<div class='dg-workspace-metric-value'>{escape(_text(metric.value, '—'))}</div>"
        f"<div class='dg-workspace-metric-note'>{escape(_text(metric.note))}</div>"
        "</div>"
        for metric in header.metrics
        if _text(metric.label)
    )
    return (
        "<header class='dg-application-workspace' aria-label='DynastyGM workspace'>"
        "<div class='dg-workspace-page'>"
        "<div class='dg-workspace-page-kicker'>DynastyGM Workspace</div>"
        f"<h1 class='dg-workspace-page-title'>{escape(page_title)}</h1>"
        f"<p class='dg-workspace-page-note'>{escape(page_note)}</p>"
        "</div>"
        "<div class='dg-workspace-context' aria-label='Active league context'>"
        f"{avatar}"
        "<div class='dg-workspace-context-copy'>"
        f"<div class='dg-workspace-platform'>{escape(platform)}</div>"
        f"<div class='dg-workspace-league'>{escape(league_name)}</div>"
        f"<div class='dg-workspace-team'>{context_bits}</div>"
        f"<div class='dg-workspace-sync'>Sync status: {escape(_text(header.sync_status, 'Refresh on demand'))}</div>"
        "</div></div>"
        + (f"<div class='dg-workspace-metrics' aria-label='Workspace summary'>{metrics}</div>" if metrics else "")
        + "</header>"
    )

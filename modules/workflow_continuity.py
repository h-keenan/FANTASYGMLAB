"""Executive workflow continuity — presentation-only return context and back navigation.

Does not change football logic, recommendations, Trust, valuations, or ordering.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from html import escape
from typing import Any, Mapping, MutableMapping

WORKFLOW_RETURN_KEY = "executive_workflow_return"

# Surfaces that may show a return banner when a workflow handoff is active.
CONTINUITY_SURFACES: tuple[str, ...] = (
    "dashboard",
    "trade_hub",
    "trade_analyzer",
    "waivers",
    "my_team",
    "live_draft",
    "player_detail",
    "rankings",
    "teams",
    "news",
    "startup_draft_center",
    "draft_summary",
)


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


@dataclass(frozen=True)
class WorkflowReturnContext:
    """Where the user came from before the current workflow step."""

    origin_page: str
    origin_label: str
    note: str = ""
    league_id: str = ""
    recommendation_id: str = ""
    handoff_source: str = ""

    def to_dict(self) -> dict[str, str]:
        return {key: _text(getattr(self, key)) for key in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> WorkflowReturnContext | None:
        if not isinstance(payload, Mapping):
            return None
        values = {field.name: _text(payload.get(field.name)) for field in fields(cls)}
        if not values.get("origin_page"):
            return None
        return cls(**values)


def push_return_context(
    state: MutableMapping[str, Any],
    origin_page: str,
    *,
    origin_label: str = "",
    note: str = "",
    league_id: str = "",
    recommendation_id: str = "",
    handoff_source: str = "",
) -> None:
    """Record the page the user should return to after a workflow handoff."""

    page = _text(origin_page)
    if not page:
        return
    state[WORKFLOW_RETURN_KEY] = WorkflowReturnContext(
        origin_page=page,
        origin_label=_text(origin_label) or _default_page_label(page),
        note=_text(note),
        league_id=_text(league_id),
        recommendation_id=_text(recommendation_id),
        handoff_source=_text(handoff_source),
    ).to_dict()


def clear_return_context(state: MutableMapping[str, Any]) -> None:
    state.pop(WORKFLOW_RETURN_KEY, None)


def current_return_context(
    state: Mapping[str, Any] | None,
    *,
    league_id: str = "",
) -> WorkflowReturnContext | None:
    if not isinstance(state, Mapping):
        return None
    context = WorkflowReturnContext.from_dict(state.get(WORKFLOW_RETURN_KEY))
    if context is None:
        return None
    league_key = _text(league_id)
    if context.league_id and league_key and context.league_id != league_key:
        return None
    return context


def _default_page_label(page: str) -> str:
    labels = {
        "dashboard": "Dashboard",
        "trade_hub": "Trade Hub",
        "trade_analyzer": "Trade Analyzer",
        "waivers": "Waivers",
        "my_team": "My Team",
        "live_draft": "Live Draft",
        "player_detail": "Player Profile",
        "rankings": "League Overview",
        "teams": "Teams",
        "news": "News",
        "startup_draft_center": "Startup Draft Center",
        "draft_summary": "Draft Center",
        "notification_center": "Notifications",
    }
    return labels.get(_text(page), _text(page).replace("_", " ").title() or "Previous step")


def continuity_banner_html(context: WorkflowReturnContext, *, current_page: str) -> str:
    """Render a quiet workflow breadcrumb — same recommendation, clear return path."""

    origin = escape(context.origin_label or _default_page_label(context.origin_page))
    current = escape(_default_page_label(current_page))
    note = _text(context.note)
    note_html = (
        f"<span class='dg-workflow-continuity-note'>{escape(note)}</span>"
        if note
        else ""
    )
    provenance = (
        f" data-recommendation-id='{escape(context.recommendation_id, quote=True)}'"
        if context.recommendation_id
        else ""
    )
    return (
        "<nav class='dg-workflow-continuity' aria-label='Workflow continuity'>"
        f"<span class='dg-workflow-continuity-trail'>{origin} → {current}</span>"
        + note_html
        + (
            f"<span class='dg-workflow-continuity-provenance'{provenance}></span>"
            if context.recommendation_id
            else ""
        )
        + "</nav>"
    )


def next_action_hint(current_page: str, *, has_return: bool) -> str:
    """One-line guidance for what to do next on this surface."""

    hints = {
        "dashboard": "Review Your Next Move, then open Trade Hub or Waivers to act.",
        "trade_hub": "Review the lead package, open Trade Review, or tap a player for Quick View.",
        "waivers": "Compare priority adds, open a player dossier, then return to My Team.",
        "my_team": "Use Next Move and roster cards, then open Trade Hub for partner paths.",
        "live_draft": "Pick from the ranked board or send a target to Trade Hub.",
        "rankings": "Compare teams, then return to Dashboard or Trade Hub with context.",
    }
    base = hints.get(_text(current_page), "")
    if has_return and base:
        return f"{base} Use Back to return without losing your place."
    return base

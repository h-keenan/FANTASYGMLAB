"""Canonical presentation contracts for football assets.

Players are the first production implementation.  This module owns presentation
only: callers continue to resolve football meaning, values, prestige, and injury
state before constructing a view model.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Literal


PlayerCardDensity = Literal["compact", "standard", "dense"]
PlayerCardMode = Literal["read-only", "action-enabled"]
PRESTIGE_LEVELS = (
    "elite",
    "starter",
    "contributor",
    "development",
    "depth",
    "replacement",
)


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


@dataclass(frozen=True)
class FootballPlayerAsset:
    """Immutable UI input; it deliberately contains no valuation logic."""

    player_id: str
    display_name: str
    position: str
    team: str
    prestige_label: str
    prestige_level: str
    status: str = ""
    value_label: str = ""
    value: str = ""
    insight: str = ""
    age: str = ""

    def __post_init__(self) -> None:
        if self.prestige_level not in PRESTIGE_LEVELS:
            raise ValueError(f"Unsupported prestige level: {self.prestige_level}")


def position_badge_html(position: str) -> str:
    label = _text(position).upper() or "PLAYER"
    return (
        "<span class='dg-football-position player-position-badge' "
        f"aria-label='Position {escape(label, quote=True)}'>{escape(label)}</span>"
    )


def team_chip_html(team: str) -> str:
    label = _text(team).upper() or "FA"
    return (
        "<span class='dg-football-team' "
        f"aria-label='Team {escape(label, quote=True)}'>{escape(label)}</span>"
    )


def prestige_indicator_html(label: str, level: str) -> str:
    normalized = _text(level).lower()
    if normalized not in PRESTIGE_LEVELS:
        raise ValueError(f"Unsupported prestige level: {normalized}")
    readable = _text(label) or normalized.title()
    semantic_name = {
        "elite": "Premium",
        "starter": "Information",
        "contributor": "Information",
        "development": "Neutral",
        "depth": "Neutral",
        "replacement": "Danger",
    }[normalized]
    return (
        f"<span class='dg-football-prestige dg-football-prestige--{normalized} dg-ui-badge "
        f"player-prestige player-prestige-{normalized}' "
        f"data-prestige='{normalized}' "
        f"aria-label='{semantic_name} status: {escape(readable, quote=True)}'>"
        "<span class='dg-football-prestige__rail' aria-hidden='true'></span>"
        f"<span>{escape(readable)}</span></span>"
    )


def injury_badge_html(
    status: str,
    *,
    accessible_label: str = "",
    extra_classes: tuple[str, ...] = (),
) -> str:
    """Render normalized status text without interpreting injury semantics."""

    label = _text(status).upper()
    if not label:
        return ""
    tone = "caution" if label in {"Q", "QUESTIONABLE"} else "danger"
    if label in {"ACTIVE", "HEALTHY"}:
        tone = "success"
    elif label not in {
        "Q", "QUESTIONABLE", "D", "DOUBTFUL", "O", "OUT", "IR",
        "PUP", "SUSP", "SUSPENDED", "INACTIVE",
    }:
        tone = "neutral"
    short = {
        "QUESTIONABLE": "Q",
        "DOUBTFUL": "D",
        "OUT": "O",
        "SUSPENDED": "SUSP",
    }.get(label, label)
    classes = " ".join(("dg-football-injury", f"dg-football-injury--{tone}", *extra_classes))
    aria = accessible_label or f"Player status: {label.title()}"
    return (
        f"<span class='{classes}' "
        f"aria-label='{escape(aria, quote=True)}'>"
        f"{escape(short)}</span>"
    )


def status_chip_html(label: str, *, tone: str = "neutral") -> str:
    readable = _text(label)
    if not readable:
        return ""
    safe_tone = tone if tone in {"neutral", "information", "success", "caution", "danger"} else "neutral"
    return (
        f"<span class='dg-football-status dg-football-status--{safe_tone}'>"
        f"{escape(readable)}</span>"
    )


def value_display_html(label: str, value: str) -> str:
    readable_label = _text(label)
    readable_value = _text(value) or "—"
    from modules import dense_list_primitives

    compact = dense_list_primitives.compact_metric_label(readable_label)
    return (
        "<span class='dg-football-value dg-dense-metric' "
        f"aria-label='{escape(f'{compact}: {readable_value}', quote=True)}'>"
        f"<strong class='dg-football-value__number dg-dense-metric__value'>{escape(readable_value)}</strong>"
        f"<span class='dg-football-value__label dg-dense-metric__label'>{escape(compact)}</span>"
        "</span>"
    )


def player_card_html(
    asset: FootballPlayerAsset,
    *,
    density: PlayerCardDensity = "standard",
    mode: PlayerCardMode = "action-enabled",
    avatar_html: str = "",
    tags_html: str = "",
    position_html: str = "",
    value_html: str = "",
    details_html: str = "",
    extra_classes: tuple[str, ...] = (),
) -> str:
    """Render the one player-card hierarchy used by production consumers.

    HTML fragments are internal, already-rendered component slots.  All model
    text is escaped here.  User-controlled callers must never pass raw strings
    through the fragment slots.
    """

    if density not in {"compact", "standard", "dense"}:
        raise ValueError(f"Unsupported player-card density: {density}")
    interactive = mode == "action-enabled" and bool(asset.player_id)
    classes = list(
        dict.fromkeys(
            ("dg-football-asset", f"dg-football-asset--{density}", *extra_classes)
        )
    )
    if interactive:
        for class_name in ("dg-football-asset--interactive", "player-card-tappable"):
            if class_name not in classes:
                classes.append(class_name)
    attributes = ""
    if interactive:
        attributes = (
            f" data-player-id='{escape(asset.player_id, quote=True)}'"
            " role='button' tabindex='0'"
            f" aria-label='Open Player Quick View for {escape(asset.display_name, quote=True)}'"
        )
    identity_meta = " · ".join(
        value for value in (asset.team.upper() or "FA", asset.age) if value
    )
    resolved_value = value_html or value_display_html(asset.value_label, asset.value)
    injury_html = injury_badge_html(asset.status)
    return (
        f"<article class='{' '.join(classes)}'{attributes}>"
        f"<span class='dg-football-asset__prestige-rail dg-football-asset__prestige-rail--{asset.prestige_level}' "
        "aria-hidden='true'></span>"
        + (f"<div class='dg-football-asset__avatar'>{avatar_html}</div>" if avatar_html else "")
        + "<div class='dg-football-asset__body compact-player-body'>"
        + f"<h3 class='dg-football-asset__name compact-player-name'>{escape(asset.display_name)}</h3>"
        + f"<div class='dg-football-asset__meta compact-player-meta'>{escape(identity_meta)}</div>"
        + "<div class='dg-football-asset__badges compact-player-badges'>"
        + prestige_indicator_html(asset.prestige_label, asset.prestige_level)
        + (position_html or position_badge_html(asset.position))
        + injury_html
        + tags_html
        + "</div>"
        + (
            f"<p class='dg-football-asset__insight compact-player-reason'><strong>Why:</strong> "
            f"{escape(asset.insight)}</p>"
            if asset.insight
            else ""
        )
        + details_html
        + "</div>"
        + f"<div class='dg-football-asset__value'>{resolved_value}</div>"
        + "</article>"
    )

"""Normalized, presentation-only models for the shared Player Quick View."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from html import escape
from typing import Mapping, Sequence
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from modules import player_profile_ui
from modules.player_awards import PlayerBadge
from modules.player_tier_identity import (
    PlayerTierIdentity,
    player_tier_legend_html,
    portrait_frame_classes,
)
from modules.player_history import (
    CareerResume,
    HistoricalSeason,
    prioritize_milestones,
    summarize_career_resume,
)

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_PRODUCTION_HOSTS = frozenset(
    {
        "app.fantasygmlab.com",
        "fantasygmlab.com",
        "www.fantasygmlab.com",
        "fantasygmlab.onrender.com",
    }
)


@dataclass(frozen=True)
class StatItem:
    label: str
    value: str
    note: str
    tone: str


@dataclass(frozen=True)
class SeasonStatView:
    season: int | None
    season_type: str
    games: int | None
    complete: bool | None
    key_stats: tuple[StatItem, ...]
    fantasy: tuple[StatItem, ...]
    usage: tuple[StatItem, ...]

    @property
    def label(self) -> str:
        if self.season is None:
            return f"{self.season_type} (year unavailable)"
        return f"{self.season} {self.season_type}".strip()


@dataclass(frozen=True)
class PlayerQuickViewStats:
    seasons: tuple[SeasonStatView, ...]
    college: tuple[StatItem, ...]
    college_available: bool
    career_totals_available: bool = False
    position: str = ""


@dataclass(frozen=True)
class NewsItem:
    headline: str = ""
    source: str = ""
    freshness: str = ""
    snippet: str = ""
    url: str = ""
    summary: str = ""
    event_type: str = ""
    corroboration: str = ""
    corroboration_note: str = ""
    status_line: str = ""

    def display_headline(self) -> str:
        return self.headline or self.summary

    def display_snippet(self) -> str:
        return self.snippet


@dataclass(frozen=True)
class DossierSnapshot:
    dynasty_value: str
    rank: str
    tier: str
    recommendation: str
    trend: str
    recommendation_note: str
    position_rank: str = ""
    fantasy_ppg: str = ""
    recommendation_tone: str = "strategy"
    health: str = ""
    scoring_format: str = ""


@dataclass(frozen=True)
class CareerProfile:
    achievements: tuple[str, ...] = ()
    season_highlights: tuple[str, ...] = ()

    @property
    def available(self) -> bool:
        return bool(self.achievements or self.season_highlights)


@dataclass(frozen=True)
class ExecutiveSnapshot:
    years_in_league: str = ""
    draft_capital: str = ""
    college: str = ""
    height: str = ""
    weight: str = ""
    bye_week: str = ""
    contract_status: str = ""


def build_executive_snapshot(
    row: Mapping[str, object],
    metadata: Mapping[str, object] | None = None,
) -> ExecutiveSnapshot:
    """Normalize verified profile metadata without inventing unavailable fields."""
    source = dict(metadata or {})
    source.update({key: value for key, value in row.items() if _text(value)})

    years_raw = pd.to_numeric(pd.Series([source.get("years_exp")]), errors="coerce").iloc[0]
    years = ""
    if pd.notna(years_raw) and float(years_raw) >= 0:
        seasons = int(float(years_raw))
        years = "Rookie" if seasons == 0 else f"{seasons} season{'s' if seasons != 1 else ''}"

    round_raw = pd.to_numeric(pd.Series([source.get("draft_round")]), errors="coerce").iloc[0]
    pick_raw = pd.to_numeric(
        pd.Series([source.get("draft_slot") or source.get("draft_pick")]),
        errors="coerce",
    ).iloc[0]
    year_raw = pd.to_numeric(pd.Series([source.get("draft_year")]), errors="coerce").iloc[0]
    draft_parts: list[str] = []
    if pd.notna(year_raw):
        draft_parts.append(str(int(float(year_raw))))
    if pd.notna(round_raw):
        draft_parts.append(f"Round {int(float(round_raw))}")
    if pd.notna(pick_raw):
        draft_parts.append(f"Pick {int(float(pick_raw))}")

    height = _text(source.get("height"))
    if height.isdigit():
        total_inches = int(height)
        height = f"{total_inches // 12}'{total_inches % 12}\""
    weight = _text(source.get("weight"))
    if weight and weight.replace(".", "", 1).isdigit():
        weight = f"{int(float(weight))} lb"

    return ExecutiveSnapshot(
        years_in_league=years,
        draft_capital=" / ".join(draft_parts),
        college=_text(source.get("college")),
        height=height,
        weight=weight,
        bye_week=_text(source.get("bye_week")),
        contract_status=_text(source.get("contract_status")),
    )


def _text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _integer(value: object) -> int | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(numeric) else int(numeric)


def _items(items: list[dict]) -> tuple[StatItem, ...]:
    return tuple(
        StatItem(
            label=_text(item.get("label")) or "Metric",
            value=_text(item.get("value")),
            note=_text(item.get("note")),
            tone=_text(item.get("tone")) or "reference",
        )
        for item in items
    )


def _group_items(row: pd.Series) -> dict[str, list[dict]]:
    return {
        label: list(items)
        for label, items in player_profile_ui.player_profile_stat_groups(row)
    }


def _key_stats(row: pd.Series, groups: Mapping[str, list[dict]]) -> list[dict]:
    by_label = {str(item.get("label")): item for item in groups.get("NFL Stats", [])}
    position = _text(row.get("position")).upper()
    order = {
        "QB": ["Games", "Pass Att", "Pass Yards", "Pass TDs", "Rush Yards", "Rush TDs"],
        "RB": ["Games", "Rush Att", "Rush Yards", "Rush TDs", "Targets", "Receptions", "Rec Yards", "Rec TDs"],
        "WR": ["Games", "Targets", "Receptions", "Rec Yards", "Rec TDs", "Rush Yards", "Rush TDs"],
        "TE": ["Games", "Targets", "Receptions", "Rec Yards", "Rec TDs", "Rush Yards", "Rush TDs"],
    }.get(
        position,
        ["Games", "Targets", "Receptions", "Rec Yards", "Rec TDs", "Rush Att", "Rush Yards", "Rush TDs", "Pass Yards", "Pass TDs"],
    )
    return [dict(by_label[label]) for label in order if label in by_label]


def _fantasy_stats(groups: Mapping[str, list[dict]], games: int | None) -> list[dict]:
    by_label = {str(item.get("label")): item for item in groups.get("Fantasy Stats", [])}
    formats = [
        ("Fantasy PPR", "PPR"),
        ("Half PPR", "Half PPR"),
        ("Fantasy Pts", "Standard"),
    ]
    present = [(source, label, by_label[source]) for source, label in formats if source in by_label]
    distinct_values = {str(item.get("value")) for _source, _label, item in present}
    suffix = f" across {games} games." if games is not None else "."
    if len(present) > 1 and len(distinct_values) == 1:
        source, _label, item = present[-1]
        collapsed = dict(item)
        collapsed["label"] = "Fantasy Points"
        collapsed["note"] = f"Scoring totals are identical across loaded formats{suffix}"
        output = [collapsed]
    else:
        output = []
        for _source, label, item in present:
            cloned = dict(item)
            cloned["label"] = label
            cloned["note"] = f"{label} season total{suffix}"
            output.append(cloned)
    if "PPG" in by_label:
        ppg = dict(by_label["PPG"])
        ppg["label"] = "PPR PPG"
        ppg["note"] = f"PPR points per game{suffix}"
        output.append(ppg)
    return output


def _usage_stats(groups: Mapping[str, list[dict]]) -> list[dict]:
    by_label = {str(item.get("label")): item for item in groups.get("Usage", [])}
    return [
        {**by_label[source], "label": label}
        for source, label in (
            ("Snap Share", "Snap %"),
            ("Route Part.", "Route %"),
            ("Target Share", "Target Share"),
            ("Rush Share", "Carry Share"),
            ("Opportunity Share", "Opportunity"),
        )
        if source in by_label
    ]


def build_stats_view(row: pd.Series) -> PlayerQuickViewStats:
    """Build the view from the one regular-season aggregate loaded today.

    The production loader joins exactly one ``stats_season`` record per player.
    It does not retain weekly rows or prior seasons, so this model deliberately
    exposes one season and never invents career totals.
    """

    groups = _group_items(row)
    games = _integer(row.get("games_played"))
    season = _integer(row.get("stats_season"))
    season_view = SeasonStatView(
        season=season,
        season_type="Regular Season",
        games=games,
        complete=None,
        key_stats=_items(_key_stats(row, groups)),
        fantasy=_items(_fantasy_stats(groups, games)),
        usage=_items(_usage_stats(groups)),
    )
    college = _items(groups.get("College Stats", []))
    has_professional_stats = bool(
        season_view.key_stats or season_view.fantasy or season_view.usage
    )
    return PlayerQuickViewStats(
        seasons=(season_view,) if has_professional_stats else (),
        college=college,
        college_available=bool(college),
        position=_text(row.get("position")),
    )


def dense_section_html(title: str, items: tuple[StatItem, ...] | list[StatItem]) -> str:
    rows = "".join(
        "<div class='player-quick-view-stat-row'>"
        f"<div class='player-quick-view-stat-label'>{escape(item.label)}</div>"
        "<div class='player-quick-view-stat-copy'>"
        f"<div class='player-quick-view-stat-value dg-stat-tone-{escape(item.tone)}'>{escape(item.value)}</div>"
        + (f"<div class='player-quick-view-stat-note'>{escape(item.note)}</div>" if item.note else "")
        + "</div></div>"
        for item in items
    )
    return (
        "<section class='player-quick-view-stat-section'>"
        f"<h3 class='player-quick-view-stat-heading'>{escape(title)}</h3>"
        f"<div class='player-quick-view-stat-grid'>{rows}</div></section>"
    )


def dossier_section_heading_html(title: str, subtitle: str = "") -> str:
    return (
        "<header class='player-dossier-section-heading'>"
        f"<h3>{escape(title)}</h3>"
        + (f"<p>{escape(subtitle)}</p>" if subtitle else "")
        + "</header>"
    )


def rank_strip_html(
    *,
    overall_display: str,
    position_display: str = "",
    scoring_format: str = "",
    dynasty_value: str = "",
) -> str:
    """One compact value/rank owner: dynasty value, overall, position, format."""

    cells: list[tuple[str, str]] = []
    overall = _text(overall_display)
    if overall and overall.casefold() not in {
        "rank unavailable",
        "not available",
        "unavailable",
        "unknown",
    }:
        cells.append(("Overall rank", overall))
    position = _text(position_display)
    if position and position.casefold() not in {"not available", "unavailable", "unknown"}:
        cells.append(("Position rank", position))
    value = _text(dynasty_value)
    if value and value.casefold() not in {"not available", "unavailable", "unknown"}:
        cells.append(("Dynasty value", value))
    fmt = _text(scoring_format)
    if fmt:
        cells.append(("Format", fmt))
    if not cells:
        return ""
    cell_html = "".join(
        "<div class='player-dossier-rank-cell'>"
        f"<span>{escape(label)}</span><strong>{escape(text)}</strong>"
        "</div>"
        for label, text in cells
    )
    return (
        "<div class='player-dossier-rank-strip pqv-hero-value' role='group' "
        "aria-label='Dynasty value and rank'>"
        f"{cell_html}</div>"
    )


def pqv_hero_html(
    *,
    avatar_html: str,
    name: str,
    position: str,
    team: str,
    age_text: str,
    source_label: str = "",
    role_label: str = "",
    overall_display: str = "",
    position_display: str = "",
    dynasty_value: str = "",
    scoring_format: str = "",
    signal_badges: list[tuple[str, str]] | tuple[tuple[str, str], ...] = (),
    identity: PlayerTierIdentity | None = None,
    include_tier_legend: bool = False,
) -> str:
    """Identity + value snapshot. Canonical owner for who / how good / tier / rank."""

    role = _text(role_label)
    role_html = (
        f"<div class='pqv-hero-role'>{escape(role)}</div>"
        if role and role.casefold() not in {"opportunity unclear", "unknown", "unavailable"}
        else ""
    )
    value_html = rank_strip_html(
        overall_display=overall_display,
        position_display=position_display,
        scoring_format=scoring_format,
        dynasty_value=dynasty_value,
    )
    filtered_badges = []
    for question, answer in signal_badges:
        if _text(answer).casefold() == role.casefold() and role:
            continue
        if _text(question).casefold() in {
            "depth-chart role",
            "role",
            "roster impact",
            "fantasy action",
        }:
            continue
        filtered_badges.append((question, answer))
    portrait_class = portrait_frame_classes(
        identity,
        base="pqv-hero-portrait",
        frame_mode="full",
    )
    portrait_attrs = ""
    tier_label_html = ""
    if identity is not None:
        portrait_attrs = (
            f" data-player-tier='{escape(identity.tier_id, quote=True)}'"
            f" title='{escape(identity.accessibility_label, quote=True)}'"
            f" aria-label='{escape(identity.accessibility_label, quote=True)}'"
        )
        tier_label_html = (
            f"<div class='pqv-hero-tier' title='{escape(identity.accessibility_label, quote=True)}'>"
            f"{escape(identity.short_label)}</div>"
        )
    legend_html = (
        player_tier_legend_html(compact=True) if include_tier_legend else ""
    )
    return (
        "<div class='player-quick-view-shell dg-quick-view-panel'>"
        "<div class='player-quick-view-header-band player-quick-view-hero'>"
        f"<div class='{portrait_class}'{portrait_attrs}>{avatar_html}</div>"
        "<div class='player-quick-view-copy'>"
        + (f"<div class='player-quick-view-source'>{escape(_text(source_label))}</div>" if _text(source_label) else "")
        + tier_label_html
        + f"<h3 class='player-quick-view-name'>{escape(_text(name) or 'Player')}</h3>"
        + f"<div class='player-quick-view-meta'>{escape(_text(position) or 'Player')} · {escape(_text(team) or 'FA')} · Age {escape(_text(age_text) or 'N/A')}</div>"
        + role_html
        + value_html
        + labeled_signal_badges_html(filtered_badges)
        + legend_html
        + "</div></div></div>"
    )


def labeled_signal_badges_html(badges: list[tuple[str, str]] | tuple[tuple[str, str], ...]) -> str:
    """Labeled identity badges. Each badge answers a distinct question."""

    parts: list[str] = []
    seen: set[str] = set()
    for question, answer in badges:
        label = _text(question)
        value = _text(answer)
        if not label or not value:
            continue
        key = f"{label.casefold()}|{value.casefold()}"
        if key in seen:
            continue
        seen.add(key)
        parts.append(
            "<span class='pqv-signal-badge' role='listitem'>"
            f"<span class='pqv-signal-badge-question'>{escape(label)}</span>"
            f"<span class='pqv-signal-badge-answer'>{escape(value)}</span>"
            "</span>"
        )
        if len(parts) >= 4:
            break
    if not parts:
        return ""
    return (
        "<div class='pqv-signal-badge-group' role='list' "
        "aria-label='Player status signals'>"
        + "".join(parts)
        + "</div>"
    )


_TRADE_PACKAGE_MARKERS = (
    "future flexibility",
    "partner motivation",
    "market path",
    "believable market",
    "wr surplus",
    "rb surplus",
    "you add ",
    "they move from",
    "gets rb help",
    "gets wr help",
    "trade partner",
    "package believ",
    "lead the board",
    "enough partner",
)


def is_trade_package_copy(text: object) -> bool:
    """True when copy describes a trade package rather than the player."""

    key = _text(text).casefold()
    return bool(key) and any(marker in key for marker in _TRADE_PACKAGE_MARKERS)


def compact_player_line(text: object, *, limit: int = 140) -> str:
    """Keep 1–2 interpretive lines without fabricating new claims."""

    detail = re.sub(r"\s+", " ", _text(text)).strip()
    if not detail:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", detail)
    kept: list[str] = []
    for part in parts:
        candidate = " ".join(kept + [part]).strip()
        if kept and len(candidate) > limit:
            break
        kept.append(part)
        if len(" ".join(kept)) >= limit:
            break
        if len(kept) >= 2:
            break
    compact = " ".join(kept).strip()
    if len(compact) > limit + 24:
        compact = compact[:limit].rsplit(" ", 1)[0].rstrip(".,;:") + "."
    return compact


def canonical_player_read_copy(
    *,
    why_candidates: Sequence[object] = (),
    fit_candidates: Sequence[object] = (),
    risk_candidates: Sequence[object] = (),
    blocked_values: Sequence[object] = (),
) -> dict[str, str]:
    """Player-only Why / Fit / Risk. Trade-package narrative is blocked."""

    blocked = {
        _text(item).casefold()
        for item in blocked_values
        if _text(item)
    }

    def _first_player_line(candidates: Sequence[object]) -> str:
        seen: set[str] = set()
        for raw in candidates:
            detail = compact_player_line(raw)
            key = detail.casefold()
            if not detail or key in seen or key in blocked or is_trade_package_copy(detail):
                continue
            seen.add(key)
            return detail
        return ""

    return {
        "why": _first_player_line(why_candidates),
        "fit": _first_player_line(fit_candidates),
        "risk": _first_player_line(risk_candidates),
    }


def _owned_copy_is_redundant(detail: str, skipped: set[str]) -> bool:
    """Drop copy that only restates facts owned by Hero / Current Season."""

    key = _text(detail).casefold()
    if not key:
        return True
    if key.startswith("current roster role:"):
        return True
    compact = re.sub(r"[^a-z0-9#]+", "", key)
    for owned in skipped:
        token = re.sub(r"[^a-z0-9#]+", "", owned)
        if token and token == compact:
            return True
        if token and token in compact and len(key) <= len(owned) + 28:
            return True
    if (
        re.search(r"\bovr\b", key)
        and re.search(r"#\d+", key)
        and re.search(r"\b(qb|rb|wr|te)\b", key)
        and len(key) < 72
    ):
        return True
    return False


def compose_fantasygm_read_factors(
    *,
    why: str = "",
    team_fit: str = "",
    risk: str = "",
    skip_values: Sequence[str] | None = None,
) -> list[tuple[str, str]]:
    """One canonical synthesis block. Duplicate sentences are dropped."""

    skipped = {
        _text(item).casefold()
        for item in (skip_values or ())
        if _text(item)
    }
    seen_values: set[str] = set(skipped)
    items: list[tuple[str, str]] = []
    for label, raw in (
        ("Why", why),
        ("Fit", team_fit),
        ("Risk", risk),
    ):
        detail = _text(raw)
        key = detail.casefold()
        if not detail or key in seen_values or _owned_copy_is_redundant(detail, skipped):
            continue
        seen_values.add(key)
        items.append((label, detail))
    return items


def why_this_recommendation_html(
    factors: list[tuple[str, str]] | tuple[tuple[str, str], ...],
    *,
    title: str = "FantasyGM Read",
    skip_values: Sequence[str] | None = None,
) -> str:
    """At most four concise valuation factors. Omits empty and duplicate copy."""

    skipped = {
        _text(item).casefold()
        for item in (skip_values or ())
        if _text(item)
    }
    items: list[tuple[str, str]] = []
    seen_labels: set[str] = set()
    seen_values: set[str] = set(skipped)
    for label, value in factors:
        heading = _text(label)
        detail = _text(value)
        if not heading or not detail:
            continue
        label_key = heading.casefold()
        value_key = detail.casefold()
        if label_key in seen_labels or value_key in seen_values:
            continue
        seen_labels.add(label_key)
        seen_values.add(value_key)
        items.append((heading, detail))
        if len(items) >= 4:
            break
    if not items:
        return ""
    body = "".join(
        "<div class='pqv-why-factor"
        + (
            " pqv-why-factor--fit"
            if label.casefold() == "fit"
            else " pqv-why-factor--risk"
            if label.casefold() == "risk"
            else ""
        )
        + "'>"
        f"<span>{escape(label)}</span><strong>{escape(compact_player_line(value))}</strong>"
        "</div>"
        for label, value in items
    )
    heading = dossier_section_heading_html(title).replace(
        "<h3>",
        "<h3 id='pqv-why-title'>",
        1,
    )
    return (
        "<section class='pqv-why-recommendation' aria-labelledby='pqv-why-title'>"
        + heading
        + f"<div class='pqv-why-grid'>{body}</div></section>"
    )


def _accolade_emblem_svg(kind: str) -> str:
    """Inline category marks. No network images."""

    mark = {
        "finish": (
            "<path d='M6 24h20M10 24V14h4v10M14 24V8h4v16M18 24V16h4v8' "
            "fill='none' stroke='currentColor' stroke-width='1.8'/>"
            "<path class='pqv-accolade-emblem-fill' d='M14 8h4v4h-4z' fill='currentColor'/>"
        ),
        "yards": (
            "<path d='M4 16h24M8 12v8M16 10v12M24 12v8' fill='none' "
            "stroke='currentColor' stroke-width='1.8'/>"
            "<path d='M14 6h4v4h-4z' fill='currentColor'/>"
        ),
        "scores": (
            "<ellipse cx='16' cy='16' rx='10' ry='6.2' fill='none' stroke='currentColor' stroke-width='1.8'/>"
            "<path d='M8 16c2.4-3 5.2-4.6 8-4.6S21.6 13 24 16' fill='none' "
            "stroke='currentColor' stroke-width='1.4'/>"
            "<path d='M8 16c2.4 3 5.2 4.6 8 4.6S21.6 19 24 16' fill='none' "
            "stroke='currentColor' stroke-width='1.4'/>"
        ),
        "workhorse": (
            "<path d='M8 8h16l2 8-10 12L6 16z' fill='none' stroke='currentColor' stroke-width='1.8'/>"
            "<path class='pqv-accolade-emblem-fill' d='M12 12h8v4h-8z' fill='currentColor'/>"
        ),
        "targets": (
            "<circle cx='16' cy='16' r='10' fill='none' stroke='currentColor' stroke-width='1.6'/>"
            "<circle cx='16' cy='16' r='6' fill='none' stroke='currentColor' stroke-width='1.6'/>"
            "<circle cx='16' cy='16' r='2.2' fill='currentColor'/>"
        ),
    }.get(kind, "")
    if not mark:
        mark = (
            "<circle cx='16' cy='16' r='9' fill='none' stroke='currentColor' stroke-width='1.8'/>"
        )
    return (
        "<svg class='pqv-accolade-medal pqv-accolade-emblem' viewBox='0 0 32 32' "
        "aria-hidden='true' focusable='false'>"
        f"{mark}</svg>"
    )


def _accolade_kind(badge: PlayerBadge) -> str:
    family = _text(badge.family).casefold()
    category = _text(badge.category).casefold()
    if family in {"positional-finish", "overall-finish"} or category == "fantasy_finish":
        return "finish"
    if family.endswith("-yards") or "yard" in family:
        return "yards"
    if family.endswith("-td") or "touch" in family:
        return "scores"
    if family == "workhorse":
        return "workhorse"
    if family == "targets" or "target" in family:
        return "targets"
    return "finish"


def _accolade_item_html(badge: PlayerBadge) -> str:
    tier = badge.tier if badge.tier in {"gold", "silver", "bronze"} else "plain"
    year = str(badge.season) if badge.season else ""
    repeats = badge.occurrence_count > 1
    count_mark = (
        f"<span class='pqv-accolade-count'>{badge.occurrence_count}×</span>"
        if repeats
        else ""
    )
    title = _text(badge.title) or _text(badge.short_label)
    short = _text(badge.short_label)
    if repeats and "×" in short:
        short = short.replace(" 2×", "").replace(" 3×", "").replace(" 4×", "").strip()
    meta = year
    return (
        "<li class='pqv-accolade "
        f"pqv-accolade--{escape(tier)} pqv-accolade--{escape(_accolade_kind(badge))}'>"
        "<span class='pqv-accolade-emblem-wrap'>"
        f"{_accolade_emblem_svg(_accolade_kind(badge))}"
        f"{count_mark}</span>"
        "<span class='pqv-accolade-copy'>"
        f"<strong>{escape(short)}</strong>"
        + (f"<small>{escape(meta)}</small>" if meta else "")
        + f"<span class='visually-hidden'>{escape(title)}</span>"
        + "</span></li>"
    )


def accolades_cluster_html(
    badges: tuple[PlayerBadge, ...] | list[PlayerBadge],
    *,
    overflow: tuple[PlayerBadge, ...] | list[PlayerBadge] = (),
) -> str:
    """Badge cluster only. Empty input returns an empty string."""

    visible = tuple(badges)
    extra = tuple(overflow)
    if not visible:
        return ""
    items = "".join(_accolade_item_html(badge) for badge in visible)
    more = ""
    if extra:
        extra_items = "".join(_accolade_item_html(badge) for badge in extra)
        more = (
            "<details class='dg-info-disclosure dg-client-disclosure pqv-accolades-more'>"
            f"<summary>View all accomplishments ({len(visible) + len(extra)})</summary>"
            f"<ul class='pqv-accolade-cluster pqv-accolade-cluster--all'>{extra_items}</ul>"
            "</details>"
        )
    return f"<ul class='pqv-accolade-cluster'>{items}</ul>" + more


def accolades_html(
    badges: tuple[PlayerBadge, ...] | list[PlayerBadge],
    *,
    overflow: tuple[PlayerBadge, ...] | list[PlayerBadge] = (),
    include_heading: bool = True,
) -> str:
    """Compact Accolades cluster. Empty input omits the section entirely."""

    cluster = accolades_cluster_html(badges, overflow=overflow)
    if not cluster:
        return ""
    if not include_heading:
        return cluster
    heading = dossier_section_heading_html("Accolades").replace(
        "<h3>",
        "<h3 id='pqv-accolades-title'>",
        1,
    )
    return (
        "<section class='pqv-accolades' aria-labelledby='pqv-accolades-title'>"
        + heading
        + cluster
        + "</section>"
    )


def career_glance_items(
    *,
    years_exp: int | None = None,
    badges: Sequence[PlayerBadge] | None = None,
) -> list[tuple[str, str]]:
    """Experience, best finish, and consistency from already-loaded awards."""

    cells: list[tuple[str, str]] = []
    if years_exp is not None and years_exp >= 0:
        if years_exp == 0:
            cells.append(("Experience", "Rookie"))
        else:
            cells.append(
                (
                    "Experience",
                    f"{years_exp} NFL season{'s' if years_exp != 1 else ''}",
                )
            )
    finish = None
    for badge in badges or ():
        if badge.family == "positional-finish":
            finish = badge
            break
    if finish is not None:
        label = _text(finish.short_label).replace(" 2×", "").replace(" 3×", "")
        year = f" · {finish.season}" if finish.season else ""
        cells.append(("Best finish", f"{label}{year}"))
        if finish.occurrence_count > 1:
            cells.append(("Consistency", f"{finish.occurrence_count}× {label}"))
    seasons = sorted(
        {badge.season for badge in badges or () if badge.season},
        reverse=True,
    )
    if seasons:
        latest = next((badge for badge in badges or () if badge.season == seasons[0]), None)
        if latest is not None:
            cells.append(("Recent arc", f"{latest.season} {latest.short_label}"))
    return cells


def career_glance_html(
    *,
    years_exp: int | None = None,
    badges: Sequence[PlayerBadge] | None = None,
    position: str = "",
) -> str:
    """Compact career strip from already-loaded awards. No extra fetch."""

    cells = career_glance_items(years_exp=years_exp, badges=badges)
    if not cells:
        return ""
    body = "".join(
        "<div class='pqv-career-glance-cell'>"
        f"<span>{escape(label)}</span><strong>{escape(value)}</strong></div>"
        for label, value in cells
    )
    heading = dossier_section_heading_html("Career").replace(
        "<h3>",
        "<h3 id='pqv-career-glance-title'>",
        1,
    )
    return (
        "<section class='pqv-career-glance' aria-labelledby='pqv-career-glance-title'>"
        + heading
        + f"<div class='pqv-career-glance-row'>{body}</div></section>"
    )


def career_dossier_html(
    *,
    badges: tuple[PlayerBadge, ...] | list[PlayerBadge] = (),
    overflow: tuple[PlayerBadge, ...] | list[PlayerBadge] = (),
    years_exp: int | None = None,
    position: str = "",
) -> str:
    """One Career surface: awards plus experience / best finish / consistency."""

    del position  # Presentation-only; finish labels already encode position.
    cluster = accolades_cluster_html(badges, overflow=overflow)
    cells = career_glance_items(years_exp=years_exp, badges=badges)
    if not cluster and not cells:
        return ""
    glance = ""
    if cells:
        glance = (
            "<div class='pqv-career-glance-row'>"
            + "".join(
                "<div class='pqv-career-glance-cell'>"
                f"<span>{escape(label)}</span><strong>{escape(value)}</strong></div>"
                for label, value in cells
            )
            + "</div>"
        )
    heading = dossier_section_heading_html("Career").replace(
        "<h3>",
        "<h3 id='pqv-career-title'>",
        1,
    )
    accolades = ""
    if cluster:
        accolades = (
            "<div class='pqv-accolades pqv-accolades--career'>"
            "<p class='pqv-kicker' id='pqv-accolades-title'>Accolades</p>"
            + cluster
            + "</div>"
        )
    return (
        "<section class='pqv-career-dossier' aria-labelledby='pqv-career-title'>"
        + heading
        + glance
        + accolades
        + "</section>"
    )


def snapshot_html(snapshot: DossierSnapshot, *, include_recommendation: bool = True) -> str:
    tone = (
        snapshot.recommendation_tone
        if snapshot.recommendation_tone in {"strategy", "opportunity", "risk"}
        else "strategy"
    )
    metrics = (
        ("Dynasty Value", snapshot.dynasty_value),
        ("Overall Rank", snapshot.rank),
        ("Position Rank", snapshot.position_rank),
        ("Format", snapshot.scoring_format),
        ("Recent PPG", snapshot.fantasy_ppg),
        ("Health", snapshot.health),
        ("Trend", snapshot.trend),
    )

    metric_html = "".join(
        "<div class='player-dossier-snapshot-metric'>"
        f"<span>{escape(label)}</span><strong>{escape(value)}</strong>"
        "</div>"
        for label, value in metrics
        if value and value.casefold() not in {"not available", "unavailable", "unknown"}
    )
    recommendation_html = ""
    if include_recommendation:
        recommendation_html = (
            f"<div class='player-dossier-decision player-dossier-decision--{tone}'>"
            "<span>Recommendation</span>"
            f"<strong>{escape(snapshot.recommendation)}</strong>"
            f"<p>{escape(snapshot.recommendation_note)}</p>"
            "</div>"
        )
    return (
        "<section class='player-dossier-snapshot' aria-labelledby='player-dossier-snapshot-title'>"
        "<h3 class='player-dossier-snapshot-title' id='player-dossier-snapshot-title'>Value &amp; Health</h3>"
        f"<div class='player-dossier-snapshot-grid'>{metric_html}</div>"
        + recommendation_html
        + "</section>"
    )


def compact_bio_html(snapshot: ExecutiveSnapshot) -> str:
    """College / body / draft facts for More Details. Experience lives on Career."""

    metrics = (
        ("College", snapshot.college),
        ("Height", snapshot.height),
        ("Weight", snapshot.weight),
        ("Draft", snapshot.draft_capital),
        ("Bye Week", snapshot.bye_week),
        ("Contract", snapshot.contract_status),
    )
    content = "".join(
        "<div class='pqv-bio-cell'>"
        f"<span>{escape(label)}</span><strong>{escape(value)}</strong></div>"
        for label, value in metrics
        if value and value.casefold() not in {"not available", "unavailable", "unknown"}
    )
    if not content:
        return ""
    heading = dossier_section_heading_html("Bio").replace(
        "<h3>",
        "<h3 id='pqv-bio-title'>",
        1,
    )
    return (
        "<section class='pqv-bio' aria-labelledby='pqv-bio-title'>"
        + heading
        + f"<div class='pqv-bio-row'>{content}</div></section>"
    )


def executive_snapshot_html(snapshot: ExecutiveSnapshot) -> str:
    metrics = (
        ("Experience", snapshot.years_in_league),
        ("Draft Capital", snapshot.draft_capital),
        ("College", snapshot.college),
        ("Height", snapshot.height),
        ("Weight", snapshot.weight),
        ("Bye Week", snapshot.bye_week),
        ("Contract", snapshot.contract_status),
    )
    content = "".join(
        "<div class='player-dossier-executive-metric'>"
        f"<span>{escape(label)}</span><strong>{escape(value)}</strong></div>"
        for label, value in metrics
        if value and value.casefold() not in {"not available", "unavailable", "unknown"}
    )
    if not content:
        return ""
    heading = dossier_section_heading_html("Executive Summary").replace(
        "<h3>",
        "<h3 id='player-dossier-executive-title'>",
        1,
    )
    return (
        "<section class='player-dossier-executive' aria-labelledby='player-dossier-executive-title'>"
        + heading
        + f"<div class='player-dossier-executive-grid'>{content}</div></section>"
    )


def _achievement_html(achievement, *, show_current_label: bool = True) -> str:
    current_label = (
        "<span class='player-dossier-achievement-current'>Current season</span>"
        if show_current_label and achievement.current_season
        else ""
    )
    return (
        f"<li class='player-dossier-achievement player-dossier-achievement--{escape(achievement.level)}'>"
        f"<span class='player-dossier-achievement-icon' aria-hidden='true'>{escape(achievement.icon)}</span>"
        "<span class='player-dossier-achievement-copy'>"
        f"<strong>{escape(achievement.label)}</strong>"
        f"<small>{escape(str(achievement.season))} · {escape(achievement.detail)}</small>"
        f"{current_label}</span></li>"
    )


def group_achievements_by_family_year(achievements: tuple) -> list[tuple[str, tuple]]:
    """Group achievements by season then family for expanded resume presentation."""

    buckets: dict[tuple[int, str], list] = {}
    order: list[tuple[int, str]] = []
    for item in achievements:
        key = (int(item.season), str(item.family))
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(item)
    return [
        (f"{season} · {family.replace('-', ' ').title()}", tuple(buckets[key]))
        for key in order
        for season, family in (key,)
    ]


def career_resume_html(
    resume: CareerResume,
    *,
    expanded: bool = False,
    position: str = "",
    years_exp: int | None = None,
    include_milestones: bool = True,
) -> str:
    """Render factual Career Context résumé — no invented prestige system."""

    heading = dossier_section_heading_html("Career Context").replace(
        "<h3>",
        "<h3 id='player-dossier-resume-title'>",
        1,
    )
    normalized_position = str(position or "").upper()
    if not normalized_position and resume.seasons:
        # Infer only for presentation when callers omit position.
        normalized_position = "PLAYER"
    summary = summarize_career_resume(
        resume,
        position=normalized_position or "PLAYER",
        years_exp=years_exp,
    )
    metrics: list[tuple[str, str]] = []
    if summary.experience_label:
        metrics.append(("Experience", summary.experience_label))
    if summary.best_finish_label:
        finish_value = summary.best_finish_label
        if summary.best_finish_season:
            finish_value = f"{finish_value} · {summary.best_finish_season}"
        metrics.append(("Best finish", finish_value))
    if summary.best_production_label:
        metrics.append(("Best season", summary.best_production_label))
    if summary.consistency_label:
        metrics.append(("Consistency", summary.consistency_label))
    if summary.arc_label and (expanded or len(resume.seasons) >= 2):
        metrics.append(("Recent arc", summary.arc_label))

    if metrics:
        metric_html = "".join(
            "<div class='player-dossier-career-metric'>"
            f"<span>{escape(label)}</span><strong>{escape(value)}</strong>"
            "</div>"
            for label, value in metrics
        )
        body = f"<div class='player-dossier-career-summary'>{metric_html}</div>"
    elif summary.empty_state:
        body = (
            f"<p class='player-dossier-career-empty'>{escape(summary.empty_state)}</p>"
        )
    else:
        body = (
            "<p class='player-dossier-career-empty'>"
            "Limited NFL history available."
            "</p>"
        )

    milestones = prioritize_milestones(
        resume.achievements,
        limit=6 if expanded else 4,
    )
    if include_milestones and milestones and expanded:
        grouped = group_achievements_by_family_year(milestones)
        milestone_parts: list[str] = [
            "<div class='player-dossier-career-milestones'>"
            "<div class='player-dossier-career-milestones-title'>Career Milestones</div>"
        ]
        for group_label, group_items in grouped:
            milestone_parts.append(
                f"<div class='player-dossier-achievement-family'>{escape(group_label)}</div>"
            )
            milestone_parts.append(
                "<ol class='player-dossier-achievement-list'>"
                + "".join(_achievement_html(item) for item in group_items)
                + "</ol>"
            )
        milestone_parts.append("</div>")
        body += "".join(milestone_parts)
    elif include_milestones and milestones:
        labels = " · ".join(item.label for item in milestones)
        body += (
            "<div class='player-dossier-career-milestones'>"
            "<div class='player-dossier-career-milestones-title'>Career Milestones</div>"
            f"<p class='player-dossier-career-milestone-line'>{escape(labels)}</p>"
            "</div>"
        )

    basis = (
        f"<p class='player-dossier-career-basis'>{escape(summary.scoring_basis)}</p>"
        if expanded
        else ""
    )
    return (
        "<section class='player-dossier-career player-dossier-resume' aria-labelledby='player-dossier-resume-title'>"
        + heading
        + body
        + basis
        + "</section>"
    )


def _season_timeline_html(season: HistoricalSeason, *, include_achievements: bool = True) -> str:
    context = []
    if season.age is not None:
        context.append(f"Age {season.age}")
    achievement_labels = (
        ", ".join(item.label for item in season.achievements[:2])
        if include_achievements
        else ""
    )
    metric_cells: list[tuple[str, str]] = []
    if season.games is not None:
        metric_cells.append((f"{season.games} games", ""))
    if season.fantasy_ppg is not None:
        metric_cells.append((f"{season.fantasy_ppg:.1f} PPG", ""))
    elif season.fantasy_points is not None:
        metric_cells.append((f"{season.fantasy_points:.1f} PPR", ""))
    for label, value in season.key_stats[:4]:
        metric_cells.append((str(value), label))
    metrics_html = "".join(
        "<span>"
        + escape(value)
        + (f" {escape(label)}" if label else "")
        + "</span>"
        for value, label in metric_cells
    )
    finish = (
        f"#{season.position_finish}"
        if season.position_finish is not None
        else ""
    )
    return (
        "<li class='player-dossier-timeline-season'>"
        f"<div class='player-dossier-timeline-year'><strong>{season.season}</strong>"
        + (f"<span>{escape(finish)}</span>" if finish else "")
        + ("<span>Current</span>" if season.current_season else "")
        + "</div><div class='player-dossier-timeline-copy'>"
        + (
            f"<div class='player-dossier-timeline-context'>{escape(' · '.join(context))}</div>"
            if context
            else ""
        )
        + (f"<div class='player-dossier-timeline-metrics'>{metrics_html}</div>" if metrics_html else "")
        + (f"<small>{escape(achievement_labels)}</small>" if achievement_labels else "")
        + "</div></li>"
    )


def career_timeline_html(
    resume: CareerResume,
    *,
    expanded: bool = False,
    include_achievements: bool = False,
) -> str:
    heading = dossier_section_heading_html("Career Timeline").replace(
        "<h3>",
        "<h3 id='player-dossier-timeline-title'>",
        1,
    )
    seasons = resume.seasons if expanded else resume.seasons[:2]
    if seasons:
        body = "<ol class='player-dossier-timeline'>" + "".join(
            _season_timeline_html(season, include_achievements=include_achievements)
            for season in seasons
        ) + "</ol>"
    else:
        body = "<p class='player-dossier-career-empty'>Historical season data is not currently available for this player.</p>"
    return (
        "<section class='player-dossier-career player-dossier-career-timeline' aria-labelledby='player-dossier-timeline-title'>"
        + heading + body + "</section>"
    )
def recommendation_context_html(
    summary: str,
    context: str = "",
    *,
    action: str = "",
    active_recommendation: bool = True,
    recommendation_id: str = "",
    confidence: str = "",
) -> str:
    """Render PQV recommendation or neutral player context.

    When ``active_recommendation`` is false, this is general player analysis —
    not a synthesized recommendation.
    """

    title = "Recommendation" if active_recommendation else "Player Context"
    heading = dossier_section_heading_html(title).replace(
        "<h3>",
        "<h3 id='player-dossier-context-title'>",
        1,
    )
    confidence_text = _text(confidence)
    action_text = _text(action) if action and active_recommendation else ""
    topline = ""
    if action_text or confidence_text:
        topline = (
            "<div class='pqv-decision-topline'>"
            + (
                f"<strong class='player-dossier-context-action'>{escape(action_text)}</strong>"
                if action_text
                else ""
            )
            + (
                f"<span class='pqv-recommendation-confidence'>{escape(confidence_text)}</span>"
                if confidence_text
                else ""
            )
            + "</div>"
        )
    summary_html = (
        f"<p class='player-dossier-context-summary'>{escape(summary)}</p>"
        if _text(summary)
        else ""
    )
    context_text = _text(context)
    summary_text = _text(summary)
    note_html = (
        f"<p class='player-dossier-context-note'>{escape(context_text)}</p>"
        if context_text and context_text.casefold() != summary_text.casefold()
        else ""
    )
    provenance = (
        f"<p class='player-dossier-context-provenance' data-recommendation-id="
        f"'{escape(recommendation_id, quote=True)}'></p>"
        if recommendation_id
        else ""
    )
    mode_class = (
        "player-dossier-recommendation-context dg-info-weight-verdict pqv-decision-summary"
        if active_recommendation
        else "player-dossier-recommendation-context player-dossier-neutral-context pqv-decision-summary"
    )
    return (
        f"<section class='{mode_class}' "
        "aria-labelledby='player-dossier-context-title'>"
        + heading
        + topline
        + summary_html
        + note_html
        + provenance
        + "</section>"
    )


_CURRENT_SEASON_PRODUCTION = {
    "QB": ("Pass Yards", "Pass TDs", "Rush Yards", "Rush TDs"),
    "RB": ("Rush Yards", "Rush TDs", "Targets", "Receptions", "Rec Yards"),
    "WR": ("Targets", "Receptions", "Rec Yards", "Rec TDs"),
    "TE": ("Targets", "Receptions", "Rec Yards", "Rec TDs"),
    "K": ("FG Made", "XP Made", "Kicking Points", "Points"),
    "DEF": ("Sacks", "INT", "PA", "TD"),
    "DST": ("Sacks", "INT", "PA", "TD"),
}


def current_season_summary_html(
    stats: pd.Series | PlayerQuickViewStats,
    *,
    extra_metrics: list[tuple[str, str]] | tuple[tuple[str, str], ...] = (),
    position: str = "",
) -> str:
    """Concise current-season evidence. Complete tables stay in More Details."""

    model = _stats_model(stats)
    selected = model.seasons[0] if model.seasons else None
    metrics: list[tuple[str, str]] = []
    if selected is not None:
        fantasy_points = next(
            (
                item.value
                for item in selected.fantasy
                if item.label.casefold() in {"fantasy points", "ppr", "fantasy ppr"}
            ),
            "",
        )
        ppg = next(
            (item.value for item in selected.fantasy if "PPG" in item.label.upper()),
            "",
        )
        by_label = {
            item.label: item.value
            for item in selected.key_stats
            if item.label and item.value
        }
        if selected.games is not None:
            metrics.append(("Games", str(selected.games)))
        if ppg:
            metrics.append(("PPR PPG", ppg))
        elif fantasy_points:
            metrics.append(("PPR Pts", fantasy_points))
        for item in selected.usage:
            label_key = item.label.casefold()
            if item.value and "snap" in label_key:
                metrics.append((item.label, item.value))
                break
        position_key = _text(position).upper() or _text(model.position).upper()
        preferred_production = _CURRENT_SEASON_PRODUCTION.get(
            position_key,
            (
                "Targets",
                "Receptions",
                "Rec Yards",
                "Rec TDs",
                "Rush Yards",
                "Rush TDs",
                "Pass Yards",
                "Pass TDs",
            ),
        )
        production_added = 0
        for label in preferred_production:
            value = by_label.get(label)
            if not value:
                continue
            metrics.append((label, value))
            production_added += 1
            if production_added >= 4:
                break
    extra_compact: list[tuple[str, str]] = []
    extra_seen: set[str] = set()
    for label, value in extra_metrics:
        heading = _text(label)
        detail = _text(value)
        key = heading.casefold()
        if not heading or not detail or key in extra_seen:
            continue
        extra_seen.add(key)
        extra_compact.append((heading, detail))
        if len(extra_compact) >= 2:
            break
    seen: set[str] = set(extra_seen)
    compact: list[tuple[str, str]] = []
    for label, value in metrics:
        key = label.casefold()
        if key in seen or not value:
            continue
        seen.add(key)
        compact.append((label, value))
    compact.extend(extra_compact)
    if not compact:
        return ""

    def _glance_cell(label: str, value: str) -> str:
        bar = ""
        if "%" in value:
            digits = "".join(ch for ch in value if ch.isdigit() or ch == ".")
            try:
                pct = max(0, min(100, int(round(float(digits)))))
            except ValueError:
                pct = 0
            bar = (
                f"<span class='pqv-glance-bar' aria-hidden='true'>"
                f"<span style='width:{pct}%'></span></span>"
            )
        return (
            "<div class='pqv-glance-cell'>"
            f"<strong>{escape(value)}</strong><span>{escape(label)}</span>{bar}</div>"
        )

    metric_html = "".join(_glance_cell(label, value) for label, value in compact)
    subtitle = selected.label if selected is not None else ""
    heading = dossier_section_heading_html(
        "Current Season",
        subtitle,
    ).replace("<h3>", "<h3 id='player-dossier-season-summary-title'>", 1)
    return (
        "<section class='player-dossier-season-summary pqv-fantasy-evidence' "
        "aria-labelledby='player-dossier-season-summary-title'>"
        + heading
        + f"<div class='pqv-glance-grid'>{metric_html}</div>"
        + "</section>"
    )


def college_unavailable_message() -> str:
    return "College production data is not currently available for this player."


def developer_diagnostics_enabled(environ: Mapping[str, str] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    enabled = _text(env.get("DYNASTYGM_DEBUG_UI")).casefold() in _TRUE_VALUES
    host = _text(env.get("APP_BASE_URL")).casefold().removeprefix("https://").removeprefix("http://").split("/")[0]
    return enabled and host not in _PRODUCTION_HOSTS


def developer_diagnostics(row: pd.Series) -> dict[str, list[str]]:
    return player_profile_ui.player_stat_field_debug(row)


def safe_news_url(value: object) -> str:
    url = _text(value)
    parsed = urlparse(url)
    return url if parsed.scheme in {"http", "https"} and bool(parsed.netloc) else ""


_KNOWN_NEWS_HOSTS = {
    "rotowire.com": "RotoWire",
    "espn.com": "ESPN",
    "cbssports.com": "CBS Sports",
    "sports.yahoo.com": "Yahoo Sports",
    "yahoo.com": "Yahoo Sports",
    "nbcsports.com": "NBC Sports",
    "nfl.com": "NFL.com",
    "theathletic.com": "The Athletic",
    "profootballtalk.nbcsports.com": "PFT",
    "pff.com": "PFF",
    "si.com": "Sports Illustrated",
    "bleacherreport.com": "Bleacher Report",
}

_KNOWN_NEWS_NAMES = {
    "espn": "ESPN",
    "espn nfl": "ESPN",
    "cbs": "CBS Sports",
    "cbs sports": "CBS Sports",
    "cbssports": "CBS Sports",
    "rotowire": "RotoWire",
    "roto wire": "RotoWire",
    "yahoo": "Yahoo Sports",
    "yahoo sports": "Yahoo Sports",
    "nbc": "NBC Sports",
    "nbc sports": "NBC Sports",
    "nfl": "NFL.com",
    "the athletic": "The Athletic",
    "profootballtalk": "PFT",
    "pft": "PFT",
    "pff": "PFF",
}


def normalize_news_source(value: object) -> str:
    """Return a publisher label; never invent a false brand for unknown hosts."""

    text = _text(value)
    if not text:
        return ""
    lower = text.casefold().strip()
    if lower in _KNOWN_NEWS_NAMES:
        return _KNOWN_NEWS_NAMES[lower]
    looks_like_url = any(token in text for token in ("://", "/", "?", "&", "www."))
    if not looks_like_url:
        return text
    candidate = text if "://" in text else f"https://{text.lstrip('/')}"
    parsed = urlparse(candidate)
    host = (parsed.netloc or "").casefold()
    if not host:
        return text
    host = host.split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    if host in _KNOWN_NEWS_HOSTS:
        return _KNOWN_NEWS_HOSTS[host]
    for known_host, label in _KNOWN_NEWS_HOSTS.items():
        if host.endswith(f".{known_host}"):
            return label
    # Clean domain label only — do not invent a publisher name.
    return host


def news_card_html(item: NewsItem) -> str:
    headline = escape(item.display_headline())
    if not headline:
        return ""
    kicker_parts = [part for part in (item.event_type, item.freshness) if part]
    kicker = escape(" · ".join(kicker_parts)) if kicker_parts else ""
    meta_parts = [part for part in (item.source, item.freshness if not item.event_type else "") if part]
    meta = escape(" · ".join(meta_parts)) if meta_parts else ""
    snippet = escape(item.display_snippet()) if item.display_snippet() else ""
    status = escape(item.status_line) if item.status_line else ""
    corr = escape(item.corroboration_note or item.corroboration) if (item.corroboration_note or item.corroboration) else ""
    return (
        "<article class='player-dossier-news-card'>"
        + (f"<p class='player-dossier-news-kicker'>{kicker}</p>" if kicker else "")
        + (f"<p class='player-dossier-news-meta'>{meta}</p>" if meta else "")
        + f"<h4 class='player-dossier-news-headline'>{headline}</h4>"
        + (f"<p class='player-dossier-news-snippet'>{snippet}</p>" if snippet else "")
        + (f"<p class='player-dossier-news-status'>{status}</p>" if status else "")
        + (f"<p class='player-dossier-news-corr'>{corr}</p>" if corr else "")
        + "</article>"
    )


def news_unavailable_html() -> str:
    return (
        "<p class='player-dossier-news-quiet'>"
        "Recent news is temporarily unavailable."
        "</p>"
    )


def news_empty_html() -> str:
    return (
        "<p class='player-dossier-news-quiet'>"
        "No recent player news is available."
        "</p>"
    )


def _stats_model(value: pd.Series | PlayerQuickViewStats) -> PlayerQuickViewStats:
    return value if isinstance(value, PlayerQuickViewStats) else build_stats_view(value)


def render_current_season(
    stats: pd.Series | PlayerQuickViewStats,
    *,
    show_heading: bool = True,
    omit_empty: bool = False,
) -> tuple[str, ...]:
    """Render the one proven regular-season aggregate loaded today."""
    model = _stats_model(stats)
    rendered: list[str] = []
    has_rows = bool(model.seasons) and bool(
        model.seasons[0].key_stats
        or model.seasons[0].fantasy
        or model.seasons[0].usage
    )
    if omit_empty and not has_rows:
        return tuple()
    if show_heading:
        st.markdown(
            dossier_section_heading_html(
                "Complete Season Stats",
                "Professional production, fantasy output, and usage from one consistent season.",
            ),
            unsafe_allow_html=True,
        )
    if model.seasons:
        selected = model.seasons[0]
        context = selected.label
        if selected.games is not None:
            context += f" | {selected.games} games"
        st.markdown(
            f"<div class='player-quick-view-season-context'>{escape(context)}</div>",
            unsafe_allow_html=True,
        )
        for title, items in (
            ("Professional Production", selected.key_stats),
            ("Fantasy Production", selected.fantasy),
            ("Usage", selected.usage),
        ):
            if items:
                rendered.append(title)
                st.markdown(dense_section_html(title, items), unsafe_allow_html=True)

    if not rendered and not omit_empty:
        st.markdown(
            "<div class='player-detail-empty player-quick-view-stats-empty'>"
            "No professional statistics are available for the loaded season."
            "</div>",
            unsafe_allow_html=True,
        )

    return tuple(rendered)


def render_news(
    news_items: list[NewsItem],
    *,
    include_shell: bool = True,
    status: str = "ok",
    default_limit: int = 3,
    omit_empty: bool = False,
) -> bool:
    """Render polished recent-news cards. Never exposes raw URLs as primary copy."""

    has_cards = status == "ok" and bool(news_items)
    if omit_empty and not has_cards and status not in {"error", "loading"}:
        return False

    if include_shell and (has_cards or not omit_empty):
        st.markdown(
            dossier_section_heading_html(
                "Recent News",
                "Automatically loaded player headlines — not a news feed.",
            ),
            unsafe_allow_html=True,
        )

    if status == "error":
        if omit_empty:
            st.caption("Recent news is temporarily unavailable.")
        else:
            st.markdown(news_unavailable_html(), unsafe_allow_html=True)
        return True
    if status == "loading":
        st.caption("Loading recent news…")
        return True
    if not news_items:
        if not omit_empty:
            st.markdown(news_empty_html(), unsafe_allow_html=True)
        return False

    visible = list(news_items[: max(1, int(default_limit))])
    overflow = list(news_items[len(visible) :])

    def _paint(items: list[NewsItem]) -> None:
        for index, item in enumerate(items):
            card = news_card_html(item)
            if card:
                st.markdown(card, unsafe_allow_html=True)
            if item.url:
                digest = hashlib.sha1(
                    f"{item.url}|{item.display_headline()}|{index}".encode("utf-8")
                ).hexdigest()[:12]
                st.link_button(
                    "Read article →",
                    item.url,
                    key=f"pqv_news_read_{digest}",
                    use_container_width=False,
                )

    _paint(visible)
    if overflow:
        overflow_parts: list[str] = []
        for item in overflow:
            card = news_card_html(item)
            if card:
                overflow_parts.append(card)
            if item.url:
                overflow_parts.append(
                    "<p class='player-dossier-news-link'>"
                    f"<a href='{escape(item.url, quote=True)}' target='_blank' "
                    "rel='noopener noreferrer'>Read article →</a></p>"
                )
        details = (
            f"<details class='dg-info-disclosure dg-client-disclosure "
            f"player-dossier-more-news'>"
            f"<summary>More news ({len(overflow)})</summary>"
            f"<div class='dg-client-disclosure-body'>{''.join(overflow_parts)}</div>"
            "</details>"
        )
        st.markdown(details, unsafe_allow_html=True)
    return True


def render_college_production(
    stats: pd.Series | PlayerQuickViewStats,
    *,
    omit_empty: bool = False,
) -> None:
    model = _stats_model(stats)
    if model.college_available:
        st.markdown(
            dense_section_html("College Production", model.college),
            unsafe_allow_html=True,
        )
        return
    if not omit_empty:
        st.caption(college_unavailable_message())


def render_developer_diagnostics(row: pd.Series) -> None:
    if developer_diagnostics_enabled():
        st.caption("Developer Information — field availability diagnostics.")
        st.json(developer_diagnostics(row))

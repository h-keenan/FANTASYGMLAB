"""Canonical league competition format, distinct from valuation philosophy.

Sleeper ``settings.type`` is decoded in league-value settings as:
0 = Redraft, 1 = Keeper (stored as Dynasty + ``_keeper_mode``), 2 = Dynasty.

User-facing intelligence must use this module rather than treating
``Balanced Dynasty`` as the league format or strategy.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

REDRAFT = "redraft"
KEEPER = "keeper"
DYNASTY = "dynasty"

_DISPLAY = {
    REDRAFT: "Redraft",
    KEEPER: "Keeper",
    DYNASTY: "Dynasty",
}


def competition_format(settings: Mapping[str, Any] | None) -> str:
    """Return redraft | keeper | dynasty from canonical league-value settings."""

    payload = settings if isinstance(settings, Mapping) else {}
    raw = str(payload.get("league_format") or "").strip().casefold()
    if payload.get("_keeper_mode") or raw == KEEPER:
        return KEEPER
    if raw == REDRAFT:
        return REDRAFT
    return DYNASTY


def format_display_name(settings: Mapping[str, Any] | None) -> str:
    return _DISPLAY[competition_format(settings)]


def future_picks_are_trade_capital(settings: Mapping[str, Any] | None) -> bool:
    """Redraft does not own multi-year pick boards. Keeper and dynasty do."""

    return competition_format(settings) in {KEEPER, DYNASTY}


def lead_with_franchise_construction(settings: Mapping[str, Any] | None) -> bool:
    """Age / draft-capital / franchise rank are construction metrics, not weekly redraft identity."""

    return competition_format(settings) in {KEEPER, DYNASTY}


def valuation_lens_label(archetype_badge: str | None, archetype_display_name: str | None = "") -> str:
    badge = str(archetype_badge or "").strip()
    if badge:
        return badge
    name = str(archetype_display_name or "").strip()
    if name.casefold().startswith("balanced"):
        return "Balanced"
    return name or "Balanced"


def workspace_context_button_label(
    settings: Mapping[str, Any] | None,
    *,
    archetype_badge: str = "",
    archetype_display_name: str = "",
) -> str:
    fmt = format_display_name(settings)
    lens = valuation_lens_label(archetype_badge, archetype_display_name)
    return f"{fmt} · Valuation: {lens}"


def pick_is_actionable_capital(
    season: int | None,
    *,
    current_pick_year: int,
    current_year_picks_active: bool,
    settings: Mapping[str, Any] | None,
    as_of_year: int | None = None,
) -> bool:
    """Whether a pick season is still tradable capital.

    A. Prior-season pick (before league current year) → never.
    A2. Calendar-expired season (season < as_of_year) → never, even if Sleeper
        still reports last year's league.season.
    B. Current-season pre-draft → yes when current_year_picks_active.
    C. Current-season post-draft → no.
    D. Future-season pick → keeper/dynasty only.

    Featured Trade Hub ordering / Low-confidence ranking is owned by a parallel
    PR. This filter only drops contextually impossible capital.
    """

    try:
        year = int(season)
    except (TypeError, ValueError):
        return False
    current = int(current_pick_year or 0)
    try:
        calendar_year = int(as_of_year) if as_of_year is not None else int(datetime.now().year)
    except (TypeError, ValueError):
        calendar_year = 0
    if year <= 0:
        return False
    if calendar_year and year < calendar_year:
        return False
    if current <= 0 or year < current:
        return False
    if year == current:
        return bool(current_year_picks_active)
    return future_picks_are_trade_capital(settings)

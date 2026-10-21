from html import escape
from typing import Callable

from modules.sleeper_leagues import resolve_current_season_league_id


def _safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def eligible_leagues(leagues) -> list[dict]:
    eligible: list[dict] = []
    seen_ids: set[str] = set()
    for league in leagues if isinstance(leagues, list) else []:
        if not isinstance(league, dict):
            continue
        league_id = _safe_text(league.get("league_id")).strip()
        if not league_id or league_id in seen_ids:
            continue
        seen_ids.add(league_id)
        eligible.append(league)
    return eligible


def group_league_cards_by_season(cards: list[dict]) -> list[tuple[str, list[dict]]]:
    """Group league picker cards by season, most recent season first.

    Bug report, 2026-10-21: "it keeps auto defaulting to 2025" / "we need
    to be able to separate by year" — a continuing dynasty league gets a
    brand-new league_id every season it rolls over on Sleeper's side, so
    the exact same league can legitimately appear in this picker twice
    (once per season, see last_league_option's docstring). A flat list
    made it easy to tap the wrong year's card for "the same" league;
    grouping by season under a visible year header, current season first,
    makes the distinction impossible to miss.
    """
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for card in cards if isinstance(cards, list) else []:
        if not isinstance(card, dict):
            continue
        season = _safe_text(card.get("season")).strip() or "Unknown"
        if season not in groups:
            groups[season] = []
            order.append(season)
        groups[season].append(card)

    def _season_sort_key(season: str) -> tuple[int, int]:
        try:
            return (0, -int(season))
        except (TypeError, ValueError):
            return (1, 0)

    ordered_seasons = sorted(order, key=_season_sort_key)
    return [(season, groups[season]) for season in ordered_seasons]


def last_league_option(
    *,
    username: str,
    leagues: list[dict],
    account: dict | None,
    current_league_id: str = "",
    current_username: str = "",
) -> str:
    eligible = eligible_leagues(leagues)
    valid_ids = {
        _safe_text(league.get("league_id")).strip() for league in eligible
    }
    if current_league_id and current_username.strip().casefold() == username.strip().casefold():
        resolved = resolve_current_season_league_id(current_league_id, eligible)
        if resolved in valid_ids:
            return resolved

    account = account if isinstance(account, dict) else {}
    account_username = _safe_text(account.get("username")).strip()
    account_league_id = _safe_text(account.get("league_id")).strip()
    if account_username.casefold() == username.strip().casefold() and account_league_id:
        resolved = resolve_current_season_league_id(account_league_id, eligible)
        if resolved in valid_ids:
            return resolved
    return ""


def league_card_html(
    card: dict,
    *,
    team_logo_html: Callable,
    selected: bool = False,
    last_used: bool = False,
) -> str:
    selected_class = " selected" if selected else ""
    last_used_chip = (
        "<span class='launch-league-chip launch-league-chip-last'>Last used</span>"
        if last_used
        else ""
    )
    record_label = _safe_text(card.get("record_label")).strip()
    season = _safe_text(card.get("season")).strip()
    draft_state = _safe_text(card.get("draft_state_label")).strip()
    platform_label = _safe_text(card.get("platform_label"), "Sleeper").strip()
    return (
        "<div class='launch-league-card"
        + selected_class
        + "'>"
        + "<div class='launch-league-top'>"
        + team_logo_html(
            _safe_text(card.get("avatar_url")),
            _safe_text(card.get("team_name")),
            css_class="home-hero-logo",
        )
        + "<div class='launch-league-copy'>"
        + f"<div class='launch-league-name'>{escape(_safe_text(card.get('league_name')))}</div>"
        + f"<div class='launch-league-team'>{escape(_safe_text(card.get('team_name')))}</div>"
        + "<div class='launch-league-meta'>"
        + last_used_chip
        + (
            f"<span class='launch-league-chip'>{escape(_safe_text(card.get('format_label')))}</span>"
            if _safe_text(card.get("format_label")).strip()
            else ""
        )
        + (f"<span class='launch-league-chip'>{escape(draft_state)}</span>" if draft_state else "")
        + (f"<span class='launch-league-chip'>{escape(record_label)}</span>" if record_label else "")
        + (
            f"<span class='launch-league-chip'>{escape(str(card.get('league_size')))} teams</span>"
            if int(card.get("league_size") or 0) > 0
            else ""
        )
        + (f"<span class='launch-league-chip'>S{escape(season)}</span>" if season else "")
        + (f"<span class='launch-league-chip'>{escape(platform_label)}</span>" if platform_label else "")
        + "</div></div></div></div>"
    )

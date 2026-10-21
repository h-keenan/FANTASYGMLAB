from html import escape
from typing import Callable


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


def _resolve_current_season_league_id(league_id: str, leagues: list[dict]) -> str:
    """Walk Sleeper's previous_league_id chain forward from a saved/stale
    league_id to this season's continuation of the same dynasty league.

    Sleeper mints a brand-new league_id every time a league rolls over to a
    new season (linked backward via previous_league_id); the old id keeps
    resolving on Sleeper's API indefinitely, it just stops being "this
    season's league." Without this resolution step, a saved league_id that
    is still present in a freshly-fetched multi-season lookup (because
    Sleeper still serves last season's league under its own old id) reads
    as "still valid" even though a newer, current-season version of that
    exact league now exists under a different id.
    """
    if not league_id:
        return league_id
    by_previous_id = {
        _safe_text(league.get("previous_league_id")).strip(): _safe_text(
            league.get("league_id")
        ).strip()
        for league in leagues
        if isinstance(league, dict)
        and _safe_text(league.get("previous_league_id")).strip()
        and _safe_text(league.get("league_id")).strip()
    }
    resolved = league_id
    seen = {resolved}
    while resolved in by_previous_id:
        next_id = by_previous_id[resolved]
        if not next_id or next_id in seen:
            break
        resolved = next_id
        seen.add(resolved)
    return resolved


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
        resolved = _resolve_current_season_league_id(current_league_id, eligible)
        if resolved in valid_ids:
            return resolved

    account = account if isinstance(account, dict) else {}
    account_username = _safe_text(account.get("username")).strip()
    account_league_id = _safe_text(account.get("league_id")).strip()
    if account_username.casefold() == username.strip().casefold() and account_league_id:
        resolved = _resolve_current_season_league_id(account_league_id, eligible)
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

import requests
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Literal, Optional
from urllib.parse import quote

from modules import sleeper as _sleeper
from modules import sleeper_budget

SLEEPER_BASE = "https://api.sleeper.app/v1"

LeagueLookupStatus = Literal["empty_username", "user_not_found", "no_leagues", "ok", "unavailable"]


@dataclass(frozen=True)
class LeagueLookupResult:
    leagues: List[Dict]
    status: LeagueLookupStatus


def log_league_import_diagnostic(
    *,
    stage: str,
    status: str,
    league_count: int | None = None,
    seasons_scanned: int | None = None,
    duration_ms: float | None = None,
    guest: bool = True,
    route: str = "launch",
) -> None:
    """Structured guest-import diagnostic — no username, league names, or tokens."""

    payload = {
        "flow": "guest_league_import",
        "stage": str(stage or "unknown")[:48],
        "status": str(status or "unknown")[:48],
        "league_count": league_count,
        "seasons_scanned": seasons_scanned,
        "duration_ms": None if duration_ms is None else round(float(duration_ms), 1),
        "guest": bool(guest),
        "authenticated": False if guest else True,
        "route": str(route or "launch")[:32],
    }
    try:
        print(f"DYNASTYGM_LEAGUE_IMPORT {payload}", flush=True)
    except Exception:
        pass


def _username_candidates(username: str) -> List[str]:
    candidates: List[str] = []
    for candidate in [username, username.lower(), username.casefold()]:
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _resolve_user_id(username: str) -> tuple[Optional[str], bool]:
    """Return Sleeper user_id and whether a transport error occurred."""
    transport_error = False
    for candidate in _username_candidates(username):
        url = f"{SLEEPER_BASE}/user/{quote(candidate, safe='')}"
        try:
            sleeper_budget.record_call()
            response = requests.get(url, timeout=5)
        except Exception:
            transport_error = True
            continue
        if response.status_code == 404:
            continue
        if response.status_code != 200:
            if response.status_code >= 500:
                transport_error = True
            continue
        try:
            payload = response.json()
        except Exception:
            transport_error = True
            continue
        if isinstance(payload, dict) and payload.get("user_id"):
            return str(payload.get("user_id")), False
    return None, transport_error


def resolve_sleeper_user_id(username: str) -> Optional[str]:
    """Public entry point: Sleeper user_id for a username, or None if not found.

    Delegates to modules.sleeper.get_user_id (an @lru_cache'd near-duplicate
    of this module's own _resolve_user_id — same candidate-casing loop,
    same "first match wins" contract, Optional[str] in both cases) instead
    of maintaining a second, UNCACHED copy of the same Sleeper lookup.

    Real production impact (perf audit, coridian_ 2026-10-19): this is
    called from _resolve_my_roster on nearly every league-scoped request
    (Dashboard, Trade Hub, Waivers, My Team, Trade Finder, Portfolio's own
    per-league fan-out) — a real, uncached Sleeper network round trip on
    every single one of those, for a username -> user_id mapping that
    essentially never changes. get_user_id already solves exactly this for
    every OTHER caller in the codebase; this was the one uncached straggler.

    Deliberately NOT applied to this module's OTHER caller of
    _resolve_user_id (lookup_user_leagues) — that one-time, user-initiated
    League Import flow genuinely needs the transport_error distinction
    get_user_id doesn't expose (a real "Sleeper is down" vs. "that username
    doesn't exist" difference), so it keeps its own uncached path."""

    return _sleeper.get_user_id(username)


def lookup_user_leagues(username: str, season: Optional[int] = None) -> LeagueLookupResult:
    """
    Return Sleeper leagues for a username with a customer-safe lookup status.
    """
    username_clean = (username or "").strip()
    if not username_clean:
        return LeagueLookupResult([], "empty_username")

    user_id, user_lookup_transport_error = _resolve_user_id(username_clean)
    if user_lookup_transport_error and not user_id:
        log_league_import_diagnostic(stage="username_lookup", status="unavailable")
        return LeagueLookupResult([], "unavailable")
    if not user_id:
        log_league_import_diagnostic(stage="username_lookup", status="user_not_found")
        return LeagueLookupResult([], "user_not_found")

    if season is None:
        season = datetime.now().year

    seasons_to_try = [season, season - 1]
    transport_error = False
    merged: List[Dict] = []
    seen_ids: set[str] = set()
    year_ok = False

    for yr in seasons_to_try:
        url = f"{SLEEPER_BASE}/user/{user_id}/leagues/nfl/{yr}"
        try:
            sleeper_budget.record_call()
            resp = requests.get(url, timeout=8)
        except Exception:
            transport_error = True
            continue
        if resp.status_code != 200:
            if resp.status_code >= 500:
                transport_error = True
            continue
        try:
            leagues = resp.json()
        except Exception:
            transport_error = True
            continue
        if not isinstance(leagues, list):
            continue
        year_ok = True
        for lg in leagues:
            if not isinstance(lg, dict):
                continue
            lg.setdefault("season", yr)
            league_id = str(lg.get("league_id") or "").strip()
            if not league_id or league_id in seen_ids:
                continue
            seen_ids.add(league_id)
            merged.append(lg)

    if merged:
        log_league_import_diagnostic(
            stage="username_lookup",
            status="ok",
            league_count=len(merged),
            seasons_scanned=len(seasons_to_try),
        )
        return LeagueLookupResult(merged, "ok")
    if transport_error and not year_ok:
        log_league_import_diagnostic(stage="username_lookup", status="unavailable")
        return LeagueLookupResult([], "unavailable")
    log_league_import_diagnostic(stage="username_lookup", status="no_leagues")
    return LeagueLookupResult([], "no_leagues")


def get_user_leagues(username: str, season: Optional[int] = None) -> List[Dict]:
    """
    Return all NFL leagues for this Sleeper username, trying current and previous
    season if needed.[web:4][web:181]
    """
    return lookup_user_leagues(username, season=season).leagues


def _safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def resolve_current_season_league_id(league_id: str, leagues: List[Dict]) -> str:
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

    Shared by modules.onboarding_ui (the onboarding picker's "last used"
    shortcut) and resolve_saved_league_rollover below (an already-saved
    league going stale after the fact) -- same chain-walk, two callers.
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


def resolve_saved_league_rollover(
    league_id: str, sleeper_username: str, *, season: Optional[int] = None
) -> str:
    """Given an already-saved league_id and the Sleeper username that saved
    it, return this season's continuation of that league if one exists,
    else the original league_id unchanged.

    Real production bug, 2026-10-21 (coridian_, live): a user's saved
    league keeps pointing at last season's now-frozen league_id forever
    once their real league rolls over on Sleeper -- nothing re-points it,
    so a stale roster view, and (via modules.guess_the_player_leaderboard's
    own direct saved_leagues query) a leaderboard that only matches
    leaguemates who happen to share that exact stale-or-fresh id, are both
    direct downstream consequences. This is the read path for that fix
    (see services/mobile_api_service.py's _resolve_league_rollover_cached);
    never raises and never guesses -- a lookup failure or an unresolvable
    chain returns the original id unchanged, so a transport hiccup can
    never turn into a wrong league.
    """
    league_id_clean = _safe_text(league_id).strip()
    username_clean = _safe_text(sleeper_username).strip()
    if not league_id_clean or not username_clean:
        return league_id_clean
    lookup = lookup_user_leagues(username_clean, season=season)
    if lookup.status != "ok":
        return league_id_clean
    return resolve_current_season_league_id(league_id_clean, lookup.leagues)


def league_lookup_customer_message(status: LeagueLookupStatus) -> str:
    if status == "empty_username":
        return "Enter a Sleeper username first."
    if status == "user_not_found":
        return "No Sleeper account matched that username. Check spelling and try again."
    if status == "unavailable":
        return "Sleeper is temporarily unreachable. Wait a moment and try again."
    if status == "no_leagues":
        return (
            "No leagues were found for that Sleeper username in this season or last season. "
            "Check the exact username and try again."
        )
    return ""

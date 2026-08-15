import requests
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Literal, Optional
from urllib.parse import quote

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

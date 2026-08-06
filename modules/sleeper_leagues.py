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
        return LeagueLookupResult([], "unavailable")
    if not user_id:
        return LeagueLookupResult([], "user_not_found")

    if season is None:
        season = datetime.now().year

    seasons_to_try = [season, season - 1]
    transport_error = False

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
        if isinstance(leagues, list) and leagues:
            for lg in leagues:
                lg.setdefault("season", yr)
            return LeagueLookupResult(leagues, "ok")

    if transport_error:
        return LeagueLookupResult([], "unavailable")
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

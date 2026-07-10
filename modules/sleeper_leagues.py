import requests
from typing import List, Dict, Optional
from datetime import datetime

from modules.sleeper import get_user_id

SLEEPER_BASE = "https://api.sleeper.app/v1"


def get_user_leagues(username: str, season: Optional[int] = None) -> List[Dict]:
    """
    Return all NFL leagues for this Sleeper username, trying current and previous
    season if needed.[web:4][web:181]
    """
    if not username:
        return []

    user_id = get_user_id(username)
    if not user_id:
        return []

    if season is None:
        season = datetime.now().year

    # Try current season first
    seasons_to_try = [season, season - 1]

    for yr in seasons_to_try:
        url = f"{SLEEPER_BASE}/user/{user_id}/leagues/nfl/{yr}"
        try:
            resp = requests.get(url, timeout=8)
            if resp.status_code != 200:
                continue
            leagues = resp.json()
            if isinstance(leagues, list) and leagues:
                # Attach the season to each league for clarity
                for lg in leagues:
                    lg.setdefault("season", yr)
                return leagues
        except Exception:
            continue

    return []

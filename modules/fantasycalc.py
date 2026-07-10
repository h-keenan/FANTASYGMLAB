import os
import time

import pandas as pd
import requests

BASE = "https://api.fantasycalc.com"
FANTASYCALC_CACHE_PATH = "data/fantasycalc_values.csv"
FANTASYCALC_CACHE_TTL_SECONDS = 6 * 60 * 60


def _load_cache() -> pd.DataFrame:
    if not os.path.exists(FANTASYCALC_CACHE_PATH):
        return pd.DataFrame()
    try:
        age = time.time() - os.path.getmtime(FANTASYCALC_CACHE_PATH)
        if age > FANTASYCALC_CACHE_TTL_SECONDS:
            return pd.DataFrame()
        return pd.read_csv(FANTASYCALC_CACHE_PATH)
    except Exception:
        return pd.DataFrame()


def _save_cache(df: pd.DataFrame) -> None:
    if df.empty:
        return
    os.makedirs(os.path.dirname(FANTASYCALC_CACHE_PATH), exist_ok=True)
    df.to_csv(FANTASYCALC_CACHE_PATH, index=False)


def get_dynasty_values(num_teams=12, num_qbs=1, ppr=1.0, use_cache=True) -> pd.DataFrame:
    """
    Query FantasyCalc dynasty values and return a DataFrame with columns:
    name, position, team, value
    """
    if use_cache:
        cached = _load_cache()
        if not cached.empty:
            return cached

    url = f"{BASE}/values/current"
    params = {
        "isDynasty": "true",
        "numTeams": num_teams,
        "numQbs": num_qbs,
        "ppr": ppr,
    }
    try:
        resp = requests.get(url, params=params, timeout=4)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return pd.DataFrame()

    rows = []
    for item in data:
        # FantasyCalc examples show player data nested like item['player']['name'] [web:5]
        player = item.get("player", {})
        name = player.get("name")
        pos = player.get("position")
        team = player.get("team")
        value = item.get("value") or item.get("trade_value") or item.get("overallRank")

        if not name:
            continue

        rows.append(
            {
                "name": name,
                "position": pos,
                "team": team,
                "value": value,
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        _save_cache(df)
    return df

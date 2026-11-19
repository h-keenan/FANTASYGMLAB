import json
import os
import time

import pandas as pd
import requests

BASE = "https://api.fantasycalc.com"
FANTASYCALC_CACHE_PATH = "data/fantasycalc_values.csv"
FANTASYCALC_CACHE_TTL_SECONDS = 6 * 60 * 60
FANTASYCALC_META_SUFFIX = ".meta.json"  # sidecar sits beside the CSV: data/fantasycalc_values.meta.json
# Data-truth audit 2026-11-19 (docs/audits/2026-11-data-truth.md, finding 1): a file's mtime is the checkout
# time in a git deploy, so the committed July seed CSV looked "0s old" to every refresh job and was served as
# live. With this flag ON the TTL and the "as of" come from a fetched_at timestamp stored beside the CSV
# (written only by a real provider fetch); a CSV with no such timestamp counts as stale and is refetched.
FRESH_CACHE_FLAG = "DYNASTYGM_FRESH_PROVIDER_CACHE_V1"


def meta_path() -> str:
    return os.path.splitext(FANTASYCALC_CACHE_PATH)[0] + FANTASYCALC_META_SUFFIX


def fresh_cache_enabled() -> bool:
    from modules.app_config import config_bool

    return bool(config_bool(FRESH_CACHE_FLAG))


def fetched_at() -> float | None:
    """Epoch seconds of the last real provider fetch, or None when unknown (seed file, no sidecar)."""

    try:
        with open(meta_path(), encoding="utf-8") as fh:
            value = float(json.load(fh)["fetched_at"])
        return value if value > 0 else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _load_cache(*, ignore_ttl: bool = False) -> pd.DataFrame:
    """The on-disk values. ``ignore_ttl`` is the last-known-good read used when the
    provider is down / slow / returns garbage: stale values beat an empty page, and
    ``df.attrs["as_of"]`` (epoch seconds) lets callers say "values as of X"."""

    if not os.path.exists(FANTASYCALC_CACHE_PATH):
        return pd.DataFrame()
    try:
        as_of = os.path.getmtime(FANTASYCALC_CACHE_PATH)
        if fresh_cache_enabled():
            # No sidecar = a committed seed / unknown provenance: not fresh, whatever its mtime says.
            as_of = fetched_at() or 0.0
        if not ignore_ttl and time.time() - as_of > FANTASYCALC_CACHE_TTL_SECONDS:
            return pd.DataFrame()
        df = pd.read_csv(FANTASYCALC_CACHE_PATH, dtype={"sleeper_id": str, "mfl_id": str})
        df.attrs["as_of"] = as_of
        return df
    except Exception:
        return pd.DataFrame()


def _save_cache(df: pd.DataFrame) -> None:
    if df.empty:
        return
    os.makedirs(os.path.dirname(FANTASYCALC_CACHE_PATH), exist_ok=True)
    df.to_csv(FANTASYCALC_CACHE_PATH, index=False)
    try:
        with open(meta_path(), "w", encoding="utf-8") as fh:
            json.dump({"fetched_at": time.time(), "rows": int(len(df))}, fh)
    except OSError:
        pass  # the sidecar is provenance only; never fail a good fetch over it


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
        if not isinstance(data, list) or not data:
            raise ValueError("unexpected FantasyCalc payload")  # garbage / empty: never overwrite good data
    except Exception:
        return _load_cache(ignore_ttl=True) if use_cache else pd.DataFrame()

    rows = []
    for item in data:
        if not isinstance(item, dict):
            continue
        # FantasyCalc examples show player data nested like item['player']['name'] [web:5]
        player = item.get("player", {})
        name = player.get("name")
        pos = player.get("position")
        # FantasyCalc sends the team as `maybeTeam` (there is no `team` key), so reading only `team` left every row blank.
        team = player.get("maybeTeam") or player.get("team")
        # Never fall back to `overallRank`: a rank (1..N) stored as a value would read as a near-worthless player.
        value = item.get("value") or item.get("trade_value")
        if not value:
            continue

        if not name:
            continue

        rows.append(
            {
                "name": name,
                "position": pos,
                "team": team,
                "value": value,
                # Provider-side ids let consumers join on identity, not on a name.
                "sleeper_id": player.get("sleeperId"),
                "mfl_id": player.get("mflId"),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return _load_cache(ignore_ttl=True) if use_cache else df
    _save_cache(df)
    df.attrs["as_of"] = time.time()
    return df

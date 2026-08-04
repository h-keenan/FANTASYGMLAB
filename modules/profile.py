import json
import os
from typing import Dict, Any

from modules.valuation_archetypes import DEFAULT_VALUATION_ARCHETYPE_ID

PROFILE_PATH = "data/profile.json"


def _profile_key(username: str, league_id: str) -> str:
    return f"{(username or '').strip().casefold()}|{league_id}"


def _load_raw() -> Dict[str, Any]:
    if not os.path.exists("data"):
        os.makedirs("data")
    if not os.path.exists(PROFILE_PATH):
        return {}
    try:
        with open(PROFILE_PATH, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


def _save_raw(data: Dict[str, Any]) -> None:
    if not os.path.exists("data"):
        os.makedirs("data")
    with open(PROFILE_PATH, "w") as f:
        json.dump(data, f, indent=2)


def load_profile_key(username: str, league_id: str) -> Dict[str, Any]:
    """
    Load profile (roles, trade_block, untouchables) for a specific username+league.
    """
    raw = _load_raw()
    key = _profile_key(username, league_id)
    profile = raw.get(key, {})
    profile.setdefault("roles", {})
    profile.setdefault("trade_block", [])
    profile.setdefault("untouchables", [])
    profile.setdefault("strategy_override", "Auto")
    profile.setdefault("valuation_archetype_id", DEFAULT_VALUATION_ARCHETYPE_ID)
    return profile


def save_profile_key(username: str, league_id: str, profile: Dict[str, Any]) -> None:
    raw = _load_raw()
    key = _profile_key(username, league_id)
    next_profile = {
        "roles": profile.get("roles", {}),
        "trade_block": profile.get("trade_block", []),
        "untouchables": profile.get("untouchables", []),
        "strategy_override": profile.get("strategy_override", "Auto"),
        "valuation_archetype_id": profile.get(
            "valuation_archetype_id",
            DEFAULT_VALUATION_ARCHETYPE_ID,
        ),
    }
    existing = raw.get(key)
    if existing == next_profile:
        return
    raw[key] = next_profile
    _save_raw(raw)

import json
import os
from typing import Dict, Any, List

ACCOUNTS_PATH = "data/accounts.json"


def load_accounts() -> Dict[str, Any]:
    if not os.path.exists("data"):
        os.makedirs("data")
    if not os.path.exists(ACCOUNTS_PATH):
        # Default single account from settings.yaml style
        return {"current": None, "accounts": {}}
    try:
        with open(ACCOUNTS_PATH, "r") as f:
            data = json.load(f)
        if "accounts" not in data:
            data["accounts"] = {}
        if "current" not in data:
            data["current"] = None
        return data
    except Exception:
        return {"current": None, "accounts": {}}


def save_accounts(data: Dict[str, Any]) -> None:
    if not os.path.exists("data"):
        os.makedirs("data")
    with open(ACCOUNTS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def upsert_account(name: str, league_id: str, username: str) -> Dict[str, Any]:
    data = load_accounts()
    next_record = {"league_id": str(league_id), "username": username}
    existing = data.get("accounts", {}).get(name)
    if (
        data.get("current") == name
        and isinstance(existing, dict)
        and existing.get("league_id") == next_record["league_id"]
        and existing.get("username") == next_record["username"]
    ):
        return data
    data["accounts"][name] = next_record
    data["current"] = name
    save_accounts(data)
    return data


def get_current_account() -> Dict[str, Any]:
    data = load_accounts()
    current = data.get("current")
    if current is None:
        return {"name": None, "league_id": None, "username": None}
    info = data["accounts"].get(current, {})
    return {
        "name": current,
        "league_id": info.get("league_id"),
        "username": info.get("username"),
    }


def list_account_names() -> List[str]:
    data = load_accounts()
    return sorted(list(data.get("accounts", {}).keys()))
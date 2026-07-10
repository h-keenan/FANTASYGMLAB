from __future__ import annotations

from typing import Any

from modules import sleeper as sleeper_api
from modules import sleeper_leagues
from modules.player_identity import canonicalize_player_id, canonicalize_player_ids, normalize_player_id


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return default
    return number if number >= 0 else default


class SleeperPlatformAdapter:
    platform = "sleeper"

    def __init__(self, identity_map: dict[str, dict[str, str]] | None = None):
        self.identity_map = identity_map

    def canonicalize_player_id(self, raw_id: Any) -> str | None:
        return canonicalize_player_id(self.platform, raw_id, self.identity_map)

    def canonicalize_player_ids(self, raw_ids: list[Any] | tuple[Any, ...] | set[Any] | None) -> list[str]:
        return canonicalize_player_ids(self.platform, raw_ids, self.identity_map)

    def get_user_leagues(self, username: str) -> list[dict[str, Any]]:
        return sleeper_leagues.get_user_leagues(username) or []

    def get_league(self, league_id: str) -> dict[str, Any]:
        return sleeper_api.get_league(league_id) or {}

    def get_rosters(self, league_id: str) -> list[dict[str, Any]]:
        return [self.normalize_roster(roster) for roster in sleeper_api.get_rosters(league_id) or []]

    def get_users(self, league_id: str) -> list[dict[str, Any]]:
        return sleeper_api.get_users(league_id) or []

    def get_roster_player_ids(self, league_id: str, roster_id: int) -> list[str]:
        return self.canonicalize_player_ids(sleeper_api.get_roster_player_ids(league_id, roster_id))

    def get_transactions(self, league_id: str, round_num: int) -> list[dict[str, Any]]:
        return sleeper_api.get_transactions(league_id, round_num) or []

    def get_traded_picks(self, league_id: str) -> list[dict[str, Any]]:
        return sleeper_api.get_traded_picks(league_id) or []

    def get_league_drafts(self, league_id: str) -> list[dict[str, Any]]:
        return sleeper_api.get_league_drafts(league_id) or []

    def get_draft(self, draft_id: str) -> dict[str, Any]:
        return sleeper_api.get_draft(draft_id) or {}

    def get_draft_picks(self, draft_id: str) -> list[dict[str, Any]]:
        return [self.normalize_draft_pick(pick) for pick in sleeper_api.get_draft_picks(draft_id) or []]

    def normalize_league_settings(self, raw_league: dict[str, Any] | None) -> dict[str, Any]:
        raw = raw_league if isinstance(raw_league, dict) else {}
        return {
            "platform": self.platform,
            "league_id": str(raw.get("league_id") or raw.get("id") or ""),
            "name": str(raw.get("name") or ""),
            "season": raw.get("season"),
            "settings": raw.get("settings") if isinstance(raw.get("settings"), dict) else {},
            "scoring_settings": raw.get("scoring_settings") if isinstance(raw.get("scoring_settings"), dict) else {},
            "roster_positions": raw.get("roster_positions") if isinstance(raw.get("roster_positions"), list) else [],
            "raw": raw,
        }

    def normalize_roster(self, raw_roster: dict[str, Any] | None) -> dict[str, Any]:
        raw = dict(raw_roster or {})
        raw_players = raw.get("players") or []
        if not isinstance(raw_players, list):
            raw_players = []
        canonical_players = self.canonicalize_player_ids(raw_players)
        raw["platform"] = self.platform
        raw["platform_player_ids"] = [normalize_player_id(player_id) for player_id in raw_players if normalize_player_id(player_id)]
        raw["players"] = canonical_players
        raw["roster_id"] = _safe_int(raw.get("roster_id"), 0)
        raw["owner_id"] = str(raw.get("owner_id") or "")
        return raw

    def normalize_draft_pick(self, raw_pick: dict[str, Any] | None) -> dict[str, Any]:
        raw = dict(raw_pick or {})
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        raw_player_id = (
            raw.get("player_id")
            or raw.get("sleeper_id")
            or metadata.get("player_id")
            or metadata.get("picked_player_id")
            or metadata.get("drafted_player_id")
            or metadata.get("sleeper_id")
            or metadata.get("sleeper_player_id")
            or metadata.get("playerId")
        )
        canonical_id = self.canonicalize_player_id(raw_player_id)
        raw["platform"] = self.platform
        raw["platform_player_id"] = normalize_player_id(raw_player_id)
        raw["player_id"] = canonical_id or ""
        return raw


DEFAULT_SLEEPER_ADAPTER = SleeperPlatformAdapter()


def get_sleeper_adapter(
    identity_map: dict[str, dict[str, str]] | None = None,
) -> SleeperPlatformAdapter:
    return SleeperPlatformAdapter(identity_map) if identity_map is not None else DEFAULT_SLEEPER_ADAPTER

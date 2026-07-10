from __future__ import annotations

from typing import Any, Protocol


class FantasyPlatformAdapter(Protocol):
    platform: str

    def get_user_leagues(self, username: str) -> list[dict[str, Any]]:
        ...

    def get_league(self, league_id: str) -> dict[str, Any]:
        ...

    def get_rosters(self, league_id: str) -> list[dict[str, Any]]:
        ...

    def get_users(self, league_id: str) -> list[dict[str, Any]]:
        ...

    def get_roster_player_ids(self, league_id: str, roster_id: int) -> list[str]:
        ...

    def get_transactions(self, league_id: str, round_num: int) -> list[dict[str, Any]]:
        ...

    def get_traded_picks(self, league_id: str) -> list[dict[str, Any]]:
        ...

    def get_league_drafts(self, league_id: str) -> list[dict[str, Any]]:
        ...

    def get_draft(self, draft_id: str) -> dict[str, Any]:
        ...

    def get_draft_picks(self, draft_id: str) -> list[dict[str, Any]]:
        ...

    def normalize_league_settings(self, raw_league: dict[str, Any] | None) -> dict[str, Any]:
        ...

    def normalize_roster(self, raw_roster: dict[str, Any] | None) -> dict[str, Any]:
        ...

    def normalize_draft_pick(self, raw_pick: dict[str, Any] | None) -> dict[str, Any]:
        ...

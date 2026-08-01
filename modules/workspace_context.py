"""Immutable identity shared by every workspace during one Streamlit rerun."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _text(value: Any) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class WorkspaceIdentity:
    username: str
    league_id: str
    league_name: str
    roster_id: Any = None
    platform: str = "sleeper"

    @classmethod
    def from_mapping(
        cls,
        context: Mapping[str, Any] | None,
        *,
        fallback_league_name: str = "",
        platform: str = "sleeper",
    ) -> "WorkspaceIdentity":
        context = context or {}
        return cls(
            username=_text(context.get("username")),
            league_id=_text(context.get("selected_league_id")),
            league_name=_text(context.get("selected_league_name")) or _text(fallback_league_name),
            roster_id=context.get("my_roster_id"),
            platform=_text(platform).casefold() or "sleeper",
        )

    @property
    def has_active_league(self) -> bool:
        return bool(self.league_id)

    @property
    def has_roster(self) -> bool:
        return self.roster_id is not None


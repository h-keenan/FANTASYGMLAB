"""Identity for Sleeper team-defense (D/ST) lineup entries.

Sleeper keys a team defense by the NFL team abbreviation (player_id "SF"),
and those entries are not in data/players.db (no DEF rows), so a lineup row
for one has no name/position/team unless it is derived here. The label comes
from the repo's real NFL team table (modules.my_news.TEAM_NAME_ALIASES), never
invented: an id that is not a known NFL team abbreviation returns None.
"""

from __future__ import annotations

from typing import Any

from modules.my_news import TEAM_NAME_ALIASES


def team_defense_identity(player_id: Any) -> dict[str, str] | None:
    """{"name", "position", "team"} for a team-defense player_id, else None."""

    code = str(player_id or "").strip().upper()
    names = TEAM_NAME_ALIASES.get(code)
    if not names or len(names) < 2:
        return None
    return {"name": f"{names[1]} D/ST", "position": "DEF", "team": code}

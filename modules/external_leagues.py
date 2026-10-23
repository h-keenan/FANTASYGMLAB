"""One entry point for every non-Sleeper league platform FantasyDesk imports.

ESPN, Fleaflicker and MFL leagues are all saved under a prefixed key
(``espn:`` / ``fleaflicker:`` / ``mfl:`` + ``{id}:{season}``) in the existing
``saved_leagues.league_id`` column, and all load into the same Sleeper-shaped
snapshot. This module routes a key to its platform module so ``modules.sleeper``
and the API need one check instead of one per platform, and it owns the route
gating: every league-scoped route outside ``ESPN_SUPPORTED_LEAGUE_ROUTES`` is
refused with a platform-named "Not available" message.
"""

from __future__ import annotations

import re
from typing import Any

from modules import espn_leagues, fleaflicker_leagues, mfl_leagues
from modules.external_league_common import ExternalLeagueError

PLATFORM_LABELS = {
    espn_leagues.ESPN_PLATFORM: "ESPN",
    fleaflicker_leagues.FLEAFLICKER_PLATFORM: fleaflicker_leagues.FLEAFLICKER_LABEL,
    mfl_leagues.MFL_PLATFORM: "MFL",
}
PREFIXES = tuple(f"{platform}:" for platform in PLATFORM_LABELS)
NOT_AVAILABLE_REASON = espn_leagues.ESPN_NOT_AVAILABLE_REASON
# Platforms whose preview goes through preview_league (ESPN keeps its own endpoint).
IMPORT_PLATFORMS = (fleaflicker_leagues.FLEAFLICKER_PLATFORM, mfl_leagues.MFL_PLATFORM)

_MODULES = {
    fleaflicker_leagues.FLEAFLICKER_PLATFORM: fleaflicker_leagues,
    mfl_leagues.MFL_PLATFORM: mfl_leagues,
}


def platform_of(value: Any) -> str:
    """"espn" | "fleaflicker" | "mfl", or "" for anything else (Sleeper)."""

    if isinstance(value, str):
        for platform in PLATFORM_LABELS:
            if value.startswith(f"{platform}:"):
                return platform
    return ""


def is_external_league_key(value: Any) -> bool:
    return bool(platform_of(value))


def league_platform(value: Any) -> str:
    return platform_of(value) or "sleeper"


def label_for(value: Any) -> str:
    return PLATFORM_LABELS.get(platform_of(value), "")


def get_league_snapshot(league_key: str, *, refresh: bool = False) -> dict[str, Any] | None:
    platform = platform_of(league_key)
    if platform == espn_leagues.ESPN_PLATFORM:
        return espn_leagues.get_league_snapshot(league_key, refresh=refresh)
    module = _MODULES.get(platform)
    return module.get_league_snapshot(league_key, refresh=refresh) if module else None


def league_payload(league_key: str) -> dict[str, Any]:
    snapshot = get_league_snapshot(league_key)
    return dict(snapshot["league"]) if snapshot else {}


def rosters_payload(league_key: str) -> list[dict[str, Any]]:
    snapshot = get_league_snapshot(league_key)
    return [dict(roster) for roster in snapshot["rosters"]] if snapshot else []


def users_payload(league_key: str) -> list[dict[str, Any]]:
    snapshot = get_league_snapshot(league_key)
    return [dict(user) for user in snapshot["users"]] if snapshot else []


def mapping_blocks_import(snapshot: dict[str, Any]) -> bool:
    return espn_leagues.mapping_blocks_import(snapshot)


def preview_league(platform: str, league_id: Any, season: Any) -> dict[str, Any]:
    """Load a public Fleaflicker / MFL league and describe what importing gives.

    Everyday failures are ``ok: false`` with a ``reason``, like the ESPN preview."""

    module = _MODULES.get(platform)
    if module is None:
        return {"ok": False, "reason": "invalid_input", "message": "Unknown league platform."}
    league_key = module.build_league_key(league_id, season)
    if not league_key:
        return {"ok": False, "reason": "invalid_input", "message": module.ERROR_MESSAGES["invalid_input"]}
    try:
        snapshot = module.load_league_snapshot(league_key)
    except ExternalLeagueError as exc:
        return {"ok": False, "reason": exc.reason, "message": exc.message}
    module.store_snapshot(league_key, snapshot)
    return module.preview_payload(snapshot)


_LEAGUE_PATH_PATTERN = re.compile(r"^/v1/(?:leagues|portfolio/leagues)/((?:espn|fleaflicker|mfl):[^/]*)(/.*)?$")


def gated_league_path(path: str) -> bool:
    """True when `path` asks an imported (non-Sleeper) league for a feature it can't serve."""

    match = _LEAGUE_PATH_PATTERN.match(path or "")
    if not match or path.startswith("/v1/portfolio/"):
        return False
    return not espn_leagues.is_supported_league_route(match.group(2) or "")


def not_available_payload(path: str = "") -> dict[str, Any]:
    match = _LEAGUE_PATH_PATTERN.match(path or "")
    platform = platform_of(match.group(1)) if match else espn_leagues.ESPN_PLATFORM
    platform = platform or espn_leagues.ESPN_PLATFORM
    message = f"Not available for {PLATFORM_LABELS[platform]} leagues yet."
    return {
        "ok": False,
        "error": message,
        "detail": message,
        "reason": NOT_AVAILABLE_REASON,
        "platform": platform,
    }


def clear_snapshot_caches() -> None:
    espn_leagues.clear_snapshot_cache()
    for module in _MODULES.values():
        module.clear_snapshot_cache()

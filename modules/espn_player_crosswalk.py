"""ESPN player id -> Sleeper player id crosswalk for ESPN league import.

ESPN rosters carry ESPN's own player ids. FantasyDesk's canonical player id
is the Sleeper id, so an exact id crosswalk is the most reliable way to map
an ESPN player. Two public sources are merged:

* Sleeper's own ``players/nfl`` dump (``data/sleeper_players.json``) carries
  an ``espn_id`` for many players, but in practice mostly for older
  veterans: in the live league this was validated against (ESPN league
  42654852, season 2026) it covered 15 of 60 rostered players.
* DynastyProcess's public player id table (``db_playerids.csv`` from
  https://github.com/dynastyprocess/data, part of the nflverse ecosystem)
  maps ``espn_id`` to ``sleeper_id`` for current players, rookies included.
  It covered all 60 in that league.

An ESPN id that maps to more than one Sleeper id (a handful of duplicate
records exist in both sources) is left out, so the caller falls back to
name matching instead of guessing.

The DynastyProcess file is fetched at runtime and cached on disk, the same
posture as ``modules.nflverse_contracts``: a fetch failure falls back to
the cached copy, or to no rows, and never raises. Name matching in
``modules.platforms.espn`` still covers anything the crosswalk misses.
"""

from __future__ import annotations

import functools
import os
import time
from typing import Any, Mapping

import pandas as pd
import requests

from modules import performance
from modules.player_identity import normalize_player_id

DYNASTYPROCESS_PLAYER_IDS_URL = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"
DYNASTYPROCESS_PLAYER_IDS_CACHE_PATH = "data/dynastyprocess_playerids.csv"
DYNASTYPROCESS_CACHE_TTL_SECONDS = 24 * 60 * 60
_INPROCESS_TTL_SECONDS = 60 * 60
_MISSING_VALUES = {"", "na", "nan", "none", "null"}


def _clean_id(value: Any) -> str:
    text = normalize_player_id(value)
    return "" if text.casefold() in _MISSING_VALUES else text


def _cache_is_fresh(path: str, ttl: int) -> bool:
    try:
        return os.path.exists(path) and (time.time() - os.path.getmtime(path)) < ttl
    except Exception:
        return False


def _read_pairs(path: str) -> list[tuple[str, str]]:
    frame = pd.read_csv(path, usecols=["espn_id", "sleeper_id"], dtype=str, keep_default_na=False)
    return [(_clean_id(espn), _clean_id(sleeper)) for espn, sleeper in zip(frame["espn_id"], frame["sleeper_id"])]


def _load_dynastyprocess_pairs_uncached() -> list[tuple[str, str]]:
    path = DYNASTYPROCESS_PLAYER_IDS_CACHE_PATH
    if _cache_is_fresh(path, DYNASTYPROCESS_CACHE_TTL_SECONDS):
        try:
            return _read_pairs(path)
        except Exception:
            pass
    try:
        with performance.time_block("dynastyprocess_playerids_fetch", category="external"):
            response = requests.get(DYNASTYPROCESS_PLAYER_IDS_URL, timeout=20)
        response.raise_for_status()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(response.content)
        return _read_pairs(path)
    except Exception:
        if os.path.exists(path):
            try:
                return _read_pairs(path)
            except Exception:
                pass
        return []


@functools.lru_cache(maxsize=2)
def _load_dynastyprocess_pairs_cached(_bucket: int) -> tuple[tuple[str, str], ...]:
    return tuple(_load_dynastyprocess_pairs_uncached())


def load_dynastyprocess_pairs() -> list[tuple[str, str]]:
    """(espn_id, sleeper_id) rows from DynastyProcess. Never raises."""

    return list(_load_dynastyprocess_pairs_cached(int(time.time() // _INPROCESS_TTL_SECONDS)))


def clear_cache() -> None:
    _load_dynastyprocess_pairs_cached.cache_clear()


def sleeper_dump_pairs(sleeper_players: Mapping[str, Any] | None) -> list[tuple[str, str]]:
    """(espn_id, sleeper_id) rows from Sleeper's own players/nfl dump."""

    pairs: list[tuple[str, str]] = []
    for sleeper_id, record in (sleeper_players or {}).items():
        if isinstance(record, Mapping):
            pairs.append((_clean_id(record.get("espn_id")), _clean_id(record.get("player_id") or sleeper_id)))
    return pairs


def build_crosswalk(*pair_sources: list[tuple[str, str]]) -> dict[str, str]:
    """Merge (espn_id, sleeper_id) sources, dropping ids that disagree."""

    seen: dict[str, set[str]] = {}
    for pairs in pair_sources:
        for espn_id, sleeper_id in pairs or []:
            if espn_id and sleeper_id:
                seen.setdefault(espn_id, set()).add(sleeper_id)
    return {espn_id: next(iter(ids)) for espn_id, ids in seen.items() if len(ids) == 1}


def load_espn_crosswalk(sleeper_players: Mapping[str, Any] | None = None) -> dict[str, str]:
    """ESPN id -> Sleeper id from every available source. Never raises."""

    return build_crosswalk(sleeper_dump_pairs(sleeper_players), load_dynastyprocess_pairs())


def _read_pairs_for_column(path: str, column: str) -> list[tuple[str, str]]:
    frame = pd.read_csv(path, usecols=[column, "sleeper_id"], dtype=str, keep_default_na=False)
    return [(_clean_id(raw), _clean_id(sleeper)) for raw, sleeper in zip(frame[column], frame["sleeper_id"])]


def load_platform_crosswalk(column: str) -> dict[str, str]:
    """{platform id -> Sleeper id} for another platform in the same table.

    ``column`` is a DynastyProcess id column such as ``mfl_id`` or
    ``fleaflicker_id``. Same cache file, same refresh policy and the same
    rule as the ESPN crosswalk: an id that maps to several Sleeper ids is
    dropped so the caller falls back to name matching. Never raises."""

    load_dynastyprocess_pairs()  # makes sure the cached CSV exists / is fresh
    path = DYNASTYPROCESS_PLAYER_IDS_CACHE_PATH
    try:
        return build_crosswalk(_read_pairs_for_column(path, column))
    except Exception:
        return {}

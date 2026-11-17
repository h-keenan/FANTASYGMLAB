"""NFL draft round for a player, from the nflverse ``historical_contracts`` file the app already caches.

Sleeper's player payload carries no draft capital (``rankings.draft_capital_supported_by_available_data``), but
nflverse's contracts dataset (CC BY 4.0, see ``modules.nflverse_contracts``) has ``draft_round`` per player. This is
a deliberately small, read-only lookup for ONE use: anchoring the replacement-level week of a starter the projection
layer could not model (``modules.matchup_win_probability.REPLACEMENT_WEEK_BY_ROUND``).

* Disk cache only: it never fetches. If the contracts file is not on disk, every answer is ``None`` (unknown).
* A name that maps to more than one distinct (position, round) is ambiguous and answers ``None``.
* ``0`` means a contracts row exists with no draft round (undrafted); ``None`` means unknown. Brand-new rookies
  are often missing from the file, so ``None`` is the common answer and the position anchor applies.
"""

from __future__ import annotations

import os
import threading
from typing import Any

import pandas as pd

from modules import nflverse_contracts
from modules.player_names import normalize_player_name

_lock = threading.Lock()
_index: tuple[tuple[str, float], dict[tuple[str, str], int | None]] | None = None


def _build_index(path: str) -> dict[tuple[str, str], int | None]:
    frame = pd.read_csv(path, usecols=["player", "position", "draft_round"], low_memory=False)
    seen: dict[tuple[str, str], set[int]] = {}
    for name, position, draft_round in zip(frame["player"], frame["position"], frame["draft_round"]):
        key = (normalize_player_name(name), str(position or "").strip().upper())
        if not key[0]:
            continue
        value = 0 if pd.isna(draft_round) else int(draft_round)
        seen.setdefault(key, set()).add(value)
    return {key: (next(iter(values)) if len(values) == 1 else None) for key, values in seen.items()}


def _load_index() -> dict[tuple[str, str], int | None]:
    global _index
    path = nflverse_contracts.CONTRACTS_CACHE_PATH
    try:
        stamp = (path, os.path.getmtime(path))
    except OSError:
        return {}
    with _lock:
        if _index is not None and _index[0] == stamp:
            return _index[1]
    try:
        built = _build_index(path)
    except Exception:
        return {}
    with _lock:
        _index = (stamp, built)
    return built


def draft_round_for(name: Any, position: Any) -> int | None:
    """1-7 (the round he was drafted in), 0 (undrafted) or None (unknown / ambiguous / no cached file)."""

    key = (normalize_player_name(name), str(position or "").strip().upper())
    if not key[0] or not key[1]:
        return None
    return _load_index().get(key)


def clear_cache() -> None:
    global _index
    with _lock:
        _index = None

"""Local structured football freshness — patch Sleeper metadata, recompute locally.

Current disk-first path (Founder Beta startup):

1. ``app.ensure_players(allow_network_refresh=False)``
2. ``startup_cold_path.ensure_players_for_startup``
3. ``rankings.load_players`` → ``_cached_public_players`` keyed by
   ``public_player_source_fingerprint`` (sqlite + sleeper JSON + FantasyCalc CSV
   + season-stats mtime/size)
4. ``_load_players_uncached``
   - public-player snapshot hydrate, or
   - sqlite ``load_players`` / ``_load_players_without_snapshot``
5. Deferred ``players_refresh_flight`` may later rebuild via FantasyCalc/stats
6. ``prepared_player_frame`` applies league lens + tiers + canonical ranks

Sleeper JSON on disk can already be newer than sqlite while the deferred flight
is still queued. This module patches **structured Sleeper-owned fields** onto
the persisted frame (join by canonical ``player_id`` only) and recomputes
injury, opportunity, and composite score using existing rankings owners.

Network-heavy FantasyCalc / season stats / news stay on the deferred flight.
``apply_valuation_model`` is not called here because it fetches FantasyCalc.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Mapping

import pandas as pd

from modules import performance
from modules.rankings import (
    apply_local_structured_valuation,
    normalize_player_record,
)
from modules.sleeper import load_cached_players_disk

# Owners: ``rankings.normalize_player_record`` / Sleeper player object.
# Do not patch market, search_rank, production, snaps, age, or years_exp.
STRUCTURED_PATCH_FIELDS: tuple[str, ...] = (
    "team",
    "team_abbr",
    "status",
    "injury_status",
    "depth_chart_position",
    "depth_chart_order",
    "active",
    "news_updated",
)


def structured_state_fingerprint(df: pd.DataFrame) -> str:
    """Deterministic digest of evaluation-driving structured fields."""

    if df is None or df.empty or "player_id" not in df.columns:
        return hashlib.sha1(b"empty").hexdigest()
    cols = ["player_id"] + [column for column in STRUCTURED_PATCH_FIELDS if column in df.columns]
    work = df.loc[:, cols].copy()
    work["player_id"] = work["player_id"].fillna("").astype(str)
    for column in cols:
        if column == "player_id":
            continue
        work[column] = work[column].map(_fingerprint_cell)
    work = work.sort_values("player_id", kind="mergesort")
    payload = work.to_csv(index=False).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def _fingerprint_cell(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    text = str(value).strip()
    if text.lower() in {"nan", "none", "<na>"}:
        return ""
    return text


def _lookup_sleeper_record(
    sleeper_players: Mapping[str, Any],
    player_id: str,
) -> Mapping[str, Any] | None:
    if not sleeper_players or not player_id:
        return None
    raw = sleeper_players.get(player_id)
    if raw is None and player_id.isdigit():
        raw = sleeper_players.get(int(player_id))
    if not isinstance(raw, Mapping):
        return None
    return raw


def _assign_structured_value(work: pd.DataFrame, idx, column: str, value: object) -> None:
    if column not in work.columns:
        return
    dtype = work[column].dtype
    if value is None or (isinstance(value, float) and pd.isna(value)):
        if pd.api.types.is_object_dtype(dtype) or str(dtype) == "string":
            work.at[idx, column] = None
        return
    if pd.api.types.is_bool_dtype(dtype):
        work.at[idx, column] = bool(value)
        return
    if pd.api.types.is_integer_dtype(dtype):
        if isinstance(value, bool) or value in {True, False}:
            work.at[idx, column] = int(bool(value))
            return
        parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        if pd.isna(parsed):
            return
        work.at[idx, column] = int(parsed)
        return
    if pd.api.types.is_float_dtype(dtype):
        parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        if pd.isna(parsed):
            return
        work.at[idx, column] = float(parsed)
        return
    work.at[idx, column] = value


def _patch_structured_fields(
    frame: pd.DataFrame,
    sleeper_players: Mapping[str, Any],
) -> pd.DataFrame:
    work = frame.copy()
    if "player_id" not in work.columns or not sleeper_players:
        return work
    ids = work["player_id"].fillna("").astype(str)
    for idx, player_id in ids.items():
        raw = _lookup_sleeper_record(sleeper_players, player_id)
        if raw is None:
            continue
        record = normalize_player_record(player_id, dict(raw))
        for column in STRUCTURED_PATCH_FIELDS:
            if column in record:
                _assign_structured_value(work, idx, column, record[column])
    return work


def refresh_structured_player_state(
    persisted_frame: pd.DataFrame,
    latest_sleeper_metadata: Mapping[str, Any] | None,
    *,
    source_mtime: int = 0,
) -> pd.DataFrame:
    """Patch Sleeper structured metadata and recompute local football state.

    Join is strictly ``player_id``. Unmatched rows are preserved. The input
    frame is not mutated. Market and production columns are left in place.
    """

    started = time.perf_counter()
    if persisted_frame is None or persisted_frame.empty:
        return persisted_frame

    before = structured_state_fingerprint(persisted_frame)
    patched = _patch_structured_fields(persisted_frame, latest_sleeper_metadata or {})
    after = structured_state_fingerprint(patched)
    recomputed = False
    if after != before:
        required = {"position", "market_score"}
        if required.issubset(set(patched.columns)):
            patched = apply_local_structured_valuation(patched)
            recomputed = True
    patched.attrs["structured_state_fingerprint"] = after
    patched.attrs["structured_refresh_recomputed"] = recomputed
    patched.attrs["structured_source_mtime"] = int(source_mtime or 0)
    performance.record_timing(
        "structured_player_refresh",
        (time.perf_counter() - started) * 1000,
        category="data",
        result_size=int(len(patched)),
    )
    return patched


def refresh_structured_player_state_from_disk(
    persisted_frame: pd.DataFrame,
    *,
    path: str | None = None,
) -> pd.DataFrame:
    """Disk-only structured refresh. Never calls ``requests`` / ``get_players``."""

    players, mtime_ns = load_cached_players_disk(path)
    return refresh_structured_player_state(
        persisted_frame,
        players,
        source_mtime=mtime_ns,
    )

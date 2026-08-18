"""Versioned disk snapshot for deterministic public-player hydration only."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Iterable, Sequence

import pandas as pd


PUBLIC_PLAYER_SNAPSHOT_SCHEMA_VERSION = 1
FORBIDDEN_SNAPSHOT_COLUMNS = frozenset(
    {
        "value",
        "search_rank",
        "fantasycalc_value",
        "fantasycalc_score",
        "market_score",
        "valuation_blend",
        "age_multiplier",
        "age_curve_score",
        "scarcity_score",
        "role_score",
        "score",
        "age_penalty",
        "dynasty_score",
        "value_score",
        "news_factor",
    }
)
FORBIDDEN_SNAPSHOT_OUTPUT_COLUMNS = frozenset(
    {
        "opportunity_signal_confidence",
        "opportunity_fallback",
        "factor_market",
        "factor_age",
        "factor_production",
        "factor_scarcity",
        "factor_role",
        "factor_opportunity",
    }
)


@dataclass(frozen=True)
class PublicPlayerSnapshot:
    frame: pd.DataFrame
    output_columns: tuple[str, ...]
    status: str


def snapshot_paths(db_path: str | Path) -> tuple[Path, Path]:
    source = Path(db_path)
    stem = source.with_suffix("")
    return (
        Path(f"{stem}.public-player-snapshot.pkl"),
        Path(f"{stem}.public-player-snapshot.json"),
    )


def source_fingerprint_digest(source_fingerprint: object) -> str:
    payload = repr(source_fingerprint).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _snapshot_columns_allowed(columns: Iterable[str]) -> bool:
    normalized = {str(column) for column in columns}
    return not (
        normalized.intersection(FORBIDDEN_SNAPSHOT_COLUMNS)
        or any(column.startswith("trust_") for column in normalized)
    )


def build_public_player_snapshot(
    hydrated: pd.DataFrame,
    *,
    hydration_columns: Sequence[str],
) -> pd.DataFrame:
    if hydrated is None or hydrated.empty or "player_id" not in hydrated.columns:
        raise ValueError("public-player hydration requires a non-empty player_id frame")
    columns = tuple(
        dict.fromkeys(
            ["player_id", *(str(column) for column in hydration_columns)]
        )
    )
    if not _snapshot_columns_allowed(columns):
        raise ValueError("snapshot contains valuation, ranking, or Trust columns")
    missing = [column for column in columns if column not in hydrated.columns]
    if missing:
        raise ValueError(f"snapshot hydration columns missing: {missing}")
    snapshot = hydrated.loc[:, list(columns)].copy(deep=True).reset_index(drop=True)
    player_ids = snapshot["player_id"].fillna("").astype(str)
    if player_ids.eq("").any() or player_ids.duplicated().any():
        raise ValueError("snapshot player_id values must be non-empty and unique")
    return snapshot


def invalidate_public_player_snapshot(db_path: str | Path) -> None:
    for path in snapshot_paths(db_path):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def save_public_player_snapshot(
    db_path: str | Path,
    snapshot: pd.DataFrame,
    *,
    source_fingerprint: object,
    output_columns: Sequence[str],
) -> dict[str, int]:
    if snapshot is None or snapshot.empty or not _snapshot_columns_allowed(snapshot.columns):
        raise ValueError("invalid deterministic public-player snapshot")
    data_path, metadata_path = snapshot_paths(db_path)
    data_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "schema_version": PUBLIC_PLAYER_SNAPSHOT_SCHEMA_VERSION,
        "source_fingerprint": source_fingerprint_digest(source_fingerprint),
        "columns": [str(column) for column in snapshot.columns],
        "dtypes": {str(column): str(dtype) for column, dtype in snapshot.dtypes.items()},
        "output_columns": [str(column) for column in output_columns],
        "row_count": int(len(snapshot)),
    }
    data_temp = None
    metadata_temp = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=data_path.parent,
            prefix=f"{data_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            data_temp = Path(handle.name)
        snapshot.to_pickle(data_temp)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=metadata_path.parent,
            prefix=f"{metadata_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            metadata_temp = Path(handle.name)
            json.dump(metadata, handle, sort_keys=True, separators=(",", ":"))
        os.replace(data_temp, data_path)
        os.replace(metadata_temp, metadata_path)
    finally:
        for temporary in (data_temp, metadata_temp):
            if temporary is not None and temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass
    return {
        "row_count": int(len(snapshot)),
        "memory_bytes": int(snapshot.memory_usage(index=True, deep=True).sum()),
        "snapshot_bytes": int(data_path.stat().st_size + metadata_path.stat().st_size),
    }


def load_public_player_snapshot(
    db_path: str | Path,
    *,
    source_fingerprint: object,
) -> PublicPlayerSnapshot | None:
    data_path, metadata_path = snapshot_paths(db_path)
    if not data_path.is_file() or not metadata_path.is_file():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if int(metadata.get("schema_version") or 0) != PUBLIC_PLAYER_SNAPSHOT_SCHEMA_VERSION:
            invalidate_public_player_snapshot(db_path)
            return None
        if metadata.get("source_fingerprint") != source_fingerprint_digest(source_fingerprint):
            invalidate_public_player_snapshot(db_path)
            return None
        columns = tuple(str(column) for column in metadata.get("columns") or ())
        if not columns or not _snapshot_columns_allowed(columns):
            invalidate_public_player_snapshot(db_path)
            return None
        frame = pd.read_pickle(data_path)
        if not isinstance(frame, pd.DataFrame):
            raise TypeError("snapshot payload is not a DataFrame")
        if tuple(str(column) for column in frame.columns) != columns:
            raise ValueError("snapshot columns do not match metadata")
        if int(metadata.get("row_count") or -1) != len(frame):
            raise ValueError("snapshot row count does not match metadata")
        expected_dtypes = {
            str(column): str(dtype)
            for column, dtype in (metadata.get("dtypes") or {}).items()
        }
        actual_dtypes = {str(column): str(dtype) for column, dtype in frame.dtypes.items()}
        if expected_dtypes != actual_dtypes:
            raise ValueError("snapshot dtypes do not match metadata")
        player_ids = frame["player_id"].fillna("").astype(str)
        if player_ids.eq("").any() or player_ids.duplicated().any():
            raise ValueError("snapshot player identities are invalid")
        output_columns = tuple(
            str(column) for column in metadata.get("output_columns") or ()
        )
        if set(output_columns).intersection(FORBIDDEN_SNAPSHOT_OUTPUT_COLUMNS):
            invalidate_public_player_snapshot(db_path)
            return None
        return PublicPlayerSnapshot(
            frame=frame.copy(deep=True),
            output_columns=output_columns,
            status="hit",
        )
    except Exception:
        invalidate_public_player_snapshot(db_path)
        return None

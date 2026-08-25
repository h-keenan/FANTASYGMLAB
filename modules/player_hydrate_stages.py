"""Exclusive named stages for the public-player hydrate pipeline.

Does not change player truth. Records wall time for disk, decode, normalize,
eligibility, structured refresh, Streamlit cache hashing, and process reuse so a
cold ``player_hydrate`` miss is attributable to a real owner.
"""

from __future__ import annotations

from contextlib import contextmanager
import time
from typing import Any, Iterator


STAGE_KEY = "_player_hydrate_stages"
_PROCESS_STAGES: list[dict[str, Any]] = []
_LAST_STATUS = ""
_LAST_LOAD_PATH = ""
_LAST_ELAPSED_MS = 0.0
_LAST_FINGERPRINT_PREFIX = ""
_LAST_PROCESS_STORE_BEFORE = False
_LAST_WAIT_MS = 0.0
_LAST_BUILDER_MS = 0.0


def reset() -> None:
    _PROCESS_STAGES.clear()
    global _LAST_STATUS, _LAST_LOAD_PATH, _LAST_ELAPSED_MS
    global _LAST_FINGERPRINT_PREFIX, _LAST_PROCESS_STORE_BEFORE, _LAST_WAIT_MS, _LAST_BUILDER_MS
    _LAST_STATUS = ""
    _LAST_LOAD_PATH = ""
    _LAST_ELAPSED_MS = 0.0
    _LAST_FINGERPRINT_PREFIX = ""
    _LAST_PROCESS_STORE_BEFORE = False
    _LAST_WAIT_MS = 0.0
    _LAST_BUILDER_MS = 0.0


def recorded() -> list[dict[str, Any]]:
    return list(_PROCESS_STAGES)


def last_status() -> str:
    return str(_LAST_STATUS or "")


def last_load_path() -> str:
    return str(_LAST_LOAD_PATH or "")


def last_elapsed_ms() -> float:
    return float(_LAST_ELAPSED_MS or 0.0)


def last_fingerprint_prefix() -> str:
    return str(_LAST_FINGERPRINT_PREFIX or "")


def last_process_store_before() -> bool:
    return bool(_LAST_PROCESS_STORE_BEFORE)


def last_wait_ms() -> float:
    return float(_LAST_WAIT_MS or 0.0)


def last_builder_ms() -> float:
    return float(_LAST_BUILDER_MS or 0.0)


def hydrate_detail() -> dict[str, Any]:
    return {
        "fingerprint_prefix": last_fingerprint_prefix(),
        "process_store_before": last_process_store_before(),
        "wait_ms": round(last_wait_ms(), 1),
        "builder_ms": round(last_builder_ms(), 1),
        "load_path": last_load_path(),
    }


def note_outcome(
    *,
    cache_status: str,
    load_path: str = "",
    elapsed_ms: float = 0.0,
    fingerprint_prefix: str = "",
    process_store_before: bool = False,
    wait_ms: float = 0.0,
    builder_ms: float = 0.0,
) -> None:
    global _LAST_STATUS, _LAST_LOAD_PATH, _LAST_ELAPSED_MS
    global _LAST_FINGERPRINT_PREFIX, _LAST_PROCESS_STORE_BEFORE, _LAST_WAIT_MS, _LAST_BUILDER_MS
    _LAST_STATUS = str(cache_status or "")[:32]
    _LAST_LOAD_PATH = str(load_path or "")[:48]
    _LAST_ELAPSED_MS = float(elapsed_ms or 0.0)
    _LAST_FINGERPRINT_PREFIX = str(fingerprint_prefix or "")[:32]
    _LAST_PROCESS_STORE_BEFORE = bool(process_store_before)
    _LAST_WAIT_MS = float(wait_ms or 0.0)
    _LAST_BUILDER_MS = float(builder_ms or 0.0)


def begin_hydrate() -> None:
    _PROCESS_STAGES.clear()


@contextmanager
def stage(name: str, *, kind: str = "cpu") -> Iterator[dict[str, str]]:
    meta: dict[str, str] = {"cache_status": ""}
    started = time.perf_counter()
    try:
        yield meta
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000
        row = {
            "name": str(name or "stage")[:64],
            "elapsed_ms": round(max(0.0, elapsed_ms), 1),
            "cache_status": str(meta.get("cache_status") or "")[:24],
            "kind": str(kind or "cpu")[:24],
        }
        _PROCESS_STAGES.append(row)
        try:
            from modules import hot_path_profile
            from modules import dashboard_waterfall

            hot_path_profile.record(
                f"player_hydrate.{row['name']}",
                float(row["elapsed_ms"]),
                cache_status=row["cache_status"],
                kind=row["kind"],
            )
            dashboard_waterfall.record(
                f"player_hydrate.{row['name']}",
                float(row["elapsed_ms"]),
                cache_status=row["cache_status"],
            )
        except Exception:
            pass

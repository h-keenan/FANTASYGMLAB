"""Persistence for sim worlds, on the sim_* tables only.

Pure: talks to a ``SimBackend`` (Supabase REST in production, in-memory in
tests). Every call is scoped by user_id, and any backend failure, including the
tables not existing yet (docs/supabase_sim.sql is applied by hand), surfaces as
``SimStoreError`` so the API can answer "unavailable" instead of crashing.
"""

from __future__ import annotations

import copy
import functools
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from modules.sim.types import LeagueSnapshot, Strategy
from modules.sim.version import ENGINE_VERSION

WORLDS = "sim_worlds"
SNAPSHOTS = "sim_snapshots"
RESULTS = "sim_results"
MAX_WORLDS_PER_USER = 10


def classify_store_error(message: str) -> str:
    """A short diagnostic code for a backend error string (no secrets, no row data).

    Backends embed ``(<http status>)`` and ``pg=<SQLSTATE>`` in their messages."""

    import re

    text = str(message or "")
    pg = re.search(r"pg=(\w+)", text)
    status = re.search(r"\((\d{3})\)", text)
    code = int(status.group(1)) if status else 0
    if pg and pg.group(1) in ("23514", "22P02", "22003", "23502", "22P05"):
        return "constraint"  # CHECK / type / NOT NULL rejection: our payload, not an outage
    if code in (401, 403) or (pg and pg.group(1) == "42501"):
        return "rls"
    if code == 413:
        return "payload_too_large"
    if code in (408, 504) or (pg and pg.group(1) == "57014") or "timed out" in text.lower():
        return "timeout"
    if code >= 500:
        return "http_5xx"
    if "reach" in text.lower():
        return "unreachable"
    if "not valid json" in text.lower() or "serializ" in text.lower():
        return "bad_payload"
    if "gap" in text or "inconsistent" in text:
        return "log_inconsistent"
    if code >= 400:
        return "http_4xx"
    return "store_error"


TRANSIENT_CODES = frozenset({"timeout", "http_5xx", "unreachable"})


class SimStoreError(Exception):
    """Storage is unreachable or the sim_* tables are not set up.

    ``code`` is a coarse diagnostic (``classify_store_error``); ``str(exc)`` keeps
    the backend message (SQLSTATE and HTTP status, never secrets)."""

    def __init__(self, message: str = "", code: str | None = None) -> None:
        super().__init__(message)
        self.code = code or classify_store_error(message)


class SimBackend(Protocol):
    def select(
        self, table: str, *, user_id: str, filters: Mapping[str, str] | None = None,
        columns: str = "*", order: str = "", limit: int = 0,
    ) -> tuple[list[dict[str, Any]], str]: ...

    def upsert(self, table: str, row: Mapping[str, Any], *, on_conflict: str) -> tuple[bool, str]: ...

    def update(
        self, table: str, *, user_id: str, filters: Mapping[str, str], values: Mapping[str, Any]
    ) -> tuple[bool, str]: ...

    def delete(self, table: str, *, user_id: str, filters: Mapping[str, str]) -> tuple[bool, str]: ...

    def insert_many(self, table: str, rows: list[Mapping[str, Any]]) -> tuple[bool, str]:
        """Insert-only (never overwrites). A duplicate primary key fails the whole
        batch with the error string ``CONFLICT``: the optimistic-concurrency guard
        for the append-only game event log."""
        ...


# Filter values are equality by default. A value like ``"gte.5"`` is a range
# comparison (PostgREST syntax); used by the game event log (``seq >= n``).
FILTER_OPS = ("gte.", "gt.", "lte.", "lt.")
CONFLICT = "CONFLICT"


def parse_filter(value: Any) -> tuple[str, str]:
    text = str(value)
    for op in FILTER_OPS:
        if text.startswith(op):
            return op[:-1], text[len(op):]
    return "eq", text


def _matches(row_value: Any, value: Any) -> bool:
    op, raw = parse_filter(value)
    if op == "eq":
        return str(row_value) == raw
    try:
        left, right = float(row_value), float(raw)
    except (TypeError, ValueError):
        return False
    return {"gte": left >= right, "gt": left > right, "lte": left <= right, "lt": left < right}[op]


def _locked(fn):
    """Serialize a backend call: the game store issues independent calls in parallel threads."""

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return fn(self, *args, **kwargs)

    return wrapper


class InMemoryBackend:
    """Test/dev backend with the same contract as the Supabase one."""

    def __init__(self, *, fail: bool = False) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.fail = fail
        self._lock = threading.RLock()

    @_locked
    def select(self, table, *, user_id, filters=None, columns="*", order="", limit=0):
        if self.fail:
            return [], "Supabase tables are not set up yet."
        rows = [r for r in self.tables.get(table, []) if r.get("user_id") == user_id]
        for key, value in (filters or {}).items():
            rows = [r for r in rows if _matches(r.get(key), value)]
        if order:
            name, _, direction = order.partition(".")
            numeric = all(isinstance(r.get(name), (int, float)) for r in rows)
            rows.sort(key=lambda r: r.get(name) if numeric else str(r.get(name)), reverse=direction == "desc")
        if limit:
            rows = rows[:limit]
        if columns != "*":
            keep = {c.strip() for c in columns.split(",")}
            rows = [{k: v for k, v in r.items() if k in keep} for r in rows]
        return copy.deepcopy(rows), ""

    @_locked
    def upsert(self, table, row, *, on_conflict):
        if self.fail:
            return False, "Supabase tables are not set up yet."
        rows = self.tables.setdefault(table, [])
        row = copy.deepcopy(dict(row))
        cols = on_conflict.split(",")  # composite keys: "game_id,week"
        for i, existing in enumerate(rows):
            if all(existing.get(c) == row.get(c) for c in cols):
                rows[i] = {**existing, **row}
                return True, ""
        rows.append(row)
        return True, ""

    @_locked
    def update(self, table, *, user_id, filters, values):
        if self.fail:
            return False, "Supabase tables are not set up yet."
        for row in self.tables.get(table, []):
            if row.get("user_id") == user_id and all(_matches(row.get(k), v) for k, v in filters.items()):
                row.update(copy.deepcopy(dict(values)))
        return True, ""

    @_locked
    def delete(self, table, *, user_id, filters):
        if self.fail:
            return False, "Supabase tables are not set up yet."
        rows = self.tables.get(table, [])
        self.tables[table] = [
            r for r in rows
            if not (r.get("user_id") == user_id and all(_matches(r.get(k), v) for k, v in filters.items()))
        ]
        return True, ""

    # Primary key of the tables insert_many is used on.
    _PKS = {
        "sim_events": ("game_id", "seq"), "sim_week_checkpoints": ("game_id", "week"),
        "sim_games": ("id",),
    }

    @_locked
    def insert_many(self, table, rows):
        if self.fail:
            return False, "Supabase tables are not set up yet."
        pk = self._PKS.get(table, ("id",))
        existing = self.tables.setdefault(table, [])
        taken = {tuple(r.get(k) for k in pk) for r in existing}
        fresh = []
        for row in rows:
            key = tuple(row.get(k) for k in pk)
            if key in taken:
                return False, CONFLICT
            taken.add(key)
            fresh.append(copy.deepcopy(dict(row)))
        existing.extend(fresh)
        return True, ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SimStore:
    def __init__(self, backend: SimBackend) -> None:
        self.backend = backend

    def _select(self, table: str, user_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        rows, error = self.backend.select(table, user_id=user_id, **kwargs)
        if error:
            raise SimStoreError(error)
        return rows

    def _upsert(self, table: str, row: Mapping[str, Any], on_conflict: str) -> None:
        ok, error = self.backend.upsert(table, row, on_conflict=on_conflict)
        if not ok:
            raise SimStoreError(error or "write failed")

    def _update(self, table: str, user_id: str, filters: Mapping[str, str], values: Mapping[str, Any]) -> None:
        ok, error = self.backend.update(table, user_id=user_id, filters=filters, values=values)
        if not ok:
            raise SimStoreError(error or "update failed")

    def _delete(self, table: str, user_id: str, filters: Mapping[str, str]) -> None:
        ok, error = self.backend.delete(table, user_id=user_id, filters=filters)
        if not ok:
            raise SimStoreError(error or "delete failed")

    # ---------------------------------------------------------------- worlds

    def count_worlds(self, user_id: str) -> int:
        return len(self._select(WORLDS, user_id, columns="id"))

    def create_world(
        self, user_id: str, *, league_id: str, snapshot: LeagueSnapshot, strategy: Strategy, seed: int
    ) -> dict[str, Any]:
        world_id = str(uuid.uuid4())
        now = _now()
        world = {
            "id": world_id, "user_id": user_id, "source_league_id": league_id,
            "league_name": snapshot.settings.league_name, "mode": snapshot.mode, "seed": seed,
            "engine_version": ENGINE_VERSION, "status": "ready", "strategy": strategy.to_dict(),
            "grade_letter": None, "created_at": now, "updated_at": now,
        }
        self._upsert(WORLDS, world, "id")
        try:
            self._upsert(SNAPSHOTS, {"world_id": world_id, "user_id": user_id, "payload": snapshot.to_dict()}, "world_id")
        except SimStoreError:
            self._delete(WORLDS, user_id, {"id": world_id})
            raise
        return world

    def list_worlds(self, user_id: str) -> list[dict[str, Any]]:
        return self._select(WORLDS, user_id, order="created_at.desc", limit=MAX_WORLDS_PER_USER * 2)

    def get_world(self, user_id: str, world_id: str) -> dict[str, Any] | None:
        rows = self._select(WORLDS, user_id, filters={"id": world_id}, limit=1)
        return rows[0] if rows else None

    def get_snapshot(self, user_id: str, world_id: str) -> LeagueSnapshot | None:
        rows = self._select(SNAPSHOTS, user_id, filters={"world_id": world_id}, limit=1)
        return LeagueSnapshot.from_dict(rows[0]["payload"]) if rows else None

    def set_strategy(self, user_id: str, world_id: str, strategy: Strategy) -> None:
        self._update(
            WORLDS, user_id, {"id": world_id},
            {"strategy": strategy.to_dict(), "status": "ready", "grade_letter": None, "updated_at": _now()},
        )
        self._delete(RESULTS, user_id, {"world_id": world_id})

    def save_result(self, user_id: str, world_id: str, result: Mapping[str, Any]) -> None:
        grade = (result.get("grade") or {}).get("letter")
        self._upsert(RESULTS, {"world_id": world_id, "user_id": user_id, "payload": dict(result)}, "world_id")
        self._update(
            WORLDS, user_id, {"id": world_id},
            {"status": "simulated", "grade_letter": grade, "updated_at": _now()},
        )

    def get_result(self, user_id: str, world_id: str) -> dict[str, Any] | None:
        rows = self._select(RESULTS, user_id, filters={"world_id": world_id}, limit=1)
        return rows[0]["payload"] if rows else None

    def delete_world(self, user_id: str, world_id: str) -> None:
        # Children first: correct even where the cascade is not in place.
        self._delete(RESULTS, user_id, {"world_id": world_id})
        self._delete(SNAPSHOTS, user_id, {"world_id": world_id})
        self._delete(WORLDS, user_id, {"id": world_id})


def public_world(row: Mapping[str, Any]) -> dict[str, Any]:
    """The world fields clients see (never user_id)."""

    keys = (
        "id", "source_league_id", "league_name", "mode", "seed", "engine_version", "status",
        "strategy", "grade_letter", "created_at", "updated_at",
    )
    return {k: row.get(k) for k in keys}

"""Persistence for GM-game saves on the sim_* tables only.

Follows ``store.py``'s conventions: it talks to a ``SimBackend`` (Supabase REST
in production, in-memory in tests), every call is scoped by ``user_id``, and any
backend failure, including the tables not existing yet
(``docs/supabase_sim_game.sql`` is applied by hand), surfaces as
``SimStoreError``. A lost write race on the event log surfaces as
``GameConflict``.

Tables: ``sim_games`` (the save: settings + frozen snapshot), ``sim_events``
(append-only source of truth, primary key ``(game_id, seq)``) and
``sim_week_checkpoints`` (rebuildable cache of the folded state).
"""

from __future__ import annotations

import threading
import uuid
from collections import OrderedDict
from typing import Any, Mapping, Sequence

from modules.sim.game_state import GameState, fold
from modules.sim.game_types import GAME_ENGINE_VERSION, GameSnapshot
from modules.sim.store import CONFLICT, SimBackend, SimStoreError, _now

GAMES = "sim_games"
EVENTS = "sim_events"
CHECKPOINTS = "sim_week_checkpoints"
GAME_TABLES = (GAMES, EVENTS, CHECKPOINTS)
LIST_COLUMNS = (
    "id,seed,engine_version,scoring_model,settings,status,current_week,difficulty,grade_letter,"
    "event_count,created_at,updated_at"
)
CHECKPOINTS_KEPT = 2
EVENT_PAGE = 1000
_SNAPSHOT_CACHE_SIZE = 24


class GameConflict(Exception):
    """Another write appended the same event sequence first. Reload and retry."""


class _SnapshotCache:
    """Frozen snapshots never change, so cache them per process. Access control
    stays with the caller: the row lookup (scoped by user) comes first."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: OrderedDict[str, GameSnapshot] = OrderedDict()

    def get(self, key: str) -> GameSnapshot | None:
        with self._lock:
            snap = self._items.get(key)
            if snap is not None:
                self._items.move_to_end(key)
            return snap

    def put(self, key: str, snap: GameSnapshot) -> None:
        with self._lock:
            self._items[key] = snap
            while len(self._items) > _SNAPSHOT_CACHE_SIZE:
                self._items.popitem(last=False)

    def drop(self, key: str) -> None:
        with self._lock:
            self._items.pop(key, None)


SNAPSHOTS = _SnapshotCache()


class GameStore:
    def __init__(self, backend: SimBackend) -> None:
        self.backend = backend

    # ----------------------------------------------------------- primitives

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

    # ---------------------------------------------------------------- games

    def count_games(self, user_id: str) -> int:
        return len(self._select(GAMES, user_id, columns="id"))

    def list_games(self, user_id: str) -> list[dict[str, Any]]:
        return self._select(GAMES, user_id, columns=LIST_COLUMNS, order="created_at.desc", limit=20)

    def get_game(self, user_id: str, game_id: str) -> dict[str, Any] | None:
        """The save's row without its (large) snapshot and result."""

        rows = self._select(GAMES, user_id, filters={"id": game_id}, columns=LIST_COLUMNS, limit=1)
        return rows[0] if rows else None

    def create_game(
        self, user_id: str, *, snapshot: GameSnapshot, seed: int, status: str = "drafting"
    ) -> dict[str, Any]:
        game_id = str(uuid.uuid4())
        now = _now()
        settings = snapshot.settings
        row = {
            "id": game_id, "user_id": user_id, "seed": seed, "engine_version": GAME_ENGINE_VERSION,
            "scoring_model": snapshot.scoring_model, "settings": settings.to_dict(), "status": status,
            "current_week": 0, "difficulty": settings.difficulty, "snapshot": snapshot.to_dict(),
            "event_count": 0, "created_at": now, "updated_at": now,
        }
        self._upsert(GAMES, row, "id")
        SNAPSHOTS.put(game_id, snapshot)
        return {k: v for k, v in row.items() if k not in ("snapshot", "user_id")}

    def get_snapshot(self, user_id: str, game_id: str) -> GameSnapshot | None:
        cached = SNAPSHOTS.get(game_id)
        if cached is not None:
            return cached
        rows = self._select(GAMES, user_id, filters={"id": game_id}, columns="snapshot", limit=1)
        if not rows:
            return None
        snap = GameSnapshot.from_dict(rows[0]["snapshot"])
        SNAPSHOTS.put(game_id, snap)
        return snap

    def get_result(self, user_id: str, game_id: str) -> dict[str, Any] | None:
        rows = self._select(GAMES, user_id, filters={"id": game_id}, columns="result", limit=1)
        return rows[0].get("result") if rows else None

    def save_result(self, user_id: str, game_id: str, result: Mapping[str, Any], grade_letter: str | None) -> None:
        self._update(GAMES, user_id, {"id": game_id}, {
            "result": dict(result), "grade_letter": grade_letter, "updated_at": _now(),
        })

    def touch(self, user_id: str, game_id: str, *, status: str, week: int, event_count: int) -> None:
        """Denormalized list-view fields; events remain the source of truth."""

        self._update(GAMES, user_id, {"id": game_id}, {
            "status": status, "current_week": week, "event_count": event_count, "updated_at": _now(),
        })

    def delete_game(self, user_id: str, game_id: str) -> None:
        # Children first: correct even where the cascade is not in place.
        self._delete(EVENTS, user_id, {"game_id": game_id})
        self._delete(CHECKPOINTS, user_id, {"game_id": game_id})
        self._delete(GAMES, user_id, {"id": game_id})
        SNAPSHOTS.drop(game_id)

    # --------------------------------------------------------------- events

    def append_events(self, user_id: str, game_id: str, events: Sequence[Mapping[str, Any]]) -> None:
        """Insert-only. A duplicate ``(game_id, seq)`` means another request got
        there first: ``GameConflict``."""

        if not events:
            return
        rows = [
            {
                "game_id": game_id, "user_id": user_id, "seq": int(e["seq"]), "week": int(e["week"]),
                "actor": str(e["actor"]), "type": str(e["type"]), "payload": e["payload"],
            }
            for e in events
        ]
        ok, error = self.backend.insert_many(EVENTS, rows)
        if not ok:
            if error == CONFLICT:
                raise GameConflict()
            raise SimStoreError(error or "event write failed")

    def load_events(self, user_id: str, game_id: str, from_seq: int = 0) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        cursor = from_seq
        while True:
            rows = self._select(
                EVENTS, user_id, filters={"game_id": game_id, "seq": f"gte.{cursor}"},
                columns="seq,week,actor,type,payload", order="seq.asc", limit=EVENT_PAGE,
            )
            out.extend({k: r[k] for k in ("seq", "week", "actor", "type", "payload")} for r in rows)
            if len(rows) < EVENT_PAGE:
                return out
            cursor = int(rows[-1]["seq"]) + 1

    def delete_events_from(self, user_id: str, game_id: str, seq: int) -> None:
        self._delete(EVENTS, user_id, {"game_id": game_id, "seq": f"gte.{seq}"})

    # ---------------------------------------------------------- checkpoints

    def save_checkpoint(self, user_id: str, game_id: str, state: GameState, week: int) -> None:
        self._upsert(CHECKPOINTS, {
            "game_id": game_id, "user_id": user_id, "week": week, "event_seq": state.seq,
            "state": state.to_dict(),
        }, "game_id,week")
        rows = self._select(CHECKPOINTS, user_id, filters={"game_id": game_id}, columns="week", order="week.desc")
        for row in rows[CHECKPOINTS_KEPT:]:
            self._delete(CHECKPOINTS, user_id, {"game_id": game_id, "week": str(row["week"])})

    def latest_checkpoint(self, user_id: str, game_id: str) -> dict[str, Any] | None:
        rows = self._select(CHECKPOINTS, user_id, filters={"game_id": game_id}, order="week.desc", limit=1)
        return rows[0] if rows else None

    def load_state(
        self, user_id: str, game_id: str, snapshot: GameSnapshot, *, use_checkpoint: bool = True
    ) -> GameState:
        """Latest checkpoint plus the events after it (or every event from the
        start when ``use_checkpoint`` is off: the replay)."""

        cp = self.latest_checkpoint(user_id, game_id) if use_checkpoint else None
        if cp is not None:
            state = GameState.from_dict(snapshot, cp["state"])
            from_seq = int(cp["event_seq"])
            if state.seq != from_seq:
                raise SimStoreError("checkpoint is inconsistent")
        else:
            state, from_seq = GameState(snapshot), 0
        events = self.load_events(user_id, game_id, from_seq)
        if events and int(events[0]["seq"]) != from_seq:
            raise SimStoreError("event log has a gap")
        fold(snapshot, events, state)
        return state


def public_game_row(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "id", "seed", "engine_version", "scoring_model", "settings", "status", "current_week",
        "difficulty", "grade_letter", "created_at", "updated_at",
    )
    return {k: row.get(k) for k in keys}


__all__ = [
    "GameStore", "GameConflict", "GAMES", "EVENTS", "CHECKPOINTS", "GAME_TABLES", "SNAPSHOTS",
    "public_game_row",
]

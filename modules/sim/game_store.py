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

import logging
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Mapping, Sequence

from modules.sim.game_state import GameState, fold
from modules.sim.game_types import GAME_ENGINE_VERSION, GameSnapshot
from modules.sim.store import CONFLICT, TRANSIENT_CODES, SimBackend, SimStoreError, _now

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
# sim_games_status_check only allows these (docs/supabase_sim_game.sql). The fold's
# own status ("offseason" between dynasty seasons) is richer; the column is only a
# list-view cache, so anything else is stored as the closest allowed value.
DB_STATUSES = frozenset({"drafting", "in_season", "playoffs", "complete"})
_log = logging.getLogger(__name__)
RETRY_DELAY = 0.3


def db_status(status: str) -> str:
    return status if status in DB_STATUSES else "in_season"


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

_STATE_CACHE_SIZE = max(0, int(os.environ.get("SIM_GAME_STATE_CACHE", "12") or 0))  # 0 turns the cache off


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_MICRO = timedelta(microseconds=1)


def _stamp(value: Any) -> Any:
    """A timestamp as integer microseconds, so ``...:00.12345+00:00`` (what Postgres prints) and
    ``...:00.123450+00:00`` (what ``isoformat`` prints) are the same version. Unparseable: the raw text."""

    text = str(value or "")
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (dt - _EPOCH) // _MICRO
    except ValueError:
        return text


def row_version(row: Mapping[str, Any]) -> tuple[int, Any]:
    """The save's version token: the denormalized ``event_count`` plus the ``updated_at`` stamp that
    every write (events, revert, result) refreshes. A different token means someone else wrote."""

    return int(row.get("event_count") or 0), _stamp(row.get("updated_at"))


class _StateCache:
    """The folded ``GameState`` of recently used games, shared by every request in this process.

    Entries are immutable by convention: a read hands out the shared instance, a command works on
    ``state.clone()`` and publishes the result as the new entry once its events are written. An entry
    is only trusted while its version (see ``row_version``) equals the save row's, which every request
    reads first (one tiny select), so a write from another worker is noticed on the next request. Two
    guards on top: the cached state's own ``seq`` must equal the row's event count, and any failed or
    conflicting write drops the entry. Loads are single-flight per game (a burst of parallel GETs after
    a write costs one reload, not N). Bounded LRU: ``SIM_GAME_STATE_CACHE`` entries (default 12; 0 = off)."""

    def __init__(self, size: int) -> None:
        self.size = size
        self._lock = threading.Lock()
        self._items: OrderedDict[str, tuple[str, tuple[int, Any], GameState, int | None]] = OrderedDict()
        self._flights: dict[str, list[Any]] = {}  # game id -> [lock, waiters]: one load per game at a time
        self.hits = 0
        self.misses = 0

    @property
    def enabled(self) -> bool:
        return self.size > 0

    def get(self, key: str, uid: str, version: tuple[int, Any]) -> tuple[GameState, int | None] | None:
        with self._lock:
            item = self._items.get(key) if self.enabled else None
            if item is not None and item[0] == uid and item[1] == version and item[2].seq == version[0]:
                self._items.move_to_end(key)
                self.hits += 1
                return item[2], item[3]
            self.misses += 1
            return None

    def cp_week(self, key: str, uid: str) -> int | None:
        with self._lock:
            item = self._items.get(key)
            return item[3] if item is not None and item[0] == uid else None

    def put(self, key: str, uid: str, version: tuple[int, Any], state: GameState, cp_week: int | None) -> None:
        if not self.enabled or state.seq != version[0]:
            return
        with self._lock:
            self._items[key] = (uid, version, state, cp_week)
            self._items.move_to_end(key)
            while len(self._items) > self.size:
                self._items.popitem(last=False)

    def drop(self, key: str) -> None:
        with self._lock:
            self._items.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self.hits = self.misses = 0

    @contextmanager
    def flight(self, key: str) -> Iterator[None]:
        """Single-flight: concurrent cold loads of one game queue here (later ones then find the cache
        filled). Per game, so a slow load never holds up another game's requests."""

        with self._lock:
            entry = self._flights.setdefault(key, [threading.Lock(), 0])
            entry[1] += 1
        try:
            with entry[0]:
                yield
        finally:
            with self._lock:
                entry[1] -= 1
                if entry[1] == 0 and self._flights.get(key) is entry:
                    del self._flights[key]


STATES = _StateCache(_STATE_CACHE_SIZE)

_IO = ThreadPoolExecutor(max_workers=8, thread_name_prefix="sim-store")


def parallel(*fns: Callable[[], Any]) -> list[Any]:
    """Run independent store calls at the same time (one network round trip instead of N). The first runs
    on the calling thread; the first error is re-raised after every call finished."""

    if len(fns) == 1:
        return [fns[0]()]
    futures = [_IO.submit(fn) for fn in fns[1:]]
    results: list[Any] = []
    error: BaseException | None = None
    try:
        results.append(fns[0]())
    except BaseException as exc:  # noqa: BLE001 - re-raised below once the others are done
        error = exc
        results.append(None)
    for fut in futures:
        try:
            results.append(fut.result())
        except BaseException as exc:  # noqa: BLE001
            error = error or exc
            results.append(None)
    if error is not None:
        raise error
    return results


class PendingWrite:
    """Writes started in parallel with building the response. ``finish`` joins them, publishes the
    new state to the cache and re-raises a failed required write; a failed checkpoint write is only a
    cache miss later, never an error."""

    def __init__(self, store: "GameStore", uid: str, gid: str, state: GameState, version: tuple[int, Any],
                 cp_week: int | None, required: list[Any], optional: list[Any]) -> None:
        self._store, self._uid, self._gid, self._state = store, uid, gid, state
        self._version, self._cp_week = version, cp_week
        self._required, self._optional = required, optional

    def finish(self) -> None:
        error: BaseException | None = None
        for fut in self._required:
            try:
                fut.result()
            except BaseException as exc:  # noqa: BLE001
                error = error or exc
        cp_ok = True
        for fut in self._optional:
            try:
                fut.result()
            except Exception:  # noqa: BLE001 - the checkpoint is a cache; events are the truth
                cp_ok = False
        if error is not None:
            # The events are the truth and are already saved: a stale list-view row must not fail the
            # action (the client would think it was lost). The cache entry no longer matches the row, so drop it.
            STATES.drop(self._gid)
            _log.warning("sim touch failed game=%s", self._gid, exc_info=error)
            return
        STATES.put(self._gid, self._uid, self._version, self._state, self._cp_week if cp_ok else None)


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
        STATES.drop(game_id)  # the row's version moved without a new event: reload rather than guess

    def touch(self, user_id: str, game_id: str, *, status: str, week: int, event_count: int,
              updated_at: str | None = None) -> str:
        """Denormalized list-view fields (and the cache's version token); events remain the source of
        truth. Returns the ``updated_at`` stamp written."""

        stamp = updated_at or _now()
        self._update(GAMES, user_id, {"id": game_id}, {
            "status": db_status(status), "current_week": week, "event_count": event_count, "updated_at": stamp,
        })
        return stamp

    def delete_game(self, user_id: str, game_id: str) -> None:
        # Children first: correct even where the cascade is not in place.
        self._delete(EVENTS, user_id, {"game_id": game_id})
        self._delete(CHECKPOINTS, user_id, {"game_id": game_id})
        self._delete(GAMES, user_id, {"id": game_id})
        SNAPSHOTS.drop(game_id)
        STATES.drop(game_id)

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
        ok, error = self._insert_events(rows)
        if ok:
            return
        if error == CONFLICT:
            # A retry of a request whose first attempt actually landed (double tap,
            # a timeout after commit) finds exactly our events: that is success.
            if self._already_written(user_id, game_id, rows):
                return
            STATES.drop(game_id)  # whatever we held is stale now
            raise GameConflict()
        STATES.drop(game_id)  # unproven: reload rather than guess
        _log.warning("sim event write failed game=%s events=%d: %s", game_id, len(rows), error)
        raise SimStoreError(error or "event write failed")

    def _insert_events(self, rows: list[dict[str, Any]]) -> tuple[bool, str]:
        """One batched request (atomic: all rows or none), one retry on a transient failure."""

        ok, error = self.backend.insert_many(EVENTS, rows)
        if ok or error == CONFLICT or SimStoreError(error or "").code not in TRANSIENT_CODES:
            return ok, error
        time.sleep(RETRY_DELAY)
        ok, error = self.backend.insert_many(EVENTS, rows)
        return ok, error

    def _already_written(self, user_id: str, game_id: str, rows: list[dict[str, Any]]) -> bool:
        try:
            stored = self.load_events(user_id, game_id, rows[0]["seq"])
        except SimStoreError:
            return False
        by_seq = {int(r["seq"]): r for r in stored}
        return all(
            (r["seq"] in by_seq) and by_seq[r["seq"]]["type"] == r["type"] and by_seq[r["seq"]]["payload"] == r["payload"]
            for r in rows
        )

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
        STATES.drop(game_id)
        self._delete(EVENTS, user_id, {"game_id": game_id, "seq": f"gte.{seq}"})

    def delete_checkpoints_after(self, user_id: str, game_id: str, seq: int) -> None:
        """Drop checkpoints taken after event ``seq`` (going back past them): a checkpoint must never describe events that no
        longer exist."""
        STATES.drop(game_id)
        self._delete(CHECKPOINTS, user_id, {"game_id": game_id, "event_seq": f"gt.{seq}"})

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
        self, user_id: str, game_id: str, snapshot: GameSnapshot, *, use_checkpoint: bool = True,
        _cp: Mapping[str, Any] | None = None,
    ) -> GameState:
        """Latest checkpoint plus the events after it (or every event from the
        start when ``use_checkpoint`` is off: the replay). Always reads the store."""

        cp = (_cp if _cp is not None else self.latest_checkpoint(user_id, game_id)) if use_checkpoint else None
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

    def load_game(
        self, user_id: str, game_id: str, row: Mapping[str, Any]
    ) -> tuple[GameSnapshot | None, GameState | None]:
        """The frozen snapshot and the folded state for the save whose row was just read (``row`` is the
        version check). The state is a SHARED, read-only instance: commands must ``clone()`` it. A hit
        costs no store call; a miss is single-flight and reads the snapshot and checkpoint at the same
        time, then the event tail. ``(None, None)`` when the snapshot row has gone."""

        version = row_version(row)
        snap = SNAPSHOTS.get(game_id)
        hit = STATES.get(game_id, user_id, version) if snap is not None else None
        if hit is not None:
            return snap, hit[0]
        with STATES.flight(game_id):
            snap = SNAPSHOTS.get(game_id)
            hit = STATES.get(game_id, user_id, version) if snap is not None else None
            if hit is not None:
                return snap, hit[0]
            if snap is None:
                got, cp = parallel(
                    lambda: self._select(GAMES, user_id, filters={"id": game_id}, columns="snapshot", limit=1),
                    lambda: self.latest_checkpoint(user_id, game_id),
                )
                if not got:
                    return None, None
                snap = GameSnapshot.from_dict(got[0]["snapshot"])
                SNAPSHOTS.put(game_id, snap)
            else:
                cp = self.latest_checkpoint(user_id, game_id)
            state = self.load_state(user_id, game_id, snap, _cp=cp)
            STATES.put(game_id, user_id, version, state, int(cp["week"]) if cp else None)
            return snap, state

    # -------------------------------------------------------------- commits

    def commit(
        self, user_id: str, game_id: str, state: GameState, events: Sequence[Mapping[str, Any]], *,
        checkpoint_week: int | None = None, prev_checkpoint_week: int | None = None,
    ) -> PendingWrite:
        """Append ``events`` (the optimistic-concurrency gate: a lost race is ``GameConflict``), then start
        the bookkeeping writes (list-view fields, and the weekly checkpoint with its pruning) at the same
        time. The caller builds its response and then calls ``finish()`` on the result, so those round
        trips overlap the response work instead of adding to it."""

        self.append_events(user_id, game_id, events)
        stamp = _now()
        touch_fn = lambda: self.touch(  # noqa: E731
            user_id, game_id, status=state.status, week=state.week, event_count=state.seq, updated_at=stamp)
        required = [_IO.submit(touch_fn)]
        optional: list[Any] = []
        cp_known = checkpoint_week if checkpoint_week is not None else prev_checkpoint_week
        if checkpoint_week is not None:
            optional.append(_IO.submit(self._write_checkpoint, user_id, game_id, state, checkpoint_week, prev_checkpoint_week))
        return PendingWrite(self, user_id, game_id, state, (state.seq, _stamp(stamp)), cp_known, required, optional)

    def _write_checkpoint(self, user_id: str, game_id: str, state: GameState, week: int, prev: int | None) -> None:
        if prev is not None and week > prev:
            # Keep this week and the previous latest; everything older goes, in the same round trip.
            parallel(
                lambda: self._upsert(CHECKPOINTS, {
                    "game_id": game_id, "user_id": user_id, "week": week, "event_seq": state.seq,
                    "state": state.to_dict(),
                }, "game_id,week"),
                lambda: self._delete(CHECKPOINTS, user_id, {"game_id": game_id, "week": f"lt.{prev}"}),
            )
        else:
            self.save_checkpoint(user_id, game_id, state, week)

    def cached_checkpoint_week(self, user_id: str, game_id: str) -> int | None:
        """The latest checkpoint week the cache knows for this game (None: unknown)."""

        return STATES.cp_week(game_id, user_id)


def public_game_row(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "id", "seed", "engine_version", "scoring_model", "settings", "status", "current_week",
        "difficulty", "grade_letter", "created_at", "updated_at",
    )
    return {k: row.get(k) for k in keys}


__all__ = [
    "GameStore", "GameConflict", "GAMES", "EVENTS", "CHECKPOINTS", "GAME_TABLES", "SNAPSHOTS",
    "public_game_row", "STATES", "PendingWrite", "row_version", "parallel",
]

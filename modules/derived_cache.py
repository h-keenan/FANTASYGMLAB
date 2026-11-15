"""Exact memoisation of pure, expensive derivations (per process).

The Desk endpoints rebuild the same league-level structures on every request: the roster value context behind
Waivers' needs model and drop board, the league's waiver pool and per-team needs behind the Trade Analyzer.
Each is a *pure function of explicit inputs*, so it can be reused whenever those inputs are identical. Nothing
here guesses: a result is only stored and served under a key built from the full content of every input
(``fingerprint``), and an input that cannot be fingerprinted (a DataFrame with no known origin, an object of an
unknown type) makes the caller skip the memo and compute exactly as before.

* ``fingerprint(*parts)``: stable SHA-1 of plain data (dict/list/tuple/set/str/number/None/bool, numpy scalars).
  Anything else raises ``Unfingerprintable``.
* ``tag_frame`` / ``frame_key``: DataFrames are far too big to hash per request, but the shared caches that hand
  them out (``league_value_settings.build_valued_players_frame_cached``, ``waivers_logic.build_waiver_free_agent_pool_cached``)
  already know the exact cache entry a frame came from. They tag the object they return; a downstream memo keys on that tag.
  The tag is by object identity (weak), so a slice, copy or any derived frame is untagged and bypasses the memo unless the
  deriving code re-tags it with ``derive_frame_key`` (parent key + the operation's own arguments).
* ``Memo``: bounded LRU with a TTL and per-key single flight (concurrent identical requests compute once). A hit returns
  ``copy`` of the stored value (default ``copy.deepcopy``) because callers decorate what they get.

Staleness is bounded by the TTL (120 s, the same bucket the frames themselves are cached under), and every dependency that
can change inside it is part of the key: rosters, league payload, the user's resolved posture, scoring settings, the
season window. ``SIM``-style kill switch: ``DERIVED_CACHE=0`` disables every memo (compute directly)."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import time
import weakref
from collections import OrderedDict
from typing import Any, Callable, Mapping

DEFAULT_TTL_SECONDS = 120.0
ENABLED = os.environ.get("DERIVED_CACHE", "1").strip().lower() not in {"0", "false", "no", "off"}


class Unfingerprintable(TypeError):
    """An input has no stable content identity: skip the memo and compute directly."""


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return repr(value)  # nan / inf / -0.0 stay distinct and JSON-safe
    item = getattr(value, "item", None)  # numpy scalars
    if callable(item) and type(value).__module__.startswith("numpy"):
        return _plain(item())
    if isinstance(value, Mapping):
        return {"{}:{}".format(type(k).__name__, k): _plain(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_plain(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
    raise Unfingerprintable(type(value).__name__)


def fingerprint(*parts: Any) -> str:
    """Stable SHA-1 over the full content of ``parts`` (see module docstring)."""

    blob = json.dumps([_plain(p) for p in parts], sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- frame identity

_FRAME_KEYS: dict[int, tuple[weakref.ReferenceType, str, tuple]] = {}
_FRAME_LOCK = threading.Lock()


def _signature(frame: Any) -> tuple:
    """Cheap structural checksum taken when a frame is tagged and re-checked on every lookup, so a frame edited in place after
    tagging (a column added or dropped, rows changed, numeric cells overwritten) no longer matches its tag and is treated as
    untagged. Text cells edited in place with the shape unchanged are the one thing it cannot see: frames are tagged only where
    callers treat them as read-only."""

    try:
        import numpy as np

        numeric = frame.select_dtypes("number").to_numpy(dtype="float64", copy=False)
        return (tuple(frame.shape), tuple(str(c) for c in frame.columns), float(np.nansum(numeric)))
    except Exception:
        return (id(frame),)


def tag_frame(frame: Any, key: str) -> Any:
    """Record that ``frame`` (this exact object) is the content named ``key``. Returns ``frame``."""

    if not key:
        return frame
    frame_id = id(frame)

    def _forget(ref: weakref.ReferenceType, frame_id: int = frame_id) -> None:
        with _FRAME_LOCK:
            entry = _FRAME_KEYS.get(frame_id)
            if entry is not None and entry[0] is ref:
                del _FRAME_KEYS[frame_id]

    try:
        ref = weakref.ref(frame, _forget)
    except TypeError:
        return frame
    signature = _signature(frame)
    with _FRAME_LOCK:
        _FRAME_KEYS[frame_id] = (ref, key, signature)
    return frame


def frame_key(frame: Any) -> str:
    """The content key ``frame`` was tagged with, or "" for any untagged (or since-modified) object."""

    with _FRAME_LOCK:
        entry = _FRAME_KEYS.get(id(frame))
    if entry is None or entry[0]() is not frame or _signature(frame) != entry[2]:
        return ""
    return entry[1]


def derive_frame_key(parent: Any, result: Any, *operation: Any) -> Any:
    """Tag ``result`` as the pure derivation ``operation`` of ``parent``. An untagged parent (or an operation that is not
    plain data) leaves ``result`` untagged, so everything downstream bypasses the memo."""

    parent_key = frame_key(parent)
    if not parent_key:
        return result
    try:
        return tag_frame(result, fingerprint(parent_key, *operation))
    except Unfingerprintable:
        return result


# ---------------------------------------------------------------- the memo


class Memo:
    def __init__(self, name: str, *, max_entries: int = 64, ttl_seconds: float = DEFAULT_TTL_SECONDS,
                 copier: Callable[[Any], Any] = copy.deepcopy, clock: Callable[[], float] = time.monotonic) -> None:
        self.name = name
        self.max_entries = max_entries
        self.ttl = ttl_seconds
        self._copier = copier
        self._clock = clock
        self._items: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()
        self._flights: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self.hits = self.misses = 0

    def get_or_compute(self, key: str | None, compute: Callable[[], Any]) -> Any:
        """``compute()`` unless an identical-key result is fresh. ``key=None`` (an unfingerprintable input) or a disabled
        cache computes directly. A compute that raises stores nothing and lets every waiter retry for itself."""

        if key is None or not ENABLED or self.max_entries <= 0:
            return compute()
        while True:
            with self._lock:
                hit = self._items.get(key)
                if hit is not None and self._clock() - hit[0] < self.ttl:
                    self._items.move_to_end(key)
                    self.hits += 1
                    value = hit[1]
                    break
                flight = self._flights.get(key)
                if flight is None:
                    self._flights[key] = threading.Event()
                    self.misses += 1
                    value = _LEADER
                    break
            flight.wait(30.0)  # a leader is computing this key: wait, then look again
        if value is not _LEADER:
            return self._copier(value)
        try:
            result = compute()
            stored = self._copier(result)
            with self._lock:
                self._items[key] = (self._clock(), stored)
                self._items.move_to_end(key)
                while len(self._items) > self.max_entries:
                    self._items.popitem(last=False)
            return result
        finally:
            with self._lock:
                event = self._flights.pop(key, None)
            if event is not None:
                event.set()


_LEADER = object()


def share(value: Any) -> Any:
    """Copier for values that are immutable by contract (shared as is, never copied)."""

    return value

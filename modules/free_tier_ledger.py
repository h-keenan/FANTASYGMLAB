"""Server-controlled Free-tier allowances (the paywall's counters).

Why this exists: every Free-tier limit that used to live in a request
parameter (`ad_unlocks`, `shown_count`) or in the user-writable
`user_settings` row was forgeable -- the caller chose its own allowance. The
counters here live in Redis, keyed by the authenticated user id, and are
only ever advanced by the server:

* Trade-idea pool: ONE per-user set of revealed recommendation ids (per UTC
  day) that every page (Trade Hub, All Trades, Dashboard headline, share
  cards) draws from. Re-seeing an id already in the pool is free; a new id
  is admitted only while the pool is under its cap.
* Ad unlocks: granted by the server, at most one per cooldown and
  MAX per day, regardless of what the client claims. (Proper verification
  needs rewarded-ad server-side verification; see docs/paywall-audit-2026-10.md.)
* Free league claims: leagues a Free account may use before/without saving.
* Weekly Trade Analyzer evaluations.

Every mutation is an atomic Redis primitive that can only ever under-grant
under a race (parallel requests are both refused rather than both admitted).
If Redis is unreachable a per-process in-memory ledger is used instead, so
the cap still holds per worker (it never fails open to "unlimited").
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from modules import redis_cache

AD_UNLOCK_COOLDOWN_SECONDS = 10
_DAY_SECONDS = 86400 + 3600
_WEEK_SECONDS = 8 * 86400
_LEAGUE_CLAIM_SECONDS = 30 * 86400

_memory_lock = threading.Lock()
_memory_sets: dict[str, set[str]] = {}
_memory_counts: dict[str, int] = {}
_memory_cooldowns: dict[str, float] = {}


def reset_memory_for_testing() -> None:
    with _memory_lock:
        _memory_sets.clear()
        _memory_counts.clear()
        _memory_cooldowns.clear()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _day(now: datetime | None = None) -> str:
    return (now or _now()).strftime("%Y%m%d")


def _week(now: datetime | None = None) -> str:
    current = now or _now()
    monday = (current - timedelta(days=current.weekday())).strftime("%Y%m%d")
    return monday


def _key(kind: str, user_id: str, window: str) -> str:
    return redis_cache.build_cache_key("free_ledger", kind, user_id, window)


def _text(value: object) -> str:
    return str(value or "").strip()


# --------------------------------------------------------------------------
# Trade-idea pool
# --------------------------------------------------------------------------


def revealed_idea_ids(user_id: str) -> set[str]:
    uid = _text(user_id)
    if not uid:
        return set()
    key = _key("ideas", uid, _day())
    try:
        return {m.decode() if isinstance(m, bytes) else str(m) for m in redis_cache.get_redis_client().smembers(key)}
    except Exception:
        with _memory_lock:
            return set(_memory_sets.get(key, set()))


def claim_trade_ideas(user_id: str, idea_ids: Iterable[str], cap: int) -> set[str]:
    """Admit idea ids (in priority order) into the user's pool; return the
    ids the user may see. An id already in the pool is always allowed; a new
    one only while the pool holds fewer than `cap` ids."""

    uid = _text(user_id)
    ids = [_text(i) for i in idea_ids if _text(i)]
    allowed: set[str] = set()
    if not uid or cap <= 0:
        return allowed
    key = _key("ideas", uid, _day())
    try:
        client = redis_cache.get_redis_client()
        for idea_id in ids:
            if client.sismember(key, idea_id):
                allowed.add(idea_id)
                continue
            client.sadd(key, idea_id)
            # SADD-then-check: under a race both parties may see an
            # over-cap count and both back out -- never over-admits.
            if client.scard(key) > cap:
                client.srem(key, idea_id)
                continue
            client.expire(key, _DAY_SECONDS)
            allowed.add(idea_id)
        return allowed
    except Exception:
        pass
    allowed = set()
    with _memory_lock:
        pool = _memory_sets.setdefault(key, set())
        for idea_id in ids:
            if idea_id in pool or len(pool) < cap:
                pool.add(idea_id)
                allowed.add(idea_id)
    return allowed


def is_idea_revealed(user_id: str, idea_id: str) -> bool:
    return _text(idea_id) in revealed_idea_ids(user_id)


def pool_size(user_id: str) -> int:
    return len(revealed_idea_ids(user_id))


# --------------------------------------------------------------------------
# Ad unlocks
# --------------------------------------------------------------------------


def ad_unlocks_granted(user_id: str) -> int:
    uid = _text(user_id)
    if not uid:
        return 0
    key = _key("ads", uid, _day())
    try:
        raw = redis_cache.get_redis_client().get(key)
        return int(raw) if raw else 0
    except Exception:
        with _memory_lock:
            return _memory_counts.get(key, 0)


def grant_ad_unlock_if_claimed(user_id: str, claimed: int, max_unlocks: int) -> int:
    """Server-side ad-unlock count after considering the client's claim.

    The client's number is only a *hint that an ad was watched*: it can
    raise the stored count by at most one per cooldown, never past
    `max_unlocks` per day, and never lowers it. Returns the stored count."""

    uid = _text(user_id)
    if not uid:
        return 0
    granted = ad_unlocks_granted(uid)
    try:
        claim = int(claimed or 0)
    except (TypeError, ValueError):
        claim = 0
    if claim <= granted or granted >= max_unlocks:
        return min(granted, max_unlocks)
    key = _key("ads", uid, _day())
    cooldown_key = _key("ads_cooldown", uid, "x")
    try:
        client = redis_cache.get_redis_client()
        if not client.set(cooldown_key, "1", nx=True, ex=AD_UNLOCK_COOLDOWN_SECONDS):
            return granted
        new_value = int(client.incr(key))
        client.expire(key, _DAY_SECONDS)
        if new_value > max_unlocks:
            client.decr(key)
            return max_unlocks
        return new_value
    except Exception:
        import time

        with _memory_lock:
            last = _memory_cooldowns.get(cooldown_key, 0.0)
            if time.monotonic() - last < AD_UNLOCK_COOLDOWN_SECONDS:
                return _memory_counts.get(key, 0)
            _memory_cooldowns[cooldown_key] = time.monotonic()
            _memory_counts[key] = min(max_unlocks, _memory_counts.get(key, 0) + 1)
            return _memory_counts[key]


# --------------------------------------------------------------------------
# Free league claims
# --------------------------------------------------------------------------


def claim_league(user_id: str, league_id: str, capacity: int) -> bool:
    """Let a Free account use an unsaved league while it has spare league
    capacity (cap minus saved leagues). With no spare capacity (the account
    has saved a league) NOTHING is allowed here, even a league claimed
    earlier: the claim is released when a league is saved
    (`release_league_claims`) and refused here regardless. Already-claimed
    leagues stay allowed only while capacity remains."""

    uid = _text(user_id)
    lid = _text(league_id)
    if not uid or not lid or capacity <= 0:
        return False
    key = redis_cache.build_cache_key("free_ledger", "leagues", uid)
    try:
        client = redis_cache.get_redis_client()
        if client.sismember(key, lid):
            return True
        client.sadd(key, lid)
        if client.scard(key) > capacity:
            client.srem(key, lid)
            return False
        client.expire(key, _LEAGUE_CLAIM_SECONDS)
        return True
    except Exception:
        pass
    with _memory_lock:
        pool = _memory_sets.setdefault(key, set())
        if lid in pool or len(pool) < capacity:
            pool.add(lid)
            return True
        return False


def release_league_claims(user_id: str) -> None:
    """Forget the account's unsaved-league claim. Called whenever the saved
    league set changes (save or remove) so the claim is replaced by the real
    saved league instead of lingering as a second allowed league."""

    uid = _text(user_id)
    if not uid:
        return
    key = redis_cache.build_cache_key("free_ledger", "leagues", uid)
    with _memory_lock:
        _memory_sets.pop(key, None)
    try:
        redis_cache.get_redis_client().delete(key)
    except Exception:
        pass


def claimed_leagues(user_id: str) -> set[str]:
    uid = _text(user_id)
    if not uid:
        return set()
    key = redis_cache.build_cache_key("free_ledger", "leagues", uid)
    try:
        return {
            m.decode() if isinstance(m, bytes) else str(m)
            for m in redis_cache.get_redis_client().smembers(key)
        }
    except Exception:
        with _memory_lock:
            return set(_memory_sets.get(key, set()))


# --------------------------------------------------------------------------
# Weekly Trade Analyzer evaluations
# --------------------------------------------------------------------------


def consume_weekly_trade_eval(user_id: str, limit: int) -> bool:
    """Atomically use one weekly evaluation; False once `limit` is spent."""

    uid = _text(user_id)
    if not uid or limit <= 0:
        return False
    key = _key("evals", uid, _week())
    try:
        client = redis_cache.get_redis_client()
        used = int(client.incr(key))
        client.expire(key, _WEEK_SECONDS)
        if used > limit:
            client.decr(key)
            return False
        return True
    except Exception:
        pass
    with _memory_lock:
        used = _memory_counts.get(key, 0)
        if used >= limit:
            return False
        _memory_counts[key] = used + 1
        return True

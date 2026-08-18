"""Honest freshness buckets for news and structured Sleeper status.

Never invent publication timestamps. Never claim an injury *happened*
at cache-sync time — only that player status was synced then.
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Mapping

BUCKET_FRESH = "FRESH"
BUCKET_RECENT = "RECENT"
BUCKET_AGING = "AGING"
BUCKET_STALE = "STALE"
BUCKET_UNKNOWN = "UNKNOWN"

SOURCE_PUBLISHED = "published"
SOURCE_FETCHED = "fetched"
SOURCE_CACHE = "cache"
SOURCE_UNKNOWN = "unknown"

# Presentation buckets — age of the *observation*, not event occurrence.
_FRESH_MAX = 30 * 60
_RECENT_MAX = 6 * 60 * 60
_AGING_MAX = 36 * 60 * 60


def freshness_bucket(age_seconds: float | None) -> str:
    if age_seconds is None or age_seconds < 0:
        return BUCKET_UNKNOWN
    age = float(age_seconds)
    if age < _FRESH_MAX:
        return BUCKET_FRESH
    if age < _RECENT_MAX:
        return BUCKET_RECENT
    if age < _AGING_MAX:
        return BUCKET_AGING
    return BUCKET_STALE


def format_age_short(age_seconds: float | None) -> str:
    if age_seconds is None or age_seconds < 0:
        return ""
    delta = max(0, int(age_seconds))
    if delta < 60:
        return "just now"
    if delta < 60 * 60:
        return f"{max(1, delta // 60)}m"
    if delta < 24 * 60 * 60:
        return f"{max(1, delta // 3600)}h"
    return f"{max(1, delta // 86400)}d"


def format_calendar_day(age_seconds: float | None, *, now: float | None = None) -> str:
    if age_seconds is None or age_seconds < 0:
        return ""
    now_ts = float(now if now is not None else time.time())
    observed = datetime.fromtimestamp(now_ts - float(age_seconds), tz=timezone.utc)
    return f"{observed.strftime('%b')} {observed.day}"


def format_human_age_label(
    age_seconds: float | None,
    *,
    now: float | None = None,
    stale: bool = False,
) -> str:
    """Product freshness: 28m / 3h / 2d / Aug 10. Never unbounded minutes."""

    if age_seconds is None or age_seconds < 0:
        return ""
    delta = max(0, int(age_seconds))
    calendar = format_calendar_day(delta, now=now)
    if stale or delta >= 7 * 86400:
        return f"Last confirmed {calendar}" if calendar else "Last confirmed"
    if delta < 60 * 60:
        return f"{max(1, delta // 60)}m"
    if delta < 24 * 60 * 60:
        return f"{max(1, delta // 3600)}h"
    return f"{max(1, delta // 86400)}d"


_MINUTE_AGE = re.compile(r"(?i)(?:stale\s*·\s*)?(\d+)m\b")


def humanize_age_label(label: object, *, age_seconds: float | None = None) -> str:
    """Rewrite legacy `stale · 60486m` / 4+ digit minute strings."""

    text = str(label or "").strip()
    seconds = age_seconds
    if seconds is None:
        match = _MINUTE_AGE.search(text)
        if match:
            minutes = int(match.group(1))
            seconds = minutes * 60
    stale = "stale" in text.casefold()
    if seconds is not None:
        return format_human_age_label(seconds, stale=stale)
    if stale and text:
        cleaned = re.sub(r"(?i)stale\s*·\s*", "", text).strip()
        return f"Last confirmed {cleaned}" if cleaned else "Last confirmed"
    return text


def _float_ts(value: object) -> float:
    try:
        ts = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return ts if ts > 0 else 0.0


def news_cache_mtime(path: str = "data/news_cache.json") -> float:
    try:
        return float(os.path.getmtime(path))
    except OSError:
        return 0.0


def normalize_news_freshness(
    item: Mapping[str, Any] | None,
    *,
    now: float | None = None,
    cache_mtime: float | None = None,
) -> dict[str, Any]:
    """Attach honest news age metadata. Does not invent published_at."""

    payload = dict(item or {})
    now_ts = float(now if now is not None else time.time())
    published = _float_ts(payload.get("published_ts") or payload.get("published_at"))
    fetched = _float_ts(payload.get("fetched_at") or payload.get("cached_at"))
    cache_ts = _float_ts(cache_mtime)

    if published > 0:
        source = SOURCE_PUBLISHED
        observed = published
    elif fetched > 0:
        source = SOURCE_FETCHED
        observed = fetched
    elif cache_ts > 0:
        source = SOURCE_CACHE
        observed = cache_ts
    else:
        source = SOURCE_UNKNOWN
        observed = 0.0

    age = max(0.0, now_ts - observed) if observed > 0 else None
    bucket = freshness_bucket(age)
    short = format_age_short(age)
    if source == SOURCE_PUBLISHED and short:
        age_label = short if short == "just now" else f"{short} ago"
        display = short
    elif source == SOURCE_FETCHED and short:
        age_label = f"Fetched {short} ago" if short != "just now" else "Fetched just now"
        display = f"fetched {short}"
    elif source == SOURCE_CACHE and short:
        age_label = f"Cached {short} ago" if short != "just now" else "Cached just now"
        display = f"cached {short}"
    else:
        age_label = "Timestamp unavailable"
        display = ""
        bucket = BUCKET_UNKNOWN

    return {
        "source": str(payload.get("source") or ""),
        "published_at": published or None,
        "fetched_at": fetched or None,
        "age_seconds": None if age is None else int(age),
        "freshness_bucket": bucket,
        "timestamp_source": source,
        "age_label": age_label,
        "age_display": display,
        "unavailable": source == SOURCE_UNKNOWN,
    }


def players_cache_synced_at(path: str | None = None) -> float:
    """mtime of the Sleeper players JSON — observation time, not injury time."""

    from modules.sleeper import PLAYERS_CACHE_PATH

    target = path or PLAYERS_CACHE_PATH
    try:
        return float(os.path.getmtime(target))
    except OSError:
        return 0.0


def status_sync_freshness(
    *,
    now: float | None = None,
    synced_at: float | None = None,
    cache_path: str | None = None,
) -> dict[str, Any]:
    """User-visible Sleeper status freshness. Never claims injury occurrence time."""

    now_ts = float(now if now is not None else time.time())
    observed = float(synced_at) if synced_at and synced_at > 0 else players_cache_synced_at(cache_path)
    if observed <= 0:
        return {
            "status_source": "Sleeper",
            "status_synced_at": None,
            "age_seconds": None,
            "freshness_bucket": BUCKET_UNKNOWN,
            "label": "Player status sync time unavailable",
            "short_label": "Status sync unavailable",
        }
    age = max(0.0, now_ts - observed)
    short = format_age_short(age)
    when = "just now" if short == "just now" else f"{short} ago"
    return {
        "status_source": "Sleeper",
        "status_synced_at": observed,
        "age_seconds": int(age),
        "freshness_bucket": freshness_bucket(age),
        "label": f"Player status synced {when}",
        "short_label": f"synced {when}",
    }


def news_source_unavailable_label() -> str:
    return "News source unavailable"

"""Scheduled RSS news ingest with revision history and per-source health.

Why: the request-triggered cache in ``modules.news`` overwrites one file on
one host, keeps no history and cannot tell anyone a source has been down.
This module is run by ``scripts/ingest_news.py`` from a scheduled GitHub
Action (``.github/workflows/news-ingest.yml``) and is the ONLY thing that
fetches in this design; every read path (the ``/v1/external/news`` feed)
reads the store and never touches the network.

Sources: exactly the existing ``modules.news.NEWS_FEEDS`` publisher RSS
feeds, fetched with the honest identifying user agent. Nothing is scraped.

What is stored (all facts we really hold):
* ``news_items``           one row per canonical article URL.
* ``news_item_revisions``  append-only history; a new revision is written
                           when the feed's title/summary text for the same
                           URL changes. ``seq`` is the feed cursor.
* ``news_source_health``   per-feed last attempt / success / error /
                           consecutive failures / item counts.

``content_hash`` is a hash of the FEED-SUPPLIED title+summary used only to
detect that the feed text changed. It is not a checked article document and
is never exposed as ``content_sha256``.

Persistence is Supabase (``docs/supabase_news_items.sql``) when configured
and the tables exist; otherwise a local JSON file (``data/news_items.json``,
git-ignored). The migration is applied by hand; its absence is detected,
reported (``fallback_reason``) and never assumed.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping, Protocol
from urllib.parse import urlsplit

import requests

from modules import app_config, news, news_signal

ITEMS_TABLE = "news_items"
REVISIONS_TABLE = "news_item_revisions"
HEALTH_TABLE = "news_source_health"
FILE_STORE_PATH = "data/news_items.json"
FILE_STORE_MAX_REVISIONS = 6000
SUMMARY_MAX_CHARS = 1500
_CHUNK = 200


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _parse_iso(value: Any) -> float:
    try:
        text = str(value or "").replace("Z", "+00:00")
        return datetime.fromisoformat(text).timestamp()
    except (TypeError, ValueError):
        return 0.0


def source_key(feed_url: str) -> str:
    host = (urlsplit(str(feed_url or "")).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def item_id_for(url: str) -> str:
    return hashlib.sha256(news_signal.canonical_url(url).encode("utf-8")).hexdigest()[:24]


def feed_text_hash(title: Any, summary: Any) -> str:
    """Change-detector over feed-supplied text only (NOT a checked article)."""

    raw = f"{str(title or '').strip()}\x1f{str(summary or '').strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def revision_id_for(item_id: str, content_hash: str) -> str:
    return hashlib.sha256(f"{item_id}\x1f{content_hash}".encode("utf-8")).hexdigest()[:24]


def _strip_markup(text: Any) -> str:
    import re

    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(text or ""))).strip()


def build_record(item: Mapping[str, Any], feed_url: str, now: float) -> dict[str, Any] | None:
    """One normalized ingest record from a ``news._entry_to_item`` item."""

    link = str(item.get("link") or "").strip()
    title = _strip_markup(item.get("title"))
    if not link or not title:
        return None
    summary = _strip_markup(item.get("summary") or item.get("description"))[:SUMMARY_MAX_CHARS]
    iid = item_id_for(link)
    chash = feed_text_hash(title, summary)
    tokens = news_signal.title_tokens(title)
    ts = float(item.get("published_ts") or 0.0)
    return {
        "item_id": iid,
        "revision_id": revision_id_for(iid, chash),
        "content_hash": chash,
        "title": title,
        "summary": summary,
        "link": link,
        "canonical_url": news_signal.canonical_url(link),
        "published_ts": ts if ts > 0 else None,
        "source_key": source_key(feed_url),
        "feed_url": feed_url,
        "dedupe_key": hashlib.sha256(" ".join(sorted(tokens)).encode("utf-8")).hexdigest()[:24] if tokens else None,
        "_tokens": tokens,
        "_now": now,
    }


class NewsStore(Protocol):
    backend: str
    durable: bool
    fallback_reason: str | None

    def get_items(self, ids: Iterable[str]) -> dict[str, dict[str, Any]]: ...
    def recent_items(self, since_ts: float) -> list[dict[str, Any]]: ...
    def write(self, items: list[dict[str, Any]], revisions: list[dict[str, Any]]) -> None: ...
    def read_revisions(self, after_seq: int, since_ts: float, limit: int) -> list[dict[str, Any]]: ...
    def latest_revisions(self, ids: Iterable[str]) -> dict[str, str]: ...
    def duplicates_of(self, ids: Iterable[str]) -> dict[str, list[dict[str, Any]]]: ...
    def read_health(self) -> list[dict[str, Any]]: ...
    def write_health(self, rows: list[dict[str, Any]]) -> None: ...


class FileNewsStore:
    """Local JSON fallback. Same semantics as the Supabase store."""

    backend = "file"
    durable = False

    def __init__(self, path: str = FILE_STORE_PATH, fallback_reason: str | None = None):
        self.path = path
        self.fallback_reason = fallback_reason

    def _load(self) -> dict[str, Any]:
        data = news._load_json(self.path, {})
        if not isinstance(data, dict):
            data = {}
        data.setdefault("seq", 0)
        data.setdefault("items", {})
        data.setdefault("revisions", [])
        data.setdefault("health", {})
        return data

    def get_items(self, ids):
        items = self._load()["items"]
        return {i: items[i] for i in ids if i in items}

    def recent_items(self, since_ts):
        return [r for r in self._load()["items"].values() if _parse_iso(r.get("first_seen_at")) >= since_ts]

    def write(self, items, revisions):
        data = self._load()
        for row in items:
            data["items"][row["item_id"]] = row
        for rev in revisions:
            data["seq"] += 1
            data["revisions"].append({**rev, "seq": data["seq"]})
        data["revisions"] = data["revisions"][-FILE_STORE_MAX_REVISIONS:]
        news._save_json(self.path, data)

    def read_revisions(self, after_seq, since_ts, limit):
        out = []
        for rev in self._load()["revisions"]:
            if rev["seq"] <= after_seq:
                continue
            if since_ts and _parse_iso(rev.get("created_at")) < since_ts:
                continue
            out.append(rev)
            if len(out) >= limit:
                break
        return out

    def latest_revisions(self, ids):
        items = self._load()["items"]
        return {i: items[i].get("latest_revision_id") for i in ids if i in items}

    def duplicates_of(self, ids):
        wanted = set(ids)
        out: dict[str, list[dict[str, Any]]] = {}
        for row in self._load()["items"].values():
            dup = row.get("duplicate_of")
            if dup in wanted:
                out.setdefault(dup, []).append(row)
        return out

    def read_health(self):
        return list(self._load()["health"].values())

    def write_health(self, rows):
        data = self._load()
        for row in rows:
            data["health"][row["source_key"]] = row
        news._save_json(self.path, data)


class StoreError(RuntimeError):
    pass


class SupabaseNewsStore:
    backend = "supabase"
    durable = True
    fallback_reason = None

    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.key = key

    def _headers(self, prefer: str = "") -> dict[str, str]:
        headers = {"apikey": self.key, "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _get(self, table: str, params: Mapping[str, str]) -> list[dict[str, Any]]:
        try:
            resp = requests.get(f"{self.url}/rest/v1/{table}", headers=self._headers(), params=dict(params), timeout=20)
        except Exception as exc:  # noqa: BLE001
            raise StoreError(f"{table} read failed: {exc}") from exc
        if resp.status_code >= 400:
            raise StoreError(f"{table} read status {resp.status_code}: {str(resp.text)[:160]}")
        rows = resp.json()
        return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []

    def _post(self, table: str, rows: list[dict[str, Any]], conflict: str, ignore: bool = False) -> None:
        for start in range(0, len(rows), _CHUNK):
            prefer = ("resolution=ignore-duplicates" if ignore else "resolution=merge-duplicates") + ",return=minimal"
            try:
                resp = requests.post(
                    f"{self.url}/rest/v1/{table}",
                    headers=self._headers(prefer),
                    params={"on_conflict": conflict},
                    json=rows[start : start + _CHUNK],
                    timeout=30,
                )
            except Exception as exc:  # noqa: BLE001
                raise StoreError(f"{table} write failed: {exc}") from exc
            if resp.status_code >= 400:
                raise StoreError(f"{table} write status {resp.status_code}: {str(resp.text)[:160]}")

    def probe(self) -> None:
        for table in (ITEMS_TABLE, REVISIONS_TABLE, HEALTH_TABLE):
            self._get(table, {"select": "*", "limit": "1"})

    def get_items(self, ids):
        out: dict[str, dict[str, Any]] = {}
        ids = list(ids)
        for start in range(0, len(ids), 100):
            chunk = ids[start : start + 100]
            for row in self._get(ITEMS_TABLE, {"select": "*", "item_id": f"in.({','.join(chunk)})"}):
                out[row["item_id"]] = row
        return out

    def recent_items(self, since_ts):
        return self._get(
            ITEMS_TABLE, {"select": "*", "first_seen_at": f"gte.{_iso(since_ts)}", "order": "first_seen_at.desc", "limit": "2000"}
        )

    def write(self, items, revisions):
        self._post(REVISIONS_TABLE, revisions, "revision_id", ignore=True)
        self._post(ITEMS_TABLE, items, "item_id")

    def read_revisions(self, after_seq, since_ts, limit):
        params = {"select": "*", "seq": f"gt.{int(after_seq)}", "order": "seq.asc", "limit": str(int(limit))}
        if since_ts:
            params["created_at"] = f"gte.{_iso(since_ts)}"
        return self._get(REVISIONS_TABLE, params)

    def latest_revisions(self, ids):
        out: dict[str, str] = {}
        ids = list(ids)
        for start in range(0, len(ids), 100):
            chunk = ids[start : start + 100]
            for row in self._get(ITEMS_TABLE, {"select": "item_id,latest_revision_id", "item_id": f"in.({','.join(chunk)})"}):
                out[row["item_id"]] = row.get("latest_revision_id")
        return out

    def duplicates_of(self, ids):
        out: dict[str, list[dict[str, Any]]] = {}
        ids = list(ids)
        for start in range(0, len(ids), 100):
            chunk = ids[start : start + 100]
            for row in self._get(ITEMS_TABLE, {"select": "*", "duplicate_of": f"in.({','.join(chunk)})"}):
                out.setdefault(row["duplicate_of"], []).append(row)
        return out

    def read_health(self):
        return self._get(HEALTH_TABLE, {"select": "*"})

    def write_health(self, rows):
        self._post(HEALTH_TABLE, rows, "source_key")


_STORE_CACHE: dict[str, Any] = {"store": None, "at": 0.0}
_STORE_CACHE_TTL = 60.0


def open_store(*, environ: Mapping[str, str] | None = None, file_path: str = FILE_STORE_PATH, use_cache: bool = False) -> NewsStore:
    """Supabase when configured AND the migration tables exist; otherwise the
    file store with the reason recorded. Never raises."""

    if use_cache and _STORE_CACHE["store"] is not None and time.time() - _STORE_CACHE["at"] < _STORE_CACHE_TTL:
        return _STORE_CACHE["store"]
    url = app_config.config_value("SUPABASE_URL", environ=environ)
    key = app_config.config_value("SUPABASE_SERVICE_ROLE_KEY", environ=environ)
    store: NewsStore
    if not (url and key):
        store = FileNewsStore(file_path, fallback_reason="supabase_not_configured")
    else:
        sb = SupabaseNewsStore(url, key)
        try:
            sb.probe()
            store = sb
        except StoreError as exc:
            reason = "supabase_news_tables_missing_or_unreadable"
            store = FileNewsStore(file_path, fallback_reason=f"{reason}: {str(exc)[:120]}")
    if use_cache:
        _STORE_CACHE.update(store=store, at=time.time())
    return store


def ingest_once(
    store: NewsStore,
    *,
    feeds: Iterable[str] | None = None,
    fetch: Callable[[str], Any] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Fetch every feed once, persist new items/revisions and source health.

    Returns stats; ``ok`` is False when every source failed. Per-source
    failures never abort the others. This is the only fetching path.
    """

    now = time.time() if now is None else now
    fetch = fetch or news._parse_feed
    feed_urls = list(feeds if feeds is not None else news.NEWS_FEEDS)
    prior_health = {h["source_key"]: h for h in store.read_health()}

    records: dict[str, dict[str, Any]] = {}
    health_rows: list[dict[str, Any]] = []
    for feed_url in feed_urls:
        key = source_key(feed_url)
        prev = prior_health.get(key, {})
        feed = fetch(feed_url)
        entries = list(getattr(feed, "entries", []) or [])
        failed = bool(getattr(feed, "bozo", False)) and not entries
        error = str(getattr(feed, "bozo_exception", "") or "unknown error")[:300] if failed else None
        count = 0
        if not failed:
            for entry in entries:
                item = news._entry_to_item(entry, feed_url)
                rec = build_record(item, feed_url, now) if item else None
                if rec:
                    if rec["item_id"] not in records:
                        count += 1
                    records[rec["item_id"]] = rec
        health_rows.append(
            {
                "source_key": key,
                "feed_url": feed_url,
                "last_attempt_at": _iso(now),
                "last_success_at": prev.get("last_success_at") if failed else _iso(now),
                "last_error": error,
                "consecutive_failures": int(prev.get("consecutive_failures") or 0) + 1 if failed else 0,
                "last_item_count": 0 if failed else count,
                "last_new_item_count": 0,
                "updated_at": _iso(now),
            }
        )

    existing = store.get_items(list(records))
    window_start = now - news_signal.NEAR_DUPLICATE_WINDOW_SECONDS
    recent = [r for r in store.recent_items(window_start) if not r.get("duplicate_of")]
    canon_pool: list[tuple[frozenset, float, str]] = [
        (news_signal.title_tokens(r.get("title")), float(r.get("published_ts") or _parse_iso(r.get("first_seen_at"))), r["item_id"])
        for r in recent
    ]

    item_rows: list[dict[str, Any]] = []
    revision_rows: list[dict[str, Any]] = []
    new_by_source: dict[str, int] = {}
    revised = 0
    # Oldest first so the earliest outlet becomes the canonical copy.
    for rec in sorted(records.values(), key=lambda r: r["published_ts"] or r["_now"]):
        prior = existing.get(rec["item_id"])
        if prior and prior.get("latest_revision_id") == rec["revision_id"]:
            continue
        created_at = _iso(now)
        duplicate_of = prior.get("duplicate_of") if prior else None
        if not prior:
            ts = rec["published_ts"] or now
            for tokens, other_ts, other_id in canon_pool:
                if abs(ts - other_ts) <= news_signal.NEAR_DUPLICATE_WINDOW_SECONDS and news_signal.tokens_near_duplicate(
                    rec["_tokens"], tokens
                ):
                    duplicate_of = other_id
                    break
            if not duplicate_of:
                canon_pool.append((rec["_tokens"], ts, rec["item_id"]))
            new_by_source[rec["source_key"]] = new_by_source.get(rec["source_key"], 0) + 1
        else:
            revised += 1
        revision_rows.append(
            {
                "revision_id": rec["revision_id"],
                "item_id": rec["item_id"],
                "previous_revision_id": prior.get("latest_revision_id") if prior else None,
                "content_hash": rec["content_hash"],
                "title": rec["title"],
                "summary": rec["summary"],
                "link": rec["link"],
                "published_ts": rec["published_ts"],
                "source_key": rec["source_key"],
                "feed_url": rec["feed_url"],
                "created_at": created_at,
            }
        )
        item_rows.append(
            {
                "item_id": rec["item_id"],
                "canonical_url": rec["canonical_url"],
                "title": rec["title"],
                "link": rec["link"],
                "published_ts": rec["published_ts"],
                "source_key": rec["source_key"],
                "feed_url": rec["feed_url"],
                "dedupe_key": rec["dedupe_key"],
                "duplicate_of": duplicate_of,
                "first_seen_at": prior.get("first_seen_at") if prior else created_at,
                "latest_revision_id": rec["revision_id"],
                "updated_at": created_at,
            }
        )
    for row in health_rows:
        row["last_new_item_count"] = new_by_source.get(row["source_key"], 0)

    errors: list[str] = []
    try:
        if item_rows:
            store.write(item_rows, revision_rows)
    except Exception as exc:  # noqa: BLE001 - report, health still recorded below
        errors.append(f"write: {exc}")
    try:
        store.write_health(health_rows)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"health: {exc}")

    failed_sources = [h["source_key"] for h in health_rows if h["consecutive_failures"] > 0]
    return {
        "ok": len(failed_sources) < len(health_rows) and not errors,
        "backend": store.backend,
        "durable": store.durable,
        "fallback_reason": store.fallback_reason,
        "sources": len(health_rows),
        "failed_sources": failed_sources,
        "new_items": sum(new_by_source.values()),
        "new_revisions": revised,
        "errors": errors,
    }


def stats_json(stats: Mapping[str, Any]) -> str:
    return json.dumps(stats, indent=2, sort_keys=True)

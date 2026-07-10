import json
import hashlib
import os
import time
from urllib.parse import quote_plus

import feedparser

NEWS_FEEDS = [
    "https://www.rotowire.com/rss/news.php?sport=NFL",
    "https://www.espn.com/espn/rss/nfl/news",
    "https://www.cbssports.com/rss/headlines/nfl/",
]

NEWS_CACHE_PATH = "data/news_cache.json"
ROSTER_NEWS_CACHE_PATH = "data/roster_news_cache.json"
NEWS_CACHE_TTL_SECONDS = 20 * 60
PLAYER_NEWS_TERMS = [
    "injury",
    "practice",
    "starter",
    "starting",
    "depth chart",
    "contract",
    "trade",
    "suspension",
    "holdout",
    "role",
    "waived",
    "released",
]
LAST_FETCH_STATUS = {"source": "none", "errors": []}
NEWS_REASON_WEIGHTS = {
    "injury/status": 36,
    "transaction/drama": 28,
    "role/depth chart": 24,
}


def _news_item_timestamp(item):
    ts = item.get("published_ts")
    if ts:
        try:
            return float(ts)
        except Exception:
            pass

    parsed = item.get("published_parsed")
    if parsed:
        try:
            return time.mktime(parsed)
        except Exception:
            return 0.0
    return 0.0


def _set_status(source: str, errors=None):
    LAST_FETCH_STATUS["source"] = source
    LAST_FETCH_STATUS["errors"] = errors or []


def get_news_status():
    return dict(LAST_FETCH_STATUS)


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        return default


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _load_cache():
    cached = _load_json(NEWS_CACHE_PATH, [])
    return cached if isinstance(cached, list) else []


def _load_roster_cache():
    cached = _load_json(ROSTER_NEWS_CACHE_PATH, {})
    return cached if isinstance(cached, dict) else {}


def _save_roster_cache(cache):
    _save_json(ROSTER_NEWS_CACHE_PATH, cache)


def _roster_cache_key(player_names):
    names = sorted(
        {
            str(name).strip().casefold()
            for name in player_names
            if isinstance(name, str) and name.strip()
        }
    )
    raw = "|".join(names)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _serializable_item(item):
    serializable = dict(item)
    serializable.pop("published_parsed", None)
    serializable["published_ts"] = _news_item_timestamp(item)
    return serializable


def _entry_to_item(entry, source):
    link = str(entry.get("link") or "")
    if not link:
        return None
    summary = entry.get("summary") or entry.get("description") or ""
    content_items = []
    if entry.get("content"):
        if isinstance(entry.content, list):
            content_items = [
                str(item.value or "")
                for item in entry.content
                if getattr(item, "value", None) is not None
            ]
        else:
            content_items = [str(entry.content)]
    content = " ".join(content_items)
    body = entry.get("body") or ""
    description = entry.get("description") or ""
    item = {
        "title": entry.get("title"),
        "summary": summary,
        "content": content,
        "description": description,
        "body": body,
        "link": link,
        "published": entry.get("published"),
        "published_parsed": entry.get("published_parsed") or entry.get("updated_parsed"),
        "published_ts": 0.0,
        "source": source,
    }
    item["published_ts"] = _news_item_timestamp(item)
    return item


def _player_news_reason(text):
    matches = []
    lower = text.lower()
    context_groups = {
        "injury/status": [
            "injury",
            "injured",
            "questionable",
            "doubtful",
            "out",
            "inactive",
            "practice",
            "limited",
            "surgery",
            "ir",
            "concussion",
            "hamstring",
            "ankle",
            "knee",
            "illness",
        ],
        "role/depth chart": [
            "starter",
            "starting",
            "depth chart",
            "first team",
            "first-team",
            "backup",
            "competition",
            "role",
            "targets",
            "snaps",
            "workload",
        ],
        "transaction/drama": [
            "contract",
            "extension",
            "trade",
            "traded",
            "waived",
            "released",
            "signed",
            "suspended",
            "suspension",
            "holdout",
            "unhappy",
            "arrest",
            "lawsuit",
        ],
    }
    for label, phrases in context_groups.items():
        if any(phrase in lower for phrase in phrases):
            matches.append(label)
    return ", ".join(matches) if matches else "player headline"


def _reason_priority(reason: str) -> int:
    score = 0
    lower = str(reason or "").lower()
    for label, weight in NEWS_REASON_WEIGHTS.items():
        if label in lower:
            score += weight
    return score


def _recency_bonus(item) -> int:
    ts = _news_item_timestamp(item)
    if ts <= 0:
        return 0
    age_seconds = max(0.0, time.time() - ts)
    if age_seconds <= 6 * 60 * 60:
        return 24
    if age_seconds <= 24 * 60 * 60:
        return 18
    if age_seconds <= 3 * 24 * 60 * 60:
        return 11
    if age_seconds <= 7 * 24 * 60 * 60:
        return 5
    return 0


def _player_news_query(player_name):
    terms = " OR ".join(f'"{term}"' if " " in term else term for term in PLAYER_NEWS_TERMS)
    query = f'"{player_name}" NFL ({terms}) when:30d'
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"


def fetch_roster_news(player_names, max_players=28, max_items=24, force_refresh=False):
    usable_names = [
        str(name).strip()
        for name in player_names
        if isinstance(name, str) and str(name).strip()
    ]
    if not usable_names:
        return []

    cache_key = _roster_cache_key(usable_names)
    cache = _load_roster_cache()
    cached_entry = cache.get(cache_key, {})
    now = time.time()
    if (
        not force_refresh
        and cached_entry
        and now - float(cached_entry.get("saved_at", 0) or 0) < NEWS_CACHE_TTL_SECONDS
    ):
        items = cached_entry.get("items", [])
        _set_status("roster_cache", [])
        return items if isinstance(items, list) else []

    items = []
    seen_links = set()
    errors = []
    for player_name in usable_names[:max_players]:
        feed_url = _player_news_query(player_name)
        feed = feedparser.parse(
            feed_url,
            request_headers={"User-Agent": "Mozilla/5.0"},
        )
        if getattr(feed, "bozo", False) and not getattr(feed, "entries", []):
            errors.append(f"{player_name}: {getattr(feed, 'bozo_exception', 'unknown error')}")
            continue

        for entry in feed.entries[:4]:
            item = _entry_to_item(entry, "Google News")
            if not item:
                continue
            link = item["link"]
            if link in seen_links:
                continue
            text = " ".join(
                str(item.get(key, "") or "")
                for key in ["title", "summary", "description", "body", "content"]
            )
            if player_name.casefold() not in text.casefold():
                continue
            seen_links.add(link)
            item["matched_player"] = player_name
            item["relevance_reason"] = _player_news_reason(text)
            base_score = 140 if item["relevance_reason"] != "player headline" else 100
            item["relevance_score"] = base_score + _reason_priority(item["relevance_reason"]) + _recency_bonus(item)
            items.append(item)

    items.sort(
        key=lambda item: (
            int(item.get("relevance_score") or 0),
            _news_item_timestamp(item),
        ),
        reverse=True,
    )
    items = items[:max_items]
    if items:
        cache[cache_key] = {
            "saved_at": now,
            "items": [_serializable_item(item) for item in items],
        }
        _save_roster_cache(cache)
        _set_status("roster_live", errors)
        return items

    if cached_entry and cached_entry.get("items"):
        _set_status("roster_cache", errors)
        return cached_entry["items"]

    _set_status("roster_empty", errors)
    return []


def _save_cache(items):
    if not items:
        return
    serializable_items = [_serializable_item(item) for item in items]
    _save_json(NEWS_CACHE_PATH, serializable_items)


def fetch_news():
    items = []
    seen_links = set()
    errors = []
    for feed_url in NEWS_FEEDS:
        feed = feedparser.parse(
            feed_url,
            request_headers={"User-Agent": "Mozilla/5.0"},
        )
        if getattr(feed, "bozo", False) and not getattr(feed, "entries", []):
            errors.append(f"{feed_url}: {getattr(feed, 'bozo_exception', 'unknown error')}")
        for entry in feed.entries:
            link = str(entry.get("link") or "")
            if not link or link in seen_links:
                continue
            seen_links.add(link)
            item = _entry_to_item(entry, feed_url)
            if item:
                items.append(item)

    items.sort(key=_news_item_timestamp, reverse=True)
    for item in items:
        item["published_ts"] = _news_item_timestamp(item)

    if items:
        _save_cache(items)
        _set_status("live", errors)
        return items

    cached = _load_cache()
    if cached:
        cached.sort(key=_news_item_timestamp, reverse=True)
        _set_status("cache", errors)
        return cached

    _set_status("empty", errors)
    return []

"""Read-only Founder Analytics over host-local launch_analytics JSONL.

Does not write events. Does not call providers. Does not invent conversion rates.
"""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from modules import launch_analytics as la

WINDOWS: tuple[tuple[str, str, float | None], ...] = (
    ("24h", "Last 24 hours", 86400.0),
    ("7d", "Last 7 days", 7 * 86400.0),
    ("30d", "Last 30 days", 30 * 86400.0),
    ("all", "All retained data", None),
)

DECISION_EVENTS: dict[str, str] = {
    "first_game_plan_seen": "Game Plan seen",
    "game_plan_item_opened": "Game Plan item opened",
    "pqv_opened": "PQV opened",
    "trade_hub_opened": "Trade Hub opened",
    "trade_review_opened": "Trade review opened",
    "trade_analyzer_opened": "Trade Analyzer opened",
    "trade_analyzer_analyzed": "Trade Analyzer ran",
    "waivers_opened": "Waivers opened",
    "waiver_candidate_opened": "Waiver candidate opened",
    "gm_targets_viewed": "GM Targets viewed",
    "gm_target_added": "GM Target added",
    "share_card_opened": "Share card opened",
    "share_card_shared": "Share card shared",
    "notification_center_opened": "Alerts opened",
    "notification_item_opened": "Alert item opened",
}

PREMIUM_EVENTS: dict[str, str] = {
    "premium_viewed": "Premium page opens",
    "premium_cta_clicked": "Premium CTA clicks",
    "checkout_started": "Checkout starts",
    "checkout_completed": "Checkout completed (recorded)",
    "premium_entitlement_activated": "Entitlement activated (recorded)",
    "portal_opened": "Billing portal opens",
}


def window_since_ts(window_key: str, *, now: float | None = None) -> float | None:
    now_ts = float(now if now is not None else time.time())
    for key, _label, seconds in WINDOWS:
        if key == window_key:
            return None if seconds is None else now_ts - seconds
    return now_ts - 86400.0


def window_label(window_key: str) -> str:
    for key, label, _seconds in WINDOWS:
        if key == window_key:
            return label
    return "Last 24 hours"


def _count_named(rows: list[dict[str, Any]], names: Mapping[str, str]) -> list[dict[str, Any]]:
    counts = Counter()
    for row in rows:
        event = la.normalize_event_name(str(row.get("event") or ""))
        if event in names:
            counts[event] += 1
    return [
        {"event": event, "label": names[event], "count": int(counts.get(event) or 0)}
        for event in names
    ]


def _interval_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counted: dict[str, int] = {}
    for row in rows:
        event = la.normalize_event_name(str(row.get("event") or ""))
        if event != "checkout_started":
            continue
        props = row.get("props") if isinstance(row.get("props"), Mapping) else {}
        interval = str(props.get("interval") or "unspecified").strip().casefold()[:32]
        counted[interval] = counted.get(interval, 0) + 1
    return counted


def _unique_ids(rows: list[dict[str, Any]], *, field: str) -> int:
    values = {str(row.get(field) or "").strip() for row in rows}
    values.discard("")
    return len(values)


def _storage_honesty(*, writes_enabled: bool, path: Path, source: str = "local_jsonl") -> dict[str, Any]:
    if source == "supabase":
        return {
            "kind": "supabase",
            "file_name": la.ANALYTICS_SUPABASE_TABLE,
            "directory": "supabase",
            "exists": True,
            "size_bytes": 0,
            "writes_enabled": writes_enabled,
            "retention_days": la.RETENTION_DAYS,
            "survives_render_deploy": True,
            "multi_instance": "Durable Supabase table — counts are cluster-wide across every instance.",
            "scope_label": "All app instances (Supabase-backed) — not host-local.",
        }
    exists = path.is_file()
    size_bytes = path.stat().st_size if exists else 0
    return {
        "kind": "host_local_jsonl",
        "file_name": path.name,
        "directory": path.parent.name,
        "exists": exists,
        "size_bytes": size_bytes,
        "writes_enabled": writes_enabled,
        "retention_days": la.RETENTION_DAYS,
        "survives_render_deploy": False,
        "multi_instance": "Each Render instance has its own disk file. Totals are not cluster-wide.",
        "scope_label": "This host file only — Supabase not available; not all-user totals.",
    }


def build_report(
    *,
    window_key: str = "7d",
    path: Path | None = None,
    now: float | None = None,
    writes_enabled: bool | None = None,
) -> dict[str, Any]:
    local_path = path or la.analytics_path()
    enabled = la.analytics_enabled() if writes_enabled is None else bool(writes_enabled)
    since = window_since_ts(window_key, now=now)
    # Supabase-first, local-JSONL-fallback — see
    # modules.launch_analytics.read_events_with_source. Fetch once and reuse
    # the same rows for adoption/health below rather than issuing a second
    # (and third) Supabase round trip for the same report.
    rows, source = la.read_events_with_source(path=path, since_ts=since)
    event_counts: dict[str, int] = {}
    for row in rows:
        event = la.normalize_event_name(str(row.get("event") or ""))
        if event:
            event_counts[event] = event_counts.get(event, 0) + 1

    modules = []
    adoption = la.feature_adoption_summary(rows=rows)
    for name, stats in sorted(
        adoption.items(),
        key=lambda item: (-int(item[1].get("views") or 0), item[0]),
    ):
        modules.append({"module": name, **stats})

    health = la.health_summary(rows=rows)
    buckets: dict[str, int] = {}
    for row in rows:
        event = la.normalize_event_name(str(row.get("event") or ""))
        if event != "startup_complete":
            continue
        props = row.get("props") if isinstance(row.get("props"), Mapping) else {}
        bucket = str(props.get("latency_bucket") or "unknown")
        buckets[bucket] = buckets.get(bucket, 0) + 1

    return {
        "window_key": window_key,
        "window_label": window_label(window_key),
        "measured": True,
        "event_count": len(rows),
        "sessions": _unique_ids(rows, field="session_key") or _unique_ids(rows, field="anon_id"),
        "anonymous_users": _unique_ids(rows, field="anon_id"),
        "hashed_accounts": _unique_ids(rows, field="user_key")
        or _unique_ids(rows, field="account_hash"),
        "product_modules": modules,
        "decision_engagement": _count_named(rows, DECISION_EVENTS),
        "premium": _count_named(rows, PREMIUM_EVENTS),
        "checkout_intervals": _interval_counts(rows),
        "errors": health.get("errors_by_class") or {},
        "error_sessions": health.get("error_sessions") or 0,
        "performance": health.get("performance") or {},
        "startup_latency_buckets": buckets,
        "storage": _storage_honesty(writes_enabled=enabled, path=local_path, source=source),
        "unavailable": (
            []
            if rows or source == "supabase" or local_path.is_file()
            else ["No analytics file on this host yet."]
        ),
        "partial_notes": [
            "Counts are measured events" + (
                " from the durable Supabase log." if source == "supabase"
                else " on this instance's JSONL."
            ),
            "Conversion rates are omitted because these counts cannot represent all users.",
            "Enable DYNASTYGM_LAUNCH_ANALYTICS=1 on FANTASYGMLAB to record new events.",
        ],
    }

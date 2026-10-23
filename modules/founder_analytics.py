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


def _row_platform(row: Mapping[str, Any]) -> str:
    props = row.get("props") if isinstance(row.get("props"), Mapping) else {}
    value = str(props.get("platform") or "").strip().casefold()
    # Rows written before the platform property existed are web traffic.
    return value if value in la.CLIENT_PLATFORMS else "web"


def _platform_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {name: 0 for name in sorted(la.CLIENT_PLATFORMS)}
    for row in rows:
        counts[_row_platform(row)] += 1
    return counts


def _feature_use_table(rows: list[dict[str, Any]], *, limit: int = 40) -> list[dict[str, Any]]:
    """feature_use events grouped by (feature, action) with a platform split
    and the Free/Pro tier split (props.tier), most used first."""

    table: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if la.normalize_event_name(str(row.get("event") or "")) != "feature_use":
            continue
        props = row.get("props") if isinstance(row.get("props"), Mapping) else {}
        feature = str(props.get("feature") or "unknown").strip()[:60] or "unknown"
        action = str(props.get("action") or "used").strip()[:40] or "used"
        entry = table.setdefault(
            (feature, action),
            {
                "feature": feature,
                "action": action,
                "total": 0,
                "web": 0,
                "ios": 0,
                "android": 0,
                "free": 0,
                "pro": 0,
            },
        )
        entry["total"] += 1
        entry[_row_platform(row)] += 1
        tier = str(props.get("tier") or "").strip().casefold()
        if tier in {"free", "pro"}:
            entry[tier] += 1
    ordered = sorted(table.values(), key=lambda e: (-e["total"], e["feature"], e["action"]))
    return ordered[:limit]


def _row_user_id(row: Mapping[str, Any]) -> str:
    for field in ("user_key", "account_hash", "anon_id"):
        value = str(row.get(field) or "").strip()
        if value:
            return value
    return ""


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole > 0 else 0.0


def _onboarding_funnel(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Onboarding funnel from stored ``feature_use`` / ``onboarding`` events.

    Users are distinct anon/account ids. Returns None (the UI shows nothing)
    when no onboarding event was actually stored -- never zeros."""

    viewed: dict[str, set[str]] = {}
    step_index: dict[str, int] = {}
    skipped: dict[str, set[str]] = {}
    skipped_any: set[str] = set()
    completed: set[str] = set()
    started: set[str] = set()
    experience: dict[str, set[str]] = {}
    seen = False
    for row in rows:
        if la.normalize_event_name(str(row.get("event") or "")) != "feature_use":
            continue
        props = row.get("props") if isinstance(row.get("props"), Mapping) else {}
        if str(props.get("feature") or "").strip() != "onboarding":
            continue
        user = _row_user_id(row)
        if not user:
            continue
        action = str(props.get("action") or "").strip()
        step = str(props.get("step") or "").strip()[:40]
        seen = True
        if action == "step_viewed" and step:
            viewed.setdefault(step, set()).add(user)
            started.add(user)
            try:
                idx = int(props.get("step_index"))
            except (TypeError, ValueError):
                idx = 999
            step_index[step] = min(step_index.get(step, idx), idx)
        elif action == "skipped":
            skipped_any.add(user)
            if step:
                skipped.setdefault(step, set()).add(user)
        elif action == "completed":
            completed.add(user)
        elif action == "experience_selected":
            choice = str(props.get("experience") or "").strip().casefold()
            if choice in {"new", "expert"}:
                experience.setdefault(choice, set()).add(user)
    if not seen:
        return None
    order = sorted(viewed, key=lambda name: (step_index.get(name, 999), name))
    steps: list[dict[str, Any]] = []
    prev: int | None = None
    for name in order:
        users = len(viewed[name])
        steps.append(
            {
                "step": name,
                "step_index": step_index.get(name, 999),
                "users": users,
                "drop_off_pct": _pct(max(prev - users, 0), prev) if prev else None,
                "skipped_users": len(skipped.get(name, set())),
            }
        )
        prev = users
    base = len(started)
    exp_total = sum(len(v) for v in experience.values())
    return {
        "started_users": base,
        "completed_users": len(completed),
        "completion_rate_pct": _pct(len(completed), base) if base else None,
        "skipped_users": len(skipped_any),
        "skip_rate_pct": _pct(len(skipped_any), base) if base else None,
        "steps": steps,
        "experience": {
            key: {"users": len(experience[key]), "pct": _pct(len(experience[key]), exp_total)}
            for key in sorted(experience)
        },
    }


ESPN_IMPORT_FAIL_RESULTS = ("espn_private", "espn_not_found", "espn_error")


def _espn_import_outcomes(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Failed ESPN import attempts from ``feature_use`` ``league_import`` /
    ``failed`` events, split by ``result``. None (UI shows nothing) when there
    are none. Only failures are emitted, so ``private_pct`` is the share of
    failed attempts that were private leagues."""

    counts = dict.fromkeys(ESPN_IMPORT_FAIL_RESULTS, 0)
    for row in rows:
        if la.normalize_event_name(str(row.get("event") or "")) != "feature_use":
            continue
        props = row.get("props") if isinstance(row.get("props"), Mapping) else {}
        if str(props.get("feature") or "").strip() != "league_import":
            continue
        if str(props.get("action") or "").strip() != "failed":
            continue
        result = str(props.get("result") or "").strip()
        if result in counts:
            counts[result] += 1
    total = sum(counts.values())
    if total == 0:
        return None
    return {**counts, "total_failed": total, "private_pct": _pct(counts["espn_private"], total)}


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
        "platforms": _platform_counts(rows),
        "feature_use": _feature_use_table(rows),
        "onboarding_funnel": _onboarding_funnel(rows),
        "espn_import_outcomes": _espn_import_outcomes(rows),
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

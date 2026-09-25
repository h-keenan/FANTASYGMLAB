"""Canonical product analytics owner for DynastyGM launch readiness.

Application code calls this module only — never a vendor SDK.

Persistence: durable Supabase table (``analytics_events`` — see
``docs/supabase_analytics_events.sql``), write-through, service-role only,
best-effort and fully asynchronous (never blocks the caller). Local JSONL
(privacy-conscious, host-local) remains a fail-open cache/fallback: it is
still written on every event and is what read paths fall back to when
Supabase is unconfigured or unreachable. Kill switch
``DYNASTYGM_LAUNCH_ANALYTICS`` defaults off. Fail-soft: never raises into
the product path. No synchronous network I/O on the Dashboard critical path
— the Supabase write happens on a background thread.

See ``docs/founder-beta-product-analytics-contract.md``.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, MutableMapping

import requests

from modules import build_identity
from modules.app_config import config_bool, config_value, is_managed_cloud_host


_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_PATH = _REPO_ROOT / "data" / "launch_analytics.jsonl"
ANALYTICS_ENV_KEY = "DYNASTYGM_LAUNCH_ANALYTICS"
ANALYTICS_PATH_ENV_KEY = "DYNASTYGM_LAUNCH_ANALYTICS_PATH"
ANALYTICS_ENVIRONMENT_KEY = "DYNASTYGM_ANALYTICS_ENV"
RETENTION_DAYS = 120
EVENT_VERSION = 2

# Canonical allowlist. Prefer stable names already emitted in Founder Beta;
# LEGACY_EVENT_ALIASES maps alternate / requested taxonomy names onto these.
TRACKED_EVENTS: frozenset[str] = frozenset(
    {
        # Session
        "session_started",
        "session_restored",
        "session_usable",
        # Navigation / landing
        "landing_viewed",
        "page_view",
        "primary_cta_clicked",
        "secondary_cta_clicked",
        "pricing_viewed",
        # Auth / onboarding
        "signup_started",
        "signup_completed",
        "login_completed",
        "guest_username_submitted",
        "guest_league_selected",
        "guest_first_useful",
        "guest_signup_prompt_seen",
        "guest_signup_started",
        "guest_signup_completed",
        "guest_signin_started",
        "guest_signin_completed",
        "league_import_started",
        "league_import_completed",
        "league_import_failed",
        # Core surfaces (route + engagement)
        "dashboard_reached",
        "first_game_plan_seen",
        "game_plan_item_opened",
        "deep_analysis_opened",
        "trade_hub_opened",
        "trade_review_opened",
        "trade_candidate_opened",
        "trade_analyzer_opened",
        "trade_analyzer_partner_selected",
        "trade_analyzer_analyzed",
        "trade_analyzer_result",
        "pqv_opened",
        "waivers_opened",
        "waiver_candidate_opened",
        "my_team_opened",
        "league_overview_opened",
        "players_opened",
        "draft_center_opened",
        "live_draft_opened",
        "news_opened",
        "notification_center_opened",
        "notification_item_opened",
        "news_item_opened",
        "gm_orb_opened",
        "gm_destination_selected",
        "feedback_submitted",
        # Premium
        "premium_viewed",
        "premium_cta_clicked",
        "premium_gate_seen",
        "checkout_started",
        "checkout_completed",
        "premium_checkout_cancelled",
        "premium_entitlement_activated",
        "portal_opened",
        "subscription_cancel_requested",
        # Experimental / memory
        "decision_memory_viewed",
        "decision_memory_event_opened",
        "gm_targets_viewed",
        "gm_target_added",
        "gm_target_removed",
        "gm_target_opened",
        # Share cards
        "share_card_opened",
        "share_card_generated",
        "share_card_shared",
        "share_card_downloaded",
        # Errors / performance (bounded)
        "application_error",
        "provider_error",
        "route_error",
        "degraded_mode_entered",
        "startup_complete",
        "dashboard_first_useful",
        "route_ready",
        "package_build",
        "provider_call",
        "cache_lookup",
    }
)

LEGACY_EVENT_ALIASES: dict[str, str] = {
    "landing_visit": "landing_viewed",
    "account_created": "signup_completed",
    "league_imported": "league_import_completed",
    "league_connect_started": "league_import_started",
    "league_connect_completed": "league_import_completed",
    "league_connect_failed": "league_import_failed",
    "player_quick_view_opened": "pqv_opened",
    "premium_checkout_started": "checkout_started",
    "premium_checkout_completed": "checkout_completed",
    "dashboard_viewed": "dashboard_reached",
    "game_plan_viewed": "first_game_plan_seen",
    "recommendation_opened": "game_plan_item_opened",
    "my_team_viewed": "my_team_opened",
    "trade_hub_viewed": "trade_hub_opened",
    "trade_detail_opened": "trade_review_opened",
    "trade_analyzer_viewed": "trade_analyzer_opened",
    "waivers_viewed": "waivers_opened",
    "draft_center_viewed": "draft_center_opened",
    "live_draft_viewed": "live_draft_opened",
    "explorer_viewed": "players_opened",
    "asset_opened": "pqv_opened",
    "alert_seen": "notification_center_opened",
    "alert_opened": "notification_item_opened",
    "paywall_viewed": "premium_viewed",
    "entitlement_activated": "premium_entitlement_activated",
    "route_changed": "page_view",
}

ALLOWED_PROP_KEYS: frozenset[str] = frozenset(
    {
        "account_state",
        "entitlement",
        "league_key",
        "route",
        "source_surface",
        "prompt_surface",
        "interval",
        "confirmation_required",
        "experiment_decision_memory",
        "experiment_gm_targets",
        "experiment_share_cards",
        "item_kind",
        "destination",
        "billing_flag",
        "action",
        "reason",
        "viewport_category",
        "platform",
        "device_class",
        "feature",
        "result",
        "provider",
        "cache_status",
        "latency_ms",
        "latency_bucket",
        "error_class",
        "error_fingerprint",
        "league_format",
        "scoring",
        "qb_type",
        "team_count",
        "te_premium",
        "session_reason",
    }
)

# league_id accepted only to be hashed into league_key — never persisted raw.
_TRANSIENT_PROP_KEYS: frozenset[str] = frozenset({"league_id"})

BLOCKED_PROP_KEYS: frozenset[str] = frozenset(
    {
        "email",
        "token",
        "access_token",
        "refresh_token",
        "password",
        "cookie",
        "cookies",
        "authorization",
        "anon_key",
        "service_role",
        "secret",
        "api_key",
        "message",
        "body",
        "note",
        "player_name",
        "league_name",
        "username",
        "stripe_customer_id",
        "stripe_subscription_id",
        "checkout_session_id",
        "session_id",
        "customer_id",
        "subscription_id",
        "roster",
        "players",
        "trade",
        "stack",
        "traceback",
        "exception_args",
        "query",
        "search",
        "freeform",
    }
)

FUNNEL_STEPS: tuple[tuple[str, str], ...] = (
    ("Landing", "landing_viewed"),
    ("Session", "session_started"),
    ("Guest username", "guest_username_submitted"),
    ("Guest league", "guest_league_selected"),
    ("First useful", "guest_first_useful"),
    ("Signup prompt", "guest_signup_prompt_seen"),
    ("Signup", "guest_signup_completed"),
    ("League Import", "league_import_completed"),
    ("Dashboard", "dashboard_reached"),
    ("Game Plan", "first_game_plan_seen"),
    ("Trade Hub", "trade_hub_opened"),
    ("Core Feature Use", "_core_feature_use"),
    ("Premium View", "premium_viewed"),
    ("Checkout Start", "checkout_started"),
    ("Checkout Complete", "checkout_completed"),
    ("Entitlement Active", "premium_entitlement_activated"),
)

CORE_FEATURE_EVENTS: frozenset[str] = frozenset(
    {
        "trade_hub_opened",
        "trade_analyzer_opened",
        "trade_analyzer_analyzed",
        "pqv_opened",
        "waivers_opened",
        "my_team_opened",
        "trade_review_opened",
        "league_overview_opened",
        "first_game_plan_seen",
        "game_plan_item_opened",
        "deep_analysis_opened",
        "notification_center_opened",
        "notification_item_opened",
        "decision_memory_viewed",
        "gm_targets_viewed",
        "gm_target_added",
        "players_opened",
        "draft_center_opened",
        "live_draft_opened",
        "gm_orb_opened",
    }
)

MEANINGFUL_ENGAGEMENT_EVENTS: frozenset[str] = frozenset(
    CORE_FEATURE_EVENTS
    | {
        "game_plan_item_opened",
        "notification_item_opened",
        "checkout_started",
        "gm_destination_selected",
        "trade_candidate_opened",
        "waiver_candidate_opened",
        "gm_target_opened",
        "deep_analysis_opened",
    }
)

FEATURE_EVENT_MAP: dict[str, frozenset[str]] = {
    "Dashboard": frozenset({"dashboard_reached", "first_game_plan_seen", "deep_analysis_opened"}),
    "Game Plan": frozenset({"first_game_plan_seen", "game_plan_item_opened"}),
    "My Team": frozenset({"my_team_opened"}),
    "Trade Hub": frozenset({"trade_hub_opened", "trade_review_opened", "trade_candidate_opened"}),
    "Trade Analyzer": frozenset(
        {
            "trade_analyzer_opened",
            "trade_analyzer_partner_selected",
            "trade_analyzer_analyzed",
            "trade_analyzer_result",
        }
    ),
    "Waivers": frozenset({"waivers_opened", "waiver_candidate_opened"}),
    "Draft Center": frozenset({"draft_center_opened"}),
    "Live Draft": frozenset({"live_draft_opened"}),
    "Explorer": frozenset({"players_opened", "pqv_opened"}),
    "PQV": frozenset({"pqv_opened"}),
    "Decision Memory": frozenset({"decision_memory_viewed", "decision_memory_event_opened"}),
    "GM Targets": frozenset({"gm_targets_viewed", "gm_target_added", "gm_target_opened"}),
    "News": frozenset({"news_opened", "news_item_opened"}),
    "Alerts": frozenset({"notification_center_opened", "notification_item_opened"}),
    "GM Orb": frozenset({"gm_orb_opened", "gm_destination_selected"}),
    "Premium": frozenset(
        {
            "premium_viewed",
            "premium_cta_clicked",
            "checkout_started",
            "checkout_completed",
            "premium_entitlement_activated",
        }
    ),
}

ROUTE_EVENT_MAP: dict[str, str] = {
    "dashboard": "dashboard_reached",
    "trade_hub": "trade_hub_opened",
    "trade_analyzer": "trade_analyzer_opened",
    "waivers": "waivers_opened",
    "my_team": "my_team_opened",
    "rankings": "league_overview_opened",
    "premium": "premium_viewed",
    "gm_targets": "gm_targets_viewed",
    "players": "players_opened",
    "draft_summary": "draft_center_opened",
    "startup_draft_center": "draft_center_opened",
    "live_draft": "live_draft_opened",
    "news": "news_opened",
}

_LOCK = threading.Lock()
_SESSION_EMITTED: set[str] = set()

ENABLED = str(os.environ.get(ANALYTICS_ENV_KEY, "")).strip().casefold() in {
    "1",
    "true",
    "yes",
    "on",
}
ANALYTICS_PATH = str(
    Path(os.environ.get(ANALYTICS_PATH_ENV_KEY, str(_DEFAULT_PATH))).expanduser()
)

# --- Durable Supabase storage (write-through + read-through) ---------------
# See docs/supabase_analytics_events.sql. Service-role only (never a user's
# own JWT — analytics events come from anonymous/guest sessions as often as
# authenticated ones, and Founder Analytics reads must see every account's
# events, so this cannot be an RLS-scoped per-user table). Mirrors the same
# config/header pattern as modules.push_triggers / modules.stripe_webhook /
# modules.revenuecat_webhook.
ANALYTICS_SUPABASE_TABLE = "analytics_events"


@dataclass(frozen=True)
class AnalyticsSupabaseConfig:
    url: str = ""
    service_role_key: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.url and self.service_role_key)


def load_analytics_supabase_config(
    *, environ: Mapping[str, str] | None = None, secrets: Any = None
) -> AnalyticsSupabaseConfig:
    return AnalyticsSupabaseConfig(
        url=config_value("SUPABASE_URL", environ=environ, secrets=secrets),
        service_role_key=config_value(
            "SUPABASE_SERVICE_ROLE_KEY", environ=environ, secrets=secrets
        ),
    )


def _analytics_supabase_headers(
    config: AnalyticsSupabaseConfig, *, prefer: str = ""
) -> dict[str, str]:
    headers = {
        "apikey": config.service_role_key,
        "Authorization": f"Bearer {config.service_role_key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _supabase_row_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Map the JSONL event payload 1:1 onto analytics_events columns."""

    row: dict[str, Any] = {
        "event": payload.get("event"),
        "event_version": payload.get("event_version"),
        "ts": payload.get("ts"),
        "build": payload.get("build"),
        "environment": payload.get("environment"),
        "session_key": payload.get("session_key"),
        "anon_id": payload.get("anon_id"),
        "user_key": payload.get("user_key"),
        "account_hash": payload.get("account_hash"),
        "props": payload.get("props") or {},
    }
    try:
        row["occurred_at"] = datetime.fromtimestamp(
            float(payload.get("ts")), tz=timezone.utc
        ).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        pass
    return row


def _write_event_supabase(config: AnalyticsSupabaseConfig, row: Mapping[str, Any]) -> bool:
    """Single best-effort insert. Never raises — caller already fired this on
    a background thread so a hang here cannot block the product path."""

    if not config.configured:
        return False
    try:
        response = requests.post(
            f"{config.url}/rest/v1/{ANALYTICS_SUPABASE_TABLE}",
            headers=_analytics_supabase_headers(config, prefer="return=minimal"),
            json=dict(row),
            timeout=8,
        )
    except Exception:
        return False
    return response.status_code < 400


def _spawn_background(fn) -> None:
    """Fire-and-forget seam. Real runtime: a daemon thread, so the Supabase
    write-through never adds synchronous network I/O to the caller's path
    (see module docstring). Tests monkeypatch this to run ``fn`` inline.
    """

    threading.Thread(target=fn, daemon=True).start()


def _queue_supabase_write(payload: Mapping[str, Any]) -> None:
    """Best-effort, non-blocking write-through. Never raises, never blocks.

    An unreachable/misconfigured Supabase is silently a no-op — the local
    JSONL write in track_event() already happened (or was itself attempted)
    independently of this, so an outage here never breaks the calling code
    path or drops the event from the local fallback/cache.
    """

    try:
        config = load_analytics_supabase_config()
        if not config.configured:
            return
        row = _supabase_row_from_payload(payload)
        _spawn_background(lambda: _write_event_supabase(config, row))
    except Exception:
        return


def _fetch_events_supabase(
    config: AnalyticsSupabaseConfig,
    *,
    since_ts: float | None = None,
    limit: int = 20_000,
) -> tuple[list[dict[str, Any]], bool]:
    """Cross-instance read of the durable event log.

    Returns ``(rows, ok)`` — ``ok`` is False on any failure (network, HTTP,
    parse) so the caller can fall back to the local JSONL file; never raises.
    ``limit`` bounds one Founder Analytics page load the same way the
    existing JSONL path is only viable up to ~10k DAU (see VOLUME_MODEL) —
    beyond that scale this needs a warehouse, not a bigger limit.
    """

    if not config.configured:
        return [], False
    params: dict[str, str] = {
        "select": "event,event_version,ts,build,environment,session_key,anon_id,user_key,account_hash,props",
        "order": "ts.asc",
        "limit": str(max(1, int(limit))),
    }
    if since_ts is not None:
        try:
            params["ts"] = f"gte.{float(since_ts)}"
        except (TypeError, ValueError):
            pass
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{ANALYTICS_SUPABASE_TABLE}",
            headers=_analytics_supabase_headers(config),
            params=params,
            timeout=15,
        )
    except Exception:
        return [], False
    if response.status_code >= 400:
        return [], False
    try:
        parsed = response.json()
    except Exception:
        return [], False
    if not isinstance(parsed, list):
        return [], False
    return [dict(row) for row in parsed if isinstance(row, Mapping)], True


SESSION_ANON_KEY = "_launch_analytics_anon_id"
SESSION_SCOPE_KEY = "_launch_analytics_account_scope"
SESSION_LEAGUE_KEY = "_launch_analytics_league_scope"
SESSION_DEVICE_KEY = "_launch_analytics_device_class"
SESSION_STARTED_KEY = "_launch_analytics_session_started"
INTERNAL_ANALYTICS_ROUTES = frozenset({"founder_labs", "founder_ops"})
INTERNAL_SOURCE_SURFACES = frozenset(
    {
        "profile_founder_labs",
        "profile_founder_ops",
        "founder_labs",
        "founder_ops",
        "founder_analytics",
    }
)


def is_internal_analytics_traffic(
    *,
    route: str = "",
    source_surface: str = "",
    extra: Mapping[str, Any] | None = None,
) -> bool:
    """Founder Labs/Ops review must not inflate customer product metrics."""

    dest = ""
    payload = extra if isinstance(extra, Mapping) else {}
    dest = str(payload.get("destination") or payload.get("route") or "")
    for value in (route, source_surface, dest):
        key = str(value or "").strip().casefold()
        if key in INTERNAL_ANALYTICS_ROUTES or key in INTERNAL_SOURCE_SURFACES:
            return True
    return False


def analytics_enabled(
    *,
    environ: Mapping[str, str] | None = None,
    secrets: Any = None,
) -> bool:
    """Operational kill switch — default off."""

    try:
        return bool(
            config_bool(
                ANALYTICS_ENV_KEY,
                default=False,
                environ=environ,
                secrets=secrets,
            )
        )
    except Exception:
        return bool(ENABLED)


def _writes_enabled() -> bool:
    """Honor test monkeypatches of ENABLED as well as runtime config."""

    if ENABLED:
        return True
    return analytics_enabled()


def resolve_environment(*, environ: Mapping[str, str] | None = None) -> str:
    """Coarse environment stamp: production | development | test."""

    env = os.environ if environ is None else environ
    explicit = str(env.get(ANALYTICS_ENVIRONMENT_KEY) or "").strip().casefold()
    if explicit in {"production", "development", "test"}:
        return explicit
    if env.get("PYTEST_CURRENT_TEST") or env.get("DYNASTYGM_TEST_MODE"):
        return "test"
    try:
        if is_managed_cloud_host(environ=env):
            return "production"
    except Exception:
        pass
    return "development"


def analytics_path() -> Path:
    raw = str(os.environ.get(ANALYTICS_PATH_ENV_KEY, ANALYTICS_PATH) or ANALYTICS_PATH)
    target = Path(raw).expanduser()
    if not target.is_absolute():
        target = (_REPO_ROOT / target).resolve()
    return target


def clear_emitted(*, prefix: str = "") -> None:
    """Clear dedupe markers (logout / account switch / tests)."""

    marker = str(prefix or "")
    with _LOCK:
        if not marker:
            _SESSION_EMITTED.clear()
            return
        doomed = [item for item in _SESSION_EMITTED if item.startswith(marker)]
        for item in doomed:
            _SESSION_EMITTED.discard(item)


def clear_analytics_session(state: MutableMapping[str, Any] | None) -> None:
    """Drop Streamlit-scoped analytics identity on logout / account switch."""

    if isinstance(state, MutableMapping):
        state.pop(SESSION_ANON_KEY, None)
        state.pop(SESSION_SCOPE_KEY, None)
        state.pop(SESSION_LEAGUE_KEY, None)
        state.pop(SESSION_DEVICE_KEY, None)
        state.pop(SESSION_STARTED_KEY, None)
    clear_emitted()


def set_league_scope(state: MutableMapping[str, Any] | None, league_id: str) -> None:
    """Update league scope for subsequent events. Does not wipe account dedupe."""

    if not isinstance(state, MutableMapping):
        return
    state[SESSION_LEAGUE_KEY] = str(league_id or "").strip()


def set_device_class(state: MutableMapping[str, Any] | None, device_class: str) -> None:
    """Store coarse device class: mobile | tablet | desktop."""

    if not isinstance(state, MutableMapping):
        return
    label = str(device_class or "").strip().casefold()
    if label not in {"mobile", "tablet", "desktop"}:
        return
    state[SESSION_DEVICE_KEY] = label


def anonymous_id(state: MutableMapping[str, Any] | None = None) -> str:
    """Stable per-browser-session anonymous id — not an email."""

    if isinstance(state, MutableMapping):
        existing = str(state.get(SESSION_ANON_KEY) or "").strip()
        if existing:
            return existing
        minted = f"anon_{uuid.uuid4().hex[:16]}"
        state[SESSION_ANON_KEY] = minted
        return minted
    return f"anon_{uuid.uuid4().hex[:16]}"


def hash_account_id(user_id: str) -> str:
    """Non-reversible account scope for internal correlation."""

    text = str(user_id or "").strip()
    if not text:
        return ""
    digest = hashlib.sha256(f"dynastygm-analytics:{text}".encode("utf-8")).hexdigest()
    return f"acct_{digest[:16]}"


def hash_league_id(league_id: str) -> str:
    """Pseudonymous league key — never persist raw provider league ids."""

    text = str(league_id or "").strip()
    if not text:
        return ""
    digest = hashlib.sha256(f"dynastygm-league:{text}".encode("utf-8")).hexdigest()
    return f"lg_{digest[:16]}"


def error_fingerprint(error_class: str, *, route: str = "", provider: str = "") -> str:
    raw = "|".join(
        [
            str(error_class or "").strip().casefold()[:80],
            str(route or "").strip().casefold()[:40],
            str(provider or "").strip().casefold()[:40],
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"err_{digest[:12]}"


def latency_bucket(latency_ms: float | int | None) -> str:
    try:
        value = float(latency_ms)
    except (TypeError, ValueError):
        return "unknown"
    if value < 0:
        return "unknown"
    for edge in (100, 250, 500, 1000, 2000, 5000, 10000, 30000):
        if value < edge:
            return f"lt_{edge}ms"
    return "gte_30000ms"


def _safe_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_props(props: Mapping[str, Any] | None) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    raw = dict(props or {})
    # Hash raw league_id before allowlist filtering.
    if "league_id" in raw and "league_key" not in raw:
        hashed = hash_league_id(_safe_text(raw.get("league_id")))
        if hashed:
            raw["league_key"] = hashed
    for key, value in raw.items():
        name = _safe_text(key).casefold()
        if not name or name in BLOCKED_PROP_KEYS or name in _TRANSIENT_PROP_KEYS:
            continue
        if name not in ALLOWED_PROP_KEYS:
            continue
        if isinstance(value, bool) or value is None:
            clean[name] = value
        elif isinstance(value, (int, float)):
            if name == "latency_ms":
                try:
                    clean[name] = int(max(0, min(float(value), 600_000)))
                except (TypeError, ValueError):
                    continue
            else:
                clean[name] = value
        elif isinstance(value, str):
            clean[name] = value.strip()[:120]
        else:
            continue
    return clean


def build_context_props(
    state: Mapping[str, Any] | None = None,
    *,
    route: str = "",
    source_surface: str = "",
    league_id: str = "",
    entitlement: str = "",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble safe metadata from session without PII."""

    session = state if isinstance(state, Mapping) else {}
    auth = session.get("auth_session") if isinstance(session.get("auth_session"), Mapping) else {}
    profile = (
        session.get("account_profile")
        if isinstance(session.get("account_profile"), Mapping)
        else {}
    )
    user_id = _safe_text(auth.get("user_id") or profile.get("user_id"))
    account_state = "authenticated" if user_id else "guest"
    ent = _safe_text(entitlement) or _safe_text(profile.get("entitlement"), "free")
    league = (
        _safe_text(league_id)
        or _safe_text(session.get(SESSION_LEAGUE_KEY))
        or _safe_text(session.get("selected_league_id"))
    )
    device = _safe_text(session.get(SESSION_DEVICE_KEY))
    props: dict[str, Any] = {
        "account_state": account_state,
        "entitlement": ent.casefold() or "free",
    }
    if league:
        props["league_key"] = hash_league_id(league)
    if route:
        props["route"] = _safe_text(route)
    if source_surface:
        props["source_surface"] = _safe_text(source_surface)
    if device:
        props["device_class"] = device
    try:
        from modules.app_config import config_bool as _cfg

        props["experiment_decision_memory"] = bool(
            _cfg("DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY", default=False)
        )
        props["experiment_gm_targets"] = bool(
            _cfg("DYNASTYGM_EXPERIMENTAL_GM_TARGETS", default=False)
        )
        props["experiment_share_cards"] = bool(
            _cfg("DYNASTYGM_EXPERIMENTAL_SHARE_CARDS", default=False)
        )
    except Exception:
        pass
    props.update(dict(extra or {}))
    return _safe_props(props)


def normalize_event_name(event: str) -> str:
    name = _safe_text(event)
    return LEGACY_EVENT_ALIASES.get(name, name)


def track_event(
    event: str,
    *,
    props: dict | None = None,
    once_key: str = "",
    state: MutableMapping[str, Any] | None = None,
) -> bool:
    """Append one analytics event when enabled. Never raises."""

    name = normalize_event_name(_safe_text(event))
    if name not in TRACKED_EVENTS:
        return False
    raw_props = props if isinstance(props, Mapping) else {}
    if is_internal_analytics_traffic(
        route=_safe_text(raw_props.get("route")),
        source_surface=_safe_text(raw_props.get("source_surface")),
        extra=raw_props,
    ):
        return False
    if not _writes_enabled():
        return False

    if once_key:
        marker = f"{name}:{once_key}"
        with _LOCK:
            if marker in _SESSION_EMITTED:
                return False
            _SESSION_EMITTED.add(marker)

    anon = anonymous_id(state)
    account_hash = ""
    if isinstance(state, Mapping):
        auth = state.get("auth_session") if isinstance(state.get("auth_session"), Mapping) else {}
        profile = (
            state.get("account_profile")
            if isinstance(state.get("account_profile"), Mapping)
            else {}
        )
        account_hash = hash_account_id(
            _safe_text(auth.get("user_id") or profile.get("user_id"))
        )

    payload = {
        "event": name,
        "event_version": EVENT_VERSION,
        "ts": time.time(),
        "build": build_identity.resolve_build_identity().revision,
        "environment": resolve_environment(),
        "session_key": anon,
        "anon_id": anon,
        "user_key": account_hash,
        "account_hash": account_hash,
        "props": _safe_props(props),
    }
    wrote_local = False
    try:
        target = analytics_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        with _LOCK:
            with target.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        wrote_local = True
    except Exception:
        wrote_local = False

    # Durable write-through — best-effort, asynchronous, independent of the
    # local write above (an outage on either side never affects the other,
    # and never affects this function's return value or raises here).
    try:
        _queue_supabase_write(payload)
    except Exception:
        pass

    return wrote_local


def track_page_view(
    route: str,
    *,
    state: MutableMapping[str, Any] | None = None,
    source_surface: str = "navigation",
    changed: bool = True,
) -> bool:
    """Page/route view with Streamlit rerun protection."""

    if not changed:
        return False
    route_key = _safe_text(route)
    if not route_key:
        return False
    if is_internal_analytics_traffic(route=route_key, source_surface=source_surface):
        return False
    # Prefer specific surface milestones when mapped — do not also emit page_view.
    if route_key in ROUTE_EVENT_MAP:
        return track_route_opened(
            route_key, state=state, source_surface=source_surface, changed=True
        )
    scope = anonymous_id(state)
    league = ""
    if isinstance(state, Mapping):
        auth = state.get("auth_session") if isinstance(state.get("auth_session"), Mapping) else {}
        scope = hash_account_id(_safe_text(auth.get("user_id"))) or scope
        league = _safe_text(state.get(SESSION_LEAGUE_KEY) or state.get("selected_league_id"))
    return track_event(
        "page_view",
        props=build_context_props(
            state, route=route_key, source_surface=source_surface, league_id=league
        ),
        once_key=f"{scope}:{hash_league_id(league)}:{route_key}",
        state=state,
    )


def track_feature_use(
    feature: str,
    *,
    action: str = "opened",
    state: MutableMapping[str, Any] | None = None,
    route: str = "",
    once_key: str = "",
    extra: Mapping[str, Any] | None = None,
) -> bool:
    """Meaningful feature engagement (not presence / hover)."""

    feature_key = _safe_text(feature).casefold().replace(" ", "_")
    action_key = _safe_text(action).casefold() or "opened"
    # Map common features onto canonical events when possible.
    mapped = {
        ("game_plan", "opened"): "first_game_plan_seen",
        ("game_plan", "item_opened"): "game_plan_item_opened",
        ("recommendation", "opened"): "game_plan_item_opened",
        ("gm_orb", "opened"): "gm_orb_opened",
        ("gm_orb", "destination_selected"): "gm_destination_selected",
        ("deep_analysis", "opened"): "deep_analysis_opened",
        ("pqv", "opened"): "pqv_opened",
        ("alert", "opened"): "notification_item_opened",
        ("alert", "seen"): "notification_center_opened",
    }.get((feature_key, action_key))
    event = mapped or "page_view"
    props = build_context_props(
        state,
        route=route,
        source_surface=feature_key,
        extra={"feature": feature_key, "action": action_key, **dict(extra or {})},
    )
    marker = once_key or f"{feature_key}:{action_key}:{route}"
    return track_event(event, props=props, once_key=marker, state=state)


def track_error(
    error_class: str,
    *,
    state: MutableMapping[str, Any] | None = None,
    route: str = "",
    provider: str = "",
    kind: str = "application_error",
    result: str = "fail_soft",
    once_per_session: bool = True,
) -> bool:
    """Sanitized error observability — no stack traces or secrets in JSONL."""

    event = normalize_event_name(kind)
    if event not in {
        "application_error",
        "provider_error",
        "route_error",
        "degraded_mode_entered",
    }:
        event = "application_error"
    cls = _safe_text(error_class).casefold()[:80] or "unknown"
    fingerprint = error_fingerprint(cls, route=route, provider=provider)
    props = build_context_props(
        state,
        route=route,
        source_surface="error",
        extra={
            "error_class": cls,
            "error_fingerprint": fingerprint,
            "provider": _safe_text(provider).casefold()[:40],
            "result": _safe_text(result).casefold()[:40] or "fail_soft",
        },
    )
    once = fingerprint if once_per_session else ""
    return track_event(event, props=props, once_key=once, state=state)


def track_performance(
    milestone: str,
    *,
    latency_ms: float | int | None = None,
    state: MutableMapping[str, Any] | None = None,
    route: str = "",
    provider: str = "",
    cache_status: str = "",
    result: str = "",
    once_key: str = "",
) -> bool:
    """Bounded performance telemetry — bucketed, not raw waterfall spam."""

    event = normalize_event_name(milestone)
    if event not in {
        "startup_complete",
        "dashboard_first_useful",
        "route_ready",
        "package_build",
        "provider_call",
        "cache_lookup",
        "session_usable",
    }:
        return False
    props = build_context_props(
        state,
        route=route,
        source_surface="performance",
        extra={
            "latency_ms": latency_ms,
            "latency_bucket": latency_bucket(latency_ms),
            "provider": _safe_text(provider).casefold()[:40],
            "cache_status": _safe_text(cache_status).casefold()[:20],
            "result": _safe_text(result).casefold()[:40],
        },
    )
    marker = once_key or f"perf:{event}:{route or 'app'}"
    return track_event(event, props=props, once_key=marker, state=state)


def track_session_started(
    state: MutableMapping[str, Any] | None = None,
    *,
    reason: str = "script_start",
    restored: bool = False,
) -> bool:
    """Emit once per Streamlit session for DAU / session denominators."""

    if not isinstance(state, MutableMapping):
        state = {}
    if state.get(SESSION_STARTED_KEY):
        # Still allow restored marker once.
        if restored:
            return track_event(
                "session_restored",
                props=build_context_props(
                    state, source_surface="session", extra={"session_reason": reason}
                ),
                once_key="session",
                state=state,
            )
        return False
    state[SESSION_STARTED_KEY] = True
    event = "session_restored" if restored else "session_started"
    return track_event(
        event,
        props=build_context_props(
            state, source_surface="session", extra={"session_reason": reason}
        ),
        once_key="session",
        state=state,
    )


def track_route_opened(
    route: str,
    *,
    state: MutableMapping[str, Any] | None = None,
    source_surface: str = "destination_navigation",
    changed: bool = True,
) -> bool:
    """Emit a route milestone once per meaningful navigation (not per rerun)."""

    if not changed:
        return False
    route_key = _safe_text(route)
    if is_internal_analytics_traffic(route=route_key, source_surface=source_surface):
        return False
    event = ROUTE_EVENT_MAP.get(route_key)
    if not event:
        return False
    scope = anonymous_id(state)
    league = ""
    if isinstance(state, Mapping):
        auth = state.get("auth_session") if isinstance(state.get("auth_session"), Mapping) else {}
        scope = hash_account_id(_safe_text(auth.get("user_id"))) or scope
        league = _safe_text(state.get(SESSION_LEAGUE_KEY) or state.get("selected_league_id"))
    return track_event(
        event,
        props=build_context_props(
            state, route=route_key, source_surface=source_surface, league_id=league
        ),
        once_key=f"{scope}:{hash_league_id(league)}:{route_key}",
        state=state,
    )


def _iter_events(
    *,
    path: Path | None = None,
    since_ts: float | None = None,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    target = path or analytics_path()
    if not target.is_file():
        return rows
    try:
        with target.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                try:
                    row = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                if since_ts is not None:
                    try:
                        if float(row.get("ts") or 0) < float(since_ts):
                            continue
                    except (TypeError, ValueError):
                        continue
                if environment:
                    row_env = _safe_text(row.get("environment")).casefold()
                    # Legacy rows (no environment) are included; stamped rows must match.
                    if row_env and row_env != environment.casefold():
                        continue
                rows.append(row)
    except OSError:
        return []
    return rows


def read_events_with_source(
    *,
    path: Path | None = None,
    since_ts: float | None = None,
    environment: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Founder Analytics read path: durable Supabase first, local JSONL
    fallback. Returns ``(rows, source)`` where ``source`` is
    ``"supabase"`` or ``"local_jsonl"`` — fail-open, never raises.

    Passing an explicit ``path`` always reads that JSONL file only (used by
    tests and any caller that wants a specific host file rather than the
    cross-instance durable log); Supabase is only attempted when ``path`` is
    left as the default ``None``.
    """

    if path is None:
        try:
            config = load_analytics_supabase_config()
        except Exception:
            config = None
        if config is not None and config.configured:
            rows, ok = _fetch_events_supabase(config, since_ts=since_ts)
            if ok:
                return rows, "supabase"
    return _iter_events(path=path, since_ts=since_ts, environment=environment), "local_jsonl"


def read_events(
    *,
    path: Path | None = None,
    since_ts: float | None = None,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """Rows only — see read_events_with_source for the fallback contract."""

    rows, _source = read_events_with_source(path=path, since_ts=since_ts, environment=environment)
    return rows


def _identity_key(row: Mapping[str, Any]) -> str:
    return (
        _safe_text(row.get("user_key"))
        or _safe_text(row.get("account_hash"))
        or _safe_text(row.get("session_key"))
        or _safe_text(row.get("anon_id"))
    )


def read_event_counts(
    *,
    path: Path | None = None,
    since_ts: float | None = None,
) -> dict[str, int]:
    """Count events (Supabase-first, JSONL fallback); map legacy names onto canonical keys."""

    counts: dict[str, int] = {name: 0 for name in sorted(TRACKED_EVENTS)}
    for row in read_events(path=path, since_ts=since_ts):
        event = normalize_event_name(_safe_text(row.get("event")))
        if event in counts:
            counts[event] += 1
        elif event:
            counts[event] = counts.get(event, 0) + 1
    return counts


def funnel_summary(counts: Mapping[str, int] | None = None) -> list[dict[str, Any]]:
    """Simple founder funnel with conversion rates vs prior step."""

    data = dict(counts or read_event_counts())
    core_use = sum(int(data.get(name) or 0) for name in CORE_FEATURE_EVENTS)
    rows: list[dict[str, Any]] = []
    previous = None
    for label, key in FUNNEL_STEPS:
        value = int(core_use) if key == "_core_feature_use" else int(data.get(key) or 0)
        conversion = None
        if previous is not None and previous > 0:
            conversion = round((value / previous) * 100.0, 1)
        rows.append(
            {
                "step": label,
                "event": key,
                "count": value,
                "conversion_from_prior_pct": conversion,
            }
        )
        previous = value
    return rows


def retention_summary(
    *,
    path: Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """DAU/WAU/MAU and D1/D7/D30 from pseudonymous identities + timestamps.

    Active user = distinct user_key/account_hash/anon_id with ≥1 event in window.
    Meaningful active user = identity with ≥1 MEANINGFUL_ENGAGEMENT_EVENTS event.
    """

    now_ts = float(now if now is not None else time.time())
    day = 86400.0
    rows = read_events(path=path)
    by_day: dict[str, set[str]] = defaultdict(set)
    meaningful_day: dict[str, set[str]] = defaultdict(set)
    first_seen: dict[str, float] = {}
    sessions_by_id: dict[str, set[str]] = defaultdict(set)
    meaningful_actions = 0

    for row in rows:
        identity = _identity_key(row)
        if not identity:
            continue
        try:
            ts = float(row.get("ts") or 0)
        except (TypeError, ValueError):
            continue
        if ts <= 0:
            continue
        day_key = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        by_day[day_key].add(identity)
        event = normalize_event_name(_safe_text(row.get("event")))
        if event in MEANINGFUL_ENGAGEMENT_EVENTS:
            meaningful_day[day_key].add(identity)
            meaningful_actions += 1
        first_seen[identity] = min(first_seen.get(identity, ts), ts)
        sessions_by_id[identity].add(
            _safe_text(row.get("session_key") or row.get("anon_id")) or identity
        )

    def _window_users(days: int) -> set[str]:
        cutoff = now_ts - (days * day)
        users: set[str] = set()
        for row in rows:
            try:
                ts = float(row.get("ts") or 0)
            except (TypeError, ValueError):
                continue
            if ts >= cutoff:
                identity = _identity_key(row)
                if identity:
                    users.add(identity)
        return users

    dau = _window_users(1)
    wau = _window_users(7)
    mau = _window_users(30)

    # Rolling retention: of users active on day T-N, % also active on day T.
    today_key = datetime.fromtimestamp(now_ts, tz=timezone.utc).strftime("%Y-%m-%d")

    def _rolling_retention(offset_days: int) -> float | None:
        base_key = datetime.fromtimestamp(now_ts - offset_days * day, tz=timezone.utc).strftime(
            "%Y-%m-%d"
        )
        base = by_day.get(base_key, set())
        if not base:
            return None
        returned = base & by_day.get(today_key, set())
        return round((len(returned) / len(base)) * 100.0, 1)

    sessions = sum(len(items) for items in sessions_by_id.values())
    return {
        "dau": len(dau),
        "wau": len(wau),
        "mau": len(mau),
        "meaningful_dau": len(
            {
                identity
                for day_key, users_set in meaningful_day.items()
                if day_key == today_key
                for identity in users_set
            }
        ),
        "d1_retention_pct": _rolling_retention(1),
        "d7_retention_pct": _rolling_retention(7),
        "d30_retention_pct": _rolling_retention(30),
        "sessions": sessions,
        "sessions_per_user": round(sessions / max(1, len(sessions_by_id)), 2),
        "meaningful_actions": meaningful_actions,
        "meaningful_actions_per_session": round(
            meaningful_actions / max(1, sessions), 2
        ),
        "unique_users": len(sessions_by_id),
        "definition": {
            "active_user": "distinct user_key/account_hash/anon_id with ≥1 event in window",
            "meaningful_active_user": "identity with ≥1 MEANINGFUL_ENGAGEMENT_EVENTS event",
            "retention": "rolling: share of users active on day T-N also active on day T",
        },
    }


def feature_adoption_summary(
    *,
    path: Path | None = None,
    since_ts: float | None = None,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, int]]:
    """Per-feature users / sessions / views / meaningful interactions.

    ``rows`` lets a caller (e.g. founder_analytics.build_report) reuse an
    already-fetched, already-window-filtered event list instead of issuing a
    second Supabase/JSONL read for the same report.
    """

    rows = read_events(path=path, since_ts=since_ts) if rows is None else rows
    out: dict[str, dict[str, int]] = {}
    for feature, events in FEATURE_EVENT_MAP.items():
        users: set[str] = set()
        sessions: set[str] = set()
        views = 0
        interactions = 0
        for row in rows:
            event = normalize_event_name(_safe_text(row.get("event")))
            if event not in events:
                continue
            identity = _identity_key(row)
            if identity:
                users.add(identity)
            sessions.add(
                _safe_text(row.get("session_key") or row.get("anon_id")) or identity
            )
            views += 1
            if event in MEANINGFUL_ENGAGEMENT_EVENTS:
                interactions += 1
        out[feature] = {
            "users": len(users),
            "sessions": len(sessions - {""}),
            "views": views,
            "meaningful_interactions": interactions,
        }
    return out


def health_summary(
    *,
    path: Path | None = None,
    since_ts: float | None = None,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Error / performance aggregates for Founder Ops HEALTH view.

    ``rows`` lets a caller reuse an already-fetched event list — see
    feature_adoption_summary's docstring for why.
    """

    rows = read_events(path=path, since_ts=since_ts) if rows is None else rows
    error_events = {
        "application_error",
        "provider_error",
        "route_error",
        "degraded_mode_entered",
    }
    perf_events = {
        "startup_complete",
        "dashboard_first_useful",
        "route_ready",
        "package_build",
        "provider_call",
        "cache_lookup",
    }
    sessions: set[str] = set()
    error_sessions: set[str] = set()
    errors_by_class: dict[str, int] = defaultdict(int)
    errors_by_build: dict[str, int] = defaultdict(int)
    latencies: dict[str, list[float]] = defaultdict(list)
    cache_hits = 0
    cache_total = 0

    for row in rows:
        session = _safe_text(row.get("session_key") or row.get("anon_id"))
        if session:
            sessions.add(session)
        event = normalize_event_name(_safe_text(row.get("event")))
        props = row.get("props") if isinstance(row.get("props"), Mapping) else {}
        build = _safe_text(row.get("build"), "unknown")
        if event in error_events:
            if session:
                error_sessions.add(session)
            cls = _safe_text(props.get("error_class"), "unknown")
            errors_by_class[cls] += 1
            errors_by_build[build] += 1
        if event in perf_events:
            try:
                latency = float(props.get("latency_ms"))
            except (TypeError, ValueError):
                latency = None
            if latency is not None:
                latencies[event].append(latency)
            if event == "cache_lookup":
                cache_total += 1
                if _safe_text(props.get("cache_status")).casefold() == "hit":
                    cache_hits += 1

    def _percentile(values: list[float], pct: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        if len(ordered) == 1:
            return round(ordered[0], 1)
        rank = (len(ordered) - 1) * pct
        low = int(rank)
        high = min(low + 1, len(ordered) - 1)
        weight = rank - low
        return round(ordered[low] * (1 - weight) + ordered[high] * weight, 1)

    perf_out: dict[str, dict[str, float | None]] = {}
    for name, values in latencies.items():
        perf_out[name] = {
            "p50": _percentile(values, 0.50),
            "p90": _percentile(values, 0.90),
            "p95": _percentile(values, 0.95),
            "n": float(len(values)),
        }

    return {
        "sessions": len(sessions),
        "error_sessions": len(error_sessions),
        "error_rate": round(len(error_sessions) / max(1, len(sessions)), 4),
        "errors_by_class": dict(sorted(errors_by_class.items(), key=lambda item: (-item[1], item[0]))),
        "errors_by_build": dict(sorted(errors_by_build.items(), key=lambda item: (-item[1], item[0]))),
        "performance": perf_out,
        "cache_hit_rate": round(cache_hits / cache_total, 4) if cache_total else None,
        "degraded_mode_count": sum(
            1
            for row in rows
            if normalize_event_name(_safe_text(row.get("event"))) == "degraded_mode_entered"
        ),
    }


def founder_ops_metrics(counts: Mapping[str, int] | None = None) -> dict[str, Any]:
    """Compact Founder Ops card metrics."""

    data = dict(counts or read_event_counts())
    retention = retention_summary()
    features = feature_adoption_summary()
    health = health_summary()
    return {
        "sessions_landing": int(data.get("landing_viewed") or 0),
        "sessions_started": int(data.get("session_started") or 0)
        + int(data.get("session_restored") or 0),
        "signups": int(data.get("signup_completed") or 0),
        "logins": int(data.get("login_completed") or 0),
        "leagues_imported": int(data.get("league_import_completed") or 0),
        "dashboard_reached": int(data.get("dashboard_reached") or 0),
        "trade_hub_opens": int(data.get("trade_hub_opened") or 0),
        "pqv_opens": int(data.get("pqv_opened") or 0),
        "premium_views": int(data.get("premium_viewed") or 0),
        "checkout_starts": int(data.get("checkout_started") or 0),
        "checkout_completions": int(data.get("checkout_completed") or 0),
        "feedback_submissions": int(data.get("feedback_submitted") or 0),
        "decision_memory_views": int(data.get("decision_memory_viewed") or 0),
        "gm_targets_adds": int(data.get("gm_target_added") or 0),
        "gm_orb_opens": int(data.get("gm_orb_opened") or 0),
        "application_errors": int(data.get("application_error") or 0)
        + int(data.get("provider_error") or 0)
        + int(data.get("route_error") or 0),
        "retention_days": RETENTION_DAYS,
        "retention": retention,
        "feature_adoption": features,
        "health": health,
        "event_version": EVENT_VERSION,
        "expected_events_per_session": EXPECTED_EVENTS_PER_SESSION,
    }


def prune_expired_events(
    *, now: float | None = None, retention_days: int = RETENTION_DAYS
) -> int:
    """Best-effort retention prune. Returns removed line count. Fail-soft."""

    target = analytics_path()
    if not target.is_file():
        return 0
    cutoff = float(now if now is not None else time.time()) - (
        max(1, int(retention_days)) * 86400
    )
    kept: list[str] = []
    removed = 0
    try:
        with target.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                try:
                    row = json.loads(text)
                    ts = float(row.get("ts") or 0)
                except (json.JSONDecodeError, TypeError, ValueError):
                    removed += 1
                    continue
                if ts < cutoff:
                    removed += 1
                    continue
                kept.append(text)
        if removed:
            with _LOCK:
                with target.open("w", encoding="utf-8") as handle:
                    for line in kept:
                        handle.write(line + "\n")
    except OSError:
        return 0
    return removed


# Volume model constants for founder planning (documented in contract).
EXPECTED_EVENTS_PER_SESSION = 12
VOLUME_MODEL = {
    "events_per_session": EXPECTED_EVENTS_PER_SESSION,
    "events_per_dau": 18,
    "dau_100": {"events_day": 1_800, "notes": "Founder Beta scale"},
    "dau_1k": {"events_day": 18_000, "notes": "Local JSONL still viable single-host"},
    "dau_10k": {
        "events_day": 180_000,
        "notes": "Plan durable warehouse / object log drain",
    },
    "dau_100k": {
        "events_day": 1_800_000,
        "notes": "Requires external analytics warehouse; not this JSONL path",
    },
}

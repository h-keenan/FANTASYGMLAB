"""Founder Beta product analytics — observe behavior, never affect it.

Privacy-conscious JSONL milestones. Kill switch: DYNASTYGM_LAUNCH_ANALYTICS=1
(default off). Fail-soft: write errors never raise into the product path.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from modules import build_identity
from modules.app_config import config_bool


_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_PATH = _REPO_ROOT / "data" / "launch_analytics.jsonl"
ANALYTICS_ENV_KEY = "DYNASTYGM_LAUNCH_ANALYTICS"
ANALYTICS_PATH_ENV_KEY = "DYNASTYGM_LAUNCH_ANALYTICS_PATH"
RETENTION_DAYS = 120

TRACKED_EVENTS: frozenset[str] = frozenset(
    {
        "landing_viewed",
        "primary_cta_clicked",
        "secondary_cta_clicked",
        "pricing_viewed",
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
        "dashboard_reached",
        "first_game_plan_seen",
        "trade_hub_opened",
        "trade_review_opened",
        "pqv_opened",
        "waivers_opened",
        "my_team_opened",
        "league_overview_opened",
        "notification_center_opened",
        "feedback_submitted",
        "premium_viewed",
        "premium_cta_clicked",
        "premium_gate_seen",
        "checkout_started",
        "checkout_completed",
        "premium_checkout_cancelled",
        "premium_entitlement_activated",
        "portal_opened",
        "subscription_cancel_requested",
        "decision_memory_viewed",
        "decision_memory_event_opened",
        "gm_targets_viewed",
        "gm_target_added",
        "gm_target_removed",
        "game_plan_item_opened",
        "notification_item_opened",
        "share_card_opened",
        "share_card_generated",
        "share_card_shared",
        "share_card_downloaded",
    }
)

LEGACY_EVENT_ALIASES: dict[str, str] = {
    "landing_visit": "landing_viewed",
    "account_created": "signup_completed",
    "league_imported": "league_import_completed",
    "player_quick_view_opened": "pqv_opened",
    "premium_checkout_started": "checkout_started",
    "premium_checkout_completed": "checkout_completed",
}

ALLOWED_PROP_KEYS: frozenset[str] = frozenset(
    {
        "account_state",
        "entitlement",
        "league_id",
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
    }
)

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
    }
)

FUNNEL_STEPS: tuple[tuple[str, str], ...] = (
    ("Landing", "landing_viewed"),
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
)

CORE_FEATURE_EVENTS: frozenset[str] = frozenset(
    {
        "trade_hub_opened",
        "pqv_opened",
        "waivers_opened",
        "my_team_opened",
        "trade_review_opened",
        "league_overview_opened",
        "first_game_plan_seen",
        "game_plan_item_opened",
        "notification_center_opened",
        "notification_item_opened",
        "decision_memory_viewed",
        "gm_targets_viewed",
        "gm_target_added",
    }
)

ROUTE_EVENT_MAP: dict[str, str] = {
    "dashboard": "dashboard_reached",
    "trade_hub": "trade_hub_opened",
    "waivers": "waivers_opened",
    "my_team": "my_team_opened",
    "rankings": "league_overview_opened",
    "premium": "premium_viewed",
    "gm_targets": "gm_targets_viewed",
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

SESSION_ANON_KEY = "_launch_analytics_anon_id"
SESSION_SCOPE_KEY = "_launch_analytics_account_scope"
SESSION_LEAGUE_KEY = "_launch_analytics_league_scope"


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
    clear_emitted()


def set_league_scope(state: MutableMapping[str, Any] | None, league_id: str) -> None:
    """Update league scope for subsequent events. Does not wipe account dedupe."""

    if not isinstance(state, MutableMapping):
        return
    state[SESSION_LEAGUE_KEY] = str(league_id or "").strip()


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


def _safe_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_props(props: Mapping[str, Any] | None) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in dict(props or {}).items():
        name = _safe_text(key).casefold()
        if not name or name in BLOCKED_PROP_KEYS:
            continue
        if name not in ALLOWED_PROP_KEYS:
            continue
        if isinstance(value, bool) or value is None:
            clean[name] = value
        elif isinstance(value, (int, float)):
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
    props: dict[str, Any] = {
        "account_state": account_state,
        "entitlement": ent.casefold() or "free",
    }
    if league:
        props["league_id"] = league
    if route:
        props["route"] = _safe_text(route)
    if source_surface:
        props["source_surface"] = _safe_text(source_surface)
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


def track_event(
    event: str,
    *,
    props: dict | None = None,
    once_key: str = "",
    state: MutableMapping[str, Any] | None = None,
) -> bool:
    """Append one analytics event when enabled. Never raises."""

    name = _safe_text(event)
    if name not in TRACKED_EVENTS:
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
        "ts": time.time(),
        "build": build_identity.resolve_build_identity().revision,
        "anon_id": anon,
        "account_hash": account_hash,
        "props": _safe_props(props),
    }
    try:
        target = analytics_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        with _LOCK:
            with target.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return True
    except Exception:
        return False


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
        once_key=f"{scope}:{league}:{route_key}",
        state=state,
    )


def normalize_event_name(event: str) -> str:
    name = _safe_text(event)
    return LEGACY_EVENT_ALIASES.get(name, name)


def read_event_counts(
    *,
    path: Path | None = None,
    since_ts: float | None = None,
) -> dict[str, int]:
    """Count events from JSONL; map legacy names onto canonical keys."""

    counts: dict[str, int] = {name: 0 for name in sorted(TRACKED_EVENTS)}
    target = path or analytics_path()
    if not target.is_file():
        return counts
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
                if since_ts is not None:
                    try:
                        if float(row.get("ts") or 0) < float(since_ts):
                            continue
                    except (TypeError, ValueError):
                        continue
                event = normalize_event_name(_safe_text(row.get("event")))
                if event in counts:
                    counts[event] += 1
                elif event:
                    counts[event] = counts.get(event, 0) + 1
    except OSError:
        return counts
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


def founder_ops_metrics(counts: Mapping[str, int] | None = None) -> dict[str, Any]:
    """Compact Founder Ops card metrics."""

    data = dict(counts or read_event_counts())
    return {
        "sessions_landing": int(data.get("landing_viewed") or 0),
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
        "retention_days": RETENTION_DAYS,
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

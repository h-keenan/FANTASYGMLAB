"""Founder-only operational health snapshot (read-only diagnostics).

Enabled exclusively by DYNASTYGM_FOUNDER_OPS. Never grants Premium, never
mutates football/auth/Stripe business state, and never exposes secrets.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from modules import app_config
from modules import build_identity
from modules import feedback
from modules import launch_analytics
from modules import performance
from modules import stripe_billing


FOUNDER_OPS_ENV = "DYNASTYGM_FOUNDER_OPS"
FOUNDER_OPS_PAGE_KEY = "founder_ops"
DEFAULT_WEBHOOK_HEALTH_URL = "https://fantasygm-lab-stripe-webhook.onrender.com/health"
HEARTBEAT_PATH = Path(
    os.environ.get(
        "DYNASTYGM_FOUNDER_OPS_HEARTBEAT_PATH",
        str(Path(__file__).resolve().parents[1] / "data" / "founder_ops_heartbeat.json"),
    )
).expanduser()
PUBLIC_PLAYER_DB = Path(__file__).resolve().parents[1] / "data" / "players.db"
SLEEPER_PLAYERS_CACHE = Path(__file__).resolve().parents[1] / "data" / "sleeper_players.json"
STALE_PUBLIC_PLAYER_HOURS = 36.0
STALE_SLEEPER_HOURS = 24.0
FEEDBACK_BACKLOG_WARN = 5


@dataclass(frozen=True)
class OpsWarning:
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class FounderOpsSnapshot:
    build_sha: str
    build_branch: str
    deploy_timestamp: str
    environment: str
    app_base_url: str
    performance_budget_status: str
    cache_status: str
    startup_timing: dict[str, Any]
    feedback_count: int
    feedback_open_count: int
    analytics_enabled: bool
    analytics_event_counts: dict[str, int]
    stripe_checkout_configured: bool
    stripe_mode: str
    stripe_webhook_configured: bool
    stripe_webhook_health: str
    last_stripe_webhook: str
    last_sleeper_refresh: str
    sleeper_cache_age_hours: float | None
    last_supabase_connection: str
    supabase_configured: bool
    public_player_age_hours: float | None
    process_uptime_ms: float
    analytics_funnel: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    analytics_metrics: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[OpsWarning, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["warnings"] = [asdict(item) for item in self.warnings]
        return payload


def founder_ops_enabled(
    *,
    environ: Mapping[str, Any] | None = None,
    secrets: Any = None,
) -> bool:
    """True only when the explicit founder-ops flag is set."""

    return app_config.config_bool(FOUNDER_OPS_ENV, environ=environ, secrets=secrets)


def founder_ops_authorized(
    session_state: Mapping[str, Any] | None,
    *,
    environ: Mapping[str, Any] | None = None,
    secrets: Any = None,
) -> bool:
    """Require both the process kill switch and server-sourced account capability."""

    if not founder_ops_enabled(environ=environ, secrets=secrets):
        return False
    state = session_state if isinstance(session_state, Mapping) else {}
    auth_user = state.get("auth_user") if isinstance(state.get("auth_user"), Mapping) else {}
    app_metadata = (
        auth_user.get("app_metadata")
        if isinstance(auth_user.get("app_metadata"), Mapping)
        else {}
    )
    # app_metadata is issued by Supabase Auth and cannot be edited through the
    # browser's user-metadata API. Profile and user-metadata fields are not
    # authorities because ordinary users can update their own account data.
    return app_metadata.get("founder_ops") is True


def _iso_from_mtime(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return "unavailable"


def _age_hours(path: Path) -> float | None:
    try:
        return round((time.time() - path.stat().st_mtime) / 3600.0, 2)
    except OSError:
        return None


def _environment_label(environ: Mapping[str, Any] | None = None) -> str:
    env = os.environ if environ is None else environ
    if app_config.is_managed_cloud_host(environ=env):
        service = str(env.get("RENDER_SERVICE_NAME") or env.get("RENDER_SERVICE_ID") or "render")
        return f"render:{service}"
    return "local"


def _deploy_timestamp(environ: Mapping[str, Any] | None = None) -> str:
    env = os.environ if environ is None else environ
    for key in ("RENDER_DEPLOYED_AT", "DYNASTYGM_DEPLOYED_AT"):
        value = str(env.get(key) or "").strip()
        if value:
            return value
    # Fall back to process start wall clock approximation via uptime.
    started = time.time() - (time.perf_counter() - performance.PROCESS_STARTED_AT)
    return datetime.fromtimestamp(started, tz=timezone.utc).isoformat()


def _feedback_counts() -> tuple[int, int]:
    path = Path(feedback.FEEDBACK_PATH)
    if not path.is_absolute():
        path = (Path(__file__).resolve().parents[1] / path).resolve()
    total = 0
    open_count = 0
    if not path.is_file():
        return 0, 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                total += 1
                try:
                    row = json.loads(text)
                except json.JSONDecodeError:
                    open_count += 1
                    continue
                status = str(row.get("status") or "new").strip().casefold()
                if status in {"", "new", "open", "unreviewed"}:
                    open_count += 1
    except OSError:
        return total, open_count
    return total, open_count


def _analytics_counts() -> tuple[bool, dict[str, int], list[dict[str, Any]], dict[str, Any]]:
    enabled = bool(launch_analytics.analytics_enabled() or launch_analytics.ENABLED)
    counts = launch_analytics.read_event_counts()
    funnel = launch_analytics.funnel_summary(counts)
    metrics = launch_analytics.founder_ops_metrics(counts)
    if not enabled:
        metrics = {**metrics, "status": "analytics_disabled"}
    return enabled, counts, funnel, metrics


def _read_heartbeat() -> dict[str, Any]:
    try:
        if not HEARTBEAT_PATH.is_file():
            return {}
        payload = json.loads(HEARTBEAT_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def record_ops_heartbeat(kind: str, *, ok: bool = True, detail: str = "") -> None:
    """Best-effort local heartbeat write for founder diagnostics."""

    name = str(kind or "").strip().casefold()
    if not name:
        return
    payload = _read_heartbeat()
    payload[name] = {
        "ok": bool(ok),
        "ts": datetime.now(timezone.utc).isoformat(),
        "detail": str(detail or "")[:160],
    }
    try:
        HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
        HEARTBEAT_PATH.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return


def _probe_webhook_health(url: str, *, timeout: float = 4.0) -> str:
    target = str(url or "").strip()
    if not target:
        return "not_configured"
    try:
        request = Request(
            target,
            method="GET",
            headers={"User-Agent": "FantasyGM-FounderOps/1.0"},
        )
        with urlopen(request, timeout=timeout) as response:
            body = response.read(120).decode("utf-8", "replace")
            if response.status == 200:
                return f"ok:{body[:60]}"
            return f"http_{response.status}"
    except HTTPError as exc:
        return f"http_{exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        return f"unreachable:{type(exc).__name__}"


def _cache_status(public_age: float | None, sleeper_age: float | None) -> str:
    if public_age is None and sleeper_age is None:
        return "missing_local_caches"
    issues = []
    if public_age is not None and public_age > STALE_PUBLIC_PLAYER_HOURS:
        issues.append("public_player_stale")
    if sleeper_age is not None and sleeper_age > STALE_SLEEPER_HOURS:
        issues.append("sleeper_stale")
    if issues:
        return "degraded:" + ",".join(issues)
    return "healthy"


def _performance_budget_status() -> str:
    # Report declared budgets + live process health. Full AppTest budgets run in CI.
    uptime_ms = round((time.perf_counter() - performance.PROCESS_STARTED_AT) * 1000, 1)
    return (
        f"declared:cold<=2500ms,warm<=750ms,protobuf<=520000; "
        f"process_uptime_ms={uptime_ms}"
    )


def collect_ops_snapshot(
    *,
    environ: Mapping[str, Any] | None = None,
    secrets: Any = None,
    session_state: Mapping[str, Any] | None = None,
) -> FounderOpsSnapshot:
    """Assemble a redacted founder ops snapshot from local evidence only."""

    env = os.environ if environ is None else environ
    identity = build_identity.resolve_build_identity(environment=env)
    config = app_config.redacted_config_status(environ=env, secrets=secrets)
    stripe_config = stripe_billing.load_stripe_config(environ=env, secrets=secrets)
    # Streamlit must never hold service-role; report anon/url presence only.
    supabase_configured = bool(config.get("supabase_configured"))
    feedback_total, feedback_open = _feedback_counts()
    analytics_enabled, analytics_counts, analytics_funnel, analytics_metrics = (
        _analytics_counts()
    )
    heartbeat = _read_heartbeat()
    public_age = _age_hours(PUBLIC_PLAYER_DB)
    sleeper_age = _age_hours(SLEEPER_PLAYERS_CACHE)
    webhook_health_url = str(env.get("DYNASTYGM_WEBHOOK_HEALTH_URL") or "").strip()
    if not webhook_health_url:
        webhook_health_url = DEFAULT_WEBHOOK_HEALTH_URL
    webhook_health = _probe_webhook_health(webhook_health_url)

    session = session_state if isinstance(session_state, Mapping) else {}
    profile_status = str(session.get("account_profile_status") or "").strip() or "unknown"
    profile_error = str(session.get("account_profile_error") or "").strip()
    last_supabase = heartbeat.get("supabase") if isinstance(heartbeat.get("supabase"), dict) else {}
    last_sleeper = heartbeat.get("sleeper") if isinstance(heartbeat.get("sleeper"), dict) else {}
    last_stripe = heartbeat.get("stripe_webhook") if isinstance(heartbeat.get("stripe_webhook"), dict) else {}

    if profile_status in {"ok", "ready", "loaded"}:
        supabase_connection = f"session:{profile_status}"
    elif profile_status == "error":
        supabase_connection = f"session_error:{profile_error[:80] or 'unknown'}"
    elif last_supabase.get("ts"):
        supabase_connection = f"heartbeat:{last_supabase.get('ts')}"
    elif supabase_configured:
        supabase_connection = "configured_unverified"
    else:
        supabase_connection = "not_configured"

    sleeper_refresh = (
        str(last_sleeper.get("ts") or "")
        or _iso_from_mtime(SLEEPER_PLAYERS_CACHE)
    )
    stripe_last = str(last_stripe.get("ts") or "unavailable_in_streamlit")

    startup = {
        "coordinator_phase": (session.get("_startup_coordinator") or {}).get("phase")
        if isinstance(session.get("_startup_coordinator"), dict)
        else None,
        "startup_complete": bool(session.get("_startup_coordinator_complete")),
        "process_uptime_ms": round(
            (time.perf_counter() - performance.PROCESS_STARTED_AT) * 1000, 1
        ),
    }

    warnings: list[OpsWarning] = []
    if feedback_open >= FEEDBACK_BACKLOG_WARN:
        warnings.append(
            OpsWarning(
                "feedback_backlog",
                "warning",
                f"{feedback_open} unreviewed local feedback rows (threshold {FEEDBACK_BACKLOG_WARN}).",
            )
        )
    if webhook_health.startswith("http_") or webhook_health.startswith("unreachable"):
        warnings.append(
            OpsWarning(
                "webhook_health",
                "warning",
                f"Webhook health probe reported {webhook_health}.",
            )
        )
    if not analytics_enabled:
        warnings.append(
            OpsWarning(
                "analytics_off",
                "info",
                "Launch analytics disabled (DYNASTYGM_LAUNCH_ANALYTICS unset).",
            )
        )
    cache_status = _cache_status(public_age, sleeper_age)
    if cache_status.startswith("degraded"):
        warnings.append(
            OpsWarning("cache_degradation", "warning", f"Cache status: {cache_status}."),
        )
    if public_age is not None and public_age > STALE_PUBLIC_PLAYER_HOURS:
        warnings.append(
            OpsWarning(
                "stale_public_player",
                "warning",
                f"Public player DB age {public_age}h exceeds {STALE_PUBLIC_PLAYER_HOURS}h.",
            )
        )
    if sleeper_age is not None and sleeper_age > STALE_SLEEPER_HOURS:
        warnings.append(
            OpsWarning(
                "stale_sleeper",
                "warning",
                f"Sleeper players cache age {sleeper_age}h exceeds {STALE_SLEEPER_HOURS}h.",
            )
        )
    if profile_status == "error":
        warnings.append(
            OpsWarning(
                "supabase_session_error",
                "warning",
                "Current session reports a Supabase profile lookup error.",
            )
        )
    if bool(session.get("_startup_route_render_failed")):
        warnings.append(
            OpsWarning(
                "startup_failure",
                "critical",
                "Startup route render failure flag is set for this session.",
            )
        )

    return FounderOpsSnapshot(
        build_sha=identity.revision,
        build_branch=identity.branch,
        deploy_timestamp=_deploy_timestamp(env),
        environment=_environment_label(env),
        app_base_url=str(config.get("app_base_url") or ""),
        performance_budget_status=_performance_budget_status(),
        cache_status=cache_status,
        startup_timing=startup,
        feedback_count=feedback_total,
        feedback_open_count=feedback_open,
        analytics_enabled=analytics_enabled,
        analytics_event_counts=analytics_counts,
        analytics_funnel=tuple(analytics_funnel),
        analytics_metrics=analytics_metrics,
        stripe_checkout_configured=bool(stripe_config.configured),
        stripe_mode=str(stripe_config.redacted.get("mode") or "unknown"),
        stripe_webhook_configured=bool(stripe_config.webhook_configured),
        stripe_webhook_health=webhook_health,
        last_stripe_webhook=stripe_last,
        last_sleeper_refresh=sleeper_refresh,
        sleeper_cache_age_hours=sleeper_age,
        last_supabase_connection=supabase_connection,
        supabase_configured=supabase_configured,
        public_player_age_hours=public_age,
        process_uptime_ms=float(startup["process_uptime_ms"]),
        warnings=tuple(warnings),
    )

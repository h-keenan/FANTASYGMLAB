"""Decision Memory — durable material transitions for Premium retention (#232).

Consumes DecisionChangeEvent rows already produced by lifecycle.
Does not generate football advice, recompute signatures, score, order, or Trust.

Graduated: default ON. Kill switch: DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY=0
"""

from __future__ import annotations

from datetime import datetime, timezone
from time import time
from typing import Any, Mapping, MutableMapping, Sequence

from modules import account_store
from modules import auth_supabase
from modules import decision_change_history as history
from modules import experimental_graduation
from modules import premium
from modules import recommendation_lifecycle as lifecycle


EXPERIMENT_ENV_KEY = "DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY"
EVENTS_TABLE = "decision_memory_events"
BASELINES_TABLE = "decision_memory_baselines"

RETENTION_DAYS = 90
MAX_EVENTS_PER_LEAGUE = 200

SESSION_CACHE_EVENTS_KEY = "_decision_memory_cache_events"
SESSION_CACHE_LEAGUE_KEY = "_decision_memory_cache_league"
SESSION_HYDRATED_KEY = "_decision_memory_hydrated_league"
SESSION_UNAVAILABLE_KEY = "_decision_memory_unavailable"


def _safe_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def experiment_enabled(*, environ: Mapping[str, str] | None = None) -> bool:
    """Graduated kill switch — default ON; set env to 0/false/off to disable."""

    return experimental_graduation.graduated_kill_switch_enabled(
        EXPERIMENT_ENV_KEY,
        environ=environ,
        default=experimental_graduation.GRADUATED_DEFAULT_ON,
    )

def clear_decision_memory_session(state: MutableMapping[str, Any]) -> None:
    """Drop in-memory Decision Memory cache on logout / account / league switch.

    Never deletes durable Supabase rows.
    """

    state.pop(SESSION_CACHE_EVENTS_KEY, None)
    state.pop(SESSION_CACHE_LEAGUE_KEY, None)
    state.pop(SESSION_HYDRATED_KEY, None)
    state.pop(SESSION_UNAVAILABLE_KEY, None)


def is_authenticated(session: Mapping[str, Any] | None) -> bool:
    return bool(auth_supabase.current_user_id(dict(session or {})))


def can_access_history(
    session: Mapping[str, Any] | None,
    *,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Premium + experiment + authenticated. Fail closed."""

    if not experiment_enabled(environ=environ):
        return False
    if not is_authenticated(session):
        return False
    return premium.is_premium_user(session_state=dict(session or {}))


def can_show_discovery(
    session: Mapping[str, Any] | None,
    *,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Free authenticated users may see a restrained discovery surface."""

    if not experiment_enabled(environ=environ):
        return False
    return is_authenticated(session)


def should_sync_durable(
    session: Mapping[str, Any] | None,
    *,
    environ: Mapping[str, str] | None = None,
) -> bool:
    if not can_access_history(session, environ=environ):
        return False
    if bool((session or {}).get(SESSION_UNAVAILABLE_KEY)):
        return False
    return True


def _priority_band(rank: int | None) -> str:
    if rank is None:
        return ""
    try:
        value = int(rank)
    except (TypeError, ValueError):
        return ""
    if value <= 0:
        return "top"
    if value == 1:
        return "primary"
    if value <= 3:
        return "near"
    return "background"


def event_to_row(event: history.DecisionChangeEvent, *, user_id: str) -> dict[str, Any]:
    created = datetime.fromtimestamp(float(event.timestamp), tz=timezone.utc).isoformat()
    return {
        "user_id": _safe_text(user_id),
        "event_id": _safe_text(event.event_id),
        "league_id": _safe_text(event.league_id),
        "roster_id": _safe_text(event.roster_id),
        "recommendation_id": _safe_text(event.recommendation_id),
        "event_type": _safe_text(event.reason),
        "transition": _safe_text(event.lifecycle_transition),
        "reason_code": _safe_text(event.reason),
        "category": _safe_text(event.category),
        "target_label": _safe_text(event.target_label),
        "player_id": _safe_text(event.player_id),
        "destination": _safe_text(event.destination),
        "previous_state": dict(event.previous_state or {}),
        "current_state": dict(event.current_state or {}),
        "previous_priority": event.previous_priority,
        "current_priority": event.current_priority,
        "priority_band": _priority_band(event.current_priority),
        "confidence_band": _safe_text(event.current_confidence_band),
        "scoring_format": _safe_text(event.scoring_format),
        "valuation_lens": _safe_text(event.valuation_lens),
        "summary_headline": _safe_text(event.summary_headline),
        "summary_detail": _safe_text(event.summary_detail),
        "why_label": _safe_text(event.why_label),
        "created_at": created,
    }


def row_to_event(row: Mapping[str, Any]) -> history.DecisionChangeEvent | None:
    created_raw = row.get("created_at")
    timestamp = time()
    if isinstance(created_raw, (int, float)):
        timestamp = float(created_raw)
    elif isinstance(created_raw, str) and created_raw.strip():
        try:
            timestamp = datetime.fromisoformat(
                created_raw.replace("Z", "+00:00")
            ).timestamp()
        except ValueError:
            timestamp = time()
    payload = {
        "event_id": row.get("event_id"),
        "recommendation_id": row.get("recommendation_id"),
        "league_id": row.get("league_id"),
        "roster_id": row.get("roster_id"),
        "timestamp": timestamp,
        "lifecycle_transition": row.get("transition") or "",
        "reason": row.get("reason_code") or row.get("event_type") or "",
        "category": row.get("category"),
        "target_label": row.get("target_label"),
        "player_id": row.get("player_id"),
        "destination": row.get("destination"),
        "previous_state": row.get("previous_state") or None,
        "current_state": row.get("current_state") or None,
        "previous_priority": row.get("previous_priority"),
        "current_priority": row.get("current_priority"),
        "previous_confidence_band": "",
        "current_confidence_band": row.get("confidence_band") or "",
        "scoring_format": row.get("scoring_format"),
        "valuation_lens": row.get("valuation_lens"),
        "summary_headline": row.get("summary_headline"),
        "summary_detail": row.get("summary_detail"),
        "why_label": row.get("why_label"),
    }
    return history.DecisionChangeEvent.from_dict(payload)


def _mark_unavailable(session: MutableMapping[str, Any], message: str = "") -> None:
    session[SESSION_UNAVAILABLE_KEY] = True
    if message and "does not exist" in message.casefold():
        session[SESSION_UNAVAILABLE_KEY] = True


def _resolve_config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(config, Mapping) and config:
        return dict(config)
    try:
        return auth_supabase.get_supabase_config(secrets=None)
    except Exception:
        return {}


def hydrate_session_from_durable(
    session: MutableMapping[str, Any],
    *,
    league_id: str,
    config: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Load durable baseline into session lifecycle keys when session is cold.

    Preserves #151 first-observation semantics: if no durable baseline exists,
    returns False and publish seeds without inventing events.
    """

    if not should_sync_durable(session, environ=environ):
        return False
    league_key = _safe_text(league_id)
    if not league_key:
        return False
    if _safe_text(session.get(SESSION_HYDRATED_KEY)) == league_key:
        return True
    prior_store = session.get(lifecycle.LIFECYCLE_INVENTORY_SIGNATURES_KEY)
    if isinstance(prior_store, Mapping) and prior_store:
        session[SESSION_HYDRATED_KEY] = league_key
        return True

    user_id = auth_supabase.current_user_id(session)
    access_token = auth_supabase.current_access_token(session)
    resolved_config = _resolve_config(config)
    if not auth_supabase.is_configured(resolved_config) or not user_id or not access_token:
        return False

    rows, error = account_store.fetch_rows(
        resolved_config,
        access_token,
        BASELINES_TABLE,
        user_id=user_id,
        extra_query=f"league_id=eq.{league_key}&limit=1",
        timing_label="decision_memory_baseline_read",
        timeout=8,
    )
    if error:
        if "does not exist" in error.casefold() or "schema cache" in error.casefold():
            _mark_unavailable(session, error)
        return False
    if not rows:
        session[SESSION_HYDRATED_KEY] = league_key
        return False

    row = rows[0]
    signatures = row.get("material_signatures") or {}
    snapshots = row.get("prior_snapshots") or {}
    if isinstance(signatures, Mapping) and signatures:
        session[lifecycle.LIFECYCLE_INVENTORY_SIGNATURES_KEY] = {
            str(k): str(v) for k, v in signatures.items()
        }
    if isinstance(snapshots, Mapping) and snapshots:
        session[history.DECISION_HISTORY_PRIOR_SNAPSHOT_KEY] = {
            str(k): dict(v) for k, v in snapshots.items() if isinstance(v, Mapping)
        }
    top_id = _safe_text(row.get("top_recommendation_id"))
    if top_id:
        session[lifecycle.LIFECYCLE_PRIOR_TOP_RECOMMENDATION_KEY] = top_id
    session[history.DECISION_HISTORY_ACCOUNT_SCOPE_KEY] = history._account_scope(session)
    session[history.DECISION_HISTORY_LEAGUE_SCOPE_KEY] = league_key
    session[SESSION_HYDRATED_KEY] = league_key
    return True


def persist_after_transition(
    session: MutableMapping[str, Any],
    *,
    new_events: Sequence[history.DecisionChangeEvent],
    signatures: Mapping[str, str],
    snapshots: Mapping[str, Mapping[str, Any]],
    league_id: str,
    roster_id: str = "",
    context_fingerprint: str = "",
    scoring_format: str = "",
    valuation_lens: str = "",
    top_recommendation_id: str = "",
    config: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Idempotent event upsert + baseline replace. Never blocks critical path hard."""

    result = {"wrote_events": 0, "wrote_baseline": False, "error": ""}
    if not should_sync_durable(session, environ=environ):
        return result
    user_id = auth_supabase.current_user_id(session)
    access_token = auth_supabase.current_access_token(session)
    league_key = _safe_text(league_id)
    if not user_id or not access_token or not league_key:
        return result
    resolved_config = _resolve_config(config)
    if not auth_supabase.is_configured(resolved_config):
        return result

    for event in new_events:
        if _safe_text(event.league_id) and _safe_text(event.league_id) != league_key:
            continue
        ok, error = account_store.upsert_row(
            resolved_config,
            access_token,
            EVENTS_TABLE,
            event_to_row(event, user_id=user_id),
            on_conflict="user_id,event_id",
        )
        if not ok:
            if "does not exist" in error.casefold() or "schema cache" in error.casefold():
                _mark_unavailable(session, error)
            result["error"] = error
            return result
        result["wrote_events"] += 1

    baseline_payload = {
        "user_id": user_id,
        "league_id": league_key,
        "roster_id": _safe_text(roster_id),
        "context_fingerprint": _safe_text(context_fingerprint),
        "scoring_format": _safe_text(scoring_format),
        "valuation_lens": _safe_text(valuation_lens),
        "material_signatures": {
            str(k): str(v) for k, v in dict(signatures or {}).items()
        },
        "prior_snapshots": {
            str(k): dict(v)
            for k, v in dict(snapshots or {}).items()
            if isinstance(v, Mapping)
        },
        "top_recommendation_id": _safe_text(top_recommendation_id),
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    ok, error = account_store.upsert_row(
        resolved_config,
        access_token,
        BASELINES_TABLE,
        baseline_payload,
        on_conflict="user_id,league_id",
    )
    if not ok:
        if "does not exist" in error.casefold() or "schema cache" in error.casefold():
            _mark_unavailable(session, error)
        result["error"] = error
        return result
    result["wrote_baseline"] = True

    # Best-effort retention prune — never delete the baseline row.
    _prune_expired_events(
        resolved_config,
        access_token,
        user_id=user_id,
        league_id=league_key,
    )
    # Invalidate read cache so Dashboard picks up durable rows.
    if _safe_text(session.get(SESSION_CACHE_LEAGUE_KEY)) == league_key:
        session.pop(SESSION_CACHE_EVENTS_KEY, None)
    return result


def _prune_expired_events(
    config: Mapping[str, Any],
    access_token: str,
    *,
    user_id: str,
    league_id: str,
) -> None:
    """Retain ~90 days and cap per league. Baseline table is untouched."""

    cutoff = datetime.now(tz=timezone.utc).timestamp() - (RETENTION_DAYS * 86400)
    cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()
    account_store.delete_rows(
        dict(config),
        access_token,
        EVENTS_TABLE,
        query=(
            f"user_id=eq.{_safe_text(user_id)}&league_id=eq.{_safe_text(league_id)}"
            f"&created_at=lt.{cutoff_iso}"
        ),
        timing_label="decision_memory_prune",
    )

    rows, error = account_store.fetch_rows(
        dict(config),
        access_token,
        EVENTS_TABLE,
        user_id=user_id,
        extra_query=(
            f"league_id=eq.{_safe_text(league_id)}"
            f"&select=event_id,created_at&order=created_at.desc"
            f"&offset={MAX_EVENTS_PER_LEAGUE}"
        ),
        timing_label="decision_memory_prune_overflow",
        timeout=8,
    )
    if error or not rows:
        return
    overflow_ids = [
        _safe_text(row.get("event_id"))
        for row in rows
        if _safe_text(row.get("event_id"))
    ]
    for event_id in overflow_ids[:50]:
        account_store.delete_rows(
            dict(config),
            access_token,
            EVENTS_TABLE,
            query=f"user_id=eq.{_safe_text(user_id)}&event_id=eq.{event_id}",
            timing_label="decision_memory_prune_row",
        )


def fetch_durable_events(
    session: MutableMapping[str, Any],
    *,
    league_id: str,
    limit: int = MAX_EVENTS_PER_LEAGUE,
    config: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    use_cache: bool = True,
) -> tuple[history.DecisionChangeEvent, ...]:
    """Fetch durable history for one league. Empty on any auth/entitlement/table miss."""

    if not can_access_history(session, environ=environ):
        return ()
    league_key = _safe_text(league_id)
    if not league_key:
        return ()
    if use_cache and _safe_text(session.get(SESSION_CACHE_LEAGUE_KEY)) == league_key:
        cached = session.get(SESSION_CACHE_EVENTS_KEY)
        if isinstance(cached, Sequence):
            events = []
            for row in cached:
                event = history.DecisionChangeEvent.from_dict(
                    row if isinstance(row, Mapping) else None
                )
                if event is not None:
                    events.append(event)
            return tuple(events)

    user_id = auth_supabase.current_user_id(session)
    access_token = auth_supabase.current_access_token(session)
    resolved_config = _resolve_config(config)
    if not auth_supabase.is_configured(resolved_config) or not user_id or not access_token:
        return ()

    cutoff = datetime.now(tz=timezone.utc).timestamp() - (RETENTION_DAYS * 86400)
    cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()
    rows, error = account_store.fetch_rows(
        resolved_config,
        access_token,
        EVENTS_TABLE,
        user_id=user_id,
        extra_query=(
            f"league_id=eq.{league_key}"
            f"&created_at=gte.{cutoff_iso}"
            f"&order=created_at.desc"
            f"&limit={max(1, min(int(limit), MAX_EVENTS_PER_LEAGUE))}"
        ),
        timing_label="decision_memory_history_fetch",
        timeout=8,
    )
    if error:
        if "does not exist" in error.casefold() or "schema cache" in error.casefold():
            _mark_unavailable(session, error)
        return ()

    events: list[history.DecisionChangeEvent] = []
    for row in rows:
        event = row_to_event(row if isinstance(row, Mapping) else {})
        if event is not None:
            events.append(event)
    session[SESSION_CACHE_EVENTS_KEY] = [event.to_dict() for event in events]
    session[SESSION_CACHE_LEAGUE_KEY] = league_key
    return tuple(events)


def merged_history_events(
    session: MutableMapping[str, Any],
    *,
    league_id: str,
    limit: int | None = None,
    include_durable: bool = True,
    environ: Mapping[str, str] | None = None,
) -> tuple[history.DecisionChangeEvent, ...]:
    """Merge session + durable events with event_id dedupe (durable wins age)."""

    session_events = list(
        history.list_decision_events(session, league_id=league_id)
    )
    by_id: dict[str, history.DecisionChangeEvent] = {
        event.event_id: event for event in session_events
    }
    if include_durable and can_access_history(session, environ=environ):
        for event in fetch_durable_events(
            session, league_id=league_id, environ=environ
        ):
            existing = by_id.get(event.event_id)
            if existing is None or float(event.timestamp) >= float(existing.timestamp):
                by_id[event.event_id] = event
    merged = sorted(by_id.values(), key=lambda event: event.timestamp, reverse=True)
    if limit is not None:
        return tuple(merged[: max(0, int(limit))])
    return tuple(merged)


def dashboard_recent_events(
    session: MutableMapping[str, Any],
    *,
    league_id: str,
    environ: Mapping[str, str] | None = None,
) -> tuple[history.DecisionChangeEvent, ...]:
    return merged_history_events(
        session,
        league_id=league_id,
        limit=history.MAX_DASHBOARD_EVENTS,
        environ=environ,
    )


def empty_state_copy(*, has_baseline: bool, premium_access: bool) -> tuple[str, str]:
    """Customer-facing empty copy — no technical jargon."""

    if not premium_access:
        return (
            "Decision Memory · Premium",
            "Premium keeps a durable history of how your GM priorities evolve after you leave and come back.",
        )
    if not has_baseline:
        return (
            "Decision Memory starts here",
            "Decision Memory starts learning from this point forward. Meaningful changes will appear here as your league evolves.",
        )
    return (
        "No meaningful changes",
        "No meaningful changes since your last check.",
    )


def cta_label_for_event(event: history.DecisionChangeEvent) -> str:
    destination = _safe_text(event.destination).casefold()
    if "trade" in destination:
        return "Open Trade Hub →"
    if "waiver" in destination:
        return "Open Waivers →"
    if "team" in destination or "roster" in destination:
        return "Open My Team →"
    if "player" in destination or _safe_text(event.player_id):
        return "Open player →"
    if "league" in destination:
        return "Open League Overview →"
    return "Open current context →"

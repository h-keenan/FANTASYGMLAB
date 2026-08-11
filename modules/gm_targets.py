"""GM Targets — durable league-scoped player watch preferences (#232).

Observes canonical football truth. Never modifies valuations, rankings,
recommendations, Trade Hub, waivers, Trust, confidence, or notifications.

Graduated: default ON. Kill switch: DYNASTYGM_EXPERIMENTAL_GM_TARGETS=0
Free: up to MAX_TARGETS_FREE. Premium: up to MAX_TARGETS_PREMIUM.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from time import time
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

from modules import account_store
from modules import auth_supabase
from modules import canonical_player_ranking as ranks
from modules import canonical_recommendation_narrative as narrative
from modules import decision_change_history as history
from modules import experimental_graduation
from modules import notification_center
from modules import performance
from modules import player_identity
from modules import premium


EXPERIMENT_ENV_KEY = "DYNASTYGM_EXPERIMENTAL_GM_TARGETS"
TARGETS_TABLE = "gm_targets"
MAX_TARGETS_PREMIUM = 50
MAX_TARGETS_FREE = 3
MAX_TARGETS_PER_LEAGUE = MAX_TARGETS_PREMIUM  # legacy alias

SESSION_CACHE_IDS_KEY = "_gm_targets_cache_ids"
SESSION_CACHE_ROWS_KEY = "_gm_targets_cache_rows"
SESSION_CACHE_LEAGUE_KEY = "_gm_targets_cache_league"
SESSION_HYDRATED_KEY = "_gm_targets_hydrated_league"
SESSION_UNAVAILABLE_KEY = "_gm_targets_unavailable"

FEATURE_LABEL = "GM Targets"
EXPERIMENTAL_LABEL = ""  # graduated — no experimental badge
SUPPORTING_COPY = (
    "Keep an eye on players you're considering buying, selling, adding, or monitoring."
)
ADD_ACTION_LABEL = "Add to GM Targets"
REMOVE_ACTION_LABEL = "Remove from GM Targets"


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


def clear_gm_targets_session(state: MutableMapping[str, Any]) -> None:
    """Drop in-memory GM Targets cache on logout / account / league switch.

    Never deletes durable Supabase rows.
    """

    state.pop(SESSION_CACHE_IDS_KEY, None)
    state.pop(SESSION_CACHE_ROWS_KEY, None)
    state.pop(SESSION_CACHE_LEAGUE_KEY, None)
    state.pop(SESSION_HYDRATED_KEY, None)
    state.pop(SESSION_UNAVAILABLE_KEY, None)


def is_authenticated(session: Mapping[str, Any] | None) -> bool:
    return bool(auth_supabase.current_user_id(dict(session or {})))


def max_targets_for_session(session: Mapping[str, Any] | None) -> int:
    if premium.is_premium_user(session_state=dict(session or {})):
        return MAX_TARGETS_PREMIUM
    return MAX_TARGETS_FREE


def can_access_targets(
    session: Mapping[str, Any] | None,
    *,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Authenticated Free or Premium may use Targets when feature is on."""

    if not experiment_enabled(environ=environ):
        return False
    return is_authenticated(session)


def can_show_discovery(
    session: Mapping[str, Any] | None,
    *,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Guests see a quiet discovery teaser when the feature is on."""

    if not experiment_enabled(environ=environ):
        return False
    return not is_authenticated(session)


def should_sync_durable(
    session: Mapping[str, Any] | None,
    *,
    environ: Mapping[str, str] | None = None,
) -> bool:
    if not can_access_targets(session, environ=environ):
        return False
    if bool((session or {}).get(SESSION_UNAVAILABLE_KEY)):
        return False
    return True


def _resolve_config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return an explicit config or the canonical auth_supabase loader.

    Fail-soft: missing/malformed secrets must never crash the app. Uses the
    same get_supabase_config(secrets=...) path as app._supabase_config — never
    a removed/renamed loader alias.
    """

    if isinstance(config, Mapping) and config:
        return dict(config)
    try:
        secrets = None
        try:
            import streamlit as st

            secrets = st.secrets
        except Exception:
            secrets = None
        return auth_supabase.get_supabase_config(secrets=secrets)
    except Exception:
        return {}


def _mark_unavailable(session: MutableMapping[str, Any], error: str = "") -> None:
    session[SESSION_UNAVAILABLE_KEY] = True
    if error:
        session["_gm_targets_last_error"] = account_store.customer_safe_error(
            error, context="GM Targets"
        )


def normalize_player_id(value: object) -> str:
    return player_identity.normalize_player_id(value)


@dataclass(frozen=True)
class GmTarget:
    """Preference row — identity only; football fields are enriched at display."""

    user_id: str
    league_id: str
    player_id: str
    source_surface: str = ""
    created_at: str = ""
    created_ts: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "league_id": self.league_id,
            "player_id": self.player_id,
            "source_surface": self.source_surface,
            "created_at": self.created_at,
            "created_ts": self.created_ts,
        }


def _parse_created_ts(value: object) -> float:
    text = _safe_text(value)
    if not text:
        return 0.0
    try:
        cleaned = text.replace("Z", "+00:00")
        return float(datetime.fromisoformat(cleaned).timestamp())
    except Exception:
        try:
            return float(text)
        except (TypeError, ValueError):
            return 0.0


def _positive_rank(value: object) -> int | None:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def row_to_target(row: Mapping[str, Any] | None) -> GmTarget | None:
    if not isinstance(row, Mapping):
        return None
    user_id = _safe_text(row.get("user_id"))
    league_id = _safe_text(row.get("league_id"))
    player_id = normalize_player_id(row.get("player_id"))
    if not user_id or not league_id or not player_id:
        return None
    created_at = _safe_text(row.get("created_at"))
    return GmTarget(
        user_id=user_id,
        league_id=league_id,
        player_id=player_id,
        source_surface=_safe_text(row.get("source_surface")),
        created_at=created_at,
        created_ts=_parse_created_ts(created_at) or float(row.get("created_ts") or 0.0),
    )


def _cache_targets(
    session: MutableMapping[str, Any],
    *,
    league_id: str,
    targets: Sequence[GmTarget],
) -> None:
    league_key = _safe_text(league_id)
    session[SESSION_CACHE_LEAGUE_KEY] = league_key
    session[SESSION_HYDRATED_KEY] = league_key
    session[SESSION_CACHE_ROWS_KEY] = [t.to_dict() for t in targets]
    session[SESSION_CACHE_IDS_KEY] = {t.player_id for t in targets}


def cached_target_ids(
    session: Mapping[str, Any] | None,
    *,
    league_id: str,
) -> frozenset[str]:
    if not isinstance(session, Mapping):
        return frozenset()
    if _safe_text(session.get(SESSION_CACHE_LEAGUE_KEY)) != _safe_text(league_id):
        return frozenset()
    raw = session.get(SESSION_CACHE_IDS_KEY)
    if isinstance(raw, (set, frozenset, list, tuple)):
        return frozenset(
            normalize_player_id(item) for item in raw if normalize_player_id(item)
        )
    return frozenset()


def is_targeted(
    session: Mapping[str, Any] | None,
    *,
    league_id: str,
    player_id: str,
) -> bool:
    pid = normalize_player_id(player_id)
    if not pid:
        return False
    return pid in cached_target_ids(session, league_id=league_id)


def fetch_targets_for_league(
    session: MutableMapping[str, Any],
    *,
    league_id: str,
    config: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    force: bool = False,
) -> tuple[GmTarget, ...]:
    """One list fetch supports workspace + membership cache. Soft-fails missing table."""

    league_key = _safe_text(league_id)
    if not league_key or not should_sync_durable(session, environ=environ):
        return ()

    if (
        not force
        and _safe_text(session.get(SESSION_HYDRATED_KEY)) == league_key
        and _safe_text(session.get(SESSION_CACHE_LEAGUE_KEY)) == league_key
    ):
        raw = session.get(SESSION_CACHE_ROWS_KEY) or []
        return tuple(
            t
            for t in (
                row_to_target(row if isinstance(row, Mapping) else None) for row in raw
            )
            if t is not None
        )

    user_id = auth_supabase.current_user_id(session)
    access_token = auth_supabase.current_access_token(session)
    if not user_id or not access_token:
        return ()

    resolved = _resolve_config(config)
    if not auth_supabase.is_configured(resolved):
        return ()

    with performance.time_block("gm_targets_list_fetch", category="supabase"):
        rows, error = account_store.fetch_rows(
            resolved,
            access_token,
            TARGETS_TABLE,
            user_id=user_id,
            extra_query=(
                f"league_id=eq.{league_key}"
                "&select=user_id,league_id,player_id,source_surface,created_at"
                "&order=created_at.desc"
            ),
            timing_label="gm_targets_list_fetch",
        )
    if error:
        if "does not exist" in error.casefold() or "schema cache" in error.casefold():
            _mark_unavailable(session, error)
            return ()
        session["_gm_targets_last_error"] = account_store.customer_safe_error(
            error, context="GM Targets"
        )
        return ()

    targets = tuple(
        t
        for t in (row_to_target(row) for row in rows)
        if t is not None and t.league_id == league_key
    )
    _cache_targets(session, league_id=league_key, targets=targets)
    return targets


def ensure_membership_cache(
    session: MutableMapping[str, Any],
    *,
    league_id: str,
    config: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> frozenset[str]:
    """Lazy membership hydrate for PQV — one list fetch, not per-player reads."""

    if not should_sync_durable(session, environ=environ):
        return frozenset()
    fetch_targets_for_league(
        session, league_id=league_id, config=config, environ=environ, force=False
    )
    return cached_target_ids(session, league_id=league_id)


def add_target(
    session: MutableMapping[str, Any],
    *,
    league_id: str,
    player_id: str,
    source_surface: str = "",
    config: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Idempotent add. Preference mutation only — never invalidates football caches."""

    result = {"ok": False, "error": "", "duplicate": False, "at_cap": False}
    if not should_sync_durable(session, environ=environ):
        result["error"] = "GM Targets is not available on this plan."
        return result

    league_key = _safe_text(league_id)
    pid = normalize_player_id(player_id)
    if not league_key or not pid:
        result["error"] = "Could not save that player target."
        return result

    existing = fetch_targets_for_league(
        session, league_id=league_key, config=config, environ=environ
    )
    if any(t.player_id == pid for t in existing):
        result["ok"] = True
        result["duplicate"] = True
        return result
    if len(existing) >= max_targets_for_session(session):
        cap = max_targets_for_session(session)
        result["at_cap"] = True
        result["error"] = (
            f"GM Targets is full for this league ({cap}). "
            "Remove a target before adding another."
            + (
                " Upgrade to Premium for a larger board."
                if cap <= MAX_TARGETS_FREE
                else ""
            )
        )
        return result

    user_id = auth_supabase.current_user_id(session)
    access_token = auth_supabase.current_access_token(session)
    if not user_id or not access_token:
        result["error"] = "Sign in to save GM Targets."
        return result

    resolved = _resolve_config(config)
    payload = {
        "user_id": user_id,
        "league_id": league_key,
        "player_id": pid,
        "source_surface": _safe_text(source_surface)[:64],
    }
    with performance.time_block("gm_targets_add", category="supabase"):
        ok, error = account_store.upsert_row(
            resolved,
            access_token,
            TARGETS_TABLE,
            payload,
            on_conflict="user_id,league_id,player_id",
        )
    if not ok:
        if "does not exist" in error.casefold() or "schema cache" in error.casefold():
            _mark_unavailable(session, error)
        result["error"] = account_store.customer_safe_error(error, context="GM Targets")
        return result

    merged = list(existing) + [
        GmTarget(
            user_id=user_id,
            league_id=league_key,
            player_id=pid,
            source_surface=_safe_text(source_surface)[:64],
            created_at="",
            created_ts=time(),
        )
    ]
    _cache_targets(session, league_id=league_key, targets=merged)
    result["ok"] = True
    try:
        from modules import launch_analytics

        launch_analytics.track_event(
            "gm_target_added",
            props=launch_analytics.build_context_props(
                session,
                league_id=league_key,
                source_surface=_safe_text(source_surface) or "gm_targets",
            ),
            state=session if isinstance(session, dict) else None,
        )
    except Exception:
        pass
    return result


def remove_target(
    session: MutableMapping[str, Any],
    *,
    league_id: str,
    player_id: str,
    config: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Delete preference only — never touches Decision Memory or football caches."""

    result = {"ok": False, "error": ""}
    if not should_sync_durable(session, environ=environ):
        result["error"] = "GM Targets is not available on this plan."
        return result

    league_key = _safe_text(league_id)
    pid = normalize_player_id(player_id)
    if not league_key or not pid:
        result["error"] = "Could not remove that player target."
        return result

    user_id = auth_supabase.current_user_id(session)
    access_token = auth_supabase.current_access_token(session)
    if not user_id or not access_token:
        result["error"] = "Sign in to manage GM Targets."
        return result

    resolved = _resolve_config(config)
    query = f"user_id=eq.{user_id}&league_id=eq.{league_key}&player_id=eq.{pid}"
    with performance.time_block("gm_targets_remove", category="supabase"):
        ok, error = account_store.delete_rows(
            resolved,
            access_token,
            TARGETS_TABLE,
            query=query,
            timing_label="gm_targets_remove",
        )
    if not ok:
        if "does not exist" in error.casefold() or "schema cache" in error.casefold():
            _mark_unavailable(session, error)
        result["error"] = account_store.customer_safe_error(error, context="GM Targets")
        return result

    remaining = [
        t
        for t in (
            row_to_target(row if isinstance(row, Mapping) else None)
            for row in (session.get(SESSION_CACHE_ROWS_KEY) or [])
        )
        if t is not None and t.player_id != pid
    ]
    if _safe_text(session.get(SESSION_CACHE_LEAGUE_KEY)) != league_key:
        remaining = [
            t
            for t in fetch_targets_for_league(
                session,
                league_id=league_key,
                config=config,
                environ=environ,
                force=True,
            )
            if t.player_id != pid
        ]
    _cache_targets(session, league_id=league_key, targets=remaining)
    result["ok"] = True
    try:
        from modules import launch_analytics

        launch_analytics.track_event(
            "gm_target_removed",
            props=launch_analytics.build_context_props(
                session,
                league_id=league_key,
                source_surface="gm_targets",
            ),
            state=session if isinstance(session, dict) else None,
        )
    except Exception:
        pass
    return result


def ownership_status(
    player_id: str,
    *,
    my_roster_player_ids: Iterable[str] | None = None,
    owner_by_player_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> str:
    """Resolve ownership from shared roster context — no provider calls."""

    pid = normalize_player_id(player_id)
    if not pid:
        return "Status unknown"
    mine = {normalize_player_id(item) for item in (my_roster_player_ids or ())}
    if pid in mine:
        return "On your roster"
    owner_map = owner_by_player_id or {}
    owner = owner_map.get(pid)
    if owner is None:
        for key, value in owner_map.items():
            if normalize_player_id(key) == pid:
                owner = value
                break
    if isinstance(owner, Mapping):
        team = _safe_text(owner.get("owner_team_name") or owner.get("team_name"))
        if team:
            return f"Rostered by {team}"
        if _safe_text(owner.get("owner_roster_id") or owner.get("roster_id")):
            return "Rostered by another manager"
        return "Rostered by another manager"
    if owner_by_player_id is not None:
        return "Free agent / waiver"
    return "Status unknown"


def format_rank_line(
    player_row: Mapping[str, Any] | None,
    *,
    scoring_format: str = "",
) -> str:
    if not isinstance(player_row, Mapping):
        return "Rank unavailable"
    overall = player_row.get(ranks.OVERALL_RANK_COLUMN, player_row.get("overall_rank"))
    position_rank = player_row.get(
        ranks.POSITION_RANK_COLUMN, player_row.get("position_rank")
    )
    position = player_row.get("position")
    compact = ranks.format_compact_rank(overall, position_rank, position)
    fmt = _safe_text(scoring_format) or _safe_text(
        player_row.get(ranks.RANK_FORMAT_COLUMN)
    )
    if fmt and compact != "Rank unavailable":
        return f"{compact} · {fmt}"
    return compact


def resolve_canonical_action(
    session: Mapping[str, Any] | None,
    *,
    player_id: str,
    league_id: str,
    roster_id: str = "",
) -> dict[str, str]:
    """Return existing canonical advice only — never synthesize BUY/HOLD/etc."""

    empty = {"action": "", "summary": "", "destination": "", "mode": "none"}
    pid = normalize_player_id(player_id)
    league_key = _safe_text(league_id)
    if not pid or not league_key:
        return empty

    bound = narrative.resolve_narrative_for_player(
        session,
        player_id=pid,
        league_id=league_key,
        roster_id=roster_id,
    )
    if bound is not None and bound.is_active_recommendation:
        presentation = bound.pqv_presentation()
        return {
            "action": _safe_text(presentation.get("action")),
            "summary": _safe_text(presentation.get("summary")),
            "destination": _safe_text(bound.source_surface) or "dashboard",
            "mode": "active",
        }

    snapshot = (session or {}).get(notification_center.ACTIVITY_INBOX_SNAPSHOT_KEY)
    records: Sequence[Any] = ()
    if isinstance(snapshot, Mapping):
        if _safe_text(snapshot.get("league_id")) in {"", league_key}:
            raw_records = snapshot.get("records") or ()
            if isinstance(raw_records, Sequence):
                records = raw_records
    for record in records:
        if not isinstance(record, Mapping):
            continue
        record_pid = normalize_player_id(
            record.get("player_id") or record.get("route_player_id")
        )
        narrative_payload = record.get("recommendation_narrative")
        narrative_pids: tuple[str, ...] = ()
        if isinstance(narrative_payload, Mapping):
            narrative_pids = tuple(
                normalize_player_id(item)
                for item in (narrative_payload.get("player_ids") or ())
            )
        if record_pid != pid and pid not in narrative_pids:
            continue
        action = ""
        summary = ""
        if isinstance(narrative_payload, Mapping):
            if not bool(narrative_payload.get("is_active_recommendation", True)):
                continue
            action = _safe_text(narrative_payload.get("action"))
            summary = _safe_text(narrative_payload.get("reason"))
        action = action or _safe_text(record.get("value"))
        summary = summary or _safe_text(record.get("note") or record.get("body"))
        if not action and not summary:
            continue
        return {
            "action": action,
            "summary": summary,
            "destination": _safe_text(
                record.get("destination") or record.get("route_key")
            ),
            "mode": "active",
        }
    return empty


def material_change_for_player(
    session: Mapping[str, Any] | None,
    *,
    player_id: str,
    league_id: str,
) -> dict[str, str]:
    """Surface an existing DecisionChangeEvent for this player — no new history."""

    empty = {"label": "", "detail": "", "destination": "", "event_id": ""}
    pid = normalize_player_id(player_id)
    if not pid:
        return empty
    for event in history.list_decision_events(session, league_id=league_id, limit=40):
        if normalize_player_id(event.player_id) != pid:
            continue
        return {
            "label": _safe_text(event.summary_headline) or "Material change",
            "detail": _safe_text(event.summary_detail),
            "destination": _safe_text(event.destination),
            "event_id": _safe_text(event.event_id),
        }
    return empty


@dataclass(frozen=True)
class EnrichedTargetCard:
    player_id: str
    name: str
    position: str
    team: str
    image_player_id: str
    rank_line: str
    ownership: str
    action: str
    action_summary: str
    action_destination: str
    material_label: str
    material_detail: str
    material_destination: str
    overall_rank: int | None
    created_ts: float
    has_action: bool
    has_material_change: bool


def enrich_target(
    target: GmTarget,
    *,
    session: Mapping[str, Any] | None,
    player_row: Mapping[str, Any] | None,
    my_roster_player_ids: Iterable[str] | None = None,
    owner_by_player_id: Mapping[str, Mapping[str, Any]] | None = None,
    scoring_format: str = "",
    roster_id: str = "",
) -> EnrichedTargetCard:
    row = player_row if isinstance(player_row, Mapping) else {}
    action = resolve_canonical_action(
        session,
        player_id=target.player_id,
        league_id=target.league_id,
        roster_id=roster_id,
    )
    change = material_change_for_player(
        session, player_id=target.player_id, league_id=target.league_id
    )
    overall = _positive_rank(
        row.get(ranks.OVERALL_RANK_COLUMN, row.get("overall_rank"))
    )

    return EnrichedTargetCard(
        player_id=target.player_id,
        name=_safe_text(row.get("name"), "Player"),
        position=_safe_text(row.get("position")).upper(),
        team=_safe_text(row.get("team")),
        image_player_id=target.player_id,
        rank_line=format_rank_line(row, scoring_format=scoring_format),
        ownership=ownership_status(
            target.player_id,
            my_roster_player_ids=my_roster_player_ids,
            owner_by_player_id=owner_by_player_id,
        ),
        action=_safe_text(action.get("action")),
        action_summary=_safe_text(action.get("summary")),
        action_destination=_safe_text(action.get("destination")),
        material_label=_safe_text(change.get("label")),
        material_detail=_safe_text(change.get("detail")),
        material_destination=_safe_text(change.get("destination")),
        overall_rank=overall,
        created_ts=float(target.created_ts or 0.0),
        has_action=bool(_safe_text(action.get("action"))),
        has_material_change=bool(_safe_text(change.get("label"))),
    )


def sort_enriched_targets(
    cards: Sequence[EnrichedTargetCard],
) -> tuple[EnrichedTargetCard, ...]:
    """Presentation-only ordering. Not a recommendation score.

    Order:
      1. currently actionable canonical recommendation
      2. material change present
      3. canonical OVR rank ascending (missing last)
      4. recently added (created_ts desc)
    """

    def key(card: EnrichedTargetCard) -> tuple:
        rank = card.overall_rank if card.overall_rank is not None else 10_000_000
        return (
            0 if card.has_action else 1,
            0 if card.has_material_change else 1,
            rank,
            -float(card.created_ts or 0.0),
            card.player_id,
        )

    return tuple(sorted(cards, key=key))


def discovery_copy() -> tuple[str, str]:
    return (
        FEATURE_LABEL,
        "Sign in to save a short Free board, or upgrade to Premium for a full Targets list.",
    )


def build_owner_map_from_roster_player_map(
    roster_player_map: Mapping[Any, Any] | None,
    *,
    roster_team_names: Mapping[Any, str] | None = None,
) -> dict[str, dict[str, str]]:
    """Flatten shared roster_player_map into player_id -> owner metadata."""

    owner_map: dict[str, dict[str, str]] = {}
    if not isinstance(roster_player_map, Mapping):
        return owner_map
    names = roster_team_names or {}
    for roster_id, players in roster_player_map.items():
        roster_key = _safe_text(roster_id)
        team_name = _safe_text(names.get(roster_id) or names.get(roster_key))
        player_ids: Iterable[Any]
        if isinstance(players, Mapping):
            player_ids = players.keys()
        elif isinstance(players, (list, tuple, set)):
            player_ids = players
        else:
            continue
        for raw_pid in player_ids:
            pid = normalize_player_id(raw_pid)
            if not pid:
                continue
            owner_map[pid] = {
                "owner_roster_id": roster_key,
                "owner_team_name": team_name,
            }
    return owner_map

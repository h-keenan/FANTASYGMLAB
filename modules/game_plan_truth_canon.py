"""Canonical Game Plan football inputs (#239 / phantom-strategy pass).

Locks team_strategy and base pick_score_multiplier before the first package
fingerprint so post-usable-auth / presentation reruns cannot drift truth and
force package MISS / trade rebuilds.

``team_strategy`` (Contender / Retool / Rebuild / Tank, plus Auto inference)
is intentionally separate from ``league_type`` (Dynasty / Rebuild / Non-Dynasty
valuation lens). Changing the evaluation lens must not rewrite team strategy.

team_strategy may change only when:
- the user explicitly changes the My Team strategy/team-scope control;
- an authoritative persisted preference is restored into an uninitialized session;
- league/roster scope changes and a new inferred or persisted initial value is required;
- another documented canonical football-state transition (logout, account switch).

It must not change because of navigation, Dashboard rerender, lens mount, sidebar
remount, shell enrichment, cache lookup, or session-integrity repair of valid state.

Presentation and identity-shell defaults must not overwrite a locked value.
Explicit user strategy changes replace the lock and invalidate once.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, MutableMapping
from hashlib import sha256
from typing import Any

from modules import performance


CANON_STATE_KEY = "_game_plan_truth_canon"
CANON_STRATEGY_FIELD = "team_strategy"
CANON_PICK_MULT_FIELD = "pick_score_multiplier"
CANON_AUTO_STRATEGY_FIELD = "auto_team_strategy"
CANON_OVERRIDE_FIELD = "team_strategy_override"
CANON_LABEL_FIELD = "team_strategy_label"
CANON_TRUTH_SIG_FIELD = "truth_signature"
CANON_LEAGUE_FIELD = "league_id"
CANON_ROSTER_FIELD = "roster_id"
MUTATION_LOG_KEY = "_game_plan_truth_mutation_log"
MAX_MUTATION_LOG = 16

MUTATION_EXPLICIT_USER = "explicit_user_action"
MUTATION_CANONICAL = "canonical_resolution"
MUTATION_PRESENTATION = "presentation_side_effect"


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _digest(value: Any) -> str:
    payload = {"v": value}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(encoded.encode("utf-8")).hexdigest()[:8]


def stable_pick_score_multiplier(value: Any) -> str:
    """Stable scalar string for fingerprints (avoids float repr drift)."""

    try:
        return f"{float(value):.8f}"
    except (TypeError, ValueError):
        return "0.00000000"


def build_truth_signature(
    *,
    league_id: object = "",
    roster_id: object = "",
    score_field: object = "",
    league_settings_key: object = "",
    prepared_frame_signature: object = "",
) -> str:
    return sha256(
        json.dumps(
            {
                "league_id": _safe_text(league_id),
                "roster_id": _safe_text(roster_id),
                "score_field": _safe_text(score_field),
                "league_settings_key": _safe_text(league_settings_key),
                "prepared_frame_signature": _safe_text(prepared_frame_signature),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:24]


def _store(session_state: MutableMapping[str, Any]) -> dict[str, Any]:
    raw = session_state.get(CANON_STATE_KEY)
    if not isinstance(raw, dict):
        raw = {}
        session_state[CANON_STATE_KEY] = raw
    return raw


def clear_canon(session_state: MutableMapping[str, Any]) -> None:
    session_state.pop(CANON_STATE_KEY, None)


def get_canon(session_state: Mapping[str, Any] | None) -> dict[str, Any] | None:
    raw = (session_state or {}).get(CANON_STATE_KEY)
    return dict(raw) if isinstance(raw, dict) and raw.get(CANON_STRATEGY_FIELD) else None


def presentation_strategy_view(
    session_state: Mapping[str, Any] | None,
    *,
    inferred_strategy: str,
    inferred_label: str = "",
    inferred_auto_strategy: str = "",
    inferred_override: str = "Auto",
) -> dict[str, str]:
    """Return chrome values without allowing presentation to mutate user truth.

    The inferred values are only authoritative before the canonical strategy has
    been locked. Once a canon exists, explicit/persisted truth owns the active
    strategy while the inferred value remains available only as an Auto hint.
    """

    inferred = _safe_text(inferred_strategy, "retool") or "retool"
    canon = get_canon(session_state)
    if not canon:
        return {
            CANON_STRATEGY_FIELD: inferred,
            CANON_LABEL_FIELD: _safe_text(inferred_label) or inferred,
            CANON_AUTO_STRATEGY_FIELD: _safe_text(inferred_auto_strategy) or inferred,
            CANON_OVERRIDE_FIELD: _safe_text(inferred_override, "Auto") or "Auto",
        }
    active = _safe_text(canon.get(CANON_STRATEGY_FIELD), inferred) or inferred
    return {
        CANON_STRATEGY_FIELD: active,
        CANON_LABEL_FIELD: _safe_text(canon.get(CANON_LABEL_FIELD)) or active,
        CANON_AUTO_STRATEGY_FIELD: (
            _safe_text(canon.get(CANON_AUTO_STRATEGY_FIELD))
            or _safe_text(inferred_auto_strategy)
            or inferred
        ),
        CANON_OVERRIDE_FIELD: (
            _safe_text(canon.get(CANON_OVERRIDE_FIELD), "Auto") or "Auto"
        ),
    }


def emit_field_mutation(
    session_state: MutableMapping[str, Any] | None,
    *,
    field: str,
    old_value: Any,
    new_value: Any,
    writer: str,
    mutation_kind: str,
    league_id: object = "",
) -> None:
    """Bounded mutation provenance. Printed when DYNASTYGM_STARTUP=1."""

    if old_value == new_value:
        return
    explicit = mutation_kind == MUTATION_EXPLICIT_USER
    payload: dict[str, Any] = {
        "kind": "game_plan_truth_mutation",
        "field": performance._safe_label(field)[:48],
        "old_digest": _digest(old_value),
        "new_digest": _digest(new_value),
        "writer": performance._safe_label(writer)[:64],
        "mutation_kind": performance._safe_label(mutation_kind)[:32],
        "explicit_user_action": explicit,
        "league_id_digest": _digest(_safe_text(league_id)) if _safe_text(league_id) else "",
    }
    if session_state is not None:
        try:
            from modules import auth_restore_lifecycle
            from modules import auth_storage_handshake

            payload["startup_session_id"] = _safe_text(
                session_state.get(auth_restore_lifecycle.STARTUP_SESSION_ID_KEY)
            )[:16]
            payload["startup_run_number"] = int(
                session_state.get(auth_restore_lifecycle.STARTUP_RUN_NUMBER_KEY) or 0
            )
            payload["run_cause"] = performance._safe_label(
                auth_storage_handshake.classify_script_run_cause(session_state)
            )[:48]
        except Exception:
            payload["startup_run_number"] = 0
            payload["run_cause"] = "unknown"
        log = session_state.get(MUTATION_LOG_KEY)
        if not isinstance(log, list):
            log = []
        log.append(payload)
        session_state[MUTATION_LOG_KEY] = log[-MAX_MUTATION_LOG:]
    try:
        from modules import startup_cold_path

        if startup_cold_path.startup_diagnostics_enabled():
            print("DYNASTYGM_STARTUP " + json.dumps(payload, sort_keys=True), flush=True)
    except Exception:
        pass


def mutation_log(session_state: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    raw = (session_state or {}).get(MUTATION_LOG_KEY)
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def same_team_scope(
    canon: Mapping[str, Any] | None,
    *,
    league_id: object = "",
    roster_id: object = "",
) -> bool:
    """True when locked strategy belongs to this league/roster pair."""

    if not canon:
        return False
    wanted_league = _safe_text(league_id)
    wanted_roster = _safe_text(roster_id)
    stored_league = _safe_text(canon.get(CANON_LEAGUE_FIELD))
    stored_roster = _safe_text(canon.get(CANON_ROSTER_FIELD))
    if stored_league and wanted_league and stored_league != wanted_league:
        return False
    if stored_roster and wanted_roster and stored_roster != wanted_roster:
        return False
    if stored_league or stored_roster:
        return True
    return False


def override_is_explicit_user_change(prior_override: object, strategy_choice: object) -> bool:
    """My Team selector change — not a later Auto inference of active strategy."""

    return _safe_text(prior_override, "Auto") != _safe_text(strategy_choice, "Auto")


def lock_canonical_inputs(
    session_state: MutableMapping[str, Any],
    *,
    truth_signature: str,
    team_strategy: str,
    team_strategy_label: str = "",
    auto_team_strategy: str = "",
    team_strategy_override: str = "Auto",
    pick_score_multiplier: Any,
    writer: str,
    mutation_kind: str = MUTATION_CANONICAL,
    force: bool = False,
    league_id: object = "",
    roster_id: object = "",
) -> dict[str, Any]:
    """Lock football inputs for one team scope. Presentation cannot replace."""

    store = _store(session_state)
    strategy = _safe_text(team_strategy, "retool") or "retool"
    pick = stable_pick_score_multiplier(pick_score_multiplier)
    existing_sig = _safe_text(store.get(CANON_TRUTH_SIG_FIELD))
    same_scope = same_team_scope(
        store if store.get(CANON_STRATEGY_FIELD) else None,
        league_id=league_id,
        roster_id=roster_id,
    )
    if (
        not force
        and store.get(CANON_STRATEGY_FIELD)
        and (
            same_scope
            or (existing_sig and existing_sig == _safe_text(truth_signature))
        )
    ):
        # Same team scope or same truth — keep lock; ignore presentation noise.
        return dict(store)

    old_strategy = store.get(CANON_STRATEGY_FIELD)
    old_pick = store.get(CANON_PICK_MULT_FIELD)
    if old_strategy is not None and old_strategy != strategy:
        emit_field_mutation(
            session_state,
            field=CANON_STRATEGY_FIELD,
            old_value=old_strategy,
            new_value=strategy,
            writer=writer,
            mutation_kind=mutation_kind,
            league_id=league_id or store.get(CANON_LEAGUE_FIELD),
        )
    if old_pick is not None and old_pick != pick:
        emit_field_mutation(
            session_state,
            field=CANON_PICK_MULT_FIELD,
            old_value=old_pick,
            new_value=pick,
            writer=writer,
            mutation_kind=mutation_kind,
            league_id=league_id or store.get(CANON_LEAGUE_FIELD),
        )

    store[CANON_TRUTH_SIG_FIELD] = _safe_text(truth_signature)
    store[CANON_STRATEGY_FIELD] = strategy
    store[CANON_LABEL_FIELD] = _safe_text(team_strategy_label) or strategy
    store[CANON_AUTO_STRATEGY_FIELD] = _safe_text(auto_team_strategy) or strategy
    store[CANON_OVERRIDE_FIELD] = _safe_text(team_strategy_override, "Auto") or "Auto"
    store[CANON_PICK_MULT_FIELD] = pick
    if _safe_text(league_id):
        store[CANON_LEAGUE_FIELD] = _safe_text(league_id)
    if _safe_text(roster_id):
        store[CANON_ROSTER_FIELD] = _safe_text(roster_id)
    store["locked_at_mono"] = time.perf_counter()
    store["writer"] = performance._safe_label(writer)[:64]
    store["mutation_kind"] = performance._safe_label(mutation_kind)[:32]
    session_state[CANON_STATE_KEY] = store
    return dict(store)


def apply_explicit_strategy_change(
    session_state: MutableMapping[str, Any],
    *,
    truth_signature: str,
    team_strategy: str,
    team_strategy_label: str = "",
    auto_team_strategy: str = "",
    team_strategy_override: str = "Auto",
    pick_score_multiplier: Any,
    writer: str = "explicit_strategy_widget",
    league_id: object = "",
    roster_id: object = "",
) -> dict[str, Any]:
    """User-driven strategy change — replaces lock and is expected to invalidate."""

    return lock_canonical_inputs(
        session_state,
        truth_signature=truth_signature,
        team_strategy=team_strategy,
        team_strategy_label=team_strategy_label,
        auto_team_strategy=auto_team_strategy,
        team_strategy_override=team_strategy_override,
        pick_score_multiplier=pick_score_multiplier,
        writer=writer,
        mutation_kind=MUTATION_EXPLICIT_USER,
        force=True,
        league_id=league_id,
        roster_id=roster_id,
    )


def note_presentation_strategy_write(
    session_state: MutableMapping[str, Any],
    *,
    attempted_strategy: str,
    writer: str,
) -> str:
    """Presentation tried to write strategy — keep lock; emit if drift attempted."""

    store = get_canon(session_state)
    attempted = _safe_text(attempted_strategy, "retool") or "retool"
    if not store:
        return attempted
    locked = _safe_text(store.get(CANON_STRATEGY_FIELD), attempted) or attempted
    if locked != attempted:
        emit_field_mutation(
            session_state,
            field=CANON_STRATEGY_FIELD,
            old_value=locked,
            new_value=attempted,
            writer=writer,
            mutation_kind=MUTATION_PRESENTATION,
            league_id=(session_state or {}).get("selected_league_id"),
        )
    return locked


def resolve_or_lock_strategy(
    session_state: MutableMapping[str, Any],
    *,
    truth_signature: str,
    pick_score_multiplier: Any,
    resolve_fn: Callable[[], tuple[str, str, str, str]],
    writer: str = "canonical_strategy_resolver",
    league_id: object = "",
    roster_id: object = "",
) -> dict[str, Any]:
    """Return locked canon; resolve once per league/roster via ``resolve_fn``.

    ``resolve_fn`` returns ``(auto, active, override, label)``.
    Valuation-lens / frame signature changes update pick multiplier only.
    """

    existing = get_canon(session_state)
    same_scope = same_team_scope(
        existing, league_id=league_id, roster_id=roster_id
    )
    same_truth = bool(
        existing
        and _safe_text(existing.get(CANON_TRUTH_SIG_FIELD)) == _safe_text(truth_signature)
    )
    if existing and existing.get(CANON_STRATEGY_FIELD) and (same_scope or same_truth):
        pick = stable_pick_score_multiplier(pick_score_multiplier)
        if (
            existing.get(CANON_PICK_MULT_FIELD) != pick
            or _safe_text(existing.get(CANON_TRUTH_SIG_FIELD)) != _safe_text(truth_signature)
        ):
            return lock_canonical_inputs(
                session_state,
                truth_signature=truth_signature,
                team_strategy=str(existing.get(CANON_STRATEGY_FIELD)),
                team_strategy_label=str(existing.get(CANON_LABEL_FIELD) or ""),
                auto_team_strategy=str(existing.get(CANON_AUTO_STRATEGY_FIELD) or ""),
                team_strategy_override=str(existing.get(CANON_OVERRIDE_FIELD) or "Auto"),
                pick_score_multiplier=pick_score_multiplier,
                writer=writer,
                mutation_kind=MUTATION_CANONICAL,
                force=True,
                league_id=league_id or existing.get(CANON_LEAGUE_FIELD),
                roster_id=roster_id or existing.get(CANON_ROSTER_FIELD),
            )
        return existing

    auto_strategy, active_strategy, override, label = resolve_fn()
    return lock_canonical_inputs(
        session_state,
        truth_signature=truth_signature,
        team_strategy=active_strategy,
        team_strategy_label=label,
        auto_team_strategy=auto_strategy,
        team_strategy_override=override,
        pick_score_multiplier=pick_score_multiplier,
        writer=writer,
        mutation_kind=MUTATION_CANONICAL,
        force=True,
        league_id=league_id,
        roster_id=roster_id,
    )

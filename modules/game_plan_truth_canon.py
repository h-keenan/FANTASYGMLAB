"""Canonical Game Plan football inputs (#239).

Locks team_strategy and base pick_score_multiplier before the first package
fingerprint so post-usable-auth / presentation reruns cannot drift truth and
force package MISS / trade rebuilds.

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


def emit_field_mutation(
    session_state: MutableMapping[str, Any] | None,
    *,
    field: str,
    old_value: Any,
    new_value: Any,
    writer: str,
    mutation_kind: str,
) -> None:
    """Diagnostics-only mutation provenance (DYNASTYGM_STARTUP=1)."""

    if old_value == new_value:
        return
    try:
        from modules import startup_cold_path

        if not startup_cold_path.startup_diagnostics_enabled():
            return
    except Exception:
        return
    payload: dict[str, Any] = {
        "kind": "game_plan_truth_mutation",
        "field": performance._safe_label(field)[:48],
        "old_digest": _digest(old_value),
        "new_digest": _digest(new_value),
        "writer": performance._safe_label(writer)[:64],
        "mutation_kind": performance._safe_label(mutation_kind)[:32],
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
    try:
        print("DYNASTYGM_STARTUP " + json.dumps(payload, sort_keys=True), flush=True)
    except Exception:
        pass


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
) -> dict[str, Any]:
    """Lock football inputs for one truth signature. Presentation cannot replace."""

    store = _store(session_state)
    strategy = _safe_text(team_strategy, "retool") or "retool"
    pick = stable_pick_score_multiplier(pick_score_multiplier)
    existing_sig = _safe_text(store.get(CANON_TRUTH_SIG_FIELD))
    if (
        not force
        and existing_sig
        and existing_sig == _safe_text(truth_signature)
        and store.get(CANON_STRATEGY_FIELD)
    ):
        # Same truth — keep lock; ignore presentation re-resolution noise.
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
        )
    if old_pick is not None and old_pick != pick:
        emit_field_mutation(
            session_state,
            field=CANON_PICK_MULT_FIELD,
            old_value=old_pick,
            new_value=pick,
            writer=writer,
            mutation_kind=mutation_kind,
        )

    store[CANON_TRUTH_SIG_FIELD] = _safe_text(truth_signature)
    store[CANON_STRATEGY_FIELD] = strategy
    store[CANON_LABEL_FIELD] = _safe_text(team_strategy_label) or strategy
    store[CANON_AUTO_STRATEGY_FIELD] = _safe_text(auto_team_strategy) or strategy
    store[CANON_OVERRIDE_FIELD] = _safe_text(team_strategy_override, "Auto") or "Auto"
    store[CANON_PICK_MULT_FIELD] = pick
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
        )
    return locked


def resolve_or_lock_strategy(
    session_state: MutableMapping[str, Any],
    *,
    truth_signature: str,
    pick_score_multiplier: Any,
    resolve_fn: Callable[[], tuple[str, str, str, str]],
    writer: str = "canonical_strategy_resolver",
) -> dict[str, Any]:
    """Return locked canon; resolve once per truth signature via ``resolve_fn``.

    ``resolve_fn`` returns ``(auto, active, override, label)``.
    """

    existing = get_canon(session_state)
    if (
        existing
        and _safe_text(existing.get(CANON_TRUTH_SIG_FIELD)) == _safe_text(truth_signature)
        and existing.get(CANON_STRATEGY_FIELD)
    ):
        # Keep pick multiplier aligned if base settings changed with same strategy lock.
        pick = stable_pick_score_multiplier(pick_score_multiplier)
        if existing.get(CANON_PICK_MULT_FIELD) != pick:
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
    )

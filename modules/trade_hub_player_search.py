"""Opt-in Trade Hub 'Search Around a Player' execution state.

Presentation/interaction ownership only. Does not generate trades, change
valuations, or call providers. Callers still use cached_player_trade_hub_ideas
when this module says the user explicitly executed a search.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

EXECUTED_SIG_KEY = "trade_hub_player_search_executed_sig"
CACHE_KEY = "trade_hub_player_search_cache"
FIND_BUTTON_LABEL = "Find trades around this player"
QUIET_INSTRUCTION = (
    "Choose a player and run a search to explore targeted return packages."
)
STALE_INSTRUCTION = (
    "Player or search mode changed. Run search again to see return packages."
)

_LAST_DIAG: dict[str, Any] = {
    "executed": False,
    "cache_status": "skip",
    "reason": "",
    "elapsed_ms": 0.0,
    "signature": "",
}


def last_diagnostics() -> dict[str, Any]:
    return dict(_LAST_DIAG)


def note_skip(reason: str = "not_requested") -> None:
    _LAST_DIAG.clear()
    _LAST_DIAG.update(
        {
            "executed": False,
            "cache_status": "skip",
            "reason": reason,
            "elapsed_ms": 0.0,
            "signature": "",
        }
    )


def note_run(*, cache_status: str, elapsed_ms: float, signature: str) -> None:
    _LAST_DIAG.clear()
    _LAST_DIAG.update(
        {
            "executed": True,
            "cache_status": cache_status,
            "reason": "explicit_find",
            "elapsed_ms": float(elapsed_ms),
            "signature": signature,
        }
    )


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def search_signature(
    *,
    league_id: str,
    roster_id: str,
    strategy: str,
    mode: str,
    player_id: str,
    score_field: str,
    pick_score_multiplier: float | int | str = 1,
    value_version: str = "",
) -> str:
    """Semantic inputs only — no widget keys or cosmetic labels."""

    return "|".join(
        (
            _text(league_id),
            _text(roster_id),
            _text(strategy).casefold(),
            _text(mode).casefold() or "my_player",
            _text(player_id),
            _text(score_field),
            str(pick_score_multiplier),
            _text(value_version),
        )
    )


def mark_executed(state: MutableMapping[str, Any], signature: str) -> None:
    state[EXECUTED_SIG_KEY] = _text(signature)


def queue_player_focus(
    state: MutableMapping[str, Any], *, league_id: str, player_id: str
) -> None:
    """Queue one league-safe PQV handoff for existing search execution."""

    league = _text(league_id)
    player = _text(player_id)
    if league and player:
        state[f"trade_hub_pending_focus_{league}"] = player


def consume_player_focus(
    state: MutableMapping[str, Any], *, league_id: str, player_id: str
) -> bool:
    league = _text(league_id)
    key = f"trade_hub_pending_focus_{league}"
    expected = _text(state.get(key))
    if not expected or expected != _text(player_id):
        return False
    state.pop(key, None)
    return True


def executed_signature(state: Mapping[str, Any]) -> str:
    return _text(state.get(EXECUTED_SIG_KEY))


def is_executed(state: Mapping[str, Any], signature: str) -> bool:
    current = _text(signature)
    return bool(current) and executed_signature(state) == current


def cache_get(state: Mapping[str, Any], signature: str) -> dict[str, Any] | None:
    store = state.get(CACHE_KEY)
    if not isinstance(store, Mapping):
        return None
    payload = store.get(_text(signature))
    return dict(payload) if isinstance(payload, Mapping) else None


def cache_put(
    state: MutableMapping[str, Any],
    signature: str,
    payload: Mapping[str, Any],
) -> None:
    store = state.get(CACHE_KEY)
    if not isinstance(store, dict):
        store = {}
        state[CACHE_KEY] = store
    store[_text(signature)] = dict(payload)


def instruction_for(state: Mapping[str, Any], signature: str) -> str:
    if not _text(signature):
        return QUIET_INSTRUCTION
    if not executed_signature(state):
        return QUIET_INSTRUCTION
    if not is_executed(state, signature):
        return STALE_INSTRUCTION
    return ""


def clear_league_search(state: MutableMapping[str, Any], league_id: str) -> None:
    """Drop executed/cached rows that belong to another league's search."""

    league = _text(league_id)
    executed = executed_signature(state)
    if executed and league and not executed.startswith(f"{league}|"):
        state.pop(EXECUTED_SIG_KEY, None)
    store = state.get(CACHE_KEY)
    if not isinstance(store, dict) or not league:
        return
    drop = [key for key in store if not str(key).startswith(f"{league}|")]
    for key in drop:
        store.pop(key, None)
    for key in list(state):
        if str(key).startswith("trade_hub_pending_focus_") and key != f"trade_hub_pending_focus_{league}":
            state.pop(key, None)

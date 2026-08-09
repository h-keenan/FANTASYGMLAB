"""Trade Trust context — pickle-safe module type for cache boundaries (#222).

``TradeTrustContext`` must never be defined in ``app.py`` / ``__main__``. Streamlit
``@st.cache_data`` pickles return values; ``__main__`` class identity changes on
every script rerun and raises ``UnserializableReturnValueError``.

Ownership
---------
- ``st.cache_data`` stores only the serialized payload (dict / tuples / frozenset).
- Runtime callers hydrate via ``hydrate_trade_trust_context``.
- Process memos may hold either form; hydrate before Trust enforcement.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

# Bump when the serialized trust schema changes (invalidates st.cache_data entries).
TRADE_TRUST_CACHE_VERSION = 1


@dataclass(frozen=True)
class TradeTrustContext:
    ownership_by_player: tuple[tuple[str, int], ...]
    valid_roster_ids: frozenset[int]
    team_name_to_roster: tuple[tuple[str, int], ...]
    league_context_valid: bool


def serialize_trade_trust_context(
    context: TradeTrustContext | Mapping[str, Any] | None,
) -> dict[str, Any] | Any:
    """Return a pickle-safe dict for ``st.cache_data`` / process stores."""

    if context is None:
        return None
    if isinstance(context, TradeTrustContext):
        payload = asdict(context)
        payload["valid_roster_ids"] = sorted(int(rid) for rid in context.valid_roster_ids)
        payload["cache_version"] = TRADE_TRUST_CACHE_VERSION
        return payload
    if isinstance(context, Mapping):
        payload = dict(context)
        payload.setdefault("cache_version", TRADE_TRUST_CACHE_VERSION)
        ownership = payload.get("ownership_by_player") or ()
        payload["ownership_by_player"] = tuple(
            (str(pid), int(roster)) for pid, roster in ownership
        )
        valid = payload.get("valid_roster_ids") or ()
        payload["valid_roster_ids"] = sorted({int(rid) for rid in valid})
        names = payload.get("team_name_to_roster") or ()
        payload["team_name_to_roster"] = tuple(
            (str(name), int(roster)) for name, roster in names
        )
        payload["league_context_valid"] = bool(payload.get("league_context_valid"))
        return payload
    # Test stubs / already-safe scalars pass through unchanged.
    return context


def hydrate_trade_trust_context(
    value: TradeTrustContext | Mapping[str, Any] | None,
) -> TradeTrustContext | None:
    """Rebuild ``TradeTrustContext`` from cache payload or pass through instances."""

    if value is None:
        return None
    if isinstance(value, TradeTrustContext):
        return value
    if not isinstance(value, Mapping):
        return None
    ownership = tuple(
        (str(pid), int(roster))
        for pid, roster in (value.get("ownership_by_player") or ())
    )
    valid = frozenset(int(rid) for rid in (value.get("valid_roster_ids") or ()))
    names = tuple(
        (str(name), int(roster))
        for name, roster in (value.get("team_name_to_roster") or ())
    )
    return TradeTrustContext(
        ownership_by_player=ownership,
        valid_roster_ids=valid,
        team_name_to_roster=names,
        league_context_valid=bool(value.get("league_context_valid")),
    )


def assert_pickle_safe_league_context(payload: Mapping[str, Any]) -> None:
    """Raise if league context still embeds a runtime Trust class instance."""

    trust = payload.get("trade_trust_context")
    if trust is None:
        return
    if isinstance(trust, TradeTrustContext):
        raise TypeError(
            "trade_trust_context must be serialized before st.cache_data storage"
        )
    if isinstance(trust, (Mapping, str, bytes, int, float, bool)):
        return
    raise TypeError(
        f"trade_trust_context must be mapping/None/scalar, got {type(trust)!r}"
    )

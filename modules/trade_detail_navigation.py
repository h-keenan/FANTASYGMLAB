"""Session-scoped navigation for one Trade Hub detail dialog."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import MutableMapping


_ACTIVE_KEY = "dg_trade_detail_active"
_VIEW_KEY = "dg_trade_detail_view"
_PLAYER_KEY = "dg_trade_detail_player"


@dataclass(frozen=True)
class TradeDetailNavigation:
    trade_key: str = ""
    view: str = "trade"
    player_id: str = ""

    @property
    def showing_player(self) -> bool:
        return self.view == "player" and bool(self.player_id)


def control_key(trade_key: str, control: str, player_id: str = "") -> str:
    """Return a deterministic key isolated from modal and disclosure namespaces."""

    payload = "|".join((str(trade_key), str(control), str(player_id)))
    return "trade_detail_nav_" + sha256(payload.encode("utf-8")).hexdigest()[:18]


def current(state: MutableMapping[str, object]) -> TradeDetailNavigation:
    return TradeDetailNavigation(
        trade_key=str(state.get(_ACTIVE_KEY) or ""),
        view=str(state.get(_VIEW_KEY) or "trade"),
        player_id=str(state.get(_PLAYER_KEY) or ""),
    )


def open_trade(state: MutableMapping[str, object], trade_key: str) -> None:
    state[_ACTIVE_KEY] = str(trade_key)
    state[_VIEW_KEY] = "trade"
    state.pop(_PLAYER_KEY, None)


def open_player(
    state: MutableMapping[str, object],
    *,
    trade_key: str,
    player_id: str,
) -> None:
    if not player_id:
        raise ValueError("player_id is required")
    if str(state.get(_ACTIVE_KEY) or "") != str(trade_key):
        raise ValueError("player navigation must retain the active trade")
    state[_VIEW_KEY] = "player"
    state[_PLAYER_KEY] = str(player_id)


def back_to_trade(state: MutableMapping[str, object], trade_key: str) -> None:
    if str(state.get(_ACTIVE_KEY) or "") != str(trade_key):
        return
    state[_VIEW_KEY] = "trade"
    state.pop(_PLAYER_KEY, None)


def close(state: MutableMapping[str, object], trade_key: str | None = None) -> None:
    if trade_key and str(state.get(_ACTIVE_KEY) or "") != str(trade_key):
        return
    state.pop(_ACTIVE_KEY, None)
    state.pop(_VIEW_KEY, None)
    state.pop(_PLAYER_KEY, None)


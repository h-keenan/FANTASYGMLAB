"""Parent-owned bridge for opening canonical Player Quick View from fragments."""

from __future__ import annotations

from typing import Any, MutableMapping

import streamlit as st

from modules.interaction_contract import on_clicked_change


PLAYER_QUICK_VIEW_EVENT = "dynastygm:open-player-quick-view"


_BRIDGE_JS = rf"""
    export default function(component) {{
      const {{ setTriggerValue }} = component
      const listenerKey = "__dynastygmPlayerQuickViewBridge"
      const prior = window[listenerKey]
      if (typeof prior === "function") {{
        window.removeEventListener("{PLAYER_QUICK_VIEW_EVENT}", prior)
      }}
      const listener = (event) => {{
        const detail = event && event.detail && typeof event.detail === "object"
          ? event.detail
          : {{}}
        const playerId = String(detail.player_id || "").trim()
        if (!playerId) return
        setTriggerValue("open", {{
          player_id: playerId,
          trade_key: String(detail.trade_key || "").trim(),
          source_label: String(detail.source_label || "Trade Board").trim(),
          ts: Date.now()
        }})
      }}
      window[listenerKey] = listener
      window.addEventListener("{PLAYER_QUICK_VIEW_EVENT}", listener)
    }}
"""


PLAYER_QUICK_VIEW_BRIDGE_COMPONENT = st.components.v2.component(
    "player_quick_view_parent_bridge",
    html="<span aria-hidden='true'></span>",
    js=_BRIDGE_JS,
    isolate_styles=False,
)


def consume_player_quick_view_request(
    session: MutableMapping[str, Any],
    *,
    key: str = "player_quick_view_parent_bridge",
) -> dict[str, str]:
    """Render the parent bridge and return one validated open request."""

    try:
        result = PLAYER_QUICK_VIEW_BRIDGE_COMPONENT(
            key=key,
            data={},
            width=1,
            height=1,
            on_open_change=on_clicked_change,
        )
    except ValueError as exc:
        if "is not registered" not in str(exc):
            raise
        return {}
    payload = getattr(result, "open", None)
    if not isinstance(payload, dict):
        return {}
    player_id = str(payload.get("player_id") or "").strip()
    if not player_id:
        return {}
    trade_key = str(payload.get("trade_key") or "").strip()
    if trade_key:
        from modules import trade_detail_navigation

        trade_detail_navigation.close(session, trade_key)
    return {
        "player_id": player_id,
        "trade_key": trade_key,
        "source_label": str(payload.get("source_label") or "Trade Board").strip(),
    }

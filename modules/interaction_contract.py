"""Deterministic product-tap contract (presentation / interaction only).

Stable root, event delegation, no innerHTML rewrite on identical markup.
One gesture → one owner. Player targets stopPropagation.
"""

from __future__ import annotations

from typing import Any

# Streamlit v2 components require a callback object. A module-level no-op is
# the canonical handler — do not pass a new lambda per render.
def on_clicked_change(*_args: Any, **_kwargs: Any) -> None:
    return None


# Shared by player scan grids and Trade Hub summary/detail tap roots.
TAP_DELEGATION_JS = r"""
    export default function(component) {
      const { data, parentElement, setTriggerValue } = component
      const host = parentElement && parentElement.nodeType ? parentElement : null
      if (host && host.style) {
        host.style.width = "100%"
        host.style.maxWidth = "100%"
        host.style.display = "block"
      }
      const rootId = (data && data.rootId) || "product-tap-root"
      const root = (host && host.querySelector)
        ? host.querySelector("#" + rootId)
        : document.getElementById(rootId)
      if (!root) return
      if (root.style) root.style.width = "100%"

      const html = (data && data.html) || ""
      const sig = String(html.length) + ":" + html.slice(0, 48) + ":" + html.slice(-48)
      if (root.getAttribute("data-html-sig") !== sig) {
        root.innerHTML = html
        root.setAttribute("data-html-sig", sig)
      }

      const shouldIgnoreTarget = (target) => {
        if (!target || typeof target.closest !== "function") return false
        return Boolean(target.closest("a, button, input, select, textarea, summary"))
      }

      const emit = (payload) => {
        if (!payload) return
        setTriggerValue("clicked", { ...payload, ts: Date.now() })
      }

      const emitPlayer = (playerId) => {
        if (data && data.bridgePlayerOpens) {
          // Production v2 components may execute in an isolated child window.
          // Dispatch to the Streamlit page where the parent bridge is mounted;
          // the old same-window dispatch only worked in the synthetic fixture.
          const bridgeWindow = window.parent && window.parent !== window
            ? window.parent
            : window
          bridgeWindow.dispatchEvent(new CustomEvent("dynastygm:open-player-quick-view", {
            detail: {
              player_id: playerId,
              trade_key: String(data.tradeKey || ""),
              source_label: String(data.sourceLabel || "Trade Board")
            }
          }))
          return
        }
        emit({ kind: "player", player_id: playerId })
      }

      const playerSelector = [
        ".dg-player-asset-tap[data-player-id]",
        ".player-card-tappable[data-player-id]",
        ".scan-card[data-player-id]",
        ".compact-player-row[data-player-id]",
        ".dg-dense-row[data-player-id]",
        ".dg-compact-asset--player[data-player-id]"
      ].join(", ")

      root.querySelectorAll(".trade-summary-card").forEach((card) => {
        if (!card.hasAttribute("role")) card.setAttribute("role", "button")
        if (!card.hasAttribute("tabindex")) card.setAttribute("tabindex", "0")
      })
      root.querySelectorAll(playerSelector).forEach((node) => {
        if (!node.hasAttribute("role")) node.setAttribute("role", "button")
        if (!node.hasAttribute("tabindex")) node.setAttribute("tabindex", "0")
      })

      if (root.getAttribute("data-tap-bound") === "1") return
      root.setAttribute("data-tap-bound", "1")

      const handleActivate = (event, fromKeyboard) => {
        const target = event.target
        if (!(target && target.closest)) return
        if (shouldIgnoreTarget(target) && !target.closest(playerSelector)) return

        const playerNode = target.closest(playerSelector)
        if (playerNode) {
          const playerId = playerNode.dataset.playerId
            || playerNode.getAttribute("data-player-id")
            || ""
          if (!playerId) return
          event.preventDefault()
          event.stopPropagation()
          emitPlayer(playerId)
          return
        }

        const routeCard = target.closest(".home-command-route-card[data-route]")
        if (routeCard) {
          const route = routeCard.dataset.route || routeCard.getAttribute("data-route") || ""
          if (!route) return
          if (fromKeyboard) event.preventDefault()
          emit({
            kind: "route",
            route,
            player_id: routeCard.dataset.routePlayerId
              || routeCard.getAttribute("data-route-player-id")
              || "",
            focus_mode: routeCard.dataset.routeFocusMode
              || routeCard.getAttribute("data-route-focus-mode")
              || ""
          })
          return
        }

        const tradeCard = target.closest(".trade-summary-card[data-trade-summary-key], [data-trade-chrome='1']")
        if (tradeCard) {
          const card = tradeCard.closest(".trade-summary-card") || tradeCard
          const key = card.getAttribute("data-trade-summary-key")
            || (data && data.key)
            || ""
          if (!key) return
          if (fromKeyboard) event.preventDefault()
          emit({ kind: "trade", key })
        }
      }

      root.addEventListener("click", (event) => handleActivate(event, false))
      root.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return
        handleActivate(event, true)
      })
    }
"""

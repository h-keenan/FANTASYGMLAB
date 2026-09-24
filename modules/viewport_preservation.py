"""Preserve the interacted region across in-place Streamlit reruns.

After #347, ``[data-testid=stMain]`` is the document scroller. Window
``scrollY`` stays 0. In-place actions (disabled buttons, newly mounted
alerts, footer Feedback) can move focus to a later tabbable and Safari
scrolls that node into view — the user-visible jump to page bottom.

This helper is event-driven: pointerdown records the widget, rerender and
focusin restore the region's viewport offset. It does not poll, observe
mutations, or call ``scrollIntoView``.
"""

from __future__ import annotations

import streamlit as st

from modules.html_rendering import inject_global_styles

VIEWPORT_PRESERVE_CSS = """
[class*="st-key-dg_viewport_preserve"],
[class*="st-key-dg_viewport_restore_kick"] {
    clip: rect(0, 0, 1px, 1px) !important;
    height: 1px !important;
    margin: 0 !important;
    max-height: 1px !important;
    max-width: 1px !important;
    min-width: 1px !important;
    overflow: hidden !important;
    padding: 0 !important;
    pointer-events: none !important;
    position: fixed !important;
    left: -10px !important;
    top: -10px !important;
    opacity: 0 !important;
    width: 1px !important;
}
"""

VIEWPORT_PRESERVE_JS = """
    export default function(component) {
      const hostWindow = window.parent || window
      const doc = hostWindow.document

      const pageScroller = () => {
        const main = doc.querySelector('[data-testid="stMain"]')
        if (main && main.scrollHeight > main.clientHeight + 1) return main
        return doc.scrollingElement || doc.documentElement || doc.body
      }

      const keyFrom = (el) => {
        let node = el
        while (node && node !== doc.body && node !== doc.documentElement) {
          const list = node.classList
          if (list && list.length) {
            for (const name of list) {
              if (name.indexOf("st-key-") === 0) return name
            }
          }
          node = node.parentElement
        }
        return ""
      }

      const isIntentionalNav = (el) => {
        if (!el || !el.closest) return false
        if (el.closest("[data-fgl-intentional-nav]")) return true
        const link = el.closest("a[href]")
        if (link) {
          const href = String(link.getAttribute("href") || "")
          if (href.indexOf("?page=") >= 0) return true
        }
        return false
      }

      const isOverlayChrome = (el) => {
        if (!el || !el.closest) return false
        return Boolean(
          el.closest('[data-testid="stDialog"]')
          || el.closest('[data-testid="stPopover"]')
          || el.closest('[role="dialog"]')
          || el.closest(".mobile-gm-destination-panel")
          || el.closest(".mobile-gm-sheet-marker")
        )
      }

      const isFixedOrb = (el) => {
        if (!el || !el.closest) return false
        return Boolean(
          el.closest('[class*="st-key-mobile_gm_sheet"]')
          || el.closest(".mobile-gm-floating-trigger-marker")
        )
      }

      const actionLabel = (node) => (node.innerText || node.getAttribute("aria-label") || "")
        .trim().slice(0, 120)

      const restore = () => {
        const last = hostWindow.__dgInPlaceAnchor
        if (!last || last.nav) return
        const navToken = Number(hostWindow.__dynastyGmScrollResetToken || 0)
        if (navToken > Number(last.navToken || 0)) {
          hostWindow.__dgInPlaceAnchor = null
          return
        }
        if ((Date.now() - last.t) > 5000) return
        const root = pageScroller()
        if (!root) return
        if (last.lockScroll) {
          if (Math.abs(Number(root.scrollTop || 0) - last.scrollTop) > 4) {
            root.scrollTop = last.scrollTop
          }
          return
        }
        let el = actionLabel(doc.activeElement) === last.label ? doc.activeElement : null
        if (!el) el = last.key ? doc.querySelector("." + CSS.escape(last.key)) : null
        if (el && last.label && actionLabel(el) !== last.label
            && ![...el.querySelectorAll("button, a, summary, [role='button']")]
              .some((node) => actionLabel(node) === last.label)) {
          el = null
        }
        if (!el && last.label) {
          const matches = [...doc.querySelectorAll("button, a, summary, [role='button']")]
            .filter((node) => actionLabel(node) === last.label)
          // A duplicate label has no safe identity once Streamlit keys change.
          // Keep the keyed match above when it is verified; otherwise decline
          // to re-anchor rather than selecting an unrelated control.
          el = matches.length === 1 ? matches[0] : null
        }
        if (el) {
          const rect = el.getBoundingClientRect()
          const srect = root.getBoundingClientRect()
          const delta = (rect.top - srect.top) - last.offset
          if (Math.abs(delta) >= 12) root.scrollTop += delta
          return
        }
        const max = Math.max(0, root.scrollHeight - root.clientHeight)
        if (max > 40 && (root.scrollTop <= 2 || root.scrollTop >= max - 8)) {
          root.scrollTop = Math.min(max, Math.max(0, last.scrollTop))
        }
      }

      hostWindow.__dgRestoreInPlaceAnchor = restore

      const record = (target) => {
        const root = pageScroller()
        if (!root || !target) return
        const action = target.closest("button, a, summary, [role='button'], input, textarea, select") || target
        const widget = action.closest('[data-testid="stElementContainer"]') || action
        const rect = widget.getBoundingClientRect()
        const srect = root.getBoundingClientRect()
        hostWindow.__dgInPlaceAnchor = {
          t: Date.now(),
          key: keyFrom(action),
          offset: rect.top - srect.top,
          scrollTop: Number(root.scrollTop || 0),
          nav: isIntentionalNav(action),
          lockScroll: isFixedOrb(action),
          label: actionLabel(action),
          navToken: Number(hostWindow.__dynastyGmScrollResetToken || 0)
        }
      }

      if (!hostWindow.__dgViewportPreserveBound) {
        hostWindow.__dgViewportPreserveBound = true
        doc.addEventListener("pointerdown", (event) => {
          const target = event.target
          if (!(target instanceof hostWindow.Element)) return
          if (!target.closest('[data-testid="stMain"]')) return
          if (!target.closest('button, a, [role="button"], summary, input, textarea, select, [data-baseweb="select"], [data-baseweb="popover"]')) return
          record(target)
        }, true)
        const cancelForUserScroll = () => {
          const last = hostWindow.__dgInPlaceAnchor
          if (last && !last.lockScroll) hostWindow.__dgInPlaceAnchor = null
          hostWindow.__dgUserScrollIntentAt = Date.now()
        }
        doc.addEventListener("touchmove", cancelForUserScroll, { capture: true, passive: true })
        doc.addEventListener("wheel", cancelForUserScroll, { capture: true, passive: true })
        doc.addEventListener("keydown", (event) => {
          if (["PageDown", "PageUp", "ArrowDown", "ArrowUp", "Home", "End", " "].includes(event.key)) {
            cancelForUserScroll()
          }
        }, true)
        doc.addEventListener("focusin", (event) => {
          const last = hostWindow.__dgInPlaceAnchor
          if (!last || last.nav) return
          if ((Date.now() - last.t) > 5000) return
          const focused = event.target
          if (!(focused instanceof hostWindow.Element)) return
          if (last.lockScroll) {
            // A lockScroll anchor (the GM orb's fixed-position trigger) has a
            // rect.top that stays visually constant regardless of the page's
            // real scroll offset, so the geometry-delta branches below always
            // compute ~0 for it and swallow the focusin event as a no-op —
            // leaving whatever the DOM patch that opened the sheet left
            // scrollTop at, uncorrected. Snap to the recorded absolute
            // scrollTop instead, exactly like restore()'s own lockScroll path.
            const root = pageScroller()
            if (root && Math.abs(Number(root.scrollTop || 0) - last.scrollTop) > 4) {
              root.scrollTop = last.scrollTop
            }
            return
          }
          if (isOverlayChrome(focused)) {
            const root = pageScroller()
            if (root && Math.abs(Number(root.scrollTop || 0) - last.scrollTop) > 24) {
              root.scrollTop = last.scrollTop
            }
            return
          }
          if (last.label && actionLabel(focused) === last.label) {
            const root = pageScroller()
            if (root) {
              const rect = focused.getBoundingClientRect()
              const srect = root.getBoundingClientRect()
              const delta = (rect.top - srect.top) - last.offset
              if (Math.abs(delta) >= 12) root.scrollTop += delta
            }
            return
          }
          const focusedKey = keyFrom(focused)
          if (last.key && focusedKey && focusedKey !== last.key) {
            const root = pageScroller()
            const srect = root.getBoundingClientRect()
            const far = Math.abs(focused.getBoundingClientRect().top - (srect.top + last.offset)) > 160
            if (far && typeof focused.blur === "function") focused.blur()
          }
          restore()
        }, true)
        doc.addEventListener("scroll", (event) => {
          const last = hostWindow.__dgInPlaceAnchor
          if (!last || last.nav) return
          if ((Date.now() - last.t) > 1800) return
          const root = pageScroller()
          if (!root) return
          const target = event.target
          if (target !== root && target !== doc && target !== doc.documentElement && target !== doc.body) return
          const max = Math.max(0, root.scrollHeight - root.clientHeight)
          if (max > 40 && (root.scrollTop <= 2 || root.scrollTop >= max - 8)) restore()
        }, true)
      }

      hostWindow.requestAnimationFrame(() => {
        hostWindow.requestAnimationFrame(restore)
      })
      hostWindow.setTimeout(restore, 80)
      hostWindow.setTimeout(restore, 220)
      hostWindow.setTimeout(restore, 600)
      hostWindow.setTimeout(restore, 1200)
    }
"""

def render_viewport_preservation() -> None:
    """Mount the once-per-run in-place viewport contract.

    ``data`` must change every rerun. With a constant payload (``{"v": 1}``)
    the frontend treats this as the same component instance with unchanged
    props and never re-invokes the JS module body past the very first mount
    of a session — so the rAF/setTimeout restore ladder documented on
    ``restore()`` (up to 1200ms of follow-up correction after a click) only
    ever ran once, on first page load. Every later in-place action — every
    ``click_in_place`` call and the GM orb — relied solely on
    ``render_viewport_restore_kick()``'s single double-rAF call with no
    follow-up, so a reflow that settled after those two frames (e.g. an
    avatar/headshot image finishing load just after the kick) could leave
    the scroll uncorrected with nothing left to fix it. Passing a
    per-rerun token forces the module body — and its restore ladder — to
    run again on every rerun, matching the documented behavior.
    """

    inject_global_styles(VIEWPORT_PRESERVE_CSS)
    # Register on this script-run's component manager. AppTest rebuilds the
    # manager; a module-level component() from a cached import would be missing.
    preserve = st.components.v2.component(
        "viewport_preserve",
        html="<span class='dg-viewport-preserve-marker' aria-hidden='true'></span>",
        js=VIEWPORT_PRESERVE_JS,
        isolate_styles=False,
    )
    token = int(st.session_state.get("_viewport_preserve_mount_token", 0)) + 1
    st.session_state["_viewport_preserve_mount_token"] = token
    preserve(
        key="dg_viewport_preserve",
        data={"v": token},
        width=1,
        height=1,
    )


VIEWPORT_RESTORE_KICK_JS = """
    export default function(component) {
      const hostWindow = window.parent || window
      hostWindow.__dgViewportRestoreKickSeq = Number(hostWindow.__dgViewportRestoreKickSeq || 0) + 1
      hostWindow.__dgViewportRestoreKickAt = Date.now()
      hostWindow.requestAnimationFrame(() => {
        hostWindow.requestAnimationFrame(() => {
          if (typeof hostWindow.__dgRestoreInPlaceAnchor === "function") {
            hostWindow.__dgRestoreInPlaceAnchor()
          }
        })
      })
    }
"""


def render_viewport_restore_kick() -> None:
    """Invoke the early binder's restore after the route tree is emitted."""

    token = int(st.session_state.get("_viewport_restore_kick_token", 0)) + 1
    st.session_state["_viewport_restore_kick_token"] = token
    kick = st.components.v2.component(
        "viewport_restore_kick",
        html="<span class='dg-viewport-restore-kick-marker' aria-hidden='true'></span>",
        js=VIEWPORT_RESTORE_KICK_JS,
        isolate_styles=False,
    )
    kick(key=f"dg_viewport_restore_kick_{token % 2}", data={"v": token}, width=1, height=1)

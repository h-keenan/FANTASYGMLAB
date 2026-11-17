"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";

import { PillRow } from "@/components/PillRow";
import { readSavedTab, resolveTab, saveTab, tabDirection } from "@/lib/sessionTab";
import { nextPanelMinHeight, stickyTabsOffset } from "@/lib/sheetTabs";
import { decideSwipe, lockSwipeAxis, SWIPE_EDGE_GUARD, swipeMayStart, swipeProgress, swipeTargetKey, type SwipeAxis } from "@/lib/swipeTabs";
import type { TabIconName } from "@/lib/tabIcons";

export interface TabItem {
  key: string;
  label: string;
  glyph?: TabIconName;
  /** Small count pill beside the label. */
  count?: number;
  /** Rendered only while this tab is open (panels are lazy, so a heavy tab costs nothing until it is picked). */
  render: () => ReactNode;
}

function sessionStore(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

/**
 * THE tabs for a surface that has more to say than one screen (player sheet, team sheet): the shared tab strip
 * (PillRow, in its slim in-sheet look) over lazily rendered panels. Built on the existing control, not beside it, so
 * keyboard (arrows / Home / End), the sliding underline and glass tokens are the same everywhere. Adds what a tabbed
 * surface needs: a tabpanel wired to its tab, a short slide-in from the side you moved toward (off under
 * prefers-reduced-motion) and the last tab remembered for the session under `id` (mobile twin: components/Tabs.tsx).
 */
export function Tabs({
  id,
  tabs,
  initial,
  ariaLabel,
  onChange,
  sticky = true,
}: {
  /** Stable name of the surface ("pqv", "sim-team"); the remembered tab is stored under it. */
  id: string;
  tabs: readonly TabItem[];
  initial?: string;
  ariaLabel?: string;
  onChange?: (key: string) => void;
  /** Pin the tab strip to the top of the sheet's scroll area (default). Off only where nothing scrolls. */
  sticky?: boolean;
}) {
  const uid = useId().replace(/:/g, "");
  const keys = tabs.map((t) => t.key);
  const [active, setActive] = useState(() => resolveTab(readSavedTab(sessionStore(), id), keys, initial));
  const previous = useRef(active);
  const [dir, setDir] = useState<-1 | 0 | 1>(0);
  // A remembered tab that no longer exists (a tab hidden for this player) falls back instead of rendering nothing.
  const current = keys.includes(active) ? active : resolveTab(null, keys, initial);

  function select(key: string) {
    setDir(tabDirection(keys, previous.current, key));
    previous.current = key;
    setActive(key);
    saveTab(sessionStore(), id, key);
    onChange?.(key);
  }

  useEffect(() => {
    previous.current = current;
  }, [current]);

  // No layout jump between tabs while the strip is pinned: the panel keeps the tallest height this open sheet has shown
  // as its minimum, so a short tab after a long one does not pull the strip up under the finger. An unpinned strip has
  // nothing to jump, so its panel is sized by its own content (no empty gap under a short tab; coridian_ 2026-11-16).
  const panelRef = useRef<HTMLDivElement>(null);
  const [minHeight, setMinHeight] = useState(0);
  useLayoutEffect(() => {
    const el = panelRef.current;
    if (!el || !sticky) return;
    const measured = el.scrollHeight;
    setMinHeight((prev) => {
      const next = nextPanelMinHeight(prev, measured);
      return next === prev ? prev : next;
    });
  });

  // Dock the strip flush under the sheet's chrome: measured from the real scroll container (its padding and the
  // --tabs-dock the sheet sets), not assumed, so it can never float below the header or leave a gap above itself.
  const stripRef = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const el = stripRef.current;
    if (!el || !sticky) return;
    let scroller: HTMLElement | null = el.parentElement;
    while (scroller && scroller !== document.body) {
      const oy = getComputedStyle(scroller).overflowY;
      if (oy === "auto" || oy === "scroll") break;
      scroller = scroller.parentElement;
    }
    if (!scroller || scroller === document.body) return;
    const target = scroller;
    function apply() {
      const cs = getComputedStyle(target);
      const { top, mask } = stickyTabsOffset(parseFloat(cs.paddingTop), parseFloat(cs.getPropertyValue("--tabs-dock")));
      el!.style.setProperty("--tabs-top", `${top}px`);
      el!.style.setProperty("--tabs-mask", `${mask}px`);
    }
    apply();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(apply);
    ro.observe(target);
    return () => ro.disconnect();
  }, [sticky]);

  // Swipe left/right to change tabs (an addition: the tablist stays buttons). The panel and the strip's underline follow
  // the finger, then snap with a spring. Decisions come from lib/swipeTabs (shared with mobile). Never hijacks vertical
  // scrolling, a touch that starts inside a horizontal scroller ([data-no-swipe] or overflow-x), or an OS edge back-swipe.
  const rootRef = useRef<HTMLDivElement>(null);
  const live = useRef({ keys, current, select });
  useEffect(() => {
    live.current = { keys, current, select };
  });
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const reduce = () => typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let g: { x: number; y: number; t: number; axis: SwipeAxis; dx: number; dy: number } | null = null;

    function inHorizontalScroller(target: EventTarget | null): boolean {
      let el = target instanceof Element ? target : null;
      while (el && el !== root) {
        if (el instanceof HTMLElement) {
          if (el.hasAttribute("data-no-swipe") || el.getAttribute("role") === "tablist") return true;
          const ox = getComputedStyle(el).overflowX;
          if ((ox === "auto" || ox === "scroll") && el.scrollWidth > el.clientWidth + 1) return true;
        }
        el = el.parentElement;
      }
      return false;
    }
    function indicator(): HTMLElement | null {
      return stripRef.current?.querySelector<HTMLElement>(".tab-indicator") ?? null;
    }
    function tabBox(key: string): { left: number; width: number } | null {
      const el = stripRef.current?.querySelector<HTMLElement>(`[role="tab"][id$="-tab-${key}"]`);
      return el ? { left: el.offsetLeft, width: el.offsetWidth } : null;
    }
    function follow(p: number) {
      const { keys: ks, current: cur } = live.current;
      const panel = panelRef.current;
      if (panel) {
        panel.style.transition = "none";
        panel.style.transform = `translateX(${p * 56}px)`;
        panel.style.opacity = String(1 - Math.abs(p) * 0.35);
      }
      const ind = indicator();
      const from = tabBox(cur);
      const to = tabBox(swipeTargetKey(ks, cur, p < 0 ? "next" : "prev"));
      if (ind && from && to) {
        const k = Math.min(1, Math.abs(p) * 2.5);
        ind.style.transition = "none";
        ind.style.width = `${from.width + (to.width - from.width) * k}px`;
        ind.style.transform = `translateX(${from.left + (to.left - from.left) * k}px)`;
      }
    }
    function settle(key: string) {
      const panel = panelRef.current;
      if (panel) {
        panel.style.transition = "transform 320ms cubic-bezier(0.34, 1.56, 0.64, 1), opacity 200ms ease";
        panel.style.transform = "";
        panel.style.opacity = "";
      }
      const ind = indicator();
      const box = tabBox(key);
      if (ind && box) {
        ind.style.transition = "transform 320ms cubic-bezier(0.34, 1.56, 0.64, 1), width 320ms ease";
        ind.style.width = `${box.width}px`;
        ind.style.transform = `translateX(${box.left}px)`;
      }
    }
    function onStart(e: TouchEvent) {
      g = null;
      if (e.touches.length !== 1) return;
      const t = e.touches[0];
      const ok = swipeMayStart({
        startX: t.clientX,
        viewportWidth: window.innerWidth,
        inHorizontalScroller: inHorizontalScroller(e.target),
        edgeGuard: SWIPE_EDGE_GUARD,
      });
      if (ok && live.current.keys.length > 1) g = { x: t.clientX, y: t.clientY, t: e.timeStamp, axis: "undecided", dx: 0, dy: 0 };
    }
    function onMove(e: TouchEvent) {
      if (!g) return;
      const t = e.touches[0];
      g.dx = t.clientX - g.x;
      g.dy = t.clientY - g.y;
      if (g.axis === "undecided") g.axis = lockSwipeAxis(g.dx, g.dy);
      if (g.axis === "vertical") {
        g = null;
        return;
      }
      if (g.axis !== "horizontal") return;
      if (e.cancelable) e.preventDefault();
      if (reduce()) return;
      const { keys: ks, current: cur } = live.current;
      const i = ks.indexOf(cur);
      follow(swipeProgress(g.dx, root!.clientWidth, i > 0, i < ks.length - 1));
    }
    function onEnd(e: TouchEvent) {
      const done = g;
      g = null;
      if (!done || done.axis !== "horizontal") return;
      const { keys: ks, current: cur, select: pick } = live.current;
      const i = ks.indexOf(cur);
      const v = done.dx / Math.max(1, e.timeStamp - done.t);
      const target = swipeTargetKey(ks, cur, decideSwipe(done.dx, done.dy, v, i > 0, i < ks.length - 1));
      if (reduce()) {
        if (target !== cur) pick(target);
        return;
      }
      settle(target);
      if (target !== cur) pick(target);
    }
    function onCancel() {
      if (g?.axis === "horizontal") settle(live.current.current);
      g = null;
    }
    root.addEventListener("touchstart", onStart, { passive: true });
    root.addEventListener("touchmove", onMove, { passive: false });
    root.addEventListener("touchend", onEnd, { passive: true });
    root.addEventListener("touchcancel", onCancel, { passive: true });
    return () => {
      root.removeEventListener("touchstart", onStart);
      root.removeEventListener("touchmove", onMove);
      root.removeEventListener("touchend", onEnd);
      root.removeEventListener("touchcancel", onCancel);
    };
  }, []);

  const tab = tabs.find((t) => t.key === current);
  return (
    <div ref={rootRef} className="flex flex-col gap-3" data-testid="tabs">
      <div ref={stripRef} className={sticky ? "tabs-strip tabs-sticky" : "tabs-strip"} data-sticky={sticky ? "true" : undefined}>
      <PillRow
        slim
        variant="scroll"
        ariaLabel={ariaLabel}
        tabIdPrefix={`${id}-${uid}`}
        options={tabs.map((t) => ({ label: t.label, value: t.key, glyph: t.glyph, count: t.count }))}
        active={current}
        onSelect={select}
      />
      </div>
      <div
        key={current}
        ref={panelRef}
        style={sticky && minHeight > 0 ? { minHeight } : undefined}
        role="tabpanel"
        id={`${id}-${uid}-panel-${current}`}
        aria-labelledby={`${id}-${uid}-tab-${current}`}
        className="tabs-panel flex min-w-0 flex-col gap-4"
        data-dir={dir === 0 ? undefined : dir}
        tabIndex={-1}
      >
        {tab ? tab.render() : null}
      </div>
    </div>
  );
}

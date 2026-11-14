"use client";

import { useEffect, useRef, useSyncExternalStore, type ReactNode } from "react";
import { createPortal } from "react-dom";

import "./ui.css";

const PHONE = "(max-width: 767px)";
const subscribe = (cb: () => void) => {
  if (typeof window.matchMedia !== "function") return () => {};
  const mq = window.matchMedia(PHONE);
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
};
const phoneNow = () => typeof window.matchMedia === "function" && window.matchMedia(PHONE).matches;

/**
 * THE one bottom-chrome mechanism (phones): the tab pill, the Fantasy Sim bar, the sample-league tabs.
 *
 * Portaled to <body> and `position: fixed; bottom: 0` (+ safe-area padding), so it is immune to every ancestor quirk that
 * clamped the earlier in-flow `position: sticky` version: a column whose box ends mid-page while content overflows it,
 * a flex chain that shrinks under a min-height body (iOS Safari), a transformed or overflow ancestor. Content never hides
 * behind it: the dock publishes its measured height as `--bottom-clearance` on <html> (ResizeObserver) and the page
 * column pads by it. From 768px up (and before hydration) it renders inline, exactly as before (`display: contents`).
 * Guards: lib/bottomChrome.test.ts, scripts/sim_layout_playwright/footer_pin.mjs.
 */
export function BottomDock({ children, className = "", testId }: { children: ReactNode; className?: string; testId?: string }) {
  const phone = useSyncExternalStore(subscribe, phoneNow, () => false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!phone || !el) return;
    const root = document.documentElement;
    const publish = () => root.style.setProperty("--bottom-clearance", `${Math.ceil(el.getBoundingClientRect().height)}px`);
    publish();
    const ro = typeof ResizeObserver === "function" ? new ResizeObserver(publish) : null;
    ro?.observe(el);
    return () => {
      ro?.disconnect();
      root.style.removeProperty("--bottom-clearance");
    };
  }, [phone]);
  const node = (
    <div ref={ref} className={`bottom-stack ${className}`.trim()} data-dock={phone ? "fixed" : "inline"} data-testid={testId}>
      {children}
    </div>
  );
  return phone ? createPortal(node, document.body) : node;
}

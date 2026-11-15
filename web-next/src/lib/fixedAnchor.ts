"use client";

import { useEffect, type RefObject } from "react";

import { isEditableFocus } from "@/lib/keyboardInset";

/**
 * Self-healing for `position: fixed; bottom: 0` chrome (the BottomDock pill, the GM orb rail) on iOS Safari / PWA.
 *
 * Pure CSS is the mechanism (fixed, bottom 0 + safe-area, portaled to <body>, no JS positioning). iOS WebKit is the one
 * engine that can leave a fixed layer parked at a STALE layout-viewport bottom (after the keyboard or the dynamic toolbar
 * goes away, a bfcache restore, an orientation change), which floats the pill mid-screen with content visible under it
 * (coridian_ 2026-11-14, "floating footer still"). So the element carries `transform: translateY(var(--dock-shift, 0px))`
 * with a 0 default, and this hook only ever writes that one custom property: it measures how far the element's bottom is from
 * the visible viewport bottom and, when they disagree, shifts it by the difference. In every healthy state the gap is 0 and
 * the property stays 0, so desktop and a correct phone never see JS positioning.
 */

/** Visible viewport bottom, in layout coordinates: the largest of the readings that cannot be an on-screen keyboard. */
export function visibleBottom(inner: number, client: number, vv: { height: number; offsetTop: number } | null | undefined): number {
  const v = vv ? vv.offsetTop + vv.height : 0;
  return Math.max(inner, client, v);
}

/** The new shift that puts an element whose bottom edge is `rectBottom` (currently shifted by `current`) on `target`; 0 inside tolerance. */
export function anchorShift(rectBottom: number, target: number, current: number, limit = 2000): number {
  const gap = target - rectBottom;
  if (Math.abs(gap) <= 1.5) return current;
  const next = current + gap;
  return Math.abs(next) > limit ? 0 : Math.round(next * 2) / 2;
}

export function useFixedBottomAnchor(ref: RefObject<HTMLElement | null>, enabled: boolean) {
  useEffect(() => {
    const el = ref.current;
    if (!enabled || !el || typeof window === "undefined") return;
    const vv = window.visualViewport;
    let raf = 0;
    let timers: number[] = [];
    const measure = () => {
      raf = 0;
      if (!el.isConnected) return;
      const scaled = vv ? vv.scale > 1.01 : false; // pinch-zoom moves the visual viewport on purpose
      const current = parseFloat(el.style.getPropertyValue("--dock-shift")) || 0;
      if (scaled || isEditableFocus(document.activeElement)) {
        if (current !== 0) el.style.setProperty("--dock-shift", "0px");
        return;
      }
      const target = visibleBottom(window.innerHeight, document.documentElement.clientHeight, vv);
      const next = anchorShift(el.getBoundingClientRect().bottom, target, current);
      if (next !== current) el.style.setProperty("--dock-shift", `${next}px`);
    };
    const schedule = () => {
      if (!raf) raf = requestAnimationFrame(measure);
    };
    // After a scroll or any viewport event settles (iOS fires them mid-animation), and again a beat later.
    const settle = () => {
      schedule();
      timers.forEach((t) => window.clearTimeout(t));
      timers = [window.setTimeout(schedule, 150), window.setTimeout(schedule, 600)];
    };
    settle();
    window.addEventListener("scroll", settle, { passive: true });
    window.addEventListener("resize", settle);
    window.addEventListener("orientationchange", settle);
    window.addEventListener("pageshow", settle);
    document.addEventListener("visibilitychange", settle);
    document.addEventListener("focusout", settle);
    vv?.addEventListener("resize", settle);
    vv?.addEventListener("scroll", settle);
    const ro = typeof ResizeObserver === "function" ? new ResizeObserver(settle) : null;
    ro?.observe(el);
    return () => {
      if (raf) cancelAnimationFrame(raf);
      timers.forEach((t) => window.clearTimeout(t));
      window.removeEventListener("scroll", settle);
      window.removeEventListener("resize", settle);
      window.removeEventListener("orientationchange", settle);
      window.removeEventListener("pageshow", settle);
      document.removeEventListener("visibilitychange", settle);
      document.removeEventListener("focusout", settle);
      vv?.removeEventListener("resize", settle);
      vv?.removeEventListener("scroll", settle);
      ro?.disconnect();
      el.style.removeProperty("--dock-shift");
    };
  }, [ref, enabled]);
}

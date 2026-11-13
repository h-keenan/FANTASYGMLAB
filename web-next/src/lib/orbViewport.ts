"use client";

import { useEffect, useState, type CSSProperties } from "react";

/**
 * Visual-Viewport positioning for the floating GM orb (web, phone width).
 *
 * Why: iOS Safari anchors `position: fixed` to the LAYOUT viewport, which
 * can stop matching what is actually on screen (the visual viewport) while
 * the URL/bottom bar collapses or expands, during rubber-banding and after
 * pinch-zoom. The orb then "floats" mid-screen. Layer-promotion tricks
 * (translate3d / will-change) do not change what the fixed box is anchored
 * to, so they were not a real fix. Instead we read the visual viewport
 * directly and place the orb from it, which cannot disagree with it.
 */

/** Orb box and bottom margin; must match GmOrb's `width`/`height`. */
export const ORB_SIZE_REM = 3.25;
export const ORB_MARGIN_PX = 12;

export type VisualViewportLike = {
  height: number;
  width: number;
  offsetTop: number;
  offsetLeft: number;
  scale: number;
};

export type OrbPlacement = {
  /** Visual viewport bottom edge, in layout-viewport coordinates (px). */
  bottomPx: number;
  /** Visual viewport horizontal center, in layout-viewport coordinates (px). */
  centerXPx: number;
  /** Counter-scale so the orb keeps its on-screen size under pinch-zoom. */
  scale: number;
};

/** Pure math: where the visual viewport's bottom edge and center sit. */
export function orbPlacement(vv: VisualViewportLike): OrbPlacement | null {
  const { height, width, offsetTop, offsetLeft, scale } = vv;
  if (![height, width, offsetTop, offsetLeft, scale].every(Number.isFinite) || height <= 0 || width <= 0) return null;
  const s = scale > 0 ? scale : 1;
  return {
    bottomPx: round(offsetTop + height),
    centerXPx: round(offsetLeft + width / 2),
    scale: round(1 / s),
  };
}

/**
 * Orb `top` (CSS) so its bottom edge is
 * `vvBottom - margin - safe-area`. Margin is `max(12px, safe-area-bottom)`,
 * the same value the CSS fallback uses for `bottom`. Under pinch-zoom the
 * orb is scaled by 1/scale about its bottom-center, so the offset from the
 * viewport edge is expressed in layout px (margin / scale).
 */
export function orbStyleFromPlacement(p: OrbPlacement): CSSProperties {
  const margin = `max(${ORB_MARGIN_PX}px, env(safe-area-inset-bottom, 0px))`;
  return {
    top: `calc(${p.bottomPx}px - ${ORB_SIZE_REM}rem * ${p.scale} - ${margin} * ${p.scale})`,
    bottom: "auto",
    left: `${p.centerXPx}px`,
    transform: `translate3d(-50%, 0, 0) scale(${p.scale})`,
    transformOrigin: "50% 100%",
  };
}

function round(n: number): number {
  return Math.round(n * 100) / 100;
}

/**
 * Returns inline style overrides for the orb, or null (SSR, first render,
 * or no visualViewport) in which case the caller's CSS fallback
 * (`bottom: max(12px, env(safe-area-inset-bottom))`) applies unchanged.
 */
export function useOrbViewportStyle(): CSSProperties | null {
  const [style, setStyle] = useState<CSSProperties | null>(null);
  useEffect(() => {
    const vv = typeof window !== "undefined" ? window.visualViewport : null;
    if (!vv) return;
    let raf = 0;
    const update = () => {
      raf = 0;
      const placement = orbPlacement(vv);
      setStyle((prev) => {
        const next = placement ? orbStyleFromPlacement(placement) : null;
        return JSON.stringify(prev) === JSON.stringify(next) ? prev : next;
      });
    };
    const schedule = () => {
      if (!raf) raf = window.requestAnimationFrame(update);
    };
    update();
    vv.addEventListener("resize", schedule);
    vv.addEventListener("scroll", schedule);
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    window.addEventListener("orientationchange", schedule);
    return () => {
      if (raf) window.cancelAnimationFrame(raf);
      vv.removeEventListener("resize", schedule);
      vv.removeEventListener("scroll", schedule);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      window.removeEventListener("orientationchange", schedule);
    };
  }, []);
  return style;
}

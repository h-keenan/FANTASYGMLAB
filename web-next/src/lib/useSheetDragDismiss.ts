"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";

import {
  SHEET_DRAG_IDLE,
  nearestStopIndex,
  sheetDragEnd,
  sheetDragMove,
  sheetDragProgress,
  sheetDragStart,
  sheetStops,
  type SheetDragState,
} from "@/lib/sheetGesture";

const SNAP_BACK_TRANSITION = "transform 260ms cubic-bezier(0.2, 0.9, 0.3, 1.15), opacity 200ms ease-out";
const SETTLE_MS = 280;
const CLOSE_TRANSITION_MS = 200;
const BACKDROP_TRANSITION = "background 200ms ease-out";
/** How much a story-style card shrinks / fades by the time it is fully pulled away. */
const STORY_SCALE = 0.1;
const STORY_FADE = 0.55;

/** Prefers-reduced-motion check that tolerates jsdom/SSR (no matchMedia). */
function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
}

/** scrollTop of every vertically overflowing scroll area between the touch target and the sheet. */
function scrollTopsAbove(target: EventTarget | null, sheet: HTMLElement): number[] {
  const tops: number[] = [];
  let element = target instanceof Element ? target : null;
  while (element) {
    if (element instanceof HTMLElement && element.scrollHeight > element.clientHeight) tops.push(element.scrollTop);
    if (element === sheet) break;
    element = element.parentElement;
  }
  return tops;
}

export interface SheetDragOptions {
  /** Called when the gesture dismisses (after the slide-out; immediately under reduced motion). */
  onDismiss: () => void;
  enabled?: boolean;
  /**
   * Snap points as the visible share of the sheet, e.g. `[0.5, 1]` = a half-height "peek" that drags up to full.
   * Dragging down from the lowest point dismisses. Omit for a plain sheet (`[1]`).
   */
  snapPoints?: readonly number[];
  /** The resting snap point (a value from `snapPoints`). Changing it moves the sheet there, animated. Default: the largest. */
  snap?: number;
  /** A drag settled on another snap point. */
  onSnapChange?: (snap: number) => void;
  /**
   * "sheet" (default): the surface slides down. "story": a full-screen card that follows the finger, shrinks and
   * fades as it is pulled away (the weekly recap StoryCarousel).
   */
  effect?: "sheet" | "story";
}

/**
 * Swipe-down-to-dismiss (and optional snap points) for any web sheet, dialog, pop-up or full-screen card on touch
 * devices. THE one drag implementation: attach `sheetRef` to the moving surface and spread `sheetStyle` onto it;
 * render <SheetHandle /> at its top as the affordance. The rules are the pure state machine in lib/sheetGesture.ts
 * (unit-tested with simulated sequences); this file only wires touch events to it and paints.
 *
 * - A drag starts on the handle always, or anywhere else only when every scroll area under the finger is at its
 *   top AND the pull is downward. A drag that starts inside scrolled content scrolls it, never closes the sheet.
 * - Axis lock: a clearly vertical pull claims the gesture; horizontal swipes (tab strips, chip rows, carousels)
 *   and diagonals are left to the page. Below the top snap point a pull up expands the sheet instead.
 * - The surface follows the finger with rubber-band resistance; it is moved by writing `transform` straight to
 *   the element (no React render per touchmove, which made heavy sheets like the PQV stutter).
 * - Release: dismiss when pulled past ~a quarter of the height (80-160px) OR flicked down fast (velocity over a
 *   100ms window, so one jittery sample can't close it); never when released moving back up. Otherwise it
 *   settles on the nearest snap point (a decisive flick goes to the next one).
 * - Touch only. Mouse and keyboard users keep the X button, Esc and the backdrop.
 * - Reduced motion: no slide, no spring; it still follows the finger and dismisses.
 */
export function useSheetDragDismiss<T extends HTMLElement = HTMLDivElement>({
  onDismiss,
  enabled = true,
  snapPoints,
  snap,
  onSnapChange,
  effect = "sheet",
}: SheetDragOptions): {
  sheetRef: React.RefObject<T | null>;
  sheetStyle: CSSProperties;
  backdropStyle: CSSProperties;
  /** The snap point the sheet currently rests at (visible share, 1 = full). */
  snap: number;
  /** Move to a snap point from code (a button, a tap on the peek header). Animated. */
  snapTo: (snap: number) => void;
} {
  const sheetRef = useRef<T | null>(null);
  const onDismissRef = useRef(onDismiss);
  const onSnapChangeRef = useRef(onSnapChange);
  const points = useMemo(() => (snapPoints && snapPoints.length > 0 ? [...snapPoints].sort((a, b) => b - a) : [1]), [snapPoints]);
  const initialSnap = snap ?? points[0];
  const [currentSnap, setCurrentSnap] = useState(initialSnap);
  const snapRef = useRef(initialSnap);
  const pointsRef = useRef(points);
  const applyRef = useRef<(fraction: number, animate: boolean) => void>(() => {});

  useEffect(() => {
    onDismissRef.current = onDismiss;
    onSnapChangeRef.current = onSnapChange;
    pointsRef.current = points;
  }, [onDismiss, onSnapChange, points]);

  useEffect(() => {
    const sheet = sheetRef.current;
    if (!sheet || !enabled) return;
    const surface: HTMLElement = sheet;
    // A sheet's backdrop is its wrapper; a portaled full-screen card sits directly in <body>, which must not be styled.
    const wrapper = surface.parentElement;
    const backdrop = wrapper && wrapper !== document.body ? wrapper : null;

    let state: SheetDragState = SHEET_DRAG_IDLE;
    let settleTimer: ReturnType<typeof setTimeout> | null = null;
    let closing = false;

    function stopsNow(height: number) {
      return sheetStops(pointsRef.current, height);
    }

    function paint(position: number, height: number) {
      const progress = sheetDragProgress(position, height);
      if (effect === "story") {
        surface.style.transform = position === 0 ? "" : `translate3d(0, ${position}px, 0) scale(${1 - STORY_SCALE * progress})`;
        surface.style.opacity = progress === 0 ? "" : String(1 - STORY_FADE * progress);
      } else {
        surface.style.transform = position === 0 ? "" : `translate3d(0, ${position}px, 0)`;
      }
      // Only the part of the pull heading toward closing dims the backdrop (a peek -> full drag must not).
      const stops = stopsNow(height);
      const lowest = stops[stops.length - 1] ?? 0;
      const closingProgress = sheetDragProgress(position - lowest, Math.max(1, height - lowest));
      (backdrop ?? surface).style.setProperty("--sheet-drag", String(closingProgress));
    }

    function transitionTo(position: number, height: number, animate: boolean, after?: () => void) {
      surface.style.transition = animate ? SNAP_BACK_TRANSITION : "none";
      paint(position, height);
      if (settleTimer) clearTimeout(settleTimer);
      settleTimer = setTimeout(
        () => {
          settleTimer = null;
          after?.();
        },
        animate ? SETTLE_MS : 0,
      );
    }

    // From code: move to a snap point (animated).
    applyRef.current = (fraction, animate) => {
      if (closing) return;
      const height = surface.getBoundingClientRect().height;
      const position = sheetStops([fraction], height)[0];
      snapRef.current = fraction;
      transitionTo(position, height, animate && !prefersReducedMotion());
    };
    // Resting at a partly open snap point on mount.
    if (snapRef.current !== pointsRef.current[0]) applyRef.current(snapRef.current, false);

    function reset() {
      closing = false;
      surface.style.transition = "none";
      surface.style.transform = "";
      surface.style.opacity = "";
      surface.style.willChange = "";
      (backdrop ?? surface).style.setProperty("--sheet-drag", "0");
      if (backdrop) backdrop.style.transition = BACKDROP_TRANSITION;
    }

    function handleTouchStart(event: TouchEvent) {
      if (closing || event.touches.length !== 1) {
        state = SHEET_DRAG_IDLE;
        return;
      }
      const target = event.target instanceof Element ? event.target : null;
      if (target?.closest("[data-sheet-no-drag]")) {
        state = SHEET_DRAG_IDLE;
        return;
      }
      if (settleTimer) {
        clearTimeout(settleTimer);
        settleTimer = null;
      }
      const touch = event.touches[0];
      const height = surface.getBoundingClientRect().height;
      const stops = stopsNow(height);
      const own = sheetStops([snapRef.current], height)[0];
      state = sheetDragStart({
        x: touch.clientX,
        y: touch.clientY,
        t: event.timeStamp,
        onHandle: Boolean(target?.closest("[data-sheet-handle]")),
        scrollTops: scrollTopsAbove(target, surface),
        height,
        stops,
        stopIndex: nearestStopIndex(stops, own),
      });
    }

    function handleTouchMove(event: TouchEvent) {
      if (state.phase === "idle" || state.phase === "ignored" || event.touches.length === 0) return;
      const touch = event.touches[0];
      const dx = touch.clientX - state.startX;
      const dy = touch.clientY - state.startY;
      const wasPending = state.phase === "pending";
      // While still deciding, a vertical pull the sheet may own is claimed immediately: iOS stops honouring
      // preventDefault once it has begun scrolling or overscrolling, so waiting for the slop loses the race.
      if (wasPending && event.cancelable && Math.abs(dy) >= Math.abs(dx) && ((state.canDown && dy > 0) || (state.canUp && dy < 0))) event.preventDefault();
      state = sheetDragMove(state, { x: touch.clientX, y: touch.clientY, t: event.timeStamp });
      if (state.phase !== "drag") return;
      if (event.cancelable) event.preventDefault();
      if (wasPending) {
        surface.style.transition = "none";
        surface.style.willChange = "transform";
        if (backdrop) backdrop.style.transition = "none";
      }
      paint(state.position, state.height);
    }

    function settle(index: number, from: SheetDragState) {
      const height = from.height;
      const stops = from.stops;
      const fraction = height > 0 ? 1 - stops[index] / height : 1;
      const nearest = pointsRef.current.reduce((best, p) => (Math.abs(p - fraction) < Math.abs(best - fraction) ? p : best), pointsRef.current[0]);
      const changed = nearest !== snapRef.current;
      snapRef.current = nearest;
      if (backdrop) backdrop.style.transition = BACKDROP_TRANSITION;
      transitionTo(stops[index], height, !prefersReducedMotion(), () => {
        surface.style.transition = "";
        surface.style.willChange = "";
        // A resting full-open sheet carries no transform at all (it would otherwise trap fixed-position children).
        if (stops[index] === 0) {
          surface.style.transform = "";
          surface.style.opacity = "";
        }
      });
      if (changed) {
        setCurrentSnap(nearest);
        onSnapChangeRef.current?.(nearest);
      }
    }

    function handleTouchEnd(event: TouchEvent) {
      const finished = state;
      const release = sheetDragEnd(finished, event.timeStamp);
      state = SHEET_DRAG_IDLE;
      if (!release) return;
      if (release.type === "snap") {
        settle(release.index, finished);
        return;
      }
      if (prefersReducedMotion()) {
        onDismissRef.current();
        reset();
        return;
      }
      closing = true;
      surface.style.transition = `transform ${CLOSE_TRANSITION_MS}ms ease-in, opacity ${CLOSE_TRANSITION_MS}ms ease-in`;
      if (backdrop) backdrop.style.transition = `background ${CLOSE_TRANSITION_MS}ms ease-in`;
      const gone = finished.height + 24;
      surface.style.transform = effect === "story" ? `translate3d(0, ${gone}px, 0) scale(${1 - STORY_SCALE})` : `translate3d(0, ${gone}px, 0)`;
      if (effect === "story") surface.style.opacity = String(1 - STORY_FADE);
      (backdrop ?? surface).style.setProperty("--sheet-drag", "1");
      settleTimer = setTimeout(() => {
        settleTimer = null;
        onDismissRef.current();
        // A caller that keeps this hook mounted (the GM orb) must reopen at rest, not still translated off-screen.
        reset();
      }, CLOSE_TRANSITION_MS);
    }

    function handleTouchCancel() {
      const cancelled = state;
      state = SHEET_DRAG_IDLE;
      if (cancelled.phase === "drag") settle(nearestStopIndex(cancelled.stops, cancelled.base), cancelled);
    }

    surface.addEventListener("touchstart", handleTouchStart, { passive: true });
    surface.addEventListener("touchmove", handleTouchMove, { passive: false });
    surface.addEventListener("touchend", handleTouchEnd);
    surface.addEventListener("touchcancel", handleTouchCancel);
    return () => {
      surface.removeEventListener("touchstart", handleTouchStart);
      surface.removeEventListener("touchmove", handleTouchMove);
      surface.removeEventListener("touchend", handleTouchEnd);
      surface.removeEventListener("touchcancel", handleTouchCancel);
      if (settleTimer) clearTimeout(settleTimer);
      applyRef.current = () => {};
    };
  }, [enabled, effect]);

  // A controlled `snap` moves the sheet when it changes.
  useEffect(() => {
    if (snap === undefined || snap === snapRef.current) return;
    snapRef.current = snap;
    setCurrentSnap(snap);
    applyRef.current(snap, true);
  }, [snap]);

  const snapTo = useCallback((next: number) => {
    snapRef.current = next;
    setCurrentSnap(next);
    applyRef.current(next, true);
    onSnapChangeRef.current?.(next);
  }, []);

  // Position is written to the element directly while dragging; these are the constant parts (stable identities,
  // so a re-render never touches the live transform).
  const sheetStyle = useMemo<CSSProperties>(() => ({}), []);
  const backdropStyle = useMemo<CSSProperties>(() => ({ transition: BACKDROP_TRANSITION }), []);

  return { sheetRef, sheetStyle, backdropStyle, snap: currentSnap, snapTo };
}

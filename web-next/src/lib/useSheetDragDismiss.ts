"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";

import { classifySheetGesture, sheetDragOffset, shouldDismissSheet } from "@/lib/sheetGesture";

/** A release older than this since the last move is a "hold, then let go",
 * not a flick, so its velocity is treated as zero. */
const STALE_VELOCITY_MS = 100;
const SNAP_BACK_TRANSITION = "transform 260ms cubic-bezier(0.2, 0.9, 0.3, 1.15)";
const CLOSE_TRANSITION_MS = 200;

/** Prefers-reduced-motion check that tolerates jsdom/SSR (no matchMedia). */
function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
}

/** True when nothing scrollable between the touch target and the sheet is
 * scrolled away from its top, so pulling down can only mean "close". */
function scrollChainAtTop(target: EventTarget | null, sheet: HTMLElement): boolean {
  let element = target instanceof Element ? target : null;
  while (element) {
    if (element instanceof HTMLElement && element.scrollTop > 0 && element.scrollHeight > element.clientHeight) {
      return false;
    }
    if (element === sheet) break;
    element = element.parentElement;
  }
  return true;
}

/**
 * Swipe-down-to-dismiss for any web sheet, dialog or pop-up on touch
 * devices. Attach `sheetRef` to the moving surface and spread `sheetStyle`
 * onto it; render <SheetHandle /> at its top as the affordance.
 *
 * Rules (math in lib/sheetGesture.ts):
 * - A drag can start anywhere on the sheet, but only when every scroll
 *   area under the finger is at its top. Scrolling back up inside a long
 *   sheet never closes it. A touch that starts on the handle always drags.
 * - Mostly-horizontal swipes are left alone.
 * - The sheet follows the finger, with rubber-band resistance past the
 *   dismiss distance and when pulled upward.
 * - On release it closes when pulled past a quarter of its height (80 to
 *   160px) or flicked down fast; otherwise it springs back.
 * - Touch only. Mouse and keyboard users keep the X button, Esc and the
 *   backdrop, which callers keep as they were.
 */
export function useSheetDragDismiss<T extends HTMLElement = HTMLDivElement>({
  onDismiss,
  enabled = true,
}: {
  onDismiss: () => void;
  enabled?: boolean;
}): { sheetRef: React.RefObject<T | null>; sheetStyle: CSSProperties; dragProgress: number } {
  const sheetRef = useRef<T | null>(null);
  const onDismissRef = useRef(onDismiss);
  const [offset, setOffset] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [closing, setClosing] = useState(false);
  const [sheetHeight, setSheetHeight] = useState(0);

  useEffect(() => {
    onDismissRef.current = onDismiss;
  }, [onDismiss]);

  useEffect(() => {
    const sheet = sheetRef.current;
    if (!sheet || !enabled) return;

    let tracking = false;
    let mode: "drag" | "ignore" | null = null;
    let canStartDrag = false;
    let startX = 0;
    let startY = 0;
    let lastY = 0;
    let lastTime = 0;
    let velocity = 0;
    let height = 0;
    let currentOffset = 0;
    let closeTimer: ReturnType<typeof setTimeout> | null = null;

    function handleTouchStart(event: TouchEvent) {
      if (event.touches.length !== 1 || !sheet) {
        tracking = false;
        return;
      }
      const target = event.target instanceof Element ? event.target : null;
      if (target?.closest("[data-sheet-no-drag]")) {
        tracking = false;
        return;
      }
      const touch = event.touches[0];
      tracking = true;
      mode = null;
      startX = touch.clientX;
      startY = touch.clientY;
      lastY = touch.clientY;
      lastTime = event.timeStamp;
      velocity = 0;
      currentOffset = 0;
      height = sheet.getBoundingClientRect().height;
      canStartDrag = Boolean(target?.closest("[data-sheet-handle]")) || scrollChainAtTop(target, sheet);
    }

    function handleTouchMove(event: TouchEvent) {
      if (!tracking) return;
      const touch = event.touches[0];
      const dx = touch.clientX - startX;
      const dy = touch.clientY - startY;
      if (mode === null) {
        // Inside the slop, a downward pull at the top is claimed right away:
        // some browsers stop honoring preventDefault once a scroll/overscroll
        // has begun, and there is nothing above to scroll to anyway.
        if (canStartDrag && dy > 0 && Math.abs(dy) >= Math.abs(dx) && event.cancelable) event.preventDefault();
        mode = classifySheetGesture({ dx, dy, canStartDrag });
        if (mode === null) return;
        if (mode === "ignore") {
          tracking = false;
          return;
        }
        setSheetHeight(height);
        setDragging(true);
      }
      if (event.cancelable) event.preventDefault();
      const elapsed = event.timeStamp - lastTime;
      if (elapsed > 0) velocity = (touch.clientY - lastY) / elapsed;
      lastY = touch.clientY;
      lastTime = event.timeStamp;
      currentOffset = sheetDragOffset(dy, height);
      setOffset(currentOffset);
    }

    function handleTouchEnd(event: TouchEvent) {
      if (!tracking) return;
      tracking = false;
      if (mode !== "drag") return;
      mode = null;
      setDragging(false);
      const releaseVelocity = event.timeStamp - lastTime > STALE_VELOCITY_MS ? 0 : velocity;
      if (shouldDismissSheet({ offset: currentOffset, velocity: releaseVelocity, sheetHeight: height })) {
        if (prefersReducedMotion()) {
          onDismissRef.current();
          return;
        }
        setClosing(true);
        setOffset(height + 24);
        closeTimer = setTimeout(() => {
          onDismissRef.current();
          // A caller that keeps this hook mounted (the GM orb) must reopen
          // at rest, not still translated off-screen.
          setClosing(false);
          setOffset(0);
        }, CLOSE_TRANSITION_MS);
      } else {
        setOffset(0);
      }
    }

    function handleTouchCancel() {
      if (!tracking) return;
      tracking = false;
      mode = null;
      setDragging(false);
      setOffset(0);
    }

    sheet.addEventListener("touchstart", handleTouchStart, { passive: true });
    sheet.addEventListener("touchmove", handleTouchMove, { passive: false });
    sheet.addEventListener("touchend", handleTouchEnd);
    sheet.addEventListener("touchcancel", handleTouchCancel);
    return () => {
      sheet.removeEventListener("touchstart", handleTouchStart);
      sheet.removeEventListener("touchmove", handleTouchMove);
      sheet.removeEventListener("touchend", handleTouchEnd);
      sheet.removeEventListener("touchcancel", handleTouchCancel);
      if (closeTimer) clearTimeout(closeTimer);
    };
  }, [enabled]);

  // The transition stays on between drags so a snap-back animates from the
  // released offset to rest instead of jumping.
  const sheetStyle: CSSProperties = {
    transform: offset !== 0 ? `translate3d(0, ${offset}px, 0)` : undefined,
    transition: dragging ? "none" : closing ? `transform ${CLOSE_TRANSITION_MS}ms ease-in` : SNAP_BACK_TRANSITION,
  };
  const dragProgress = sheetHeight > 0 ? Math.min(1, Math.max(0, offset / sheetHeight)) : 0;

  return { sheetRef, sheetStyle, dragProgress };
}

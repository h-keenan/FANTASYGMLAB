"use client";

import { useRef } from "react";

import { nextSheetSnap, type SheetSnap } from "@/lib/playerAnatomy";

/**
 * The grab bar at the top of every swipe-to-dismiss sheet (see
 * lib/useSheetDragDismiss.ts). A touch that starts here always drags the
 * sheet, even when the content below is scrolled. Shown only on touch
 * (coarse-pointer) devices, where the gesture exists; desktop keeps the X
 * button, Esc and the backdrop.
 *
 * A sheet with a peek and a full height (the player sheet) passes `snap` + `onSnap`: dragging the handle up goes full,
 * dragging down from full goes back to peek, and a tap toggles. Dragging down from peek stays the dismiss gesture.
 */
export function SheetHandle({ className = "", snap, onSnap }: { className?: string; snap?: SheetSnap; onSnap?: (next: SheetSnap) => void }) {
  const start = useRef<{ y: number; t: number } | null>(null);
  if (!onSnap || !snap) {
    return (
      <div className={`sheet-handle ${className}`.trim()} data-sheet-handle aria-hidden="true">
        <span className="sheet-handle-bar" />
      </div>
    );
  }
  const finish = (y: number, t: number) => {
    const s = start.current;
    start.current = null;
    if (!s) return;
    const dy = y - s.y;
    const velocity = dy / Math.max(1, t - s.t);
    const next = nextSheetSnap(snap, dy, velocity);
    if (next !== snap) onSnap(next);
  };
  return (
    <div
      className={`sheet-handle ${className}`.trim()}
      data-sheet-handle
      data-snap={snap}
      role="button"
      tabIndex={0}
      aria-label={snap === "peek" ? "Expand player sheet" : "Shrink player sheet"}
      onClick={() => onSnap(snap === "peek" ? "full" : "peek")}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSnap(snap === "peek" ? "full" : "peek");
        }
      }}
      onTouchStart={(e) => {
        start.current = { y: e.touches[0].clientY, t: Date.now() };
      }}
      onTouchEnd={(e) => finish(e.changedTouches[0].clientY, Date.now())}
    >
      <span className="sheet-handle-bar" />
    </div>
  );
}

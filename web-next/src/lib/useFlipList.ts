"use client";

import { useLayoutEffect, useRef, type RefObject } from "react";

import { flipOffset, MAX_FLIP_ROWS, MOTION_ROLE, easeCss } from "@/lib/motion";
import { useReducedMotion } from "@/lib/useMotion";

/**
 * FLIP reorder for a list whose rows change order (standings after a week, a re-sorted board): each child marked
 * `data-flip-key` slides from where it was to where it is now. Transform only, run by the browser on the compositor
 * (Web Animations API), 240ms ease-out. Rows enter/leave are not handled here (that is Presence). Skipped for reduced
 * motion, lists longer than MAX_FLIP_ROWS, and rows that moved under 2px. Pass the order key (e.g. ids joined) so it only
 * measures when the order actually changed. Mobile twin: components/ReorderRow.tsx.
 */
export function useFlipList(containerRef: RefObject<HTMLElement | null>, orderKey: string): void {
  const reduced = useReducedMotion();
  const positions = useRef<Map<string, { x: number; y: number }>>(new Map());
  useLayoutEffect(() => {
    const root = containerRef.current;
    if (!root) return;
    const rows = Array.from(root.querySelectorAll<HTMLElement>("[data-flip-key]"));
    const next = new Map<string, { x: number; y: number }>();
    for (const el of rows) {
      const box = el.getBoundingClientRect();
      next.set(el.dataset.flipKey as string, { x: box.left, y: box.top });
    }
    const previous = positions.current;
    positions.current = next;
    if (reduced || rows.length > MAX_FLIP_ROWS || previous.size === 0 || typeof rows[0]?.animate !== "function") return;
    for (const el of rows) {
      const from = previous.get(el.dataset.flipKey as string);
      const to = next.get(el.dataset.flipKey as string);
      if (!from || !to) continue;
      const offset = flipOffset(from, to);
      if (!offset) continue;
      el.animate([{ transform: `translate(${offset.dx}px, ${offset.dy}px)` }, { transform: "none" }], { duration: MOTION_ROLE.standard + 60, easing: easeCss("out") });
    }
    // orderKey is the trigger; the effect reads the DOM, not props.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderKey, reduced]);
}

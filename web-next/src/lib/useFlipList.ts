"use client";

import { useLayoutEffect, useRef, type RefObject } from "react";

import { flipOffset, MAX_FLIP_ROWS, MOTION_ROLE, easeCss, staggerDelay } from "@/lib/motion";
import { useReducedMotion } from "@/lib/useMotion";

/**
 * FLIP reorder for a list whose rows change order (standings after a week, a re-sorted board): each child marked
 * `data-flip-key` slides from where it was to where it is now. Transform only, run by the browser on the compositor
 * (Web Animations API), 240ms ease-out. Rows enter/leave are not handled here (that is Presence). Skipped for reduced
 * motion, lists longer than MAX_FLIP_ROWS, and rows that moved under 2px. Pass the order key (e.g. ids joined) so it only
 * measures when the order actually changed. `stagger` starts each row a capped step after the one above it (the Sim week-advance
 * settle: standings land in order, `staggerDelay` caps the total at 240ms). Mobile twin: components/ReorderRow.tsx.
 */
export function useFlipList(containerRef: RefObject<HTMLElement | null>, orderKey: string, options: { stagger?: boolean } = {}): void {
  const { stagger = false } = options;
  const reduced = useReducedMotion();
  const positions = useRef<Map<string, { x: number; y: number }>>(new Map());
  const lastOrder = useRef<string | null>(null);
  // Runs after every render (cheap: at most MAX_FLIP_ROWS rows are measured) so positions stay current through expanders and
  // scrolling; positions are relative to the container, so a scroll between two orders never reads as movement.
  useLayoutEffect(() => {
    const root = containerRef.current;
    if (!root) return;
    const rows = Array.from(root.querySelectorAll<HTMLElement>("[data-flip-key]"));
    if (rows.length > MAX_FLIP_ROWS) {
      positions.current = new Map();
      lastOrder.current = orderKey;
      return;
    }
    const origin = root.getBoundingClientRect();
    const next = new Map<string, { x: number; y: number }>();
    for (const el of rows) {
      const box = el.getBoundingClientRect();
      next.set(el.dataset.flipKey as string, { x: box.left - origin.left, y: box.top - origin.top });
    }
    const previous = positions.current;
    const orderChanged = lastOrder.current !== null && lastOrder.current !== orderKey;
    positions.current = next;
    lastOrder.current = orderKey;
    if (!orderChanged || reduced || previous.size === 0 || typeof rows[0]?.animate !== "function") return;
    for (const [index, el] of rows.entries()) {
      const from = previous.get(el.dataset.flipKey as string);
      const to = next.get(el.dataset.flipKey as string);
      if (!from || !to) continue;
      const offset = flipOffset(from, to);
      if (!offset) continue;
      el.animate([{ transform: `translate(${offset.dx}px, ${offset.dy}px)` }, { transform: "none" }], { duration: MOTION_ROLE.standard + 60, easing: easeCss("out"), ...(stagger ? { delay: staggerDelay(index, rows.length), fill: "backwards" as const } : {}) });
    }
  });
}

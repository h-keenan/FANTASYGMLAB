"use client";

import { useEffect, useRef, useState, useSyncExternalStore, type RefObject } from "react";

import { flashDirection, FLASH_MS } from "@/lib/motion";

const QUERY = "(prefers-reduced-motion: reduce)";

function subscribe(onChange: () => void): () => void {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return () => {};
  const mq = window.matchMedia(QUERY);
  mq.addEventListener?.("change", onChange);
  return () => mq.removeEventListener?.("change", onChange);
}

function snapshot(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function" ? window.matchMedia(QUERY).matches : false;
}

/** The reduced-motion switch: true when the OS asks for less motion. Live (updates if the setting changes). Server render: false. */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, snapshot, () => false);
}

/**
 * True once the element has entered the viewport (an IntersectionObserver, then it disconnects): entrances play
 * when something scrolls into view, not all at page load. Without IntersectionObserver (old browsers, tests) it is
 * true immediately so nothing stays hidden.
 */
export function useInView<T extends Element>(ref: RefObject<T | null>, enabled = true): boolean {
  const [seen, setSeen] = useState(() => typeof IntersectionObserver === "undefined");
  useEffect(() => {
    if (!enabled || seen) return;
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setSeen(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setSeen(true);
          io.disconnect();
        }
      },
      { rootMargin: "0px 0px -8% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [enabled, seen, ref]);
  return seen;
}

/**
 * "up" / "down" for ~1.1s after `value` changes (never on the first render), else null: drives the green/red score
 * flash. Pure change detection lives in lib/motion.ts (flashDirection).
 */
export function useFlashOnChange(value: number | null | undefined): "up" | "down" | null {
  const previous = useRef(value);
  const [flash, setFlash] = useState<"up" | "down" | null>(null);
  useEffect(() => {
    const dir = flashDirection(previous.current, value);
    previous.current = value;
    if (!dir) return;
    setFlash(dir);
    const timer = setTimeout(() => setFlash(null), FLASH_MS);
    return () => clearTimeout(timer);
  }, [value]);
  return flash;
}

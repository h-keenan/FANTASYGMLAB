"use client";

import { useSyncExternalStore } from "react";

const QUERY = "(max-width: 767px)";

/** True below 768 px. False where matchMedia is missing (tests, SSR). */
export function useIsPhone(): boolean {
  return useSyncExternalStore(
    (notify) => {
      if (typeof window === "undefined" || typeof window.matchMedia !== "function") return () => {};
      const media = window.matchMedia(QUERY);
      media.addEventListener("change", notify);
      return () => media.removeEventListener("change", notify);
    },
    () => (typeof window !== "undefined" && typeof window.matchMedia === "function" ? window.matchMedia(QUERY).matches : false),
    () => false,
  );
}

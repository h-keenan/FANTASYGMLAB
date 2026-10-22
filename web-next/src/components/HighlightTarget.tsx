"use client";

import { useEffect, useRef, type ReactNode } from "react";

/**
 * Recommendation-compliance audit, Check 3 — CTA reachability: wraps a row
 * so the one a GM Plan/Dashboard tile's CTA named (?playerId=) scrolls into
 * view and stays visually marked once the page loads, instead of leaving
 * the user to re-find it among every other row. `active` is simply false
 * whenever there's no match (stale/absent id) — renders exactly as before,
 * never breaks the page. Extracted from byte-identical local copies in
 * WaiversContent.tsx and MyTeamContent.tsx.
 */
export function HighlightTarget({ active, children }: { active: boolean; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (active && ref.current && typeof ref.current.scrollIntoView === "function") {
      ref.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [active]);
  return (
    <div
      ref={ref}
      data-highlighted={active ? "true" : undefined}
      style={active ? { outline: "2px solid var(--color-accent)", outlineOffset: "2px", borderRadius: "0.25rem" } : undefined}
    >
      {children}
    </div>
  );
}

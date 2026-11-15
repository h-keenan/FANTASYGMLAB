"use client";

import Link from "next/link";
import type { ReactNode } from "react";

/**
 * The one "go to the full page" link of a compact module (UI pass 5 D6, coridian_ 2026-11-14). A module is EITHER a row that
 * navigates (LinkModule: the whole row taps, trailing arrow) OR it expands (chevron). It is never both in the header, so the
 * destination of an expandable module lives here, at the end of its expanded body: accent text plus an arrow, 44px tall.
 * Mobile twin: `ModuleMore` in mobile/src/components/ModuleMore.tsx.
 */
export function ModuleMore({ href, onClick, children }: { href?: string; onClick?: () => void; children: ReactNode }) {
  const style = { color: "var(--color-accent)", minHeight: "var(--touch-target-min)", display: "inline-flex", alignItems: "center", gap: 4 } as const;
  const content = (
    <>
      {children}
      <span aria-hidden="true">→</span>
    </>
  );
  if (href) {
    return (
      <Link href={href} className="self-start text-sm font-bold" style={style} data-testid="module-more">
        {content}
      </Link>
    );
  }
  return (
    <button type="button" onClick={onClick} className="self-start text-sm font-bold" style={style} data-testid="module-more">
      {content}
    </button>
  );
}

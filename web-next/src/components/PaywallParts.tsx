"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { PremiumComparison } from "@/components/PremiumComparison";
import {
  PAYWALL_COMPARISON_TITLE,
  proHighlights,
  type HighlightIcon,
} from "@/lib/paywallCopy";
import type { PremiumComparisonRow } from "@/lib/premiumComparison";

const ICON_PATHS: Record<HighlightIcon, ReactNode> = {
  // Checklist: the Today briefing.
  today: (
    <>
      <path d="M4 6.5l1.6 1.6L8.4 5.2" />
      <path d="M4 12.5l1.6 1.6 2.8-2.9" />
      <path d="M4 18.5l1.6 1.6 2.8-2.9" />
      <path d="M12 7h8M12 13h8M12 19h8" />
    </>
  ),
  // Two arrows: trades.
  trades: (
    <>
      <path d="M4 8h14M14 4l4 4-4 4" />
      <path d="M20 16H6M10 12l-4 4 4 4" />
    </>
  ),
  // Plus on a list: waiver board.
  waivers: (
    <>
      <path d="M4 6h10M4 12h7M4 18h10" />
      <path d="M18 11v8M14 15h8" />
    </>
  ),
};

/** The three headline Pro benefits as icon tiles: icon, short title, Free -> Pro number. */
export function ProHighlights({ rows }: { rows: PremiumComparisonRow[] }) {
  return (
    <ul className="grid grid-cols-3 gap-2 m-0 p-0" style={{ listStyle: "none" }} data-testid="pro-highlights">
      {proHighlights(rows).map((item) => (
        <li key={item.key} className="glass-surface flex flex-col items-center gap-1.5 p-3 text-center">
          <span
            aria-hidden="true"
            className="inline-flex shrink-0 items-center justify-center"
            style={{
              width: 40,
              height: 40,
              borderRadius: 9999,
              color: "var(--color-premium)",
              background: "color-mix(in srgb, var(--color-premium) 15%, transparent)",
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              {ICON_PATHS[item.icon]}
            </svg>
          </span>
          <span className="text-sm font-bold">{item.title}</span>
          <span className="text-xs font-extrabold" style={{ color: "var(--color-premium)" }}>
            {item.stat}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** The full Free-vs-Pro table behind one "Compare plans" chip, so it never becomes a wall of text. */
export function ComparisonDisclosure({ rows }: { rows: PremiumComparisonRow[] }) {
  return (
    <details className="flex flex-col items-center" data-testid="pro-comparison">
      <summary
        className="cursor-pointer text-xs font-bold px-3"
        style={{
          minHeight: "var(--touch-target-min)",
          display: "inline-flex",
          alignItems: "center",
          color: "var(--color-premium)",
          border: "var(--border-width-default) solid var(--color-premium)",
          borderRadius: "var(--radius-pill)",
        }}
      >
        {PAYWALL_COMPARISON_TITLE}
      </summary>
      <div className="glass-surface p-3 mt-2 w-full">
        <PremiumComparison rows={rows} />
      </div>
    </details>
  );
}

/** Terms / subscription terms / privacy, one line. */
export function PaywallLegalLinks() {
  const link = (href: string, label: string) => (
    <Link href={href} className="underline" style={{ color: "var(--color-text-muted)" }}>
      {label}
    </Link>
  );
  return (
    <p className="text-xs text-center m-0" style={{ color: "var(--color-text-muted)" }}>
      By continuing you agree to our {link("/legal/terms", "Terms")}, {link("/legal/subscription_terms", "Subscription Terms")} and{" "}
      {link("/legal/privacy", "Privacy Policy")}.
    </p>
  );
}

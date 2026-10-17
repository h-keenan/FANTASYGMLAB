import Link from "next/link";

import type { PremiumUpsell } from "@/lib/api";

/**
 * The lock/upsell card every Premium-only page shows a Free caller instead
 * of real data — extracted from PortfolioContent.tsx so GM Plan and Trade
 * Finder (newly gated to match app.py's premium barriers, coridian_:
 * "streamlit had proper premium bqarriers") reuse the exact same card
 * rather than each inventing their own.
 */
export function PremiumUpsellCard({
  kicker,
  upsell,
  fallbackTitle,
  fallbackBody,
}: {
  kicker: string;
  upsell: PremiumUpsell | null;
  fallbackTitle: string;
  fallbackBody: string;
}) {
  const title = upsell?.title ?? fallbackTitle;
  const body = upsell?.body ?? fallbackBody;

  return (
    <main className="flex-1 flex flex-col gap-8 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {kicker}
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{title}</h1>
      </header>
      <div
        className="p-4 flex flex-col gap-3"
        style={{ background: "var(--color-action-soft)", border: "var(--border-width-default) solid var(--color-action)" }}
      >
        <p className="text-sm">{body}</p>
        <Link href="/premium" className="text-sm font-bold self-start" style={{ color: "var(--color-premium)" }}>
          Upgrade →
        </Link>
      </div>
    </main>
  );
}

"use client";

import { useEffect } from "react";

import { AccentCard } from "@/components/AccentCard";
import { ButtonLink } from "@/components/Button";
import { SectionHeading } from "@/components/SectionHeading";
import { trackUse } from "@/lib/analytics";
import type { PremiumUpsell } from "@/lib/api";
import { paidPreview } from "@/lib/paidPreviews";

// Kickers that are also a nav label: those pages get the page name as the H1.
const NAV_PAGE_KICKERS = new Set(["Draft Center", "College Scouting", "Commissioner", "Live Draft", "Portfolio", "GM Plan", "Trade Finder"]);

/**
 * The lock/upsell card every Premium-only page shows a Free caller instead
 * of real data: the shared `AccentCard` (premium-gold left edge, the one
 * card padding) with the upsell copy and a primary "Upgrade" button. Mirrors
 * mobile's PremiumLock.
 */
export function PremiumUpsellCard({
  kicker,
  upsell,
  fallbackTitle,
  fallbackBody,
  // GM Plan renders this mid-page, inside its OWN <main> (Protected
  // Players/Watching stay free below it). `bare` drops this component's own
  // <main> wrapper so it composes as a plain section instead of nesting one
  // <main> inside another (invalid HTML). Every other caller omits it.
  bare = false,
  leagueName,
  example,
}: {
  kicker: string;
  upsell: PremiumUpsell | null;
  fallbackTitle: string;
  fallbackBody: string;
  bare?: boolean;
  /** Names the person's own league in the preview bullets. */
  leagueName?: string;
  /** One real fact from the person's own league that the page already has
   * (never invented), shown under the preview bullets. */
  example?: string;
}) {
  const title = upsell?.title ?? fallbackTitle;
  const body = upsell?.body ?? fallbackBody;
  const Wrapper = bare ? "section" : "main";
  // Conversion-by-feature: which locked card was seen and which upsell was
  // tapped, keyed by the kicker (stable per gated surface).
  const gateFeature = kicker.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "premium";
  useEffect(() => {
    trackUse(gateFeature, "gate_seen", { tier: "free" });
  }, [gateFeature]);
  const preview = paidPreview(gateFeature, leagueName);

  return (
    <Wrapper className={bare ? "flex flex-col gap-8" : "flex-1 flex flex-col gap-8 px-4 py-8 max-w-3xl w-full mx-auto"}>
      {bare ? (
        // Inside a page that already has its own <h1>: a section heading, not a second page title.
        <SectionHeading kicker={kicker}>{title}</SectionHeading>
      ) : (
        <header className="flex flex-col gap-1">
          {NAV_PAGE_KICKERS.has(kicker) ? (
            // A whole paid page: the H1 is the page name (the nav label),
            // the pitch is the line under it.
            <>
              {leagueName ? (
                <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {leagueName}
                </span>
              ) : null}
              <h1 style={{ font: "var(--font-page-title)" }}>{kicker}</h1>
              <p className="text-base font-bold">{title}</p>
            </>
          ) : (
            <>
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                {kicker}
              </span>
              <h1 style={{ font: "var(--font-page-title)" }}>{title}</h1>
            </>
          )}
        </header>
      )}
      <AccentCard accent="var(--color-premium)" as="div" className="premium-glow-card">
        <p className="text-sm">{body}</p>
        {preview ? (
          <div className="flex flex-col gap-1.5" data-testid="paid-preview">
            <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
              What you get with Pro
            </span>
            <ul className="flex flex-col gap-1 text-sm list-disc pl-5">
              {preview.bullets.map((bullet) => (
                <li key={bullet}>{bullet}</li>
              ))}
            </ul>
            {example ? (
              <p className="text-sm font-bold" data-testid="paid-preview-example">
                {example}
              </p>
            ) : null}
            {preview.freeIncludes ? (
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                {preview.freeIncludes}
              </p>
            ) : null}
          </div>
        ) : null}
        <ButtonLink href="/premium" variant="premium" onClick={() => trackUse(gateFeature, "upsell_tapped", { tier: "free" })}>
          Upgrade →
        </ButtonLink>
      </AccentCard>
    </Wrapper>
  );
}

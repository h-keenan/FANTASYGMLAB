"use client";

import { useEffect } from "react";

import { AccentCard } from "@/components/AccentCard";
import { ButtonLink } from "@/components/Button";
import { trackUse } from "@/lib/analytics";
import type { PremiumUpsell } from "@/lib/api";

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
}: {
  kicker: string;
  upsell: PremiumUpsell | null;
  fallbackTitle: string;
  fallbackBody: string;
  bare?: boolean;
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

  return (
    <Wrapper className={bare ? "flex flex-col gap-8" : "flex-1 flex flex-col gap-8 px-4 py-8 max-w-3xl w-full mx-auto"}>
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {kicker}
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{title}</h1>
      </header>
      <AccentCard accent="var(--color-premium)" as="div" className="premium-glow-card">
        <p className="text-sm">{body}</p>
        <ButtonLink href="/premium" variant="premium" onClick={() => trackUse(gateFeature, "upsell_tapped", { tier: "free" })}>
          Upgrade →
        </ButtonLink>
      </AccentCard>
    </Wrapper>
  );
}

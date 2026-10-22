"use client";

import Link from "next/link";
import { useEffect } from "react";

import { trackUse } from "@/lib/analytics";
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
  // GM Plan (Revision 20 merge, 2026-10-18) renders this mid-page, inside
  // its OWN <main> — Protected Players/Watching stay free below it, so a
  // top-level `return <PremiumUpsellCard .../>` (every other caller's
  // pattern) isn't an option there. `bare` drops this component's own
  // <main> wrapper so it composes as a plain section instead of nesting
  // one <main> inside another (invalid HTML, and would double the page
  // padding/width constraints). Every existing caller omits this and
  // keeps the full-page <main> behavior unchanged.
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
      <div
        className="p-4 flex flex-col gap-3"
        style={{ background: "var(--color-action-soft)", border: "var(--border-width-default) solid var(--color-action)" }}
      >
        <p className="text-sm">{body}</p>
        <Link
          href="/premium"
          onClick={() => trackUse(gateFeature, "upsell_tapped", { tier: "free" })}
          className="text-sm font-bold self-start" style={{ color: "var(--color-premium)" }}>
          Upgrade →
        </Link>
      </div>
    </Wrapper>
  );
}

"use client";

import { useEffect } from "react";

import { AccentCard } from "@/components/AccentCard";
import { ButtonLink } from "@/components/Button";
import { trackUse } from "@/lib/analytics";
import type { UsageGate } from "@/lib/api";

/** Free-tier teaser for advanced usage (owner decision 2026-11-03): what Pro unlocks,
 * from the server's own gating marker. The data itself is withheld server-side, so
 * this only renders copy and an upgrade link. Mirrors mobile's PremiumLock use. */
export function UsageProTeaser({ gate, feature = "advanced_usage" }: { gate: UsageGate; feature?: string }) {
  useEffect(() => {
    trackUse(feature, "gate_seen", { tier: "free" });
  }, [feature]);
  return (
    <div data-testid="usage-pro-teaser" className="mt-3">
    <AccentCard accent="var(--color-premium)" as="div" className="premium-glow-card">
      <p className="text-sm font-bold">{gate.upsell.title}</p>
      <ul className="text-xs flex flex-col gap-0.5 list-disc pl-4" style={{ color: "var(--color-text-secondary)" }}>
        {gate.unlocks.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <ButtonLink href="/premium" variant="premium" size="sm" onClick={() => trackUse(feature, "upsell_tapped", { tier: "free" })}>
        Upgrade to Pro →
      </ButtonLink>
    </AccentCard>
    </div>
  );
}

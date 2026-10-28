"use client";

import { useEffect } from "react";

import { AccentCard } from "@/components/AccentCard";
import { ButtonLink } from "@/components/Button";
import { trackUse } from "@/lib/analytics";
import type { LimitWallModel } from "@/lib/limitWall";

/**
 * The wall a plan limit shows instead of a generic error: what limit, when
 * it resets, what Pro adds, one upgrade CTA (guests: create an account,
 * both land on /premium). Model comes from lib/limitWall.ts, shared with
 * mobile's LimitWall.
 */
export function LimitWall({ wall, feature }: { wall: LimitWallModel; feature: string }) {
  useEffect(() => {
    trackUse(feature, "gate_seen", { tier: "free" });
  }, [feature]);
  return (
    <div data-limit-wall={wall.reason}>
    <AccentCard accent="var(--color-premium)" as="div" className="premium-glow-card">
      <h2 role="alert" className="text-base font-bold m-0">
        {wall.title}
      </h2>
      <p className="text-sm m-0">{wall.body}</p>
      <p className="text-sm m-0" style={{ color: "var(--color-text-secondary)" }}>
        {wall.proLine}
      </p>
      <ButtonLink href="/premium" variant="premium" onClick={() => trackUse(feature, "upsell_tapped", { tier: "free" })}>
        {wall.ctaLabel} →
      </ButtonLink>
    </AccentCard>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { ButtonLink } from "@/components/Button";
import { trackUse } from "@/lib/analytics";
import { trackOnboardingStepViewed } from "@/lib/onboardingAnalytics";
import { funnelStepIndex, shouldShowTrialOffer, TRIAL_OFFER_CTA, TRIAL_OFFER_DISMISS, TRIAL_OFFER_NOTE, TRIAL_OFFER_TITLE } from "@/lib/firstRunFlow";
import { markOnboardingStepCompleted, trialOfferState } from "@/lib/onboardingProgress";
import { PAYWALL_HERO_SUB } from "@/lib/paywallCopy";

const SURFACE = "first_league_today";

/**
 * The trial offer, moved after connect (owner decision 2026-11): a quiet,
 * dismissible card UNDER the first league's Today briefing, shown once, so
 * the person has seen real value before being asked anything. "Continue
 * free" resolves it for good; nothing is blocked either way. Price and trial
 * terms live on /premium (real plan data), never on this card. Mobile twin:
 * mobile/src/components/FirstValueOfferCard.tsx.
 */
export function FirstValueOfferCard({ userId, isPremium }: { userId: string; isPremium: boolean }) {
  // Read after mount: localStorage is not available during prerender.
  const [visible, setVisible] = useState(false);
  /* eslint-disable react-hooks/set-state-in-effect -- localStorage is client-only, read after mount */
  useEffect(() => {
    const state = trialOfferState(userId);
    // Funnel: the first league view was actually reached (armed at connect,
    // so returning users opening their Dashboard never count).
    if (state === "armed") trackOnboardingStepViewed("first_league_view", funnelStepIndex("first_league_view"));
    setVisible(shouldShowTrialOffer({ state, isPremium, onLeagueHome: true }));
  }, [userId, isPremium]);
  /* eslint-enable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (visible) trackUse("paywall", "offer_seen", { tier: "free", props: { source_surface: SURFACE } });
  }, [visible]);

  if (!visible) return null;

  const resolve = (action: "offer_cta" | "offer_dismissed") => {
    trackUse("paywall", action, { tier: "free", props: { source_surface: SURFACE } });
    markOnboardingStepCompleted(userId, "paywall");
    if (action === "offer_dismissed") setVisible(false);
  };

  return (
    <AccentCard accent="var(--color-premium)" data-testid="first-value-offer">
      <div className="flex flex-col gap-2">
        <p className="m-0 text-base font-bold">{TRIAL_OFFER_TITLE}</p>
        <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {PAYWALL_HERO_SUB}
        </p>
        <p className="m-0 text-xs" style={{ color: "var(--color-text-muted)" }}>
          {TRIAL_OFFER_NOTE}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <ButtonLink href="/premium" variant="premium" size="sm" onClick={() => resolve("offer_cta")}>
            {TRIAL_OFFER_CTA}
          </ButtonLink>
          <button type="button" onClick={() => resolve("offer_dismissed")} className="tap-link text-sm underline" style={{ color: "var(--color-text-muted)" }}>
            {TRIAL_OFFER_DISMISS}
          </button>
        </div>
      </div>
    </AccentCard>
  );
}

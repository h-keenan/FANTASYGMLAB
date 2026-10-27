"use client";

import { useEffect, useState } from "react";

import { TRIAL_CARD_NOTE } from "@/lib/trialCopy";
import { DEFAULT_TRIAL_DAYS, fetchPublicTrialDays, trialHeadline } from "@/lib/landingTrial";

/** Landing-page trial line. Renders the shared default in the static HTML,
 * then swaps in the live length from the public billing-plans function. */
export function LandingTrialHeadline() {
  const [days, setDays] = useState(DEFAULT_TRIAL_DAYS);

  useEffect(() => {
    const controller = new AbortController();
    void fetchPublicTrialDays(controller.signal).then((live) => {
      if (live !== null && !controller.signal.aborted) setDays(live);
    });
    return () => controller.abort();
  }, []);

  return (
    <div className="flex flex-col gap-0.5 text-center md:text-left">
      <p className="text-xs font-bold" style={{ color: "var(--color-accent)" }}>
        {trialHeadline(days)}
      </p>
      {/* The checkout is created with payment_method_collection: "always"
          (supabase/functions/_shared/stripe_api.ts), so the paid trial does
          need a card; the free plan does not. Say both, once. */}
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {TRIAL_CARD_NOTE}
      </p>
    </div>
  );
}

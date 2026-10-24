"use client";

import { useEffect, useState } from "react";

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
    <p className="text-xs font-bold text-center md:text-left" style={{ color: "var(--color-accent)" }}>
      {trialHeadline(days)}
    </p>
  );
}

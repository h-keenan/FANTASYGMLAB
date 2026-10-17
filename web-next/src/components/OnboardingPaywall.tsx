"use client";

import { useEffect, useState } from "react";

import { api, type BillingPlansResponse } from "@/lib/api";
import { PlanCard } from "@/components/PremiumContent";

/**
 * Shown once, right after a brand-new account's first real sign-in (email
 * confirmed), before SleeperImportForm — the one point in the flow that is
 * definitely "this account has never finished setup" (page.tsx's own
 * returning-session effect already redirects anyone with a saved league
 * away before they ever reach here, so by construction this never shows to
 * an existing, onboarded user). Skippable: this is a trial offer, not a
 * hard gate — Free access stays real and immediate.
 *
 * `returnTo="/"` on each plan's checkout so a completed purchase resumes
 * onboarding (connect Sleeper) instead of landing on the standalone
 * /premium page, which would otherwise be a dead end mid-signup.
 */
export function OnboardingPaywall({ onSkip }: { onSkip: () => void }) {
  const [plans, setPlans] = useState<BillingPlansResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getBillingPlans()
      .then((result) => {
        if (!cancelled) setPlans(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load plans.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1 text-center">
        <h2 style={{ font: "var(--type-section-title)" }}>Start your 7-day free trial</h2>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Full access to the GM toolkit. Cancel anytime before it ends and you&apos;re never charged.
        </p>
      </div>

      {error ? (
        <p role="alert" className="text-sm" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : !plans ? (
        <p className="text-sm text-center" style={{ color: "var(--color-text-muted)" }}>
          Loading plans…
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {plans.plans.map((plan) => (
            <PlanCard key={`${plan.tier}-${plan.interval}`} plan={plan} returnTo="/" />
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={onSkip}
        className="text-xs underline self-center"
        style={{ color: "var(--color-text-muted)" }}
      >
        Skip for now — continue free
      </button>
    </div>
  );
}

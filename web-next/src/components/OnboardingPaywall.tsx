"use client";

import { SectionHeading } from "@/components/SectionHeading";
import { useEffect, useState } from "react";

import { api, type BillingPlan, type BillingPlansResponse } from "@/lib/api";
import { activeTrialDays, thenPriceLine, trialCtaLabel } from "@/lib/trialCopy";
import { trackOnboarding, trackOnboardingStepViewed } from "@/lib/onboardingAnalytics";
import { EmbeddedCheckoutModal } from "@/components/EmbeddedCheckoutModal";
import { Button } from "@/components/Button";

// Zach: "have one product here and call it Get Started For Free with a few
// bullets" (first pass: one CTA, the annual plan, with a handful of its
// real feature bullets in a card), then immediately after seeing it live:
// "have an annual button instead of showing the plan" — dropped the card/
// bullets entirely, down to a single button. Price/terms stay disclosed as
// fine print below the button (can't start a real paid trial without
// saying what it costs after), just no card chrome or feature list. The
// monthly-vs-annual choice still exists on /premium for anyone who wants
// it later.
function FreeTrialButton({ plan, publishableKey, trialDays }: { plan: BillingPlan; publishableKey: string; trialDays: number }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clientSecret, setClientSecret] = useState<string | null>(null);

  const subscribe = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.startBillingCheckout(plan.tier, plan.interval, "/", "embedded");
      if (!result.client_secret) throw new Error("Could not start checkout.");
      setClientSecret(result.client_secret);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start checkout.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      {error ? (
        <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}
      <Button
        type="button"
        onClick={subscribe}
        disabled={busy}
        style={{ alignSelf: "auto" }}
      >
        {busy ? "Starting…" : trialDays > 0 ? trialCtaLabel(trialDays) : "Subscribe"}
      </Button>
      <p className="text-xs text-center" style={{ color: "var(--color-text-muted)" }}>
        {trialDays > 0 ? thenPriceLine(plan) : `${plan.price} ${plan.cadence}. Cancel anytime.`}
      </p>
      {clientSecret ? (
        <EmbeddedCheckoutModal clientSecret={clientSecret} publishableKey={publishableKey} onClose={() => setClientSecret(null)} />
      ) : null}
    </div>
  );
}

/**
 * Shown once, right after a brand-new account's first real sign-in (email
 * confirmed), before SleeperImportForm — the one point in the flow that is
 * definitely "this account has never finished setup" (page.tsx's own
 * returning-session effect already redirects anyone with a saved league
 * away before they ever reach here, so by construction this never shows to
 * an existing, onboarded user). Skippable: this is a trial offer, not a
 * hard gate — Free access stays real and immediate.
 */
// The step after the carousel's last step (8 features + connect + level = 0..9).
const PAYWALL_STEP_INDEX = 10;

export function OnboardingPaywall({ onSkip }: { onSkip: () => void }) {
  const [plans, setPlans] = useState<BillingPlansResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    trackOnboardingStepViewed("paywall", PAYWALL_STEP_INDEX);
  }, []);

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

  const trialDays = activeTrialDays(plans?.trial);
  const annualPlan = plans?.plans.find((plan) => plan.interval === "annual") ?? plans?.plans[0] ?? null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1 text-center">
        <SectionHeading>{trialDays > 0 ? `Try Pro free for ${trialDays} days` : "Unlock the full GM toolkit"}</SectionHeading>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Full access to the GM toolkit.
        </p>
      </div>

      {error ? (
        <p role="alert" className="text-sm" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : !annualPlan ? (
        <p className="text-sm text-center" style={{ color: "var(--color-text-muted)" }}>
          Loading plans…
        </p>
      ) : (
        <FreeTrialButton plan={annualPlan} publishableKey={plans?.stripe_publishable_key ?? ""} trialDays={trialDays} />
      )}

      <button
        type="button"
        onClick={() => {
          trackOnboarding("skipped", { step: "paywall", step_index: PAYWALL_STEP_INDEX });
          onSkip();
        }}
        className="text-xs underline self-center"
        style={{ color: "var(--color-text-muted)" }}
      >
        Skip for now — continue free
      </button>
    </div>
  );
}

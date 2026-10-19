"use client";

import { useEffect, useState } from "react";

import { api, type BillingPlan, type BillingPlansResponse } from "@/lib/api";
import { EmbeddedCheckoutModal } from "@/components/EmbeddedCheckoutModal";
import { FeatureIncludedGlyph } from "@/components/PremiumGlyph";

// Zach: "have one product here and call it Get Started For Free with a few
// bullets" — this screen used to show both Pro plans (Monthly + Annual)
// side by side as separate priced cards, which buried the actual offer
// (a real 7-day FREE trial) under two dollar amounts on the one screen
// most responsible for a new visitor actually starting it. One CTA, the
// annual plan (the better deal for a visitor who doesn't yet have a
// reason to prefer month-to-month), bullets pulled straight from the
// plan's own real feature list rather than new invented copy — just
// fewer of them. The monthly-vs-annual choice still exists on /premium
// for anyone who wants it later.
const BULLET_COUNT = 4;

function FreeTrialCard({ plan, publishableKey }: { plan: BillingPlan; publishableKey: string }) {
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
    <div className="p-4 flex flex-col gap-2" style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-premium)" }}>
      <ul className="flex flex-col gap-1.5">
        {plan.features.slice(0, BULLET_COUNT).map((feature) => (
          <li key={feature} className="text-sm flex items-start gap-2" style={{ color: "var(--color-text-secondary)" }}>
            <span style={{ color: "var(--color-success)", marginTop: "0.1rem", flexShrink: 0 }}>
              <FeatureIncludedGlyph />
            </span>
            <span>{feature}</span>
          </li>
        ))}
      </ul>
      {error ? (
        <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}
      <button
        type="button"
        onClick={subscribe}
        disabled={busy}
        className="px-4 py-2.5 text-sm font-bold"
        style={{
          background: "var(--color-accent-strong)",
          color: "var(--color-brand-mark-ink)",
          fontWeight: "var(--font-weight-button)",
          opacity: busy ? "var(--opacity-disabled)" : 1,
        }}
      >
        {busy ? "Starting…" : "Get Started For Free"}
      </button>
      <p className="text-xs text-center" style={{ color: "var(--color-text-muted)" }}>
        Then {plan.price} {plan.cadence} — cancel anytime before your trial ends and you&apos;re never charged.
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

  const annualPlan = plans?.plans.find((plan) => plan.interval === "annual") ?? plans?.plans[0] ?? null;

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
      ) : !annualPlan ? (
        <p className="text-sm text-center" style={{ color: "var(--color-text-muted)" }}>
          Loading plans…
        </p>
      ) : (
        <FreeTrialCard plan={annualPlan} publishableKey={plans?.stripe_publishable_key ?? ""} />
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

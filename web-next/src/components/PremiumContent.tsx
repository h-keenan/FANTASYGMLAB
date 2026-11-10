"use client";

import { SectionHeading } from "@/components/SectionHeading";
import { useEffect, useState } from "react";

import { trackFeatureUse } from "@/lib/analytics";

import { useAuth } from "@/context/AuthContext";
import { TrialAccountGate, isAccountRequiredError } from "@/components/TrialAccountGate";
import { api, type BillingPlan, type BillingTrial } from "@/lib/api";
import { activeTrialDays, thenPriceLine, trialCtaLabel, trialEndLabel } from "@/lib/trialCopy";
import dynamic from "next/dynamic";

// Stripe.js + react-stripe-js load only when a checkout is actually opened.
const EmbeddedCheckoutModal = dynamic(() => import("@/components/EmbeddedCheckoutModal").then((m) => m.EmbeddedCheckoutModal), {
  ssr: false,
});
import { PlanTierGlyph } from "@/components/PremiumGlyph";
import { Button } from "@/components/Button";
import { ComparisonDisclosure, PaywallLegalLinks, ProHighlights } from "@/components/PaywallParts";
import { HelpLink } from "@/components/HelpLink";
import { PillRow } from "@/components/PillRow";
import { ToneBadge } from "@/components/ToneBadge";
import { FALLBACK_PREMIUM_COMPARISON } from "@/lib/premiumComparison";
import {
  PAYWALL_CARD_NOTE,
  PAYWALL_HERO_SUB,
  PAYWALL_HERO_TITLE,
  PAYWALL_TRIAL_REASSURANCE,
  annualSavingsPercent,
  parsePrice,
} from "@/lib/paywallCopy";
import type { PremiumComparisonRow } from "@/lib/premiumComparison";

/** "$59.99" -> "$5.00" (the yearly price over 12 months), keeping the currency prefix. */
function annualPerMonth(price: string): string | null {
  const n = parsePrice(price);
  if (n === null) return null;
  const prefix = /^[^\d]*/.exec(price)?.[0].trim() ?? "";
  return `${prefix}${(n / 12).toFixed(2)}`;
}

const TIER_LABELS: Record<BillingPlan["tier"], string> = {
  pro: "Pro",
  front_office: "Front Office",
};

/**
 * One plan at a time: price, the per-month equivalent for yearly, a full-width
 * CTA, and the trial/cancel reassurance. All billing logic (checkout start,
 * guest gate, embedded modal) is unchanged from the old per-plan cards; only
 * the layout changed. Benefits live once above (ProHighlights), never repeated
 * per plan.
 */
export function PlanCheckout({
  plan,
  monthlyPlan,
  returnTo,
  publishableKey,
  trialDays = 0,
}: {
  plan: BillingPlan;
  /** The same tier's monthly plan, for the per-month equivalent and savings. */
  monthlyPlan?: BillingPlan | null;
  returnTo?: string;
  publishableKey: string;
  trialDays?: number;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const { isGuest } = useAuth();
  // Also set when the server says account_required (stale/out-of-sync guest state).
  const [accountRequired, setAccountRequired] = useState(false);

  // Zach, 2026-10-19: "We need to try to embed stripe so theres not a
  // million redirectes" — mounts Stripe's own Checkout UI in place
  // (EmbeddedCheckoutModal) instead of leaving the app for
  // checkout.stripe.com. Stripe itself still navigates the page to
  // return_url once payment completes.
  const subscribe = async () => {
    setBusy(true);
    setError(null);
    trackFeatureUse("premium_cta_clicked", { dedupe: false, props: { tier: plan.tier, interval: plan.interval } });
    try {
      const result = await api.startBillingCheckout(plan.tier, plan.interval, returnTo, "embedded");
      if (!result.client_secret) throw new Error("Could not start checkout.");
      trackFeatureUse("checkout_started", { dedupe: false, props: { tier: plan.tier, interval: plan.interval } });
      setClientSecret(result.client_secret);
    } catch (err) {
      if (isAccountRequiredError(err)) {
        setAccountRequired(true);
        return;
      }
      setError(err instanceof Error ? err.message : "Could not start checkout.");
    } finally {
      setBusy(false);
    }
  };

  const perMonth = plan.interval === "annual" ? annualPerMonth(plan.price) : null;
  const savings = plan.interval === "annual" && monthlyPlan ? annualSavingsPercent(monthlyPlan.price, plan.price) : null;

  return (
    <div className="glass-surface p-4 flex flex-col gap-3 premium-glow-card" data-testid="plan-checkout">
      <div className="flex items-start justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs font-bold uppercase" style={{ color: "var(--color-premium)" }}>
          <PlanTierGlyph name={plan.tier} />
          {TIER_LABELS[plan.tier]} — {plan.label}
        </span>
        {savings ? <ToneBadge label={`Save ${savings}%`} color="var(--color-success)" /> : null}
      </div>
      <div className="flex flex-col">
        <span style={{ font: "var(--type-primary-metric)" }}>
          {plan.price} <span className="text-sm font-normal">{plan.cadence}</span>
        </span>
        {perMonth ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            About {perMonth}/month, billed yearly
          </span>
        ) : null}
      </div>
      {error ? (
        <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}
      {isGuest || accountRequired ? (
        <TrialAccountGate onSignedIn={() => setAccountRequired(false)} />
      ) : (
        <Button variant="premium" type="button" onClick={subscribe} loading={busy} fullWidth>
          {busy ? "Starting checkout…" : trialDays > 0 ? trialCtaLabel(trialDays) : "Subscribe"}
        </Button>
      )}
      <p className="text-xs text-center m-0" style={{ color: "var(--color-text-muted)" }}>
        {trialDays > 0 ? `${thenPriceLine(plan)} ${PAYWALL_CARD_NOTE}` : PAYWALL_TRIAL_REASSURANCE}
      </p>
      {clientSecret ? (
        <EmbeddedCheckoutModal clientSecret={clientSecret} publishableKey={publishableKey} onClose={() => setClientSecret(null)} />
      ) : null}
    </div>
  );
}

/** Monthly / Annual toggle for one tier, defaulting to annual (the better deal), with the saving on the tab. */
function TierPlans({ plans, publishableKey, trialDays }: { plans: BillingPlan[]; publishableKey: string; trialDays: number }) {
  const monthly = plans.find((p) => p.interval === "monthly") ?? null;
  const annual = plans.find((p) => p.interval === "annual") ?? null;
  const [interval, setInterval] = useState<string>(annual ? "annual" : plans[0].interval);
  const active = plans.find((p) => p.interval === interval) ?? plans[0];
  const savings = monthly && annual ? annualSavingsPercent(monthly.price, annual.price) : null;
  const options = plans.map((p) => ({
    value: p.interval,
    label: p.interval === "annual" && savings ? `${p.label} · Save ${savings}%` : p.label,
  }));
  return (
    <div className="flex flex-col gap-3">
      {plans.length > 1 ? <PillRow ariaLabel="Billing period" options={options} active={active.interval} onSelect={setInterval} variant="fill" /> : null}
      <PlanCheckout plan={active} monthlyPlan={monthly} publishableKey={publishableKey} trialDays={active.tier === "pro" ? trialDays : 0} />
    </div>
  );
}

function ManageBilling({ trialEndsAt }: { trialEndsAt?: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const openPortal = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.openBillingPortal();
      window.location.href = result.portal_url;
    } catch (err) {
      setBusy(false);
      setError(err instanceof Error ? err.message : "Could not open the billing portal.");
    }
  };

  return (
    <div
      className="p-4 flex flex-col gap-2 premium-glow-card"
      style={{ background: "var(--color-action-soft)", border: "var(--border-width-default) solid var(--color-premium)" }}
    >
      <p className="text-sm font-bold">You&apos;re on Pro.</p>
      {trialEndLabel(trialEndsAt) ? (
        <p
          className="text-xs font-extrabold self-start px-2 py-1"
          style={{ color: "var(--color-premium)", background: "var(--color-action-soft)", border: "var(--border-width-default) solid var(--color-premium)", borderRadius: "var(--radius-pill)" }}
        >
          {trialEndLabel(trialEndsAt)}
        </p>
      ) : null}
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        Manage your plan, payment method, or cancel anytime.
      </p>
      {error ? (
        <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}
      <Button variant="premium" type="button" onClick={openPortal} loading={busy}>
        {busy ? "Opening…" : "Manage Billing"}
      </Button>
    </div>
  );
}

export function PremiumContent({
  entitlement,
  plans,
  publishableKey,
  trial,
  trialEndsAt,
  comparison,
}: {
  entitlement: "free" | "premium";
  plans: BillingPlan[];
  publishableKey: string;
  trial?: BillingTrial;
  trialEndsAt?: string;
  comparison?: PremiumComparisonRow[];
}) {
  const trialDays = activeTrialDays(trial);
  useEffect(() => {
    trackFeatureUse("premium_viewed", { props: { tier: entitlement === "premium" ? "pro" : "free" } });
  }, [entitlement]);
  const rows = comparison ?? FALLBACK_PREMIUM_COMPARISON;
  const tiers = Array.from(new Set(plans.map((p) => p.tier)));
  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-6 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-2">
        <span className="text-xs font-bold uppercase" style={{ color: "var(--color-premium)", letterSpacing: "var(--letter-spacing-badge)" }}>
          Pro
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{PAYWALL_HERO_TITLE}</h1>
        <p className="text-base m-0" style={{ color: "var(--color-text-secondary)" }}>
          {PAYWALL_HERO_SUB}
        </p>
      </header>

      {entitlement === "premium" ? <ManageBilling trialEndsAt={trialEndsAt} /> : null}

      <section className="flex flex-col gap-3" aria-labelledby="highlights-heading">
        <SectionHeading id="highlights-heading">What Pro adds</SectionHeading>
        <ProHighlights rows={rows} />
        <ComparisonDisclosure rows={rows} />
      </section>

      {(
        <section className="flex flex-col gap-3" aria-labelledby="plans-heading">
          <SectionHeading id="plans-heading">Choose your plan</SectionHeading>
          {tiers.map((tier) => (
            <TierPlans key={tier} plans={plans.filter((p) => p.tier === tier)} publishableKey={publishableKey} trialDays={trialDays} />
          ))}
          <PaywallLegalLinks />
          <div className="flex justify-center">
            <HelpLink context={{ topic: "premium_page" }} />
          </div>
        </section>
      )}
    </main>
  );
}

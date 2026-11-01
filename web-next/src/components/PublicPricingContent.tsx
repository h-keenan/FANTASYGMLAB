"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/Button";
import { FeatureIncludedGlyph, PlanTierGlyph } from "@/components/PremiumGlyph";
import { SectionHeading } from "@/components/SectionHeading";
import type { BillingPlan } from "@/lib/api";
import { FALLBACK_PUBLIC_PLANS, fetchPublicBillingPlans } from "@/lib/publicPricing";
import { storeCurrentPathForReturnAfterSignIn } from "@/lib/protectedRouteReturn";

const TIER_LABELS: Record<BillingPlan["tier"], string> = {
  pro: "Pro",
  front_office: "Front Office",
};

/**
 * Public pricing for a signed-out visitor who lands on /premium (shared
 * link, bookmark, search result). P0 UX audit, 2026-10-27: this page used
 * to `router.replace("/")` anyone without a session before they ever saw a
 * price -- there was no public pricing page anywhere on the site. Real
 * checkout still requires an account (Stripe Checkout needs a signed-in
 * customer to attach the subscription to), so the CTA here is "Create your
 * account," not a live Subscribe button; an already-signed-in visitor still
 * gets the full PremiumContent (plan cards with embedded checkout).
 *
 * storeCurrentPathForReturnAfterSignIn before the CTA covers the one real
 * case that matters here: an EXISTING account, signed out, that clicked a
 * /premium link and should land back on /premium after signing back in
 * (see LandingAuthIsland's existing-saved-leagues branch, which is the only
 * place this gets consumed). A brand-new signup goes through the normal
 * onboarding carousel -> paywall sequence regardless, which already shows
 * equivalent paid-plan content.
 */
export function PublicPricingContent() {
  const router = useRouter();
  const [plans, setPlans] = useState<BillingPlan[]>(FALLBACK_PUBLIC_PLANS);

  useEffect(() => {
    const controller = new AbortController();
    void fetchPublicBillingPlans(controller.signal).then((live) => {
      if (live && !controller.signal.aborted) setPlans(live);
    });
    return () => controller.abort();
  }, []);

  // Monthly and annual carry the same feature list, so list it once under the
  // prices instead of repeating six bullets per card (390px phone: the page
  // was two identical screens tall).
  const sharedFeatures =
    plans.length > 1 && plans.every((plan) => plan.features.join("\n") === plans[0].features.join("\n"))
      ? plans[0].features
      : null;

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-6 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Premium
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>Unlock the full GM toolkit</h1>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Create a free account to get started -- connect your league, look around, and upgrade to Premium whenever
          you&apos;re ready.
        </p>
      </header>

      <section className="flex flex-col gap-3" aria-labelledby="plans-heading">
        <SectionHeading id="plans-heading">Plans</SectionHeading>
        <div className="grid gap-3 sm:grid-cols-2">
          {plans.map((plan) => (
            <div key={`${plan.tier}-${plan.interval}`} className="glass-surface p-4 flex flex-col gap-2 premium-glow-card">
              <span
                className="flex items-center gap-1.5 text-xs font-bold uppercase"
                style={{ color: "var(--color-premium)" }}
              >
                <PlanTierGlyph name={plan.tier} />
                {TIER_LABELS[plan.tier]} — {plan.label}
              </span>
              <span style={{ font: "var(--type-primary-metric)" }}>
                {plan.price} <span className="text-sm font-normal">{plan.cadence}</span>
              </span>
              {sharedFeatures ? null : <FeatureList features={plan.features} />}
            </div>
          ))}
        </div>
        {sharedFeatures ? (
          <div className="glass-surface p-4 flex flex-col gap-2">
            <span className="text-xs font-bold uppercase" style={{ color: "var(--color-premium)" }}>
              Included in every plan
            </span>
            <FeatureList features={sharedFeatures} />
          </div>
        ) : null}
        <Button
          variant="premium"
          type="button"
          onClick={() => {
            storeCurrentPathForReturnAfterSignIn();
            router.push("/");
          }}
        >
          Create your account
        </Button>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Already have an account?{" "}
          <Link href="/" className="underline tap-link" style={{ color: "var(--color-text-secondary)" }}>
            Sign in
          </Link>
          .
        </p>
      </section>
    </main>
  );
}

function FeatureList({ features }: { features: string[] }) {
  return (
    <ul className="flex flex-col gap-1.5">
      {features.map((feature) => (
        <li key={feature} className="text-sm flex items-start gap-2" style={{ color: "var(--color-text-secondary)" }}>
          <span style={{ color: "var(--color-success)", marginTop: "0.1rem", flexShrink: 0 }}>
            <FeatureIncludedGlyph />
          </span>
          <span>{feature}</span>
        </li>
      ))}
    </ul>
  );
}

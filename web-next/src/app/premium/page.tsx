"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type BillingPlansResponse, type MeResponse } from "@/lib/api";
import { PremiumContent } from "@/components/PremiumContent";
import { PublicPricingContent } from "@/components/PublicPricingContent";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { normalizePremiumComparison } from "@/lib/premiumComparison";
import { LoadingScreen } from "@/components/LoadingScreen";

// First real checkout surface in web-next — every other "Upgrade" link
// still points at Streamlit's `?page=premium` (see streamlitLink.ts), this
// is the page they're being migrated to point at instead. Unlike every
// league page, this has no [leagueId] segment (same reasoning as
// Portfolio) — a subscription applies to the account, not one league.
export default function PremiumPage() {
  const { session, loading: authLoading } = useAuth();

  const [me, setMe] = useState<MeResponse | null>(null);
  const [plans, setPlans] = useState<BillingPlansResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading || !session) return;
    let cancelled = false;

    Promise.all([api.getMe(), api.getBillingPlans()])
      .then(([meResult, plansResult]) => {
        if (!cancelled) {
          setMe(meResult);
          setPlans(plansResult);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Premium.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session]);

  if (authLoading) {
    return <LoadingScreen status="Loading Premium…" />;
  }

  // P0 UX audit, 2026-10-27: this used to `router.replace("/")` a signed-out
  // visitor before they ever saw a price -- /premium had no public content
  // at all. Real checkout needs an account (Stripe Checkout attaches to a
  // signed-in customer), so this shows pricing and a "Create your account"
  // CTA instead of a live Subscribe button; see PublicPricingContent.
  if (!session) {
    return <PublicPricingContent />;
  }

  if (!me && !plans && !error) {
    return <LoadingScreen status="Loading Premium…" />;
  }

  if (error || !me || !plans) {
    return (
      <ErrorState message={error || "Could not load Premium."} onRetry={reloadPage} />
    );
  }

  return <PremiumContent entitlement={me.user.entitlement} plans={plans.plans} publishableKey={plans.stripe_publishable_key} trial={plans.trial} trialEndsAt={me.user.trial_ends_at} comparison={normalizePremiumComparison(me.premium_comparison)} />;
}

"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type BillingPlansResponse, type MeResponse } from "@/lib/api";
import { PremiumContent } from "@/components/PremiumContent";
import { LoadingScreen } from "@/components/LoadingScreen";

// First real checkout surface in web-next — every other "Upgrade" link
// still points at Streamlit's `?page=premium` (see streamlitLink.ts), this
// is the page they're being migrated to point at instead. Unlike every
// league page, this has no [leagueId] segment (same reasoning as
// Portfolio) — a subscription applies to the account, not one league.
export default function PremiumPage() {
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const [me, setMe] = useState<MeResponse | null>(null);
  const [plans, setPlans] = useState<BillingPlansResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
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
  }, [authLoading, session, router]);

  if (authLoading || (!me && !plans && !error)) {
    return <LoadingScreen status="Loading Premium…" />;
  }

  if (error || !me || !plans) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load Premium."}
        </p>
      </main>
    );
  }

  return <PremiumContent entitlement={me.user.entitlement} plans={plans.plans} />;
}

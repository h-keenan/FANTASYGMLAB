"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { useValuationLens } from "@/context/ValuationLensContext";
import { api, type GmPlanResponse } from "@/lib/api";
import { GmPlanContent } from "@/components/GmPlanContent";
import { LoadingScreen } from "@/components/LoadingScreen";

export default function GmPlanPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;
  const { lens } = useValuationLens(leagueId);

  const [gmPlan, setGmPlan] = useState<GmPlanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    api
      .getGmPlan(leagueId, lens)
      .then((result) => {
        if (!cancelled) setGmPlan(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load GM Plan.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, lens, router]);

  if (authLoading || (!gmPlan && !error)) {
    return (
      <LoadingScreen status="Loading GM Plan…" />
    );
  }

  if (error || !gmPlan) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load GM Plan."}
        </p>
      </main>
    );
  }

  return <GmPlanContent leagueId={leagueId} leagueName={leagueName} data={gmPlan} />;
}

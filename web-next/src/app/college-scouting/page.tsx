"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type CollegeProspectsResponse } from "@/lib/api";
import { CollegeScoutingContent } from "@/components/CollegeScoutingContent";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

// Like Portfolio/News/Trade History, College Scouting has no [leagueId]
// segment — the real current page (modules/college_scouting_ui.py) and GET
// /v1/scouting/prospects both read the same shared prospect pool regardless
// of which league is selected (every signed-in user grades the same
// catalog). Mobile's CollegeProspectsScreen.tsx is the same: no leagueId
// param anywhere in the call.
export default function CollegeScoutingPage() {
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const [data, setData] = useState<CollegeProspectsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    api
      .getCollegeProspects()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load College Scouting.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, router]);

  if (authLoading || (!data && !error)) {
    return (
      <LoadingScreen status="Loading College Scouting…" />
    );
  }

  if (error || !data) {
    return (
      <ErrorState message={error || "Could not load College Scouting."} onRetry={reloadPage} />
    );
  }

  if (data.is_premium === false) {
    return (
      <PremiumUpsellCard
        kicker="College Scouting"
        upsell={data.upsell ?? null}
        fallbackTitle="Scout the next rookie class"
        fallbackBody="College Scouting is a Premium feature: the shared prospect board, community grades, your own scouting reports and watchlist. Start your free trial to unlock it."
      />
    );
  }

  return <CollegeScoutingContent data={data} />;
}

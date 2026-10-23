"use client";

import { useParams, useRouter } from "next/navigation";
import { useSearchParams } from "@/lib/useSearchParams";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type RecapResponse } from "@/lib/api";
import { LeagueRecapsContent } from "@/components/LeagueRecapsContent";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

export default function LeagueRecapsPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;

  const [recap, setRecap] = useState<RecapResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    api
      .getLeagueRecap(leagueId)
      .then((result) => {
        if (!cancelled) setRecap(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load League Recaps.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, router]);

  if (authLoading || (!recap && !error)) {
    return (
      <LoadingScreen status="Loading League Recaps…" />
    );
  }

  if (error || !recap) {
    return (
      <ErrorState message={error || "Could not load League Recaps."} onRetry={reloadPage} />
    );
  }

  return <LeagueRecapsContent leagueId={leagueId} leagueName={leagueName} initialRecap={recap} />;
}

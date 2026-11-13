"use client";

import { useParams, useRouter } from "next/navigation";
import { useSearchParams } from "@/lib/useSearchParams";
import { useEffect } from "react";

import { useAuth } from "@/context/AuthContext";
import { useValuationLens } from "@/context/ValuationLensContext";
import { useLiveMatchup } from "@/lib/useLiveMatchup";
import { MatchupContent } from "@/components/MatchupContent";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";
import { UNNAMED_LEAGUE } from "@/lib/leagueName";

export default function MatchupPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || UNNAMED_LEAGUE;
  const { lens, lensReady } = useValuationLens(leagueId);

  const ready = !authLoading && !!session && lensReady;
  // Hold the first fetch until the league type is known (see ValuationLensContext), so a redraft
  // league is requested once as Non-Dynasty, not once as Dynasty and again after detection.
  const { matchup, error, refreshing, ageSeconds, refresh } = useLiveMatchup(leagueId, lens, ready);

  useEffect(() => {
    if (!authLoading && !session) router.replace("/");
  }, [authLoading, session, router]);

  if (authLoading || (!matchup && !error)) {
    return (
      <LoadingScreen status="Loading Matchup…" />
    );
  }

  if (error || !matchup) {
    return (
      <ErrorState message={error || "Could not load this week's matchup."} onRetry={reloadPage} />
    );
  }

  return (
    <MatchupContent
      leagueName={leagueName}
      matchup={matchup}
      leagueId={leagueId}
      lens={lens}
      ageSeconds={ageSeconds}
      refreshing={refreshing}
      onRefresh={refresh}
    />
  );
}

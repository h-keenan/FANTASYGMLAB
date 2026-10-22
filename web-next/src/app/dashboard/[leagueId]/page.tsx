"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { useValuationLens } from "@/context/ValuationLensContext";
import { api, type DashboardResponse, type LeagueTeamRankingsResponse } from "@/lib/api";
import { DashboardContent } from "@/components/DashboardContent";
import { ErrorState } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

export default function DashboardPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;
  const { lens, lensReady } = useValuationLens(leagueId);

  const [data, setData] = useState<DashboardResponse | null>(null);
  // League Pulse's source, started in the same tick as the Dashboard request
  // (it used to start only after the Dashboard rendered, a full round trip
  // later). Handed down as a promise so the tile renders whenever it lands.
  const [teamRankings, setTeamRankings] = useState<Promise<LeagueTeamRankingsResponse> | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Bumped by the "Try again" button below — included in the fetch effect's
  // deps so a retry re-runs it without a full page reload (see
  // ErrorState.tsx for why this exists: a backgrounded-Safari timeout
  // previously left no way back except reloading the whole page).
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    // First fetch waits only for the league type, so a redraft league is
    // requested once (as Non-Dynasty), not once as Dynasty and again.
    if (!lensReady) return;
    let cancelled = false;
    const rankings = api.getTeamRankings(leagueId, lens);
    rankings.catch(() => {
      /* the tile renders nothing on failure; avoid an unhandled rejection */
    });
    api
      .getDashboard(leagueId, lens)
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setTeamRankings(rankings);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load the Dashboard.");
      });
    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, lens, lensReady, router, retryToken]);

  if (authLoading || (!data && !error)) {
    return (
      <LoadingScreen status="Loading Dashboard…" />
    );
  }

  if (error || !data) {
    return (
      <ErrorState
        message={error || "Could not load the Dashboard."}
        onRetry={() => {
          setError(null);
          setRetryToken((token) => token + 1);
        }}
      />
    );
  }

  return <DashboardContent leagueId={leagueId} leagueName={leagueName} data={data} teamRankings={teamRankings ?? undefined} />;
}

"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type LeagueRankingsResponse } from "@/lib/api";
import { PlayerCompareContent } from "@/components/PlayerCompareContent";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

/**
 * Route for Player Compare (Revision 12). Takes both player IDs as query
 * params (`a` required, `b` optional — omitting it shows the same opponent
 * picker app.py/mobile show) rather than a path segment, since a comparison
 * isn't a single addressable resource the way a league is — this mirrors
 * how mobile's PlayerCompareScreen takes its base `player` object via route
 * params from wherever the user triggered "Compare" (currently any link
 * into this page), re-resolved here from the league's own rankings pool
 * rather than trusting an unverified object shape in the URL.
 */
export default function PlayerComparePage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;
  const playerAId = searchParams.get("a") || "";
  const playerBId = searchParams.get("b") || "";

  const [rankings, setRankings] = useState<LeagueRankingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    if (!playerAId) return;
    let cancelled = false;

    api
      .getLeagueRankings(leagueId)
      .then((result) => {
        if (!cancelled) setRankings(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Player Compare.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, playerAId, router]);

  if (!playerAId) {
    return (
      <main className="flex-1 flex flex-col px-4 py-6 max-w-3xl w-full mx-auto">
        <EmptyState
          title="No player selected to compare"
          subtitle="Pick a player from the list, then tap Compare."
          actionLabel="Browse players"
          onAction={() => router.push(`/players/${encodeURIComponent(leagueId)}`)}
        />
      </main>
    );
  }

  if (authLoading || (!rankings && !error)) {
    return (
      <LoadingScreen status="Loading Player Compare…" />
    );
  }

  if (error || !rankings) {
    return (
      <ErrorState message={error || "Could not load Player Compare."} onRetry={reloadPage} />
    );
  }

  const playerA = rankings.players.find((p) => p.player_id === playerAId) ?? null;
  if (!playerA) {
    return (
      <ErrorState message="That player isn't on the current rankings board." />
    );
  }

  const initialPlayerB = playerBId ? (rankings.players.find((p) => p.player_id === playerBId) ?? null) : null;

  return (
    <PlayerCompareContent leagueName={leagueName} playerA={playerA} initialPlayerB={initialPlayerB} pool={rankings.players} />
  );
}

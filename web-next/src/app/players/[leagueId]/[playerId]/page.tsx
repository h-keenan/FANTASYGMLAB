"use client";

import { useParams, useRouter } from "next/navigation";
import { useSearchParams } from "@/lib/useSearchParams";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { useValuationLens } from "@/context/ValuationLensContext";
import { api, type LeagueRankingsResponse } from "@/lib/api";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";
import { PlayerProfileContent } from "@/components/PlayerProfileContent";

/**
 * Route for the full Player Profile page (the "PQV parity gap" —
 * PlayerQuickView.tsx's own header doc comment flags mobile's
 * PlayerDetailScreen.tsx's 5 tabs — Stats/Trends/Schedule/Career/Model — as
 * never ported to web-next; coridian_, 2026-10-19: "the pqv on the app has
 * tabs that the site doesnt. Thats a consistency error"). Reached from
 * PlayerQuickView's "Open Full Profile" link, or directly by URL/refresh.
 *
 * GET .../quick-view is league-independent and doesn't return identity
 * (name/team/position/photo/rank — see QuickViewResponse's own docstring in
 * lib/api.ts), so identity is resolved here from this league's own GET
 * .../rankings pool — the same re-resolve-from-the-league's-rankings
 * pattern player-compare/[leagueId]/page.tsx already uses for the same
 * reason, rather than trusting an unverified shape in the URL or inventing
 * a second identity endpoint.
 */
export default function PlayerProfilePage() {
  const params = useParams<{ leagueId: string; playerId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const playerId = decodeURIComponent(params.playerId);
  const leagueName = searchParams.get("name") || leagueId;
  const { lens } = useValuationLens(leagueId);

  const [rankings, setRankings] = useState<LeagueRankingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    api
      .getLeagueRankings(leagueId, lens)
      .then((result) => {
        if (!cancelled) setRankings(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load this player's profile.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, lens, router]);

  if (authLoading || (!rankings && !error)) {
    return <LoadingScreen status="Loading player profile…" />;
  }

  if (error || !rankings) {
    return (
      <ErrorState message={error || "Could not load this player's profile."} onRetry={reloadPage} />
    );
  }

  const player = rankings.players.find((candidate) => candidate.player_id === playerId) ?? null;
  if (!player) {
    return (
      <ErrorState message="That player isn't on the current rankings board for this league." />
    );
  }

  return <PlayerProfileContent player={player} leagueId={leagueId} leagueName={leagueName} lens={lens} />;
}

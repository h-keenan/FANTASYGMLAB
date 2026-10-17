"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { useValuationLens } from "@/context/ValuationLensContext";
import { api, type MatchupResponse } from "@/lib/api";
import { MatchupContent } from "@/components/MatchupContent";
import { LoadingScreen } from "@/components/LoadingScreen";

export default function MatchupPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;
  const { lens } = useValuationLens(leagueId);

  const [matchup, setMatchup] = useState<MatchupResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    api
      .getLeagueMatchup(leagueId, lens)
      .then((result) => {
        if (!cancelled) setMatchup(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load this week's matchup.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, lens, router]);

  if (authLoading || (!matchup && !error)) {
    return (
      <LoadingScreen status="Loading Matchup…" />
    );
  }

  if (error || !matchup) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load this week's matchup."}
        </p>
      </main>
    );
  }

  return <MatchupContent leagueName={leagueName} matchup={matchup} />;
}

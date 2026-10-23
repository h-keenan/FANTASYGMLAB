"use client";

import { useParams, useRouter } from "next/navigation";
import { useSearchParams } from "@/lib/useSearchParams";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { useValuationLens } from "@/context/ValuationLensContext";
import { api, type LeagueTeamRankingsResponse } from "@/lib/api";
import { LeagueRankingsContent } from "@/components/LeagueRankingsContent";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

export default function LeagueRankingsPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;
  const { lens } = useValuationLens(leagueId);

  const [rankings, setRankings] = useState<LeagueTeamRankingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Best-effort — only powers the "You" row highlight; a failure here just
  // leaves every row unhighlighted instead of blocking the page, same
  // contract TeamsScreen.tsx's myRosterId resolution follows on mobile.
  const [myRosterId, setMyRosterId] = useState<string>("");

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    api
      .getTeamRankings(leagueId, lens)
      .then((result) => {
        if (!cancelled) setRankings(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load League Rankings.");
      });

    api
      .getMyRoster(leagueId)
      .then((result) => {
        if (!cancelled && result.roster) {
          setMyRosterId(String((result.roster as { roster_id?: unknown }).roster_id ?? ""));
        }
      })
      .catch(() => {
        /* best-effort */
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, lens, router]);

  if (authLoading || (!rankings && !error)) {
    return (
      <LoadingScreen status="Loading League Rankings…" />
    );
  }

  if (error || !rankings) {
    return (
      <ErrorState message={error || "Could not load League Rankings."} onRetry={reloadPage} />
    );
  }

  return <LeagueRankingsContent leagueId={leagueId} leagueName={leagueName} data={rankings} myRosterId={myRosterId} />;
}

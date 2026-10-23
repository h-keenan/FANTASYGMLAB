"use client";

import { useParams, useRouter } from "next/navigation";
import { useSearchParams } from "@/lib/useSearchParams";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { useValuationLens } from "@/context/ValuationLensContext";
import { api, type DraftPickAsset, type LeagueIdpValuesResponse, type LeagueRankingsResponse } from "@/lib/api";
import { PlayersContent } from "@/components/PlayersContent";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

interface LoadedData {
  rankings: LeagueRankingsResponse;
  picks: DraftPickAsset[];
  rosters: Array<Record<string, unknown>>;
  idp: LeagueIdpValuesResponse | null;
}

export default function PlayersPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;
  const { lens } = useValuationLens(leagueId);

  const [data, setData] = useState<LoadedData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    Promise.all([
      api.getLeagueRankings(leagueId, lens, 300),
      // Picks/rosters back the Picks view and the roster-status facet —
      // both genuinely optional (a league with no draft-capital data yet,
      // or no roster map), same graceful-empty fallback Trade Analyzer's
      // page.tsx already uses for these same two endpoints.
      api.getLeagueDraftPicks(leagueId, lens).catch(() => ({ ok: true as const, picks: [], reason: "unavailable" })),
      api.getLeagueRosters(leagueId).catch(() => ({ ok: true as const, rosters: [] })),
      // IDP values are optional: non-IDP leagues get `idp: false`, and any
      // failure just leaves the offense board exactly as it was.
      api.getLeagueIdpValues(leagueId).catch(() => null),
    ])
      .then(([rankings, picksResult, rostersResult, idp]) => {
        if (!cancelled) {
          setData({ rankings, picks: picksResult.picks, rosters: rostersResult.rosters, idp });
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Players.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, lens, router]);

  if (authLoading || (!data && !error)) {
    return (
      <LoadingScreen status="Loading Players…" />
    );
  }

  if (error || !data) {
    return (
      <ErrorState message={error || "Could not load Players."} onRetry={reloadPage} />
    );
  }

  return (
    <PlayersContent
      leagueId={leagueId}
      leagueName={leagueName}
      data={data.rankings}
      picks={data.picks}
      rosters={data.rosters}
      idp={data.idp}
    />
  );
}

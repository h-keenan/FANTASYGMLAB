"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import {
  api,
  type DraftPickAsset,
  type MyRosterResponse,
  type RankedPlayer,
  type TeamProfile,
} from "@/lib/api";
import { TradeAnalyzerContent } from "@/components/TradeAnalyzerContent";
import { LoadingScreen } from "@/components/LoadingScreen";

interface LoadedData {
  myRoster: MyRosterResponse;
  rankings: RankedPlayer[];
  picks: DraftPickAsset[];
  rosters: Array<Record<string, unknown>>;
  teamProfiles: Record<string, TeamProfile>;
}

export default function TradeAnalyzerPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;

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
      api.getMyRoster(leagueId),
      api.getLeagueRankings(leagueId),
      // Picks/rosters/team-profiles can legitimately 404/empty for a league
      // with no draft-capital data yet (startup drafts, degraded ESPN
      // imports) — same graceful-empty fallback mobile's own screen uses,
      // so a roster-browse list with no picks never blocks the page.
      api.getLeagueDraftPicks(leagueId).catch(() => ({ ok: true as const, picks: [], reason: "unavailable" })),
      api.getLeagueRosters(leagueId).catch(() => ({ ok: true as const, rosters: [] })),
      api.getLeagueTeamProfiles(leagueId).catch(() => ({ ok: true as const, profiles: {} })),
    ])
      .then(([myRoster, rankingsResult, picksResult, rostersResult, teamProfilesResult]) => {
        if (cancelled) return;
        setData({
          myRoster,
          rankings: rankingsResult.players,
          picks: picksResult.picks,
          rosters: rostersResult.rosters,
          teamProfiles: teamProfilesResult.profiles,
        });
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Trade Analyzer.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, router]);

  if (authLoading || (!data && !error)) {
    return (
      <LoadingScreen status="Loading Trade Analyzer…" />
    );
  }

  if (error || !data) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load Trade Analyzer."}
        </p>
      </main>
    );
  }

  return (
    <TradeAnalyzerContent
      leagueId={leagueId}
      leagueName={leagueName}
      myRoster={data.myRoster}
      rankings={data.rankings}
      picks={data.picks}
      rosters={data.rosters}
      teamProfiles={data.teamProfiles}
    />
  );
}

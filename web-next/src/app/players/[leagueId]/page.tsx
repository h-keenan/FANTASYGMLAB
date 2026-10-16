"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type DraftPickAsset, type LeagueRankingsResponse } from "@/lib/api";
import { PlayersContent } from "@/components/PlayersContent";

interface LoadedData {
  rankings: LeagueRankingsResponse;
  picks: DraftPickAsset[];
  rosters: Array<Record<string, unknown>>;
}

export default function PlayersPage() {
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
      api.getLeagueRankings(leagueId, "Dynasty", 300),
      // Picks/rosters back the Picks view and the roster-status facet —
      // both genuinely optional (a league with no draft-capital data yet,
      // or no roster map), same graceful-empty fallback Trade Analyzer's
      // page.tsx already uses for these same two endpoints.
      api.getLeagueDraftPicks(leagueId).catch(() => ({ ok: true as const, picks: [], reason: "unavailable" })),
      api.getLeagueRosters(leagueId).catch(() => ({ ok: true as const, rosters: [] })),
    ])
      .then(([rankings, picksResult, rostersResult]) => {
        if (!cancelled) {
          setData({ rankings, picks: picksResult.picks, rosters: rostersResult.rosters });
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Players.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, router]);

  if (authLoading || (!data && !error)) {
    return (
      <main className="flex-1 flex items-center justify-center">
        <p style={{ color: "var(--color-text-muted)" }}>Loading Players…</p>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load Players."}
        </p>
      </main>
    );
  }

  return (
    <PlayersContent
      leagueId={leagueId}
      leagueName={leagueName}
      data={data.rankings}
      picks={data.picks}
      rosters={data.rosters}
    />
  );
}

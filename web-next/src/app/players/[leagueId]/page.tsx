"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type LeagueRankingsResponse } from "@/lib/api";
import { PlayersContent } from "@/components/PlayersContent";

export default function PlayersPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;

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
      .getLeagueRankings(leagueId, "Dynasty", 300)
      .then((result) => {
        if (!cancelled) setRankings(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Players.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, router]);

  if (authLoading || (!rankings && !error)) {
    return (
      <main className="flex-1 flex items-center justify-center">
        <p style={{ color: "var(--color-text-muted)" }}>Loading Players…</p>
      </main>
    );
  }

  if (error || !rankings) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load Players."}
        </p>
      </main>
    );
  }

  return <PlayersContent leagueId={leagueId} leagueName={leagueName} data={rankings} />;
}

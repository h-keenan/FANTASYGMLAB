"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type MyTeamResponse } from "@/lib/api";
import { TradeFinderContent } from "@/components/TradeFinderContent";
import { LoadingScreen } from "@/components/LoadingScreen";

export default function TradeFinderPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;

  const [myTeam, setMyTeam] = useState<MyTeamResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    api
      .getMyTeam(leagueId)
      .then((result) => {
        if (!cancelled) setMyTeam(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Trade Finder.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, router]);

  if (authLoading || (!myTeam && !error)) {
    return (
      <LoadingScreen status="Loading Trade Finder…" />
    );
  }

  if (error || !myTeam) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load Trade Finder."}
        </p>
      </main>
    );
  }

  return <TradeFinderContent leagueId={leagueId} leagueName={leagueName} myTeam={myTeam} />;
}

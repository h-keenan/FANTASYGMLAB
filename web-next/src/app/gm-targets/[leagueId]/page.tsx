"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type GmTargetsResponse, type LeagueRankingsResponse } from "@/lib/api";
import { GmTargetsContent } from "@/components/GmTargetsContent";

export default function GmTargetsPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;

  const [targets, setTargets] = useState<GmTargetsResponse | null>(null);
  const [rankings, setRankings] = useState<LeagueRankingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    Promise.all([api.getGmTargets(leagueId), api.getLeagueRankings(leagueId)])
      .then(([targetsResult, rankingsResult]) => {
        if (!cancelled) {
          setTargets(targetsResult);
          setRankings(rankingsResult);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load GM Targets.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, router]);

  if (authLoading || (!targets && !rankings && !error)) {
    return (
      <main className="flex-1 flex items-center justify-center">
        <p style={{ color: "var(--color-text-muted)" }}>Loading GM Targets…</p>
      </main>
    );
  }

  if (error || !targets || !rankings) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load GM Targets."}
        </p>
      </main>
    );
  }

  return <GmTargetsContent leagueId={leagueId} leagueName={leagueName} targets={targets} rankings={rankings} />;
}

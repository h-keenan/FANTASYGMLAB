"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type RecapResponse } from "@/lib/api";
import { LeagueRecapsContent } from "@/components/LeagueRecapsContent";

export default function LeagueRecapsPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;

  const [recap, setRecap] = useState<RecapResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    api
      .getLeagueRecap(leagueId)
      .then((result) => {
        if (!cancelled) setRecap(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load League Recaps.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, router]);

  if (authLoading || (!recap && !error)) {
    return (
      <main className="flex-1 flex items-center justify-center">
        <p style={{ color: "var(--color-text-muted)" }}>Loading League Recaps…</p>
      </main>
    );
  }

  if (error || !recap) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load League Recaps."}
        </p>
      </main>
    );
  }

  return <LeagueRecapsContent leagueId={leagueId} leagueName={leagueName} initialRecap={recap} />;
}

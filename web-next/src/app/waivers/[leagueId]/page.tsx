"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type WaiversResponse } from "@/lib/api";
import { WaiversContent } from "@/components/WaiversContent";
import { LoadingScreen } from "@/components/LoadingScreen";

export default function WaiversPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;

  const [waivers, setWaivers] = useState<WaiversResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    api
      .getLeagueWaivers(leagueId)
      .then((result) => {
        if (!cancelled) setWaivers(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Waivers.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, router]);

  if (authLoading || (!waivers && !error)) {
    return (
      <LoadingScreen status="Loading Waivers…" />
    );
  }

  if (error || !waivers) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load Waivers."}
        </p>
      </main>
    );
  }

  return <WaiversContent leagueName={leagueName} data={waivers} />;
}

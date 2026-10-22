"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type AlertsResponse } from "@/lib/api";
import { AlertsContent } from "@/components/AlertsContent";
import { ErrorState, reloadPage } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

export default function AlertsPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;

  const [alerts, setAlerts] = useState<AlertsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    api
      .getLeagueAlerts(leagueId)
      .then((result) => {
        if (!cancelled) setAlerts(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Alerts.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, router]);

  if (authLoading || (!alerts && !error)) {
    return (
      <LoadingScreen status="Loading Alerts…" />
    );
  }

  if (error || !alerts) {
    return (
      <ErrorState message={error || "Could not load Alerts."} onRetry={reloadPage} />
    );
  }

  return <AlertsContent leagueId={leagueId} leagueName={leagueName} data={alerts} />;
}

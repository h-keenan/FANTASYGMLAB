"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type AlertsResponse } from "@/lib/api";
import { AlertsContent } from "@/components/AlertsContent";
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

    const load = (initial: boolean) =>
      api
        .getLeagueAlerts(leagueId)
        .then((result) => {
          if (!cancelled) setAlerts(result);
        })
        .catch((err) => {
          // A failed background refresh keeps the feed already on screen.
          if (!cancelled && initial) setError(err instanceof Error ? err.message : "Could not load Alerts.");
        });

    void load(true);
    // Returning to this tab re-reads the feed, so an alert read on the
    // phone in the meantime shows as read here without a manual reload.
    const onVisibility = () => {
      if (document.visibilityState === "visible") void load(false);
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [authLoading, session, leagueId, router]);

  if (authLoading || (!alerts && !error)) {
    return (
      <LoadingScreen status="Loading Alerts…" />
    );
  }

  if (error || !alerts) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load Alerts."}
        </p>
      </main>
    );
  }

  return <AlertsContent leagueId={leagueId} leagueName={leagueName} data={alerts} userId={session?.user?.id ?? ""} />;
}

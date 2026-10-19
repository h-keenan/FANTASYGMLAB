"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type FounderAnalyticsResponse } from "@/lib/api";
import { FounderAnalyticsContent } from "@/components/FounderAnalyticsContent";
import { ErrorState } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

/**
 * Founder-only internal product analytics (coridian_, 2026-10-19: "just put
 * it in the orb menu for the specific account(s) listed on supabase"). Has
 * no `[leagueId]` segment — same single-page shape as Portfolio, since this
 * spans the whole product, not one league.
 *
 * The `founderCapable` check below (reading the signed-in session's own
 * Supabase Auth app_metadata) is a client-side UX nicety only — it quietly
 * redirects away before this page even attempts a fetch. It is NOT the real
 * security boundary: GET /v1/founder/analytics itself enforces the same
 * `founder_ops` claim server-side and returns a genuine 403 for any caller
 * without it (services/mobile_api_service.py's get_founder_analytics /
 * _founder_analytics_capable) — a non-founder who somehow reaches this route
 * directly (bookmark, typed URL) never sees real data either way, they just
 * get redirected here first instead of seeing a 403 ErrorState.
 */
export default function FounderAnalyticsPage() {
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();
  const founderCapable = session?.user?.app_metadata?.founder_ops === true;

  const [windowKey, setWindowKey] = useState("7d");
  const [data, setData] = useState<FounderAnalyticsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    if (authLoading) return;
    if (!session || !founderCapable) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    api
      .getFounderAnalytics(windowKey)
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load Founder Analytics.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, founderCapable, router, windowKey, retryToken]);

  if (authLoading || !session || !founderCapable) {
    return <LoadingScreen status="Loading…" />;
  }

  if (error) {
    return (
      <ErrorState
        message={error}
        onRetry={() => {
          setError(null);
          setRetryToken((token) => token + 1);
        }}
      />
    );
  }

  if (!data) {
    return <LoadingScreen status="Loading Founder Analytics…" />;
  }

  return <FounderAnalyticsContent data={data.report} windowKey={windowKey} onWindowChange={setWindowKey} />;
}

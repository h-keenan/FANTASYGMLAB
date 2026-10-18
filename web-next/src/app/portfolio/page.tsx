"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type PortfolioResponse } from "@/lib/api";
import { PortfolioContent } from "@/components/PortfolioContent";
import { ErrorState } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

// Unlike every other ported page, Portfolio has no [leagueId] segment — it
// spans every one of the signed-in account's saved leagues at once (see
// modules/portfolio_page.py / GET /v1/portfolio's own docstrings).
export default function PortfolioPage() {
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const [data, setData] = useState<PortfolioResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  // See ErrorState.tsx — bumped by "Try again" so a Safari-backgrounded
  // timeout has a real way back instead of a dead page.
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    api
      .getPortfolio()
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Portfolio.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, router, retryToken]);

  if (authLoading || (!data && !error)) {
    return (
      <LoadingScreen status="Loading Portfolio…" />
    );
  }

  if (error || !data) {
    return (
      <ErrorState
        message={error || "Could not load Portfolio."}
        onRetry={() => {
          setError(null);
          setRetryToken((token) => token + 1);
        }}
      />
    );
  }

  return <PortfolioContent data={data} />;
}

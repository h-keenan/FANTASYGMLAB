"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type PortfolioIndexResponse } from "@/lib/api";
import { composePortfolio, type PortfolioLeagueState } from "@/lib/portfolioProgress";
import { PortfolioContent } from "@/components/PortfolioContent";
import { ErrorState } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

// Unlike every other ported page, Portfolio has no [leagueId] segment — it
// spans every one of the signed-in account's saved leagues at once (see
// modules/portfolio_page.py / GET /v1/portfolio's own docstrings).
//
// Loads progressively (lib/portfolioProgress.ts): the cheap index first —
// the only thing the full-page loading screen waits on — then every saved
// league's own row concurrently, each card replacing its skeleton as soon
// as it arrives instead of the whole page waiting on the slowest league.
export default function PortfolioPage() {
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const [index, setIndex] = useState<PortfolioIndexResponse | null>(null);
  const [leagueStates, setLeagueStates] = useState<Record<string, PortfolioLeagueState>>({});
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
      .getPortfolioIndex()
      .then((result) => {
        if (cancelled) return;
        setIndex(result);
        setError(null);
        const savedLeagues = result.is_premium ? result.saved_leagues ?? [] : [];
        setLeagueStates(
          Object.fromEntries(savedLeagues.map((league) => [league.league_id, { status: "pending" } as const])),
        );
        for (const league of savedLeagues) {
          api
            .getPortfolioLeague(league.league_id, result.lens)
            .then((data) => {
              if (!cancelled) {
                setLeagueStates((prev) => ({ ...prev, [league.league_id]: { status: "success", data } }));
              }
            })
            .catch(() => {
              if (!cancelled) {
                setLeagueStates((prev) => ({ ...prev, [league.league_id]: { status: "error" } }));
              }
            });
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Portfolio.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, router, retryToken]);

  if (authLoading || (!index && !error)) {
    return <LoadingScreen status="Loading Portfolio…" />;
  }

  if (error || !index) {
    return (
      <ErrorState
        message={error || "Could not load Portfolio."}
        onRetry={() => {
          setError(null);
          setIndex(null);
          setLeagueStates({});
          setRetryToken((token) => token + 1);
        }}
      />
    );
  }

  const composed = composePortfolio(index, leagueStates);
  return <PortfolioContent data={composed.response} order={composed.order} pending={composed.pending} />;
}

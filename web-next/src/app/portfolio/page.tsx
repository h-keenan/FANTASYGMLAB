"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type PortfolioIndexResponse } from "@/lib/api";
import { composePortfolio, type PortfolioLeagueState } from "@/lib/portfolioProgress";
import { PortfolioContent, PortfolioShell } from "@/components/PortfolioContent";
import { PORTFOLIO_SPLASH_DELAY_MS, startLeagueLoader, type LeagueLoader } from "@/lib/portfolioLoader";
import { useDelayedFlag } from "@/lib/useDelayedFlag";
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
  const loaderRef = useRef<LeagueLoader | null>(null);
  const retryLeague = useCallback((leagueId: string) => loaderRef.current?.retry(leagueId), []);
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
    const controller = new AbortController();

    api
      .getPortfolioIndex("Dynasty", controller.signal)
      .then((result) => {
        if (cancelled) return;
        setIndex(result);
        setError(null);
        const savedLeagues = result.is_premium ? result.saved_leagues ?? [] : [];
        setLeagueStates(
          Object.fromEntries(savedLeagues.map((league) => [league.league_id, { status: "pending" } as const])),
        );
        // At most PORTFOLIO_LEAGUE_CONCURRENCY rows in flight, in saved order;
        // leaving the page aborts the in-flight ones (cleanup below).
        loaderRef.current = startLeagueLoader({
          leagueIds: savedLeagues.map((league) => league.league_id),
          load: (leagueId, signal) => api.getPortfolioLeague(leagueId, result.lens, signal),
          onState: (leagueId, state) => {
            if (!cancelled) setLeagueStates((prev) => ({ ...prev, [leagueId]: state }));
          },
        });
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Portfolio.");
      });

    return () => {
      cancelled = true;
      controller.abort();
      loaderRef.current?.abort();
      loaderRef.current = null;
    };
  }, [authLoading, session, router, retryToken]);

  // Instant shell (header + skeleton cards); the branded splash only if the
  // first paint is still waiting after PORTFOLIO_SPLASH_DELAY_MS, and it goes
  // away the moment the index arrives.
  const waiting = authLoading || (!index && !error);
  const showSplash = useDelayedFlag(waiting, PORTFOLIO_SPLASH_DELAY_MS);
  if (waiting) {
    return showSplash ? <LoadingScreen status="Loading Portfolio…" /> : <PortfolioShell />;
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
  return (
    <PortfolioContent
      data={composed.response}
      order={composed.order}
      pending={composed.pending}
      onRetryLeague={retryLeague}
    />
  );
}

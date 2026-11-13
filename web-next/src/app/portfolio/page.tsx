"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type PortfolioIndexResponse } from "@/lib/api";
import { composePortfolio, type PortfolioLeagueState } from "@/lib/portfolioProgress";
import { PortfolioContent, PortfolioShell } from "@/components/PortfolioContent";
import {
  PORTFOLIO_EAGER_LEAGUES,
  PORTFOLIO_SPLASH_DELAY_MS,
  PORTFOLIO_UNLOCK_STEP,
  startLeagueLoader,
  type LeagueLoader,
} from "@/lib/portfolioLoader";
import {
  buildPortfolioSnapshot,
  planFromSnapshot,
  readPortfolioSnapshot,
  writePortfolioSnapshot,
  type PortfolioSnapshot,
} from "@/lib/portfolioSnapshot";
import { useDelayedFlag } from "@/lib/useDelayedFlag";
import { ErrorState } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

const PORTFOLIO_LENS = "Dynasty";

function safeLocalStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

// Unlike every other ported page, Portfolio has no [leagueId] segment — it
// spans every one of the signed-in account's saved leagues at once (see
// modules/portfolio_page.py / GET /v1/portfolio's own docstrings).
//
// Loads progressively (lib/portfolioProgress.ts, lib/portfolioLoader.ts): the
// cheap index first — the only thing the full-page loading screen waits on —
// then each saved league's own row, headline first and signals after, the
// first screenful immediately and the rest as the list scrolls near them.
// Stale-while-revalidate (lib/portfolioSnapshot.ts): a revisit paints the last
// complete Portfolio at once and revalidates it in the background.
export default function PortfolioPage() {
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();
  const userId = session?.user?.id ?? "";

  const [index, setIndex] = useState<PortfolioIndexResponse | null>(null);
  const [leagueStates, setLeagueStates] = useState<Record<string, PortfolioLeagueState>>({});
  const [error, setError] = useState<string | null>(null);
  const [windowSize, setWindowSize] = useState(PORTFOLIO_EAGER_LEAGUES);
  const loaderRef = useRef<LeagueLoader | null>(null);
  const retryLeague = useCallback((leagueId: string) => loaderRef.current?.retry(leagueId), []);
  const releaseMoreLeagues = useCallback(() => {
    loaderRef.current?.unlock();
    setWindowSize((size) => size + PORTFOLIO_UNLOCK_STEP);
  }, []);
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
    const storage = safeLocalStorage();
    const snapshot: PortfolioSnapshot | null = userId
      ? readPortfolioSnapshot(storage, userId, PORTFOLIO_LENS, Date.now())
      : null;
    // What the page currently shows, for persisting the next snapshot.
    let shownIndex: PortfolioIndexResponse | null = null;
    let shownStates: Record<string, PortfolioLeagueState> = {};
    const updatedAt: Record<string, number> = Object.fromEntries(
      Object.entries(snapshot?.rows ?? {}).map(([leagueId, row]) => [leagueId, row.at]),
    );
    const persist = () => {
      if (!userId) return;
      writePortfolioSnapshot(
        storage,
        userId,
        PORTFOLIO_LENS,
        buildPortfolioSnapshot(shownIndex, shownStates, updatedAt, snapshot, Date.now()),
      );
    };

    if (snapshot) {
      // Instant paint from the last visit; the index below confirms/updates it.
      shownIndex = snapshot.index;
      shownStates = planFromSnapshot(snapshot, snapshot.index.saved_leagues.map((league) => league.league_id), Date.now()).states;
      /* eslint-disable react-hooks/set-state-in-effect -- hydrating from localStorage (an external store) on mount */
      setIndex(snapshot.index);
      setLeagueStates(shownStates);
      setError(null);
      /* eslint-enable react-hooks/set-state-in-effect */
    }

    api
      .getPortfolioIndex(PORTFOLIO_LENS, controller.signal)
      .then((result) => {
        if (cancelled) return;
        setIndex(result);
        setError(null);
        const savedLeagues = result.is_premium ? result.saved_leagues ?? [] : [];
        const plan = planFromSnapshot(snapshot, savedLeagues.map((league) => league.league_id), Date.now());
        shownIndex = result;
        shownStates = plan.states;
        setLeagueStates(plan.states);
        if (!result.is_premium) writePortfolioSnapshot(storage, userId, PORTFOLIO_LENS, null);
        // At most PORTFOLIO_LEAGUE_CONCURRENCY requests in flight, headlines
        // before signals, first screenful first; leaving the page aborts them.
        loaderRef.current = startLeagueLoader({
          leagueIds: savedLeagues.map((league) => league.league_id),
          warm: plan.warm,
          skip: plan.skip,
          load: (leagueId, signal, phase) =>
            api.getPortfolioLeague(leagueId, result.lens, signal, phase === "headline"),
          onState: (leagueId, state) => {
            if (cancelled) return;
            shownStates = { ...shownStates, [leagueId]: state };
            setLeagueStates(shownStates);
            if (state.status === "success" && state.data.league && !state.data.signals_pending) {
              updatedAt[leagueId] = Date.now();
              persist();
            }
          },
        });
      })
      .catch((err) => {
        // A failed refresh never takes the stale Portfolio off screen.
        if (!cancelled && !snapshot) setError(err instanceof Error ? err.message : "Could not load Portfolio.");
      });

    return () => {
      cancelled = true;
      controller.abort();
      loaderRef.current?.abort();
      loaderRef.current = null;
    };
  }, [authLoading, session, userId, router, retryToken]);

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
          setWindowSize(PORTFOLIO_EAGER_LEAGUES);
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
      signalsPending={composed.signalsPending}
      onRetryLeague={retryLeague}
      onNearEnd={releaseMoreLeagues}
      windowSize={windowSize}
    />
  );
}

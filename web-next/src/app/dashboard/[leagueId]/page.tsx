"use client";

import { useParams, useRouter } from "next/navigation";
import { useSearchParams } from "@/lib/useSearchParams";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { useValuationLens } from "@/context/ValuationLensContext";
import { api, type DashboardResponse, type LeagueTeamRankingsResponse } from "@/lib/api";
import { DashboardContent } from "@/components/DashboardContent";
import { ErrorState } from "@/components/ErrorState";
import { LeaguePulseCard } from "@/components/LeaguePulseCard";
import { LoadingScreen } from "@/components/LoadingScreen";
import { SkeletonBlock } from "@/components/Skeleton";

export default function DashboardPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;
  const { lens, lensReady } = useValuationLens(leagueId);

  const [data, setData] = useState<DashboardResponse | null>(null);
  // League Pulse's source, started in the same tick as the Dashboard request
  // (it used to start only after the Dashboard rendered, a full round trip
  // later). Handed down as a promise so the tile renders whenever it lands.
  const [teamRankings, setTeamRankings] = useState<Promise<LeagueTeamRankingsResponse> | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Bumped by the "Try again" button below — included in the fetch effect's
  // deps so a retry re-runs it without a full page reload (see
  // ErrorState.tsx for why this exists: a backgrounded-Safari timeout
  // previously left no way back except reloading the whole page).
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    // First fetch waits only for the league type, so a redraft league is
    // requested once (as Non-Dynasty), not once as Dynasty and again.
    if (!lensReady) return;
    let cancelled = false;
    const rankings = api.getTeamRankings(leagueId, lens);
    rankings.catch(() => {
      /* the tile renders nothing on failure; avoid an unhandled rejection */
    });
    // Handed down right away so League Pulse can paint while the (slower)
    // Dashboard request is still running.
    void Promise.resolve().then(() => {
      if (!cancelled) setTeamRankings(rankings);
    });
    // Progressive load: the first call skips the trade-idea search so the
    // page paints sooner; the second (started only once the first lands, so
    // the two never compete for the server) fills in the trade tile.
    const loadFull = () =>
      api
        .getDashboard(leagueId, lens)
        .then((result) => {
          if (!cancelled) {
            setData(result);
            setError(null);
          }
        });
    api
      .getDashboard(leagueId, lens, { deferTradeIdeas: true })
      .then((result) => {
        if (cancelled) return;
        if (!result.trade_ideas_deferred) {
          setData(result);
          setError(null);
          return;
        }
        // An empty/quiet first pass would flash the "all quiet" state until
        // the real answer lands, so keep the skeleton in that case.
        const painted = !result.quiet && result.items.length > 0;
        if (painted) {
          setData(result);
          setError(null);
        }
        return loadFull().catch((err) => {
          // Keep an already-painted first pass if the follow-up fails.
          if (!cancelled && !painted) setError(err instanceof Error ? err.message : "Could not load the Dashboard.");
        });
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load the Dashboard.");
      });
    return () => {
      cancelled = true;
    };
  }, [authLoading, session, leagueId, lens, lensReady, router, retryToken]);

  if (authLoading) {
    return <LoadingScreen status="Loading Dashboard…" />;
  }

  if (!data && !error) {
    // Show what is ready first: the page frame with height-reserving
    // skeletons, and League Pulse as soon as its own request lands, instead
    // of a splash until the slowest request finishes.
    return (
      <main className="flex-1 flex flex-col gap-6 px-4 py-5 max-w-3xl w-full mx-auto" aria-busy="true">
        <h1 className="sr-only">{leagueName}</h1>
        <SkeletonBlock height={120} />
        <SkeletonBlock height={160} />
        {teamRankings ? <LeaguePulseCard leagueId={leagueId} leagueName={leagueName} teamRankings={teamRankings} /> : null}
        <SkeletonBlock height={120} />
      </main>
    );
  }

  if (error || !data) {
    return (
      <ErrorState
        message={error || "Could not load the Dashboard."}
        onRetry={() => {
          setError(null);
          setRetryToken((token) => token + 1);
        }}
      />
    );
  }

  return <DashboardContent leagueId={leagueId} leagueName={leagueName} data={data} teamRankings={teamRankings ?? undefined} />;
}

"use client";

import { useEffect, useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { LeagueRecapsContent } from "@/components/LeagueRecapsContent";
import { SkeletonList } from "@/components/Skeleton";
import { ButtonLink } from "@/components/Button";
import { api, type RecapResponse } from "@/lib/api";
import type { RecapsTab } from "@/lib/pageTabs";
import { HOME_PATH } from "@/lib/retiredRoutes";

/**
 * News > My League (formerly the League Recaps page; 2026-11-16 nav consolidation): the weekly recap, Roundup, History
 * and Storylines of one league. News itself is account-wide, so the league comes from `?league=` (the old route and the
 * push deep links carry it) or, failing that, the account's default league; with none known it asks for one.
 */
export function NewsLeagueTab({
  league,
  recapsTab,
  week,
}: {
  league: { leagueId: string; leagueName: string } | null;
  recapsTab?: RecapsTab;
  week?: number;
}) {
  if (!league) {
    return (
      <EmptyState title="Pick a league" subtitle="My League shows the weekly recap, stories and your lineup roundup for one league.">
        <div className="mt-2">
          <ButtonLink href={HOME_PATH} size="sm">
            Choose a league
          </ButtonLink>
        </div>
      </EmptyState>
    );
  }
  return <LoadedRecap key={league.leagueId} league={league} recapsTab={recapsTab} week={week} />;
}

function LoadedRecap({ league, recapsTab, week }: { league: { leagueId: string; leagueName: string }; recapsTab?: RecapsTab; week?: number }) {
  const [recap, setRecap] = useState<RecapResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getLeagueRecap(league.leagueId, undefined, true)
      .then((result) => {
        if (!cancelled) setRecap(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load League Recaps.");
      });
    return () => {
      cancelled = true;
    };
  }, [league.leagueId, retryToken]);

  if (error) {
    return (
      <ErrorState
        bare
        message={error}
        onRetry={() => {
          setError(null);
          setRetryToken((n) => n + 1);
        }}
      />
    );
  }
  if (!recap) return <SkeletonList label="league recap" count={4} />;
  return (
    <LeagueRecapsContent
      embedded
      leagueId={league.leagueId}
      leagueName={league.leagueName}
      initialRecap={recap}
      initialTab={recapsTab}
      initialWeek={week}
    />
  );
}
